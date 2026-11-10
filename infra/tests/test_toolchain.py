"""Mocked ownership, credential, mutation and handoff tests; never uses Azure."""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import uuid
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("configure_tools", SCRIPTS / "configure_tools.py")
tools = importlib.util.module_from_spec(SPEC)
with mock.patch.object(sys, "path", [str(SCRIPTS), *sys.path]):
    SPEC.loader.exec_module(tools)

SUBSCRIPTION = "00000000-0000-0000-0000-000000000001"
TENANT = "00000000-0000-0000-0000-000000000002"
OWNER = "00000000-0000-0000-0000-000000000003"
GITHUB_TOKEN = "synthetic-github-readonly"
ARM_TOKEN = "synthetic-arm-token"
FOUNDRY_TOKEN = "synthetic-foundry-token"
GATEWAY = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/gateway/providers/Microsoft.ApiManagement/aigateways/fixture"
PROJECT = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/agents/providers/Microsoft.CognitiveServices/accounts/agents/projects/project"
SERVER_ID = GATEWAY + "/workspaces/default/toolServers/github"
MCP = "https://gateway.example.invalid/ServiceReturned/ActualRoute/mcp/"
PROJECT_ENDPOINT = "https://agents.services.ai.azure.com/api/projects/project"
CONFIG = {"owner_id": OWNER, "repository": "example/repository", "allowed_client_cidrs": ["203.0.113.42/32"]}
BODY = {"properties": {
    "displayName": "GitHub repository digest",
    "description": "Read-only GitHub tools for repository digests. Owner: terraform-toolchain/" + OWNER,
    "type": "mcp",
    "policies": [
        {"type": "contentSafety", "scope": "resource", "hateSeverity": "Medium", "selfHarmSeverity": "Medium",
         "sexualSeverity": "Medium", "violenceSeverity": "Medium"},
        {"type": "ipFilter", "scope": "resource", "action": "Allow", "cidrRanges": ["203.0.113.42/32"]},
    ],
    "endpoints": [{"namespace": "github", "kind": "mcp", "required": True,
                   "mcp": {"url": "https://api.githubcopilot.com/mcp/", "transport": "streamableHttp"},
                   "credentials": {"type": "header", "headers": {
                       "X-MCP-Readonly": ["true"], "X-MCP-Tools": ["list_pull_requests,list_issues,actions_list"],
                   }}}],
}}
HASH = hashlib.sha256(json.dumps(
    {"configuration": CONFIG, "body": BODY}, sort_keys=True, separators=(",", ":"),
).encode()).hexdigest()
LEGACY_BODY = copy.deepcopy(BODY)
LEGACY_BODY["properties"]["failureMode"] = "failClosed"
LEGACY_BODY["properties"]["endpoints"][0].pop("required")
for policy in LEGACY_BODY["properties"]["policies"]:
    policy.pop("scope")
LEGACY_HASH = hashlib.sha256(json.dumps(
    {"configuration": CONFIG, "body": LEGACY_BODY}, sort_keys=True, separators=(",", ":"),
).encode()).hexdigest()


def bootstrap(connected=False):
    return {
        "version": 1, "subscription_id": SUBSCRIPTION, "gateway_id": GATEWAY,
        "workspace_id": GATEWAY + "/workspaces/default", "gateway_endpoint": "https://gateway.example.invalid/",
        "api_version": "2025-09-01-preview", "project_id": PROJECT, "project_endpoint": PROJECT_ENDPOINT,
        "tool_access_enabled": True, "remote_tool_connection_id": PROJECT + "/connections/aigw-github" if connected else None,
        "remote_tool_endpoint": MCP if connected else None,
    }


def receipt(status="configured", connected=False, version=2):
    source = bootstrap(connected)
    return {
        "version": version, "operation": "create-toolserver", "status": status,
        "binding": {key: source[key] for key in (
            "subscription_id", "gateway_id", "workspace_id", "gateway_endpoint",
            "api_version", "project_id", "project_endpoint",
        )} | {"tenant_id": TENANT},
        "configuration": copy.deepcopy(CONFIG),
        "configuration_hash": LEGACY_HASH if version == 1 else HASH, "mutation_attempted": True,
        "toolserver": {"etag": '"revision-1"', "endpoint": MCP},
    }


def server_response(etag='"revision-1"', version=2):
    result = copy.deepcopy(LEGACY_BODY if version == 1 else BODY)
    result.update(id=SERVER_ID, etag=etag)
    result["properties"].update(mcpEndpointUrl=MCP, provisioningState="Succeeded", state="Ready")
    result["properties"]["endpoints"][0].pop("credentials")
    result["properties"]["endpoints"][0].update(id="generated-source-id", credentials={"type": "header"})
    return result


def observed_server_response(required=True):
    result = server_response()
    properties = result["properties"]
    for key in ("mcpEndpointUrl", "provisioningState", "state"):
        properties.pop(key)
    properties["gatewayEndpoints"] = [{
        "api": "mcp", "url": MCP, "baseUrl": "https://gateway.example.invalid/ServiceReturned/ActualRoute/",
    }]
    properties["endpoints"][0]["required"] = required
    properties["endpoints"][0]["credentials"]["headers"] = {
        "Authorization": None, "X-MCP-Readonly": None, "X-MCP-Tools": None,
    }
    return result


def connection_response():
    return {"id": PROJECT + "/connections/aigw-github", "properties": {
        "category": "RemoteTool", "authType": "ProjectManagedIdentity", "audience": "https://azure-api.net/aigateway",
        "target": MCP, "isSharedToAll": True, "metadata": {"type": "custom_MCP"},
    }}


def toolbox_request(version=2):
    return {"description": "Read-only GitHub MCP through AI Gateway",
            "metadata": {"terraform_toolchain_owner": OWNER,
                         "terraform_toolchain_configuration": LEGACY_HASH if version == 1 else HASH},
            "tools": [{"type": "mcp", "server_label": "aigw-github", "project_connection_id": "aigw-github",
                       "require_approval": "never"}]}


def box_reads(version="7", receipt_version=2):
    return [
        (200, {"name": "digest", "default_version": version}, None),
        (200, {**toolbox_request(receipt_version), "name": "digest", "version": version, "skills": []}, None),
    ]


def missing_server():
    return 404, {"error": {"code": "ResourceNotFound", "message": "ToolServer not found.", "details": []}}, None


def cli_context():
    return [
        {"id": SUBSCRIPTION, "tenantId": TENANT, "environmentName": "AzureCloud"},
        {"subscription": SUBSCRIPTION, "tenant": TENANT, "tokenType": "Bearer", "accessToken": ARM_TOKEN},
        {"subscription": SUBSCRIPTION, "tenant": TENANT, "tokenType": "Bearer", "accessToken": FOUNDRY_TOKEN},
    ]


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(tools.subprocess, "run", side_effect=AssertionError("Unexpected CLI invocation")).start()
        mock.patch.object(tools.urllib.request.OpenerDirector, "open",
                          side_effect=AssertionError("Unexpected network invocation")).start()
        mock.patch.object(tools.time, "sleep").start()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        self.counter = 0

    def run_main(self, operation, arm_responses=(), box_responses=(), previous=None,
                 source=None, extra=(), context=None, credential=GITHUB_TOKEN, defaults=True):
        self.counter += 1
        prefix = self.root / str(self.counter)
        source_path = prefix.with_suffix(".bootstrap.json")
        source_path.write_text(json.dumps(source or bootstrap(operation in tools.BOX_ACTIONS)), encoding="utf-8")
        receipt_path = prefix.with_suffix(".receipt.jsonl")
        args = [operation, "--bootstrap", str(source_path), "--subscription-id", SUBSCRIPTION,
                "--tenant-id", TENANT, "--receipt", str(receipt_path)]
        if previous is not None:
            previous_path = prefix.with_suffix(".previous.jsonl")
            previous_path.write_text(json.dumps(previous) + "\n", encoding="utf-8", newline="\n")
            args += ["--previous-receipt", str(previous_path)]
        if defaults:
            if operation in tools.WRITE_ACTIONS:
                args += ["--confirm-exclusive-owner"]
            if operation in tools.CREDENTIAL_ACTIONS:
                args += ["--credential-env", "SELECTED_TEST_CREDENTIAL", "--confirm-read-only-credential"]
            if operation == "create-toolserver":
                args += ["--repository", "example/repository", "--allow-client-cidr", "203.0.113.42/32"]
            if operation == "create-toolbox":
                args += ["--toolbox-name", "digest"]
        arm, foundry = mock.Mock(), mock.Mock()
        arm.call.side_effect, foundry.call.side_effect = list(arm_responses), list(box_responses)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(tools, "azure_json", side_effect=context or cli_context()) as cli, \
                mock.patch.object(tools, "Client", side_effect=[arm, foundry]) as clients, \
                mock.patch.object(tools.uuid, "uuid4", return_value=uuid.UUID(OWNER)), \
                mock.patch.dict(tools.os.environ, {"SELECTED_TEST_CREDENTIAL": credential}, clear=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = tools.main([*args, *extra])
        text = receipt_path.read_text(encoding="utf-8") if receipt_path.exists() else ""
        for secret in (GITHUB_TOKEN, ARM_TOKEN, FOUNDRY_TOKEN):
            self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue() + text)
        records = [json.loads(line) for line in text.splitlines()]
        return code, records, arm, foundry, cli, clients, stderr.getvalue()

    def test_create_preserves_exact_body_and_service_returned_endpoint(self):
        target = self.root / "tools.ready.tfvars.json"
        result = self.run_main("create-toolserver", [
            missing_server(), (201, {"echo": GITHUB_TOKEN}, None), (200, observed_server_response(), '"revision-1"'),
        ], extra=["--tfvars", str(target)])
        code, records, arm, foundry, _, _, _ = result
        self.assertEqual(code, 0)
        expected = copy.deepcopy(BODY)
        expected["properties"]["endpoints"][0]["credentials"]["headers"]["Authorization"] = ["Bearer " + GITHUB_TOKEN]
        self.assertEqual(arm.call.call_args_list, [
            mock.call("GET", SERVER_ID, "2025-09-01-preview"),
            mock.call("PUT", SERVER_ID, "2025-09-01-preview", expected, None),
            mock.call("GET", SERVER_ID, "2025-09-01-preview"),
        ])
        foundry.call.assert_not_called()
        self.assertEqual([r["status"] for r in records], ["prepared", "pending", "configured"])
        self.assertEqual(records[-1]["configuration_hash"], HASH)
        self.assertEqual(json.loads(target.read_text()), {"gateway_remote_tool_endpoint": MCP})

    def test_get_accepts_only_known_null_credential_placeholders(self):
        for headers in (None, {}, {"Authorization": None}, {
            "Authorization": None, "X-MCP-Readonly": None, "X-MCP-Tools": None,
        }):
            response = observed_server_response()
            response["properties"]["endpoints"][0]["credentials"]["headers"] = headers
            original = copy.deepcopy(response)
            with self.subTest(headers=headers):
                self.assertEqual(tools.server_readback(response, None, bootstrap(), CONFIG),
                                 {"etag": '"revision-1"', "endpoint": MCP})
                self.assertEqual(response, original)
        for headers in (
            {"Authorization": GITHUB_TOKEN}, {"Authorization": [GITHUB_TOKEN]},
            {"Authorization": "***"}, {"Authorization": ["***"]},
            {"Authorization": ""}, {"Authorization": []}, {"Authorization": [None]},
            {"X-Unknown": None}, {"authorization": None}, [],
        ):
            response = observed_server_response()
            response["properties"]["endpoints"][0]["credentials"]["headers"] = headers
            with self.subTest(shape=type(headers).__name__), self.assertRaisesRegex(
                ValueError, "unsupported credential-header data",
            ) as error:
                tools.server_readback(response, None, bootstrap(), CONFIG)
            self.assertNotIn(GITHUB_TOKEN, str(error.exception))

    def test_gateway_endpoint_metadata_is_unambiguous_and_never_guessed(self):
        for legacy in (False, True):
            response = observed_server_response()
            if legacy:
                response["properties"]["mcpEndpointUrl"] = MCP
            response["properties"]["gatewayEndpoints"][0].pop("baseUrl")
            self.assertEqual(tools.server_readback(response, None, bootstrap(), CONFIG)["endpoint"], MCP)
        partial = observed_server_response()
        partial["properties"]["gatewayEndpoints"] = []
        self.assertIsNone(tools.server_readback(partial, None, bootstrap(), CONFIG))
        cases = []
        for entries in (
            None, {}, [None], [{"url": MCP}], [{"api": "responses", "url": MCP}],
            [{"api": "mcp", "url": MCP, "unknown": None}],
            [{"api": "mcp", "url": MCP}, {"api": "mcp", "url": MCP}],
        ):
            response = observed_server_response()
            response["properties"]["gatewayEndpoints"] = entries
            cases.append(response)
        for key, value in (
            ("url", "https://other.example.invalid/mcp"),
            ("url", "https://user:password@gateway.example.invalid/mcp"),
            ("url", MCP + "?key=hidden"), ("url", MCP + "#hidden"),
            ("url", "https://gateway.example.invalid/%73ecret"),
            ("url", "https://gateway.example.invalid/"), ("url", "http://gateway.example.invalid/mcp"),
            ("baseUrl", "https://other.example.invalid/"),
            ("baseUrl", "https://user:password@gateway.example.invalid/"),
            ("baseUrl", "https://gateway.example.invalid/?key=hidden"),
            ("baseUrl", "https://gateway.example.invalid/%53erviceReturned/"),
            ("baseUrl", "https://gateway.example.invalid/Unrelated/"),
        ):
            response = observed_server_response()
            response["properties"]["gatewayEndpoints"][0][key] = value
            cases.append(response)
        response = observed_server_response()
        response["properties"]["mcpEndpointUrl"] = "https://gateway.example.invalid/Conflicting/mcp/"
        cases.append(response)
        for response in cases:
            original = copy.deepcopy(response)
            with self.subTest(properties=list(response["properties"])), self.assertRaises(ValueError):
                tools.server_readback(response, None, bootstrap(), CONFIG)
            self.assertEqual(response, original)

    def test_fail_closed_and_resource_policy_scope_are_required(self):
        for version in (1, 2):
            for required in (False, None, 0, 1, "true", "missing"):
                response = observed_server_response(required)
                if required == "missing":
                    response["properties"]["endpoints"][0].pop("required")
                with self.subTest(version=version, required=required), self.assertRaisesRegex(
                    ValueError, "fail-closed endpoint behavior",
                ):
                    tools.server_readback(response, None, bootstrap(), CONFIG, version=version)
            for failure_mode in ("failOpen", None, False):
                response = observed_server_response()
                response["properties"]["failureMode"] = failure_mode
                with self.subTest(version=version, failure_mode=failure_mode), self.assertRaisesRegex(
                    ValueError, "conflicting failure behavior",
                ):
                    tools.server_readback(response, None, bootstrap(), CONFIG, version=version)
            for scope in ("workspace", "all", None, True):
                response = observed_server_response()
                response["properties"]["policies"][0]["scope"] = scope
                with self.subTest(version=version, scope=scope), self.assertRaisesRegex(ValueError, "policy scope"):
                    tools.server_readback(response, None, bootstrap(), CONFIG, version=version)
        response = observed_server_response()
        response["properties"]["policies"][0].pop("scope")
        with self.assertRaisesRegex(ValueError, "policy scope"):
            tools.server_readback(response, None, bootstrap(), CONFIG)
        for section in ("policies", "endpoints"):
            response = observed_server_response()
            response["properties"][section][0]["unknown"] = True
            with self.subTest(section=section), self.assertRaisesRegex(ValueError, "drift"):
                tools.server_readback(response, None, bootstrap(), CONFIG)
        with self.assertRaisesRegex(ValueError, "fail-closed endpoint behavior"):
            tools.server_readback(server_response(version=1), None, bootstrap(), CONFIG)

    def test_legacy_receipts_inspect_without_rehashing_or_authorizing_writes(self):
        previous = receipt(version=1)
        for response in (server_response(version=1), observed_server_response()):
            result = self.run_main("inspect-toolserver", [(200, response, None)], previous=previous)
            self.assertEqual(result[0], 0)
            self.assertEqual((result[1][-1]["version"], result[1][-1]["configuration_hash"]), (1, LEGACY_HASH))
            self.assertFalse(result[1][-1]["mutation_attempted"])
            result[2].call.assert_called_once_with("GET", SERVER_ID, "2025-09-01-preview")
        for operation in ("rotate-credential", "create-toolbox"):
            with self.subTest(operation=operation):
                result = self.run_main(operation, previous=previous)
                self.assertEqual((result[0], result[1]), (2, []))
                self.assertIn("Version-1 receipts are read-only", result[-1])
                result[4].assert_not_called()
                result[2].call.assert_not_called()
                result[3].call.assert_not_called()

    def test_receipt_version_and_hash_are_bound_throughout_journal(self):
        for version, digest in ((1, HASH), (2, LEGACY_HASH), (True, LEGACY_HASH), (0, HASH), (3, HASH)):
            previous = receipt()
            previous.update(version=version, configuration_hash=digest)
            with self.subTest(version=version, digest=digest):
                result = self.run_main("inspect-toolserver", previous=previous)
                self.assertEqual((result[0], result[1]), (2, []))
                result[4].assert_not_called()
        path = self.root / "mixed-versions.jsonl"
        text = json.dumps(receipt(version=1)) + "\n" + json.dumps(receipt()) + "\n"
        path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ownership or operation"):
            tools.read_receipt(path, bootstrap(), TENANT)
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_explicit_repair_preserves_legacy_bytes_identity_and_request_configuration(self):
        previous = receipt(status="unconfirmed", version=1)
        previous.pop("toolserver")
        legacy_bytes = (json.dumps(previous) + "\n").encode()
        before = observed_server_response(required=False)
        after = observed_server_response()
        after["etag"] = '"revision-2"'
        target = self.root / "repaired.tfvars.json"
        result = self.run_main("repair-toolserver", [
            (200, before, None), (200, {"echo": GITHUB_TOKEN}, None), (200, after, None),
        ], previous=previous, extra=["--confirm-receipt-upgrade", "--tfvars", str(target)])
        self.assertEqual(result[0], 0)
        self.assertEqual((self.root / f"{self.counter}.previous.jsonl").read_bytes(), legacy_bytes)
        self.assertEqual([r["status"] for r in result[1]], ["prepared", "pending", "configured"])
        for record in result[1]:
            self.assertEqual((record["version"], record["configuration_hash"]), (2, HASH))
            self.assertEqual(record["upgraded_from_sha256"], hashlib.sha256(legacy_bytes).hexdigest())
        expected = copy.deepcopy(BODY)
        expected["properties"]["endpoints"][0]["id"] = "generated-source-id"
        expected["properties"]["endpoints"][0]["credentials"]["headers"]["Authorization"] = ["Bearer " + GITHUB_TOKEN]
        self.assertEqual(result[2].call.call_args_list, [
            mock.call("GET", SERVER_ID, tools.API),
            mock.call("PUT", SERVER_ID, tools.API, expected, '"revision-1"'),
            mock.call("GET", SERVER_ID, tools.API),
        ])
        self.assertEqual(json.loads(target.read_text()), {"gateway_remote_tool_endpoint": MCP})
        inspected = self.run_main("inspect-toolserver", [(200, after, None)], previous=result[1][-1])
        self.assertEqual(inspected[0], 0)
        self.assertEqual(inspected[1][-1]["upgraded_from_sha256"], hashlib.sha256(legacy_bytes).hexdigest())
        self.assertFalse(inspected[1][-1]["mutation_attempted"])

    def test_repair_requires_explicit_upgrade_and_original_consumed_legacy_create(self):
        legacy = receipt(status="unconfirmed", version=1)
        invalid = [receipt(), receipt(version=1)]
        for changes in ({"mutation_attempted": False}, {"operation": "inspect-toolserver"},
                        {"status": "prepared"}, {"toolbox": {"name": "digest"}}):
            invalid.append({**legacy, **changes})
        for previous, extra in [(legacy, [])] + [
            (value, ["--confirm-receipt-upgrade"]) for value in invalid
        ]:
            with self.subTest(previous=previous, confirmed=bool(extra)):
                result = self.run_main("repair-toolserver", previous=previous, extra=extra)
                self.assertEqual((result[0], result[1]), (2, []))
                result[4].assert_not_called()
                result[2].call.assert_not_called()
        result = self.run_main("inspect-toolserver", previous=legacy, extra=["--confirm-receipt-upgrade"])
        self.assertEqual((result[0], result[1]), (2, []))
        result[4].assert_not_called()

    def test_repair_rejects_any_drift_besides_the_known_false_required_value(self):
        responses = [observed_server_response(value) for value in (True, None, 0, 1, "false")]
        for field, value in (
            ("id", "other-resource"), ("etag", None),
            ("description", "Different owner"), ("endpoint_id", None),
            ("scope", "workspace"), ("headers", {"Authorization": GITHUB_TOKEN}),
            ("gatewayEndpoints", [{"api": "mcp", "url": "https://wrong.example.invalid/mcp"}]),
        ):
            response = observed_server_response(required=False)
            if field in ("id", "etag"):
                response[field] = value
            elif field == "endpoint_id":
                response["properties"]["endpoints"][0]["id"] = value
            elif field == "headers":
                response["properties"]["endpoints"][0]["credentials"]["headers"] = value
            elif field == "scope":
                response["properties"]["policies"][0]["scope"] = value
            else:
                response["properties"][field] = value
            responses.append(response)
        for response in responses:
            with self.subTest(response=response):
                original = copy.deepcopy(response)
                result = self.run_main("repair-toolserver", [(200, response, None)],
                                       previous=receipt(status="unconfirmed", version=1),
                                       extra=["--confirm-receipt-upgrade"])
                self.assertEqual(result[0], 2)
                self.assertFalse(result[1][-1]["mutation_attempted"])
                result[2].call.assert_called_once_with("GET", SERVER_ID, tools.API)
                self.assertEqual(response, original)

    def test_repair_failure_is_not_retried_and_repair_receipt_cannot_replay_it(self):
        for status in (0, 307, 400, 409, 412, 429, 500):
            with self.subTest(status=status):
                result = self.run_main("repair-toolserver", [
                    (200, observed_server_response(required=False), None), (status, None, None),
                ], previous=receipt(status="unconfirmed", version=1), extra=["--confirm-receipt-upgrade"])
                self.assertEqual((result[0], result[2].call.call_count), (2, 2))
                self.assertEqual(result[1][-1]["status"], "unconfirmed")
                self.assertTrue(result[1][-1]["mutation_attempted"])
                replay = self.run_main("repair-toolserver", previous=result[1][-1],
                                       extra=["--confirm-receipt-upgrade"])
                self.assertEqual((replay[0], replay[1]), (2, []))
                replay[4].assert_not_called()

    def test_repair_does_not_export_changed_endpoint_identity_or_incomplete_safety(self):
        responses = [observed_server_response(required=False)]
        changed_id = observed_server_response()
        changed_id["properties"]["endpoints"][0]["id"] = "different-id"
        responses.append(changed_id)
        changed_url = observed_server_response()
        changed_url["properties"]["gatewayEndpoints"][0]["url"] = MCP + "changed"
        responses.append(changed_url)
        for index, response in enumerate(responses):
            target = self.root / f"blocked-repair-{index}.tfvars.json"
            result = self.run_main("repair-toolserver", [
                (200, observed_server_response(required=False), None), (200, None, None), (200, response, None),
            ], previous=receipt(status="unconfirmed", version=1),
                extra=["--confirm-receipt-upgrade", "--tfvars", str(target)])
            self.assertEqual(result[0], 2)
            self.assertFalse(target.exists())
            self.assertEqual(result[1][-1]["status"], "unconfirmed")
            self.assertEqual(result[2].call.call_count, 3)

    def test_repair_provenance_cannot_change_inside_a_journal(self):
        record = receipt()
        record.update(operation="repair-toolserver", upgraded_from_sha256="a" * 64)
        path = self.root / "repair-provenance.jsonl"
        for changed in ({**record, "upgraded_from_sha256": "b" * 64},
                        {**record, "upgraded_from_sha256": None},
                        {key: value for key, value in record.items() if key != "upgraded_from_sha256"}):
            path.write_text(json.dumps(record) + "\n" + json.dumps(changed) + "\n", encoding="utf-8")
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                tools.read_receipt(path, bootstrap(), TENANT)

    def test_existing_fail_open_server_blocks_inspection_without_a_handoff(self):
        target = self.root / "blocked.tfvars.json"
        previous = receipt(status="unconfirmed", version=1)
        result = self.run_main(
            "inspect-toolserver", [(200, observed_server_response(required=False), None)],
            previous=previous, extra=["--tfvars", str(target)],
        )
        self.assertEqual(result[0], 2)
        self.assertIn("fail-closed endpoint behavior", result[-1])
        self.assertNotIn("credential-header", result[-1])
        self.assertEqual(result[1][-1]["status"], "unconfirmed")
        self.assertEqual((result[1][-1]["version"], result[1][-1]["configuration_hash"]), (1, LEGACY_HASH))
        self.assertFalse(result[1][-1]["mutation_attempted"])
        self.assertFalse(target.exists())
        result[2].call.assert_called_once_with("GET", SERVER_ID, "2025-09-01-preview")
        result[3].call.assert_not_called()

    def test_legacy_toolbox_inspection_preserves_original_metadata_hash(self):
        previous = receipt(connected=True, version=1)
        previous["operation"] = "create-toolbox"
        previous["toolbox"] = {
            "name": "digest", "version": "7",
            "endpoint": PROJECT_ENDPOINT + "/toolboxes/digest/versions/7/mcp?api-version=v1",
        }
        result = self.run_main(
            "inspect-toolbox", [(200, observed_server_response(), None), (200, connection_response(), None)],
            box_reads(receipt_version=1), previous=previous,
        )
        self.assertEqual(result[0], 0)
        self.assertEqual(result[1][-1]["configuration_hash"], LEGACY_HASH)
        self.assertEqual(result[1][-1]["toolbox"], previous["toolbox"])
        self.assertTrue(all(call.args[0] == "GET" for call in result[2].call.call_args_list
                            + result[3].call.call_args_list))

    def test_create_never_adopts_existing_or_unqualified_missing_resource(self):
        for response in (
            (200, server_response(), None), (403, {"error": GITHUB_TOKEN}, None),
            (404, {"error": {"code": "ResourceNotFound", "message": "Parent not found."}}, None),
            (404, {"error": {"code": "SubscriptionNotFound", "message": "ToolServer not found."}}, None),
        ):
            with self.subTest(status=response[0]):
                code, records, arm, *_ = self.run_main("create-toolserver", [response])
                self.assertEqual(code, 2)
                arm.call.assert_called_once_with("GET", SERVER_ID, "2025-09-01-preview")
                self.assertFalse(records[-1]["mutation_attempted"])

    def test_failed_or_uncertain_put_is_not_retried_and_has_recoverable_receipt(self):
        for status in (0, 307, 400, 409, 412, 429, 500):
            with self.subTest(status=status):
                code, records, arm, *_ = self.run_main(
                    "create-toolserver", [missing_server(), (status, {"error": GITHUB_TOKEN}, None)],
                )
                self.assertEqual((code, arm.call.call_count), (2, 2))
                self.assertEqual(records[-1]["status"], "unconfirmed")
                self.assertTrue(records[-1]["mutation_attempted"])
                inspected = self.run_main("inspect-toolserver", [(200, server_response(), None)], previous=records[-1])
                self.assertEqual(inspected[0], 0)
                inspected[2].call.assert_called_once_with("GET", SERVER_ID, "2025-09-01-preview")
                self.assertFalse(inspected[1][-1]["mutation_attempted"])

    def test_rotation_resends_complete_configuration_with_fresh_etag(self):
        code, records, arm, *_ = self.run_main("rotate-credential", [
            (200, server_response(), '"revision-1"'), (200, None, None),
            (200, server_response('"revision-2"'), '"revision-2"'),
        ], previous=receipt())
        self.assertEqual(code, 0)
        expected = copy.deepcopy(BODY)
        expected["properties"]["endpoints"][0]["credentials"]["headers"]["Authorization"] = ["Bearer " + GITHUB_TOKEN]
        self.assertEqual(arm.call.call_args_list[1], mock.call(
            "PUT", SERVER_ID, "2025-09-01-preview", expected, '"revision-1"',
        ))
        self.assertEqual(records[-1]["toolserver"], {"etag": '"revision-2"', "endpoint": MCP})

    def test_rotation_rejects_stale_receipt_policy_drift_and_missing_etag(self):
        cases = []
        drift = server_response()
        drift["properties"]["policies"].append({"type": "unknown-policy"})
        cases.append(drift)
        drift = server_response()
        drift["properties"]["endpoints"].append(copy.deepcopy(drift["properties"]["endpoints"][0]))
        cases.append(drift)
        cases += [server_response('"other"'), server_response(None), server_response("*")]
        for response in cases:
            with self.subTest(response_etag=response.get("etag")):
                code, _, arm, *_ = self.run_main("rotate-credential", [(200, response, None)], previous=receipt())
                self.assertEqual(code, 2)
                self.assertEqual(arm.call.call_count, 1)

    def test_rotation_does_not_export_an_unexpected_new_frontend_endpoint(self):
        response = server_response('"revision-2"')
        response["properties"]["mcpEndpointUrl"] = "https://gateway.example.invalid/unexpected-route"
        target = self.root / "unexpected.tfvars.json"
        result = self.run_main("rotate-credential", [
            (200, server_response(), None), (200, None, None), (200, response, None),
        ], previous=receipt(), extra=["--tfvars", str(target)])
        self.assertEqual(result[0], 2)
        self.assertEqual(result[1][-1]["status"], "unconfirmed")
        self.assertFalse(target.exists())

    def test_receipt_must_be_durable_before_a_mutation_is_sent(self):
        with mock.patch.object(tools.os, "fsync", side_effect=[None, OSError("disk unavailable"), None]):
            result = self.run_main("create-toolserver", [missing_server()])
        self.assertEqual(result[0], 2)
        result[2].call.assert_called_once_with("GET", SERVER_ID, "2025-09-01-preview")

    def test_get_rejects_secret_values_wrong_identity_conflicting_etags_and_bad_urls(self):
        cases = []
        for headers in ({"Authorization": [GITHUB_TOKEN]}, {"Authorization": ["***"]}):
            response = server_response()
            response["properties"]["endpoints"][0]["credentials"]["headers"] = headers
            cases.append((response, None))
        response = server_response()
        response["id"] = SERVER_ID.replace("/github", "/someone-else")
        cases += [(response, None), (server_response(), '"conflicting"')]
        for value in (
            "https://other.example.invalid/mcp", "https://user:password@gateway.example.invalid/mcp",
            MCP + "?token=hidden", MCP + "#hidden", "https://gateway.example.invalid/%73ecret",
            "https://gateway.example.invalid", "http://gateway.example.invalid/mcp",
        ):
            response = server_response()
            response["properties"]["mcpEndpointUrl"] = value
            cases.append((response, None))
        for response, etag in cases:
            original = copy.deepcopy(response)
            with self.subTest(kind=response.get("id")), self.assertRaises(ValueError) as error:
                tools.server_readback(response, etag, bootstrap(), CONFIG)
            self.assertNotIn(GITHUB_TOKEN, str(error.exception))
            self.assertEqual(response, original)

    def test_reflected_credential_metadata_is_not_persisted(self):
        code, records, _, _, _, _, error = self.run_main(
            "inspect-toolserver", [(200, server_response('"' + ARM_TOKEN + '"'), None)], previous=receipt(),
        )
        self.assertEqual(code, 2)
        self.assertEqual(records[-1]["status"], "prepared")
        self.assertIn("credential-exclusion", error)

    def test_bootstrap_rejects_wrong_context_version_resource_and_connection(self):
        for key, value in (
            ("api_version", "2026-11-01"), ("version", True), ("tool_access_enabled", "true"),
            ("subscription_id", TENANT), ("gateway_id", GATEWAY.replace("aigateways", "service")),
            ("workspace_id", GATEWAY + "/workspaces/other"),
            ("project_endpoint", "https://other.services.ai.azure.com/api/projects/project"),
            ("gateway_endpoint", "https://gateway.example.invalid/model/route"),
            ("remote_tool_connection_id", PROJECT + "/connections/unowned"),
            ("remote_tool_endpoint", "https://elsewhere.example.invalid/mcp"),
        ):
            source = bootstrap()
            source[key] = value
            with self.subTest(key=key):
                code, records, arm, _, cli, *_ = self.run_main("create-toolserver", source=source)
                self.assertEqual((code, records), (2, []))
                cli.assert_not_called()
                arm.call.assert_not_called()

    def test_explicit_ownership_and_readonly_credential_selection_are_required(self):
        required = ["--confirm-exclusive-owner", "--confirm-read-only-credential",
                    "--credential-env", "SELECTED_TEST_CREDENTIAL", "--repository", "example/repository"]
        for flag in ("--confirm-exclusive-owner", "--confirm-read-only-credential", "--credential-env"):
            flags = list(required)
            index = flags.index(flag)
            del flags[index:index + (2 if flag == "--credential-env" else 1)]
            with self.subTest(flag=flag):
                result = self.run_main("create-toolserver", defaults=False, extra=flags)
                self.assertEqual((result[0], result[1]), (2, []))
                result[4].assert_not_called()
        for value in ("", "Bearer " + GITHUB_TOKEN, GITHUB_TOKEN + "\n"):
            result = self.run_main("create-toolserver", credential=value)
            self.assertEqual((result[0], result[1]), (2, []))
            result[4].assert_not_called()
        source = bootstrap()
        source["tool_access_enabled"] = False
        result = self.run_main("create-toolserver", source=source)
        self.assertEqual((result[0], result[1]), (2, []))

    def test_mcp_cidrs_are_independent_normalized_and_rejected_when_unbounded(self):
        config = tools.configuration("example/repository", ["203.0.113.42/24", "2001:db8::1/48", "203.0.113.0/24"], OWNER)
        self.assertEqual(config["allowed_client_cidrs"], ["2001:db8::/48", "203.0.113.0/24"])
        self.assertEqual(tools.server_body(config)["properties"]["policies"][1]["cidrRanges"],
                         config["allowed_client_cidrs"])
        self.assertEqual(len(tools.server_body(tools.configuration("example/repository", [], OWNER))
                             ["properties"]["policies"]), 1)
        for value in ("0.0.0.0/0", "::/0", "not-a-network"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tools.configuration("example/repository", [value], OWNER)

    def test_receipt_identity_hash_and_nested_unknown_fields_stop_before_persistence(self):
        cases = []
        previous = receipt()
        previous["configuration_hash"] = "wrong"
        cases.append(previous)
        previous = receipt()
        previous["binding"]["tenant_id"] = OWNER
        cases.append(previous)
        previous = receipt()
        previous["toolserver"]["unexpected_secret"] = GITHUB_TOKEN
        cases.append(previous)
        previous = receipt()
        previous["toolbox"] = {"name": "digest", "unexpected_secret": GITHUB_TOKEN}
        cases.append(previous)
        previous = receipt()
        previous["toolbox"] = {"name": "digest", "version": "7", "endpoint": "https://unrelated.example.invalid/"}
        cases.append(previous)
        for previous in cases:
            with self.subTest(keys=list(previous)):
                code, records, arm, _, cli, *_ = self.run_main("inspect-toolserver", previous=previous)
                self.assertEqual((code, records), (2, []))
                cli.assert_not_called()
                arm.call.assert_not_called()

    def test_partial_receipt_tail_is_unconfirmed_and_cannot_authorize_rotation(self):
        path = self.root / "interrupted.jsonl"
        path.write_text(json.dumps(receipt()) + '\n{"status":', encoding="utf-8")
        recovered = tools.read_receipt(path, bootstrap(), TENANT)
        self.assertEqual(recovered["status"], "unconfirmed")
        result = self.run_main("rotate-credential", previous=recovered)
        self.assertEqual((result[0], result[1]), (2, []))
        result[4].assert_not_called()

    def test_existing_or_automatic_output_is_never_overwritten(self):
        existing = self.root / "existing.tfvars.json"
        existing.write_text("unchanged", encoding="utf-8")
        for path in (existing, self.root / "terraform.tfvars.json", self.root / "tools.auto.tfvars.json"):
            result = self.run_main("create-toolserver", extra=["--tfvars", str(path)])
            self.assertEqual(result[0], 2)
            result[4].assert_not_called()
        self.assertEqual(existing.read_text(), "unchanged")

    def test_wrong_cli_and_token_context_stops_before_requests(self):
        for stage, key, value in (
            (0, "id", TENANT), (0, "tenantId", SUBSCRIPTION), (0, "environmentName", "AzureUSGovernment"),
            (1, "subscription", TENANT), (1, "tenant", SUBSCRIPTION), (1, "tokenType", "other"),
            (1, "accessToken", "bad\nvalue"),
        ):
            context = cli_context()
            context[stage][key] = value
            with self.subTest(key=key):
                code, _, arm, _, cli, *_ = self.run_main("create-toolserver", context=context)
                self.assertEqual(code, 2)
                arm.call.assert_not_called()
                self.assertEqual(cli.call_count, stage + 1)

    def test_create_toolbox_verifies_connection_and_writes_only_review_handoff(self):
        output = self.root / "runtime.review.json"
        code, records, arm, foundry, cli, clients, _ = self.run_main(
            "create-toolbox", [(200, server_response(), None), (200, connection_response(), None)],
            [(404, None, None), (201, {"name": "digest", "version": "7"}, None), *box_reads()],
            previous=receipt(), extra=["--environment-json", str(output)],
        )
        self.assertEqual(code, 0)
        self.assertEqual(arm.call.call_args_list, [
            mock.call("GET", SERVER_ID, "2025-09-01-preview"),
            mock.call("GET", PROJECT + "/connections/aigw-github", "2025-06-01"),
        ])
        self.assertEqual(foundry.call.call_args_list[1], mock.call(
            "POST", "/toolboxes/digest/versions", "v1", toolbox_request(),
        ))
        self.assertEqual(foundry.call.call_count, 4)
        self.assertEqual(clients.call_args_list[1].args[:2], (PROJECT_ENDPOINT, FOUNDRY_TOKEN))
        self.assertEqual(cli.call_args_list[2].args[0], [
            "account", "get-access-token", "--resource", "https://ai.azure.com", "--subscription", SUBSCRIPTION,
        ])
        expected_endpoint = PROJECT_ENDPOINT + "/toolboxes/digest/versions/7/mcp?api-version=v1"
        self.assertEqual(json.loads(output.read_text()), {
            "TOOLBOX_NAME": "digest", "TOOLBOX_ENDPOINT": expected_endpoint, "GITHUB_REPOSITORY": "example/repository",
        })
        self.assertEqual(records[-1]["toolbox"]["endpoint"], expected_endpoint)

    def test_toolbox_accepts_explicit_unshared_connection_without_changing_it(self):
        connection = connection_response()
        connection["properties"]["isSharedToAll"] = False
        code, records, arm, *_ = self.run_main(
            "create-toolbox", [(200, server_response(), None), (200, connection, None)],
            [(404, None, None), (201, {"name": "digest", "version": "7"}, None), *box_reads()],
            previous=receipt(),
        )
        self.assertEqual(code, 0)
        self.assertTrue(all(call.args[0] == "GET" for call in arm.call.call_args_list))
        inspected = self.run_main(
            "inspect-toolbox", [(200, server_response(), None), (200, connection, None)],
            box_reads(), previous=records[-1],
        )
        self.assertEqual(inspected[0], 0)
        self.assertFalse(inspected[1][-1]["mutation_attempted"])

    def test_toolbox_rejects_missing_or_nonboolean_connection_sharing_before_writes(self):
        for sharing in ({}, *({"isSharedToAll": value} for value in (None, "false", 0, 1))):
            connection = connection_response()
            connection["properties"].pop("isSharedToAll")
            connection["properties"].update(sharing)
            with self.subTest(sharing=sharing):
                result = self.run_main(
                    "create-toolbox", [(200, server_response(), None), (200, connection, None)], previous=receipt(),
                )
                self.assertEqual(result[0], 2)
                result[3].call.assert_not_called()

    def test_toolbox_requires_fresh_terraform_handoff_before_authentication(self):
        result = self.run_main("create-toolbox", previous=receipt(), source=bootstrap(False))
        self.assertEqual((result[0], result[1]), (2, []))
        result[4].assert_not_called()

    def test_toolbox_rejects_connection_drift_or_credential_auth_without_writes(self):
        for key, value in (("target", "https://gateway.example.invalid/wrong"),
                           ("authType", "CustomKeys"), ("audience", "wrong"),
                           ("credentials", {"key": GITHUB_TOKEN}), ("error", "synthetic connection failure")):
            connection = connection_response()
            connection["properties"][key] = value
            with self.subTest(key=key):
                result = self.run_main(
                    "create-toolbox", [(200, server_response(), None), (200, connection, None)], previous=receipt(),
                )
                self.assertEqual(result[0], 2)
                result[3].call.assert_not_called()

    def test_toolbox_never_creates_a_version_on_an_existing_or_inaccessible_name(self):
        for status in (200, 401, 403, 429, 500):
            with self.subTest(status=status):
                result = self.run_main(
                    "create-toolbox", [(200, server_response(), None), (200, connection_response(), None)],
                    [(status, {}, None)], previous=receipt(),
                )
                self.assertEqual(result[0], 2)
                result[3].call.assert_called_once_with("GET", "/toolboxes/digest", "v1")
                self.assertFalse(result[1][-1]["mutation_attempted"])

    def test_uncertain_toolbox_post_is_not_retried_and_inspection_is_readonly(self):
        for status in (0, 307, 409, 500):
            with self.subTest(status=status):
                result = self.run_main(
                    "create-toolbox", [(200, server_response(), None), (200, connection_response(), None)],
                    [(404, None, None), (status, {"error": FOUNDRY_TOKEN}, None)], previous=receipt(),
                )
                self.assertEqual((result[0], result[3].call.call_count), (2, 2))
                inspected = self.run_main(
                    "inspect-toolbox", [(200, server_response(), None), (200, connection_response(), None)],
                    box_reads(), previous=result[1][-1],
                )
                self.assertEqual(inspected[0], 0)
                self.assertTrue(all(call.args[0] == "GET" for call in inspected[3].call.call_args_list))
                self.assertFalse(inspected[1][-1]["mutation_attempted"])

    def test_created_toolbox_version_is_retained_when_readback_fails(self):
        result = self.run_main(
            "create-toolbox", [(200, server_response(), None), (200, connection_response(), None)],
            [(404, None, None), (201, {"name": "digest", "version": "7"}, None), (503, None, None)],
            previous=receipt(),
        )
        self.assertEqual(result[0], 2)
        saved = result[1][-1]
        self.assertEqual((saved["status"], saved["toolbox"]["version"]), ("unconfirmed", "7"))
        inspected = self.run_main(
            "inspect-toolbox", [(200, server_response(), None), (200, connection_response(), None)],
            [(200, {"name": "digest", "default_version": "8"}, None)], previous=saved,
        )
        self.assertEqual(inspected[0], 2)
        inspected[3].call.assert_called_once_with("GET", "/toolboxes/digest", "v1")

    def test_rotation_retains_the_toolbox_handle_for_subsequent_readonly_inspection(self):
        previous = receipt()
        previous["operation"] = "create-toolbox"
        previous["toolbox"] = {
            "name": "digest", "version": "7",
            "endpoint": PROJECT_ENDPOINT + "/toolboxes/digest/versions/7/mcp?api-version=v1",
        }
        result = self.run_main("rotate-credential", [
            (200, server_response(), None), (200, None, None), (200, server_response('"revision-2"'), None),
        ], previous=previous, source=bootstrap(True))
        self.assertEqual(result[0], 0)
        self.assertEqual(result[1][-1]["toolbox"], previous["toolbox"])
        inspected = self.run_main(
            "inspect-toolbox", [(200, server_response('"revision-2"'), None), (200, connection_response(), None)],
            box_reads(), previous=result[1][-1],
        )
        self.assertEqual(inspected[0], 0)
        self.assertTrue(all(call.args[0] == "GET" for call in inspected[3].call.call_args_list))

    def test_toolbox_owner_tools_default_version_and_governance_must_match(self):
        record = receipt()
        record["toolbox"] = {"name": "digest"}
        cases = []
        for field, value in (
            ("metadata", {"terraform_toolchain_owner": "someone-else"}),
            ("tools", []), ("skills", [{"name": "unreviewed"}]),
            ("policies", {"rai_config": {"rai_policy_name": "unexpected"}}), ("name", "another-box"),
        ):
            responses = box_reads()
            responses[1][1][field] = value
            cases.append(responses)
        responses = box_reads("8")
        cases.append(responses)
        for responses in cases:
            client = mock.Mock()
            client.call.side_effect = responses
            with self.subTest(field=responses[0][1]), self.assertRaises(ValueError):
                tools.inspect_toolbox(client, bootstrap(True), record, "7")

    def test_readiness_only_retries_bounded_gets_and_rejects_terminal_failure(self):
        partial = server_response()
        partial["properties"].pop("mcpEndpointUrl")
        client = mock.Mock()
        client.call.side_effect = [(429, None, None), (200, partial, None), (200, server_response(), None)]
        self.assertEqual(tools.wait_server(client, bootstrap(), CONFIG, tools.time.monotonic() + 60)["endpoint"], MCP)
        self.assertEqual(client.call.call_count, 3)
        client = mock.Mock()
        client.call.return_value = (404, None, None)
        with self.assertRaisesRegex(ValueError, "limit reached"):
            tools.wait_server(client, bootstrap(), CONFIG, tools.time.monotonic() + 60)
        self.assertEqual(client.call.call_count, 30)
        for status in (301, 307, 400, 401, 403):
            client = mock.Mock()
            client.call.return_value = (status, None, None)
            with self.subTest(status=status), self.assertRaises(ValueError):
                tools.wait_server(client, bootstrap(), CONFIG, tools.time.monotonic() + 60)
            client.call.assert_called_once()

    def test_expired_deadline_stops_readiness_even_after_success(self):
        client = mock.Mock()
        client.call.return_value = (200, server_response(), None)
        with mock.patch.object(tools.time, "monotonic", return_value=11), self.assertRaisesRegex(ValueError, "Deadline"):
            tools.wait_server(client, bootstrap(), CONFIG, 10)
        client.call.assert_called_once()

    def test_transport_has_no_redirects_no_secret_argv_and_bounded_responses(self):
        response = io.BytesIO(json.dumps(server_response()).encode())
        response.status, response.headers = 200, {"ETag": '"revision-1"'}
        with mock.patch.object(tools.urllib.request, "build_opener") as factory:
            factory.return_value.open.return_value = response
            client = tools.Client(tools.ARM, ARM_TOKEN, tools.time.monotonic() + 60)
            status, _, etag = client.call("GET", SERVER_ID, tools.API)
            self.assertEqual((status, etag), (200, '"revision-1"'))
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, tools.ARM + SERVER_ID + "?api-version=2025-09-01-preview")
            self.assertEqual(request.get_header("Authorization"), "Bearer " + ARM_TOKEN)
            handler = factory.call_args.args[0]
            self.assertIsNone(handler.redirect_request(request, None, 307, "", {}, "https://other.example.invalid"))
            factory.return_value.open.side_effect = urllib.error.HTTPError(
                request.full_url, 307, GITHUB_TOKEN, {"Location": "https://other.example.invalid"}, io.BytesIO(b"hidden"),
            )
            self.assertEqual(client.call("PUT", SERVER_ID, tools.API, BODY, '"revision-1"'), (307, None, None))
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("If-match"), '"revision-1"')
            factory.return_value.open.side_effect = None
            oversized = io.BytesIO(b"x" * (tools.MAX_BYTES + 1))
            oversized.status, oversized.headers = 200, {}
            factory.return_value.open.return_value = oversized
            with self.assertRaisesRegex(ValueError, "bounded size"):
                client.call("GET", SERVER_ID, tools.API)

    def test_put_response_is_not_decoded_or_projected(self):
        response = io.BytesIO(GITHUB_TOKEN.encode())
        response.status, response.headers = 201, {}
        with mock.patch.object(tools.urllib.request, "build_opener") as factory:
            factory.return_value.open.return_value = response
            client = tools.Client(tools.ARM, ARM_TOKEN, tools.time.monotonic() + 60)
            self.assertEqual(client.call("PUT", SERVER_ID, tools.API, BODY), (201, None, None))

    def test_azure_cli_excludes_selected_github_credential_and_redacts_failures(self):
        with mock.patch.object(tools.shutil, "which", return_value=r"C:\tools\az.CMD"), \
                mock.patch.object(tools.subprocess, "run") as run, \
                mock.patch.dict(tools.os.environ, {"SELECTED": GITHUB_TOKEN, "KEEP": "safe"}, clear=True):
            run.return_value = mock.Mock(returncode=0, stdout='{"ok": true}')
            self.assertEqual(tools.azure_json(["account", "show"], tools.time.monotonic() + 60, "SELECTED"), {"ok": True})
            self.assertEqual(run.call_args.args[0], [
                r"C:\tools\az.CMD", "account", "show", "--only-show-errors", "-o", "json",
            ])
            self.assertEqual(run.call_args.kwargs["env"], {"KEEP": "safe"})
            self.assertLessEqual(run.call_args.kwargs["timeout"], 60)
            run.return_value = mock.Mock(returncode=1, stderr=GITHUB_TOKEN)
            with self.assertRaises(ValueError) as error:
                tools.azure_json(["account", "show"], tools.time.monotonic() + 60, "SELECTED")
            self.assertNotIn(GITHUB_TOKEN, str(error.exception))
            run.side_effect = subprocess.TimeoutExpired(["az"], 1, output=GITHUB_TOKEN)
            with self.assertRaises(subprocess.TimeoutExpired):
                tools.azure_json(["account", "show"], tools.time.monotonic() + 60, "SELECTED")

    def test_argument_errors_do_not_echo_mistaken_secret_arguments(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
            tools.arguments(["create-toolserver", "--token", GITHUB_TOKEN])
        self.assertEqual(error.exception.code, 2)
        self.assertNotIn(GITHUB_TOKEN, stderr.getvalue())

    def test_selected_credential_exclusion_respects_platform_casing(self):
        cases = (
            ("nt", {"SELECTED": GITHUB_TOKEN, "KEEP": "safe"}, "selected", {"KEEP": "safe"}),
            ("nt", {"SELECTED": GITHUB_TOKEN, "KEEP": "safe"}, "SeLeCtEd", {"KEEP": "safe"}),
            ("posix", {"SELECTED": "other", "selected": GITHUB_TOKEN, "KEEP": "safe"},
             "selected", {"SELECTED": "other", "KEEP": "safe"}),
        )
        for platform, environment, selected, expected in cases:
            original = environment.copy()
            with self.subTest(platform=platform, selected=selected), \
                    mock.patch.object(tools.os, "name", platform), \
                    mock.patch.object(tools.os, "environ", environment), \
                    mock.patch.object(tools.shutil, "which", return_value="az"), \
                    mock.patch.object(tools.subprocess, "run", return_value=mock.Mock(
                        returncode=0, stdout='{"ok": true}',
                    )) as run:
                tools.azure_json(["account", "show"], tools.time.monotonic() + 60, selected)
                self.assertEqual(run.call_args.kwargs["env"], expected)
                self.assertEqual(environment, original)


if __name__ == "__main__":
    unittest.main()
