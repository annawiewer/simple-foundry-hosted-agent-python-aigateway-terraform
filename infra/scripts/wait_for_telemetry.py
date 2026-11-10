"""Read native Insights readiness and write an explicit, nonsecret Terraform handoff.

Never deploys, grants access, registers providers, reads state or calls telemetry
endpoints. Uses the existing Azure CLI login for public-cloud ARM GETs only.
"""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ARM = "https://management.azure.com"
API = "2020-02-02"
MAX_RESPONSE_BYTES = 1024 * 1024
UUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
NAME = r"[A-Za-z0-9_.()-]+"
ENDPOINT = (
    r"https://[A-Za-z0-9][A-Za-z0-9.-]*(?::443)?(?:/[^?#\\\s\x00-\x1f\x7f]*)?"
    r"(?:\?api-version=\d{4}-\d{2}-\d{2}(?:-preview)?)?"
)
BOOTSTRAP_KEYS = {
    "version", "subscription_id", "mode", "gateway_id", "gateway_principal_id",
    "insights_id", "log_analytics_id",
}
GENERATED_FIELDS = {
    "data_collection_rule_id": ("DefaultDataCollectionRuleResourceId", "DataCollectionRuleResourceId"),
    "metrics_endpoint": ("MetricsIngestionEndpoint", "OTLPMetricsEndpoint"),
    "logs_endpoint": ("LogsIngestionEndpoint", "OTLPLogsEndpoint"),
    "traces_endpoint": ("TracesIngestionEndpoint", "OTLPTracesEndpoint"),
}


class ReadinessError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def valid_uuid(value):
    return isinstance(value, str) and re.fullmatch(UUID, value) is not None


def arm_id(value, subscription, resource_type):
    pattern = rf"/subscriptions/{re.escape(subscription)}/resourceGroups/{NAME}/providers/{resource_type}/{NAME}"
    if not isinstance(value, str) or not re.fullmatch(pattern, value, re.IGNORECASE):
        raise ReadinessError("Invalid resource type, subscription or ARM ID; values withheld.")
    return value


def validate_bootstrap(document, subscription):
    if not valid_uuid(subscription):
        raise ReadinessError("The explicit subscription must be a UUID.")
    if (not isinstance(document, dict) or set(document) != BOOTSTRAP_KEYS
            or type(document["version"]) is not int or document["version"] != 1
            or document["mode"] != "OpenTelemetry"):
        raise ReadinessError("Use the version-1 OpenTelemetry gateway_telemetry_bootstrap output, not state.")
    if (not valid_uuid(document["subscription_id"])
            or document["subscription_id"].casefold() != subscription.casefold()
            or not valid_uuid(document["gateway_principal_id"])):
        raise ReadinessError("Bootstrap subscription or gateway identity does not match the required contract.")
    for key, resource_type in (
        ("gateway_id", r"Microsoft\.ApiManagement/aigateways"),
        ("insights_id", r"Microsoft\.Insights/components"),
        ("log_analytics_id", r"Microsoft\.OperationalInsights/workspaces"),
    ):
        arm_id(document[key], subscription, resource_type)
    return document


def readiness(document, bootstrap):
    if (not isinstance(document, dict) or not isinstance(document.get("id"), str)
            or document["id"].casefold() != bootstrap["insights_id"].casefold()
            or not isinstance(document.get("properties"), dict)):
        raise ReadinessError("Insights GET returned a mismatched or malformed resource; response withheld.")
    properties = document["properties"]
    mode = properties.get("AzureMonitorWorkspaceIngestionMode")
    if mode is not None and mode != "Enabled":
        raise ReadinessError("Insights explicitly reports managed ingestion is not enabled.")
    workspace = properties.get("WorkspaceResourceId")
    pending = workspace in (None, "")
    if not pending and (
        not isinstance(workspace, str) or workspace.casefold() != bootstrap["log_analytics_id"].casefold()
    ):
        raise ReadinessError("Insights points at a different Log Analytics workspace; stopping.")
    result = {key: bootstrap[key] for key in
              ("version", "gateway_id", "gateway_principal_id", "insights_id", "log_analytics_id")}
    for key, aliases in GENERATED_FIELDS.items():
        values = [properties[field] for field in aliases if properties.get(field) not in (None, "")]
        if not values:
            pending = True
            continue
        if any(not isinstance(value, str) for value in values):
            raise ReadinessError("A generated readiness field is malformed; values withheld.")
        if key == "data_collection_rule_id":
            for value in values:
                arm_id(value, bootstrap["subscription_id"], r"Microsoft\.Insights/dataCollectionRules")
            distinct = {value.casefold() for value in values}
        else:
            if any(not re.fullmatch(ENDPOINT, value, re.ASCII) for value in values):
                raise ReadinessError("An OTLP endpoint is not credential-free HTTPS; values withheld.")
            distinct = set(values)
        if len(distinct) != 1:
            raise ReadinessError("Conflicting generated readiness fields; values withheld.")
        result[key] = values[0]
    return None if pending else result


def remaining(deadline, limit, clock=time.monotonic):
    seconds = deadline - clock()
    if seconds <= 0:
        raise ReadinessError("Readiness deadline reached; no handoff was written.")
    return min(limit, seconds)


def wait_for_ready(bootstrap, fetch, *, deadline, max_attempts=60, interval=10,
                   clock=time.monotonic, sleep=time.sleep):
    if type(max_attempts) is not int or not 1 <= max_attempts <= 60 or not 1 <= interval <= 30:
        raise ReadinessError("Use 1-60 attempts and a 1-30 second polling interval.")
    for attempt in range(1, max_attempts + 1):
        timeout = remaining(deadline, 30, clock)
        status, document = fetch(bootstrap["insights_id"], timeout)
        remaining(deadline, 30, clock)
        if status == 200:
            result = readiness(document, bootstrap)
            if result is not None:
                return result, attempt
        elif status not in (0, 404, 408, 429, 500, 502, 503, 504):
            raise ReadinessError(f"Insights GET failed with HTTP {status}; no retry or handoff.")
        if attempt < max_attempts:
            sleep(remaining(deadline, interval, clock))
    raise ReadinessError("Readiness attempt limit reached; no handoff was written.")


def cli_json(arguments, deadline):
    executable = shutil.which("az")
    if not executable:
        raise ReadinessError("Azure CLI is required; nothing is installed or logged in automatically.")
    result = subprocess.run(
        [executable, *arguments, "--only-show-errors", "-o", "json"],
        capture_output=True, text=True, check=False, timeout=remaining(deadline, 60),
    )
    if result.returncode:
        raise ReadinessError("Azure CLI context/authentication failed; details withheld.")
    return json.loads(result.stdout)


def arm_reader(token):
    opener = urllib.request.build_opener(NoRedirect())

    def fetch(identifier, timeout):
        request = urllib.request.Request(
            ARM + identifier + "?api-version=" + API,
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            method="GET",
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ReadinessError("Insights response exceeds the bounded size; response withheld.")
                return response.status, json.loads(body)
        except urllib.error.HTTPError as error:
            error.close()
            return error.code, None
        except (urllib.error.URLError, TimeoutError):
            return 0, None

    return fetch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", required=True, type=pathlib.Path)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--tfvars", required=True, type=pathlib.Path)
    parser.add_argument("--max-attempts", type=int, default=60, choices=range(1, 61), metavar="1-60")
    parser.add_argument("--timeout-seconds", type=int, default=600, choices=range(1, 601), metavar="1-600")
    args = parser.parse_args(argv)
    deadline = time.monotonic() + args.timeout_seconds
    try:
        if not valid_uuid(args.tenant_id):
            raise ReadinessError("The explicit tenant must be a UUID.")
        if (args.tfvars.exists() or not args.tfvars.parent.is_dir()
                or args.tfvars.resolve() == args.bootstrap.resolve()):
            raise ReadinessError("Choose a new handoff file in an existing private directory; overwrite is forbidden.")
        if (args.tfvars.name.casefold().endswith(".auto.tfvars.json")
                or args.tfvars.name.casefold() == "terraform.tfvars.json"
                or not args.tfvars.name.casefold().endswith(".tfvars.json")):
            raise ReadinessError("Use an explicitly loaded .tfvars.json filename, not an automatic Terraform variable file.")
        bootstrap = validate_bootstrap(
            json.loads(args.bootstrap.read_text(encoding="utf-8-sig")), args.subscription_id
        )
        account = cli_json(["account", "show"], deadline)
        if (str(account.get("id", "")).casefold() != args.subscription_id.casefold()
                or str(account.get("tenantId", "")).casefold() != args.tenant_id.casefold()
                or account.get("environmentName") != "AzureCloud"):
            raise ReadinessError("Azure CLI context must match the explicit subscription, tenant and public Azure cloud.")
        token = cli_json(
            ["account", "get-access-token", "--resource", ARM + "/", "--subscription", args.subscription_id],
            deadline,
        )
        if (str(token.get("subscription", "")).casefold() != args.subscription_id.casefold()
                or str(token.get("tenant", "")).casefold() != args.tenant_id.casefold()
                or token.get("tokenType") != "Bearer"
                or not isinstance(token.get("accessToken"), str) or not token["accessToken"]):
            raise ReadinessError("ARM token context does not match the explicit subscription and tenant.")
        fetch = arm_reader(token["accessToken"])
        del token
        result, attempts = wait_for_ready(
            bootstrap, fetch, deadline=deadline, max_attempts=args.max_attempts,
        )
        del fetch
        remaining(deadline, 30)
        with args.tfvars.open("x", encoding="utf-8") as destination:
            json.dump({"gateway_native_telemetry": result}, destination, indent=2)
            destination.write("\n")
        print(f"READY: nonsecret handoff written after {attempts} GET(s). Review a fresh second-stage plan; no Azure writes performed.")
        return 0
    except ReadinessError as error:
        print(str(error), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired):
        print("Input, context or readiness read failed; sensitive details withheld.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
