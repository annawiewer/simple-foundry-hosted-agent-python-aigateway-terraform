import contextlib
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "verify_live_readback",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "verify_live_readback.py",
)
readback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readback)
SUBSCRIPTION = "11111111-1111-1111-1111-111111111111"
TENANT = "22222222-2222-2222-2222-222222222222"
IDENTIFIER = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/test/providers/Test/items/test"


def fixture():
    resource = {
        "mode": "managed", "type": "azapi_resource", "address": "azapi_resource.test",
        "values": {
            "id": IDENTIFIER, "type": "Test/items@2026-09-01-preview",
            "body": {"properties": {"roleDefinitionId": IDENTIFIER + "/roles/test"}},
            "location": "Sweden Central",
            "identity": [{"type": "SystemAssigned", "principal_id": "principal"}],
        },
    }
    document = {"values": {
        "outputs": {"deployment_contract": {"value": {
            "version": 1, "subscription_id": SUBSCRIPTION,
        }}},
        "root_module": {"resources": [], "child_modules": [{"resources": [resource]}]},
    }}
    live = {
        "id": IDENTIFIER.upper(), "location": "swedencentral",
        "identity": {"type": "systemAssigned", "principalId": "principal"},
        "properties": {"roleDefinitionId": (IDENTIFIER + "/roles/test").upper()},
    }
    return document, resource, live


class LiveReadbackTests(unittest.TestCase):
    def test_nested_resources_and_documented_normalizations(self):
        document, _, live = fixture()
        fetch = mock.Mock(return_value=(200, live))
        report = readback.qualify(document, SUBSCRIPTION, fetch)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["compared_leaves"], 4)
        self.assertFalse(report["writes_performed"])
        self.assertFalse(report["runtime_accepted"])
        fetch.assert_called_once_with(IDENTIFIER, "2026-09-01-preview")

    def test_get_omitted_credential_is_incomplete_and_never_logged(self):
        document, resource, live = fixture()
        resource["values"]["body"]["properties"]["credentials"] = {
            "key": "must-not-appear-in-receipt",
        }
        report = readback.qualify(document, SUBSCRIPTION, lambda *_: (200, live))
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["resources"][0]["not_returned"], ["body.properties.credentials"])
        self.assertNotIn("must-not-appear-in-receipt", json.dumps(report))

    def test_wrong_role_identity_or_response_owner_fails(self):
        for field in ("role", "principal", "id"):
            with self.subTest(field=field):
                document, _, live = fixture()
                if field == "role":
                    live["properties"]["roleDefinitionId"] += "-wrong"
                elif field == "principal":
                    live["identity"]["principalId"] = "wrong"
                else:
                    live["id"] += "-wrong"
                report = readback.qualify(document, SUBSCRIPTION, lambda *_: (200, live))
                self.assertEqual(report["status"], "FAIL")

    def test_http_and_malformed_envelopes_fail_without_response_logging(self):
        for status, body in ((403, {"error": "must-not-log"}), (200, [])):
            with self.subTest(status=status, body=type(body).__name__):
                document, _, _ = fixture()
                report = readback.qualify(document, SUBSCRIPTION, lambda *_: (status, body))
                self.assertEqual(report["status"], "FAIL")
                self.assertNotIn("must-not-log", json.dumps(report))

    def test_wrong_subscription_and_unsupported_resource_reject_before_fetch(self):
        for change in ("contract", "resource", "provider", "query", "version"):
            with self.subTest(change=change):
                document, resource, _ = fixture()
                if change == "contract":
                    document["values"]["outputs"]["deployment_contract"]["value"]["subscription_id"] = "wrong"
                elif change == "resource":
                    resource["values"]["id"] = "/subscriptions/wrong/resourceGroups/test"
                elif change == "provider":
                    resource["type"] = "unsupported_resource"
                elif change == "query":
                    resource["values"]["id"] += "?redirect=example.invalid"
                else:
                    resource["values"]["type"] = "Test/items@invalid"
                fetch = mock.Mock()
                with self.assertRaises(readback.ReadbackError):
                    readback.qualify(document, SUBSCRIPTION, fetch)
                fetch.assert_not_called()

    def test_empty_state_and_boolean_contract_version_do_not_pass(self):
        for change in ("empty", "version"):
            with self.subTest(change=change):
                document, _, _ = fixture()
                if change == "empty":
                    document["values"]["root_module"] = {"resources": []}
                else:
                    document["values"]["outputs"]["deployment_contract"]["value"]["version"] = True
                with self.assertRaises(readback.ReadbackError):
                    readback.qualify(document, SUBSCRIPTION, mock.Mock())

    def test_type_and_array_mismatches_are_not_case_normalized(self):
        document, resource, live = fixture()
        resource["values"]["body"]["properties"].update({"enabled": True, "endpoints": ["one"]})
        live["properties"].update({"enabled": 1, "endpoints": []})
        report = readback.qualify(document, SUBSCRIPTION, lambda *_: (200, live))
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(
            set(report["resources"][0]["differences"]),
            {"body.properties.enabled", "body.properties.endpoints"},
        )

    def test_equal_json_integer_and_fractional_number_are_equivalent(self):
        document, resource, live = fixture()
        resource["values"]["body"]["properties"]["amount"] = 10.0
        live["properties"]["amount"] = 10
        report = readback.qualify(document, SUBSCRIPTION, lambda *_: (200, live))
        self.assertEqual(report["status"], "PASS")

    def test_cli_resolves_windows_batch_executable_and_withholds_failure_details(self):
        executable = r"C:\tools\az.CMD"
        with mock.patch.object(readback.shutil, "which", return_value=executable):
            with mock.patch.object(readback.subprocess, "run") as run:
                run.return_value = mock.Mock(returncode=0, stdout='{"value": "ok"}')
                self.assertEqual(readback.cli_json("account", "show"), {"value": "ok"})
                self.assertEqual(run.call_args.args[0], [executable, "account", "show", "-o", "json"])
                run.return_value = mock.Mock(returncode=1, stderr="must-not-log", stdout="")
                with self.assertRaises(readback.ReadbackError) as error:
                    readback.cli_json("account", "show")
                self.assertNotIn("must-not-log", str(error.exception))

    def test_main_sends_only_get_and_persists_safe_incomplete_without_overwrite(self):
        document, resource, live = fixture()
        resource["values"]["body"]["properties"]["credentials"] = {"key": "must-not-log"}
        response = io.BytesIO(json.dumps(live).encode())
        response.status = 200
        with tempfile.TemporaryDirectory() as directory:
            state = pathlib.Path(directory) / "state.json"
            report = pathlib.Path(directory) / "receipt.json"
            state.write_text(json.dumps(document), encoding="utf-8")
            arguments = [
                "--state-json", str(state), "--subscription-id", SUBSCRIPTION,
                "--tenant-id", TENANT, "--report", str(report),
            ]
            with mock.patch.object(readback, "cli_json", side_effect=[
                {"id": SUBSCRIPTION, "tenantId": TENANT},
                {"accessToken": "token-must-not-log"},
            ]) as cli, mock.patch.object(readback.urllib.request, "build_opener") as opener:
                opener.return_value.open.return_value = response
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(readback.main(arguments), 3)
                    original = report.read_text(encoding="utf-8")
                    self.assertEqual(readback.main(arguments), 2)
                self.assertEqual(report.read_text(encoding="utf-8"), original)
                self.assertNotIn("must-not-log", original)
                self.assertEqual(cli.call_count, 2)
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(
                    request.full_url,
                    "https://management.azure.com" + IDENTIFIER + "?api-version=2026-09-01-preview",
                )

    def test_wrong_tenant_stops_before_token_or_resource_get(self):
        document, _, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            state = pathlib.Path(directory) / "state.json"
            report = pathlib.Path(directory) / "receipt.json"
            state.write_text(json.dumps(document), encoding="utf-8")
            with mock.patch.object(readback, "cli_json", return_value={
                "id": SUBSCRIPTION, "tenantId": "wrong",
            }) as cli, mock.patch.object(readback.urllib.request, "build_opener") as opener:
                with contextlib.redirect_stderr(io.StringIO()):
                    result = readback.main([
                        "--state-json", str(state), "--subscription-id", SUBSCRIPTION,
                        "--tenant-id", TENANT, "--report", str(report),
                    ])
                self.assertEqual(result, 2)
                self.assertEqual(cli.call_count, 1)
                opener.assert_not_called()
                self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
