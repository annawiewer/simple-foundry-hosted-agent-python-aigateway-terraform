"""GET-only requested-field qualification; never print state or response values."""

import argparse
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request


MISSING = object()


class ReadbackError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def resources(module):
    yield from module.get("resources", [])
    for child in module.get("child_modules", []):
        yield from resources(child)


def compare(expected, actual, path, differences, omitted):
    if expected is None:
        return 0
    if actual is MISSING or actual is None:
        omitted.append(path)
        return 0
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            differences.append(path)
            return 0
        return sum(
            compare(value, actual.get(key, MISSING), path + "." + key, differences, omitted)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            differences.append(path)
            return 0
        return sum(
            compare(left, right, f"{path}[{index}]", differences, omitted)
            for index, (left, right) in enumerate(zip(expected, actual))
        )
    if isinstance(expected, str) and isinstance(actual, str):
        if expected.lower().startswith(("/subscriptions/", "/providers/")):
            matches = expected.casefold() == actual.casefold()
        elif path in ("body.location", "metadata.location"):
            matches = expected.replace(" ", "").casefold() == actual.replace(" ", "").casefold()
        elif path == "metadata.identity.type":
            matches = expected.casefold() == actual.casefold()
        else:
            matches = expected == actual
    elif (
        isinstance(expected, (int, float)) and not isinstance(expected, bool)
        and isinstance(actual, (int, float)) and not isinstance(actual, bool)
    ):
        matches = expected == actual
    else:
        matches = type(expected) is type(actual) and expected == actual
    if not matches:
        differences.append(path)
    return 1


def qualify(document, subscription_id, fetch):
    try:
        values = document["values"]
        contract = values["outputs"]["deployment_contract"]["value"]
        selected = list(resources(values["root_module"]))
    except (KeyError, TypeError):
        raise ReadbackError("Expected terraform show -json state with deployment_contract output.") from None
    if type(contract.get("version")) is not int or contract["version"] != 1:
        raise ReadbackError("Unsupported deployment_contract version.")
    if str(contract.get("subscription_id", "")).casefold() != subscription_id.casefold():
        raise ReadbackError("State contract differs from the explicit subscription.")
    selected = [item for item in selected if item.get("mode") != "data"]
    if not selected:
        raise ReadbackError("No managed resources were supplied.")
    prefix = "/subscriptions/" + subscription_id.casefold() + "/"
    for resource in selected:
        state = resource.get("values", {})
        identifier = state.get("id", "")
        resource_type = state.get("type", "")
        if (
            resource.get("mode") != "managed"
            or resource.get("type") != "azapi_resource"
            or not isinstance(identifier, str)
            or not identifier.casefold().startswith(prefix)
            or any(character in identifier for character in "?#")
            or not isinstance(state.get("body"), dict)
            or not isinstance(resource_type, str)
            or not re.fullmatch(r"[^@\s]+@\d{4}-\d{2}-\d{2}(?:-preview)?", resource_type)
        ):
            raise ReadbackError("Unsupported managed resource or resource outside the explicit subscription.")
    report = {
        "observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "GET-only state-requested field subset and placement/identity metadata",
        "writes_performed": False,
        "runtime_accepted": False,
        "resources": [],
    }
    for resource in selected:
        state = resource["values"]
        status, actual = fetch(state["id"], state["type"].rsplit("@", 1)[1])
        item = {
            "address": resource["address"],
            "http_status": status,
            "compared_leaves": 0,
            "differences": [],
            "not_returned": [],
        }
        differences, omitted = item["differences"], item["not_returned"]
        if status != 200 or not isinstance(actual, dict):
            item["status"] = "FAIL"
        else:
            if str(actual.get("id", "")).casefold() != state["id"].casefold():
                differences.append("metadata.id")
            leaves = compare(state["body"], actual, "body", differences, omitted)
            for field in ("location", "tags"):
                if state.get(field):
                    leaves += compare(
                        state[field], actual.get(field, MISSING),
                        "metadata." + field, differences, omitted,
                    )
            identity = state.get("identity")
            if isinstance(identity, list):
                identity = identity[0] if identity else None
            if isinstance(identity, dict):
                returned_identity = actual.get("identity") or {}
                for field, wire in (("type", "type"), ("principal_id", "principalId"),
                                    ("tenant_id", "tenantId")):
                    if identity.get(field):
                        leaves += compare(
                            identity[field], returned_identity.get(wire, MISSING),
                            "metadata.identity." + field, differences, omitted,
                        )
            item["compared_leaves"] = leaves
            item["status"] = "FAIL" if differences else ("INCOMPLETE" if omitted else "PASS")
        report["resources"].append(item)
    statuses = {item["status"] for item in report["resources"]}
    report["status"] = "FAIL" if "FAIL" in statuses else ("INCOMPLETE" if "INCOMPLETE" in statuses else "PASS")
    report["resource_count"] = len(selected)
    report["compared_leaves"] = sum(item["compared_leaves"] for item in report["resources"])
    return report


def cli_json(*arguments):
    executable = shutil.which("az")
    if not executable:
        raise ReadbackError("Azure CLI is required; no package is installed automatically.")
    result = subprocess.run(
        [executable, *arguments, "-o", "json"], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise ReadbackError("Azure CLI authentication/context operation failed; details withheld.")
    return json.loads(result.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-json", required=True, type=pathlib.Path)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--report", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        for value in (args.subscription_id, args.tenant_id):
            if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value):
                raise ReadbackError("Explicit subscription and tenant must be UUIDs.")
        if args.report.exists() or not args.report.parent.is_dir():
            raise ReadbackError("Choose a new report file in an existing protected directory.")
        if args.report.resolve() == args.state_json.resolve():
            raise ReadbackError("Report must not replace the input state.")
        document = json.loads(args.state_json.read_text(encoding="utf-8-sig"))
        account = cli_json("account", "show")
        if (str(account.get("id", "")).casefold() != args.subscription_id.casefold()
                or str(account.get("tenantId", "")).casefold() != args.tenant_id.casefold()):
            raise ReadbackError("Azure CLI context differs from the explicit subscription/tenant.")
        token = cli_json(
            "account", "get-access-token", "--resource", "https://management.azure.com/",
            "--subscription", args.subscription_id,
        )["accessToken"]
        opener = urllib.request.build_opener(NoRedirect())

        def fetch(identifier, version):
            request = urllib.request.Request(
                "https://management.azure.com" + identifier + "?api-version=" + version,
                headers={"Authorization": "Bearer " + token}, method="GET",
            )
            try:
                with opener.open(request, timeout=60) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                error.close()
                return error.code, None
            except (urllib.error.URLError, TimeoutError, ValueError):
                return 0, None

        report = qualify(document, args.subscription_id, fetch)
        token = None
        with args.report.open("x", encoding="utf-8") as destination:
            json.dump(report, destination, indent=2)
            destination.write("\n")
        print(f'{report["status"]}: {report["resource_count"]} resources, '
              f'{report["compared_leaves"]} compared leaves; no runtime acceptance.')
        return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 3}[report["status"]]
    except ReadbackError as error:
        print(str(error), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print("Input, context or readback failed; sensitive details withheld.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
