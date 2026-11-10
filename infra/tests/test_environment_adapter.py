"""Focused standard-library-only tests of the nonsecret review adapter."""

import contextlib
import copy
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "export_environment", Path(__file__).resolve().parents[1] / "scripts" / "export_environment.py"
)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
SUBSCRIPTION = "00000000-0000-0000-0000-000000000001"
BASE = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/"
CONTRACT = {
    "version": 1,
    "subscription_id": SUBSCRIPTION,
    "environment_name": "fixture",
    "location": "eastus2",
    "resource_groups": {"agents": "agents", "gateway": "gateway", "models": "models"},
    "gateway": {
        "id": BASE + "gateway/providers/Microsoft.ApiManagement/aigateways/gateway",
        "endpoint": "https://service-managed.example.invalid",
    },
    "agents": {
        "account_id": BASE + "agents/providers/Microsoft.CognitiveServices/accounts/agents",
        "project_id": BASE + "agents/providers/Microsoft.CognitiveServices/accounts/agents/projects/project",
        "project_endpoint": "https://agents.services.ai.azure.com/api/projects/project",
        "registry_id": BASE + "agents/providers/Microsoft.ContainerRegistry/registries/registry",
        "registry_endpoint": "registry.azurecr.io",
        "registry_connection_name": "acr-connection",
    },
    "models": {"aliases": {
        "primary-router": {
            "alias_name": "primary", "endpoints": ["/openai/v1/chat/completions", "/openai/v1/responses"],
        },
        "mini-router": {
            "alias_name": "mini", "endpoints": ["/openai/v1/chat/completions", "/openai/v1/responses"],
        },
    }},
}


class EnvironmentAdapterTests(unittest.TestCase):
    def test_existing_version_one_mapping(self):
        source = copy.deepcopy(CONTRACT)
        result = ADAPTER.environment_mapping(source)
        self.assertEqual(source, CONTRACT)
        self.assertEqual(result["AZURE_AI_GATEWAY_ENDPOINT"], "https://service-managed.example.invalid/")
        self.assertEqual(result["AZURE_AI_GATEWAY_MODEL"], "primary")
        self.assertEqual(result["AZURE_AI_GATEWAY_MINI_MODEL"], "mini")
        self.assertEqual(result["AZURE_AI_PROJECT_ENDPOINT"], CONTRACT["agents"]["project_endpoint"])
        self.assertEqual(result["AZURE_CONTAINER_REGISTRY_NAME"], "registry")
        self.assertEqual(result["AZURE_AI_PROJECT_ACR_CONNECTION_NAME"], "acr-connection")
        self.assertEqual(result["AZURE_RESOURCE_GROUP"], "agents")
        self.assertNotIn("AI_GATEWAY_LOCATION", result)

    def test_full_output_allowlist_and_additive_metadata(self):
        source = copy.deepcopy(CONTRACT)
        source["gateway"].update(location="swedencentral", api_key="synthetic-secret-marker")
        source["agents"]["connectionString"] = "synthetic-secret-marker"
        source["integration"] = {"remote_tool_endpoint": "https://service-managed.example.invalid/explicit-tool"}
        source.update(AZURE_AI_GATEWAY_API_KEY="synthetic-secret-marker", TOOLBOX_ENDPOINT="unverified")
        result = ADAPTER.environment_mapping({
            "deployment_contract": {"sensitive": False, "value": source},
            "unrelated_secret_output": {"sensitive": True, "value": "synthetic-secret-marker"},
        })
        self.assertEqual(result["AI_GATEWAY_LOCATION"], "swedencentral")
        self.assertNotIn("synthetic-secret-marker", json.dumps(result))
        for excluded in ("AZURE_AI_GATEWAY_API_KEY", "TOOLBOX_ENDPOINT", "TOOLBOX_NAME",
                         "AZURE_TENANT_ID", "GITHUB_TOKEN", "GITHUB_REPOSITORY"):
            self.assertNotIn(excluded, result)

    def test_reject_schema_and_sensitive_envelope(self):
        malformed = [[], {}, {**CONTRACT, "version": 2}, {**CONTRACT, "version": True},
                     {**CONTRACT, "subscription_id": "wrong"}, {**CONTRACT, "agents": []},
                     {**CONTRACT, "models": {"aliases": []}},
                     {"deployment_contract": {"sensitive": True, "value": CONTRACT}},
                     {"deployment_contract": {"value": CONTRACT}}]
        for source in malformed:
            with self.subTest(source=type(source)), self.assertRaises((ValueError, KeyError, TypeError)):
                ADAPTER.environment_mapping(source)

    def test_reject_endpoint_credentials_routes_and_malformed_values(self):
        for field, value in (
            ("endpoint", "http://service-managed.example.invalid"),
            ("endpoint", "https://user:password@service-managed.example.invalid"),
            ("endpoint", "https://service-managed.example.invalid/?key=synthetic-secret-marker"),
            ("endpoint", "https://service-managed.example.invalid/#synthetic-secret-marker"),
            ("endpoint", "https://service-managed.example.invalid/default/models"),
            ("endpoint", "https://service-managed.example.invalid:8443"),
            ("endpoint", "https://service-managed.example.invalid\\evil"),
            ("id", CONTRACT["gateway"]["id"] + "?key=synthetic-secret-marker"),
        ):
            source = copy.deepcopy(CONTRACT)
            source["gateway"][field] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                ADAPTER.environment_mapping(source)

    def test_custom_aliases_accept_responses_only(self):
        source = copy.deepcopy(CONTRACT)
        aliases = source["models"]["aliases"]
        aliases["custom-primary"] = aliases.pop("primary-router")
        aliases["custom-mini"] = aliases.pop("mini-router")
        for config in aliases.values():
            config["endpoints"] = ["/openai/v1/responses"]
        aliases["unselected"] = {"alias_name": "chat-only", "endpoints": ["/openai/v1/chat/completions"]}
        result = ADAPTER.environment_mapping(source, "custom-primary", "custom-mini")
        self.assertEqual(result["AZURE_AI_GATEWAY_MODEL"], "primary")
        self.assertEqual(result["AZURE_AI_GATEWAY_MINI_MODEL"], "mini")
        with self.assertRaises(KeyError):
            ADAPTER.environment_mapping(source)

    def test_selected_aliases_require_responses_protocol(self):
        for key in ("custom-primary", "custom-mini"):
            for endpoints in (["/openai/v1/chat/completions"], [], "/openai/v1/responses", None):
                source = copy.deepcopy(CONTRACT)
                aliases = source["models"]["aliases"]
                aliases["custom-primary"] = aliases.pop("primary-router")
                aliases["custom-mini"] = aliases.pop("mini-router")
                aliases[key]["endpoints"] = endpoints
                with self.subTest(key=key, endpoints=endpoints), self.assertRaisesRegex(ValueError, "Responses"):
                    ADAPTER.environment_mapping(source, "custom-primary", "custom-mini")

    def test_reject_project_endpoint_for_another_project_or_account(self):
        for value in (
            "https://agents.services.ai.azure.com/api/projects/other-project",
            "https://other-agents.services.ai.azure.com/api/projects/project",
            "https://agents.services.ai.azure.com.example.invalid/api/projects/project",
        ):
            source = copy.deepcopy(CONTRACT)
            source["agents"]["project_endpoint"] = value
            with self.subTest(endpoint=value), self.assertRaises(ValueError):
                ADAPTER.environment_mapping(source)

    def test_reject_project_outside_declared_account(self):
        for account_id in (
            CONTRACT["agents"]["account_id"].replace("/accounts/agents", "/accounts/other-agents"),
            CONTRACT["agents"]["account_id"].replace("/resourceGroups/agents", "/resourceGroups/other-group"),
        ):
            source = copy.deepcopy(CONTRACT)
            source["agents"]["project_id"] = account_id + "/projects/project"
            source["agents"]["project_endpoint"] = (
                f"https://{account_id.rsplit('/', 1)[-1]}.services.ai.azure.com/api/projects/project"
            )
            with self.subTest(account_id=account_id), self.assertRaises(ValueError):
                ADAPTER.environment_mapping(source)

    def test_reject_missing_or_invalid_agent_account_id(self):
        invalid_ids = (
            None,
            CONTRACT["agents"]["account_id"].replace(SUBSCRIPTION, "00000000-0000-0000-0000-000000000002"),
            CONTRACT["agents"]["project_id"],
        )
        for account_id in invalid_ids:
            source = copy.deepcopy(CONTRACT)
            if account_id is None:
                del source["agents"]["account_id"]
            else:
                source["agents"]["account_id"] = account_id
            with self.subTest(account_id=account_id), self.assertRaises((ValueError, KeyError)):
                ADAPTER.environment_mapping(source)

    def test_reject_gateway_resource_group_mismatch(self):
        source = copy.deepcopy(CONTRACT)
        source["resource_groups"]["gateway"] = "other-group"
        with self.assertRaises(ValueError):
            ADAPTER.environment_mapping(source)

    def test_resource_relationships_are_case_insensitive(self):
        for field in ("account_id", "project_id"):
            source = copy.deepcopy(CONTRACT)
            source["gateway"]["id"] = source["gateway"]["id"].upper()
            source["agents"][field] = source["agents"][field].upper()
            with self.subTest(field=field):
                result = ADAPTER.environment_mapping(source)
                self.assertEqual(result["AZURE_AI_PROJECT_ENDPOINT"], CONTRACT["agents"]["project_endpoint"])
                self.assertEqual(result["AI_GATEWAY_RESOURCE_GROUP"], "gateway")

    def test_service_owned_registry_hostnames_are_not_inferred_from_arm_names(self):
        for hostname in ("registry-a1b2c3d4.azurecr.io", "unrelated.example.invalid"):
            source = copy.deepcopy(CONTRACT)
            source["agents"]["registry_endpoint"] = hostname
            result = ADAPTER.environment_mapping(source)
            self.assertEqual(result["AZURE_CONTAINER_REGISTRY_ENDPOINT"], hostname)
            self.assertEqual(result["AZURE_CONTAINER_REGISTRY_RESOURCE_ID"], CONTRACT["agents"]["registry_id"])

    def test_cli_json_only_and_no_mutation(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["export_environment.py", "explicit-contract.json"]), \
             patch.object(Path, "read_text", return_value=json.dumps(CONTRACT)), \
             patch.dict("os.environ", {}, clear=True), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(ADAPTER.main(), 0)
            import os
            self.assertEqual(dict(os.environ), {})
        self.assertEqual(json.loads(stdout.getvalue())["AZURE_AI_GATEWAY_MODEL"], "primary")
        self.assertEqual(stderr.getvalue(), "")

    def test_cli_rejection_does_not_echo_sensitive_input(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["export_environment.py", "explicit-contract.json"]), \
             patch.object(Path, "read_text", return_value='{"secret":"synthetic-secret-marker"}'), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(ADAPTER.main(), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn("synthetic-secret-marker", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
