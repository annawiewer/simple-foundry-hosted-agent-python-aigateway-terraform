"""Render a reviewed, nonsecret environment JSON map; never apply it or invoke Azure.

Usage: python -B export_environment.py deployment-contract.json
Input is a version-1 deployment_contract object, or `terraform output -json`
with a nonsensitive deployment_contract output. Stdout is JSON only.
Custom profiles can select --model-alias-key and --mini-model-alias-key.
Credentials, Toolbox endpoints and runtime routes are deliberately not exported.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


def object_value(value):
    if not isinstance(value, dict):
        raise ValueError("Expected a deployment contract object.")
    return value


def text(value):
    if not isinstance(value, str) or not value or value.strip() != value or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise ValueError("Expected a nonempty single-line string.")
    return value


def name(value):
    value = text(value)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("Invalid resource or model name.")
    return value


def endpoint(value):
    value = text(value)
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*(?::443)?", parsed.netloc)
        or re.search(r"\s|\\", value)
    ):
        raise ValueError("Expected a credential-free HTTPS endpoint.")
    return value.rstrip("/")


def arm_id(value, resource_type, subscription):
    value = text(value)
    pattern = (
        r"/subscriptions/" + re.escape(subscription)
        + r"/resourceGroups/[A-Za-z0-9_.()-]+/providers/" + resource_type
    )
    if not re.fullmatch(pattern, value, re.IGNORECASE):
        raise ValueError("Invalid or mismatched subscription resource ID.")
    return value


def environment_mapping(document, model_alias_key="primary-router", mini_model_alias_key="mini-router"):
    contract = object_value(document)
    if "deployment_contract" in contract:
        output = object_value(contract["deployment_contract"])
        if output.get("sensitive") is not False:
            raise ValueError("deployment_contract must explicitly be nonsensitive.")
        contract = object_value(output["value"])
    if type(contract.get("version")) is not int or contract["version"] != 1:
        raise ValueError("Only deployment_contract version 1 is supported.")
    subscription = text(contract["subscription_id"])
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", subscription):
        raise ValueError("Invalid subscription UUID.")
    groups = object_value(contract["resource_groups"])
    gateway = object_value(contract["gateway"])
    agents = object_value(contract["agents"])
    aliases = object_value(object_value(contract["models"])["aliases"])
    gateway_group = name(groups["gateway"])
    gateway_id = arm_id(gateway["id"], r"Microsoft\.ApiManagement/aigateways/[A-Za-z0-9_.-]+", subscription)
    if gateway_id.split("/")[4].casefold() != gateway_group.casefold():
        raise ValueError("The gateway resource group must match its resource ID.")
    account_id = arm_id(
        agents["account_id"], r"Microsoft\.CognitiveServices/accounts/[A-Za-z0-9_.-]+", subscription
    )
    project_id = arm_id(
        agents["project_id"],
        r"Microsoft\.CognitiveServices/accounts/[A-Za-z0-9_.-]+/projects/[A-Za-z0-9_.-]+",
        subscription,
    )
    if project_id.rsplit("/", 2)[0].casefold() != account_id.casefold():
        raise ValueError("The project must belong to the declared agent account.")
    registry_id = arm_id(
        agents["registry_id"], r"Microsoft\.ContainerRegistry/registries/[A-Za-z0-9]+", subscription
    )
    gateway_endpoint = endpoint(gateway["endpoint"])
    if urlsplit(gateway_endpoint).path not in ("", "/"):
        raise ValueError("The gateway endpoint must be an origin, not a model or MCP route.")
    project_endpoint = endpoint(agents["project_endpoint"])
    project_url = urlsplit(project_endpoint)
    project_path = re.fullmatch(r"/api/projects/([A-Za-z0-9_.-]+)", project_url.path)
    if not project_path:
        raise ValueError("Expected an established Foundry project endpoint.")
    if (
        project_url.hostname != account_id.rsplit("/", 1)[-1].lower() + ".services.ai.azure.com"
        or project_path[1].casefold() != project_id.rsplit("/", 1)[-1].casefold()
    ):
        raise ValueError("The project endpoint must match the declared account and project IDs.")
    registry_endpoint = text(agents["registry_endpoint"])
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", registry_endpoint):
        raise ValueError("Expected a registry hostname, not a URL or credential.")

    def alias(key):
        config = object_value(aliases[key])
        endpoints = config["endpoints"]
        if not isinstance(endpoints, list) or "/openai/v1/responses" not in endpoints:
            raise ValueError("Selected alias must advertise the application's Responses protocol.")
        return name(config["alias_name"])

    result = {
        "AZURE_ENV_NAME": name(contract["environment_name"]),
        "AZURE_SUBSCRIPTION_ID": subscription,
        "AZURE_LOCATION": text(contract["location"]),
        "AZURE_RESOURCE_GROUP": name(groups["agents"]),
        "AI_GATEWAY_RESOURCE_GROUP": gateway_group,
        "AZURE_AI_PROJECT_ENDPOINT": project_endpoint,
        "AZURE_AI_PROJECT_ID": project_id,
        "AZURE_CONTAINER_REGISTRY_ENDPOINT": registry_endpoint,
        "AZURE_CONTAINER_REGISTRY_RESOURCE_ID": registry_id,
        "AZURE_CONTAINER_REGISTRY_NAME": registry_id.rsplit("/", 1)[-1],
        "AZURE_AI_PROJECT_ACR_CONNECTION_NAME": name(agents["registry_connection_name"]),
        "AI_GATEWAY_NAME": gateway_id.rsplit("/", 1)[-1],
        "AI_GATEWAY_RESOURCE_ID": gateway_id,
        "AZURE_AI_GATEWAY_ENDPOINT": gateway_endpoint + "/",
        "AZURE_AI_GATEWAY_MODEL": alias(model_alias_key),
        "AZURE_AI_GATEWAY_MINI_MODEL": alias(mini_model_alias_key),
    }
    if "location" in gateway:
        result["AI_GATEWAY_LOCATION"] = text(gateway["location"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path, help="Explicit nonsecret JSON export; do not supply state or credentials.")
    parser.add_argument("--model-alias-key", default="primary-router")
    parser.add_argument("--mini-model-alias-key", default="mini-router")
    args = parser.parse_args()
    try:
        document = json.loads(args.contract.read_text(encoding="utf-8-sig"))
        result = environment_mapping(document, args.model_alias_key, args.mini_model_alias_key)
    except (OSError, ValueError, KeyError, TypeError):
        print("Invalid version-1 nonsecret deployment contract or incompatible application aliases.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
