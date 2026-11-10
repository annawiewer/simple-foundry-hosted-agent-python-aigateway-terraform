import contextlib
import copy
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "wait_for_telemetry",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "wait_for_telemetry.py",
)
telemetry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(telemetry)
SUBSCRIPTION = "00000000-0000-0000-0000-000000000001"
TENANT = "00000000-0000-0000-0000-000000000003"
PREFIX = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/gateway/providers/"
DCR = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"


def fixture():
    bootstrap = {
        "version": 1, "subscription_id": SUBSCRIPTION, "mode": "OpenTelemetry",
        "gateway_id": PREFIX + "Microsoft.ApiManagement/aigateways/fixture",
        "gateway_principal_id": "00000000-0000-0000-0000-000000000002",
        "insights_id": PREFIX + "Microsoft.Insights/components/monitoring",
        "log_analytics_id": PREFIX + "Microsoft.OperationalInsights/workspaces/logs",
    }
    response = {
        "id": bootstrap["insights_id"].upper(),
        "properties": {
            "WorkspaceResourceId": bootstrap["log_analytics_id"].upper(),
            "AzureMonitorWorkspaceIngestionMode": "Enabled",
            "DefaultDataCollectionRuleResourceId": DCR,
            "MetricsIngestionEndpoint": "https://metrics.example.invalid/otlp/v1/metrics",
            "LogsIngestionEndpoint": "https://logs.example.invalid/otlp/v1/logs",
            "TracesIngestionEndpoint": "https://logs.example.invalid/otlp/v1/traces?api-version=2026-01-01-preview",
            "ConnectionString": "connection-string-must-not-leak",
        },
    }
    return bootstrap, response


def cli_context():
    return [
        {"id": SUBSCRIPTION, "tenantId": TENANT, "environmentName": "AzureCloud"},
        {"subscription": SUBSCRIPTION, "tenant": TENANT, "tokenType": "Bearer",
         "accessToken": "token-must-not-leak"},
    ]


class TelemetryReadinessTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(telemetry.subprocess, "run", side_effect=AssertionError("Unexpected CLI call")).start()
        mock.patch.object(telemetry.urllib.request.OpenerDirector, "open",
                          side_effect=AssertionError("Unexpected network call")).start()

    def test_service_property_variants_and_only_nonsecret_handoff(self):
        for alternate in (False, True):
            with self.subTest(alternate=alternate):
                bootstrap, response = fixture()
                telemetry.validate_bootstrap(bootstrap, SUBSCRIPTION)
                if alternate:
                    for first, second in telemetry.GENERATED_FIELDS.values():
                        response["properties"][second] = response["properties"].pop(first)
                result = telemetry.readiness(response, bootstrap)
                self.assertEqual(set(result), {
                    "version", "gateway_id", "gateway_principal_id", "insights_id", "log_analytics_id",
                    "data_collection_rule_id", "metrics_endpoint", "logs_endpoint", "traces_endpoint",
                })
                self.assertEqual(result["data_collection_rule_id"], DCR)
                self.assertEqual(result["traces_endpoint"],
                                 "https://logs.example.invalid/otlp/v1/traces?api-version=2026-01-01-preview")
                self.assertNotIn("must-not-leak", json.dumps(result))

    def test_wrong_bootstrap_context_or_resource_shape_is_rejected(self):
        for key, value in (
            ("version", True), ("mode", "ApplicationInsights"), ("subscription_id", TENANT),
            ("gateway_principal_id", "not-a-uuid"),
            ("gateway_id", PREFIX + "Microsoft.ApiManagement/service/legacy"),
            ("insights_id", PREFIX + "Microsoft.Insights/components/x?redirect=other"),
            ("log_analytics_id", PREFIX + "Microsoft.Insights/components/not-a-workspace"),
        ):
            with self.subTest(key=key):
                bootstrap, _ = fixture()
                bootstrap[key] = value
                with self.assertRaises(telemetry.ReadinessError):
                    telemetry.validate_bootstrap(bootstrap, SUBSCRIPTION)

    def test_mismatch_and_malformed_fields_fail_even_while_another_field_is_pending(self):
        for key, value in (
            ("id", PREFIX + "Microsoft.Insights/components/other"),
            ("WorkspaceResourceId", PREFIX + "Microsoft.OperationalInsights/workspaces/other"),
            ("DefaultDataCollectionRuleResourceId", DCR.replace(SUBSCRIPTION, TENANT)),
            ("DefaultDataCollectionRuleResourceId", DCR.replace("dataCollectionRules", "components")),
            ("MetricsIngestionEndpoint", 123),
            ("AzureMonitorWorkspaceIngestionMode", "Disabled"),
        ):
            with self.subTest(key=key, value=value):
                bootstrap, response = fixture()
                response["properties"].pop("LogsIngestionEndpoint")
                (response if key == "id" else response["properties"])[key] = value
                with self.assertRaises(telemetry.ReadinessError):
                    telemetry.readiness(response, bootstrap)

    def test_endpoint_credentials_redirect_syntax_and_controls_are_rejected(self):
        for endpoint in (
            "http://metrics.example.invalid", "https://user:password@metrics.example.invalid",
            "https://metrics.example.invalid:444/path", "https://metrics.example.invalid/path?sig=secret",
            "https://metrics.example.invalid/path#secret", "https://metrics.example.invalid/path\\secret",
            "https://metrics.example.invalid/\x00secret", "https://metrics.example.invalid/path\n",
        ):
            with self.subTest(endpoint=repr(endpoint)):
                bootstrap, response = fixture()
                response["properties"]["MetricsIngestionEndpoint"] = endpoint
                with self.assertRaises(telemetry.ReadinessError) as error:
                    telemetry.readiness(response, bootstrap)
                self.assertNotIn(endpoint, str(error.exception))

    def test_conflicting_aliases_are_not_silently_preferred(self):
        bootstrap, response = fixture()
        response["properties"]["DataCollectionRuleResourceId"] = DCR.upper()
        self.assertIsNotNone(telemetry.readiness(response, bootstrap))
        response["properties"]["OTLPMetricsEndpoint"] = "https://other.example.invalid/metrics"
        with self.assertRaisesRegex(telemetry.ReadinessError, "Conflicting"):
            telemetry.readiness(response, bootstrap)

    def test_partial_readiness_polls_exact_insights_then_succeeds(self):
        bootstrap, response = fixture()
        partial = copy.deepcopy(response)
        partial["properties"].pop("MetricsIngestionEndpoint")
        fetch = mock.Mock(side_effect=[(200, partial), (200, response)])
        sleeps = []
        result, attempts = telemetry.wait_for_ready(
            bootstrap, fetch, deadline=600, clock=lambda: 0, sleep=sleeps.append,
        )
        self.assertEqual((attempts, len(sleeps)), (2, 1))
        self.assertEqual(result["data_collection_rule_id"], DCR)
        self.assertEqual(fetch.call_args_list, [mock.call(bootstrap["insights_id"], 30)] * 2)

    def test_retryable_errors_stop_at_request_limit(self):
        bootstrap, _ = fixture()
        for status in (0, 404, 408, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                fetch = mock.Mock(return_value=(status, {"error": "must-not-leak"}))
                with self.assertRaisesRegex(telemetry.ReadinessError, "attempt limit") as error:
                    telemetry.wait_for_ready(
                        bootstrap, fetch, deadline=600, max_attempts=2, clock=lambda: 0, sleep=lambda _: None,
                    )
                self.assertEqual(fetch.call_count, 2)
                self.assertNotIn("must-not-leak", str(error.exception))

    def test_authorization_and_redirect_fail_immediately(self):
        bootstrap, _ = fixture()
        for status in (301, 302, 307, 400, 401, 403, 409):
            with self.subTest(status=status):
                fetch = mock.Mock(return_value=(status, {"error": "must-not-leak"}))
                sleep = mock.Mock()
                with self.assertRaisesRegex(telemetry.ReadinessError, f"HTTP {status}"):
                    telemetry.wait_for_ready(bootstrap, fetch, deadline=600, clock=lambda: 0, sleep=sleep)
                fetch.assert_called_once()
                sleep.assert_not_called()

    def test_deadline_caps_sleep_and_rejects_late_success(self):
        bootstrap, response = fixture()
        now = [0]
        sleep = mock.Mock(side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds))
        fetch = mock.Mock(return_value=(404, None))
        with self.assertRaisesRegex(telemetry.ReadinessError, "deadline"):
            telemetry.wait_for_ready(
                bootstrap, fetch, deadline=5, clock=lambda: now[0], sleep=sleep,
            )
        fetch.assert_called_once_with(bootstrap["insights_id"], 5)
        sleep.assert_called_once_with(5)
        fetch = mock.Mock(side_effect=lambda *_: (now.__setitem__(0, 11) or 200, response))
        now[0] = 0
        with self.assertRaisesRegex(telemetry.ReadinessError, "deadline"):
            telemetry.wait_for_ready(bootstrap, fetch, deadline=10, clock=lambda: now[0], sleep=sleep)

    def test_arm_transport_uses_get_and_rejects_redirects_and_oversized_responses(self):
        bootstrap, response = fixture()
        body = io.BytesIO(json.dumps(response).encode())
        body.status = 200
        with mock.patch.object(telemetry.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = body
            fetch = telemetry.arm_reader("token-must-not-leak")
            self.assertEqual(fetch(bootstrap["insights_id"], 7)[0], 200)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, telemetry.ARM + bootstrap["insights_id"] + "?api-version=2020-02-02")
            self.assertEqual(opener.return_value.open.call_args.kwargs, {"timeout": 7})
            handler = opener.call_args.args[0]
            self.assertIsInstance(handler, telemetry.NoRedirect)
            self.assertIsNone(handler.redirect_request(request, None, 307, "", {}, "https://other.example.invalid"))
            opener.return_value.open.side_effect = urllib.error.HTTPError(
                request.full_url, 307, "must-not-leak", {}, io.BytesIO(b"must-not-leak"),
            )
            self.assertEqual(fetch(bootstrap["insights_id"], 7), (307, None))
            opener.return_value.open.side_effect = None
            oversized = io.BytesIO(b"x" * (telemetry.MAX_RESPONSE_BYTES + 1))
            oversized.status = 200
            opener.return_value.open.return_value = oversized
            with self.assertRaisesRegex(telemetry.ReadinessError, "bounded size"):
                fetch(bootstrap["insights_id"], 7)

    def test_cli_resolves_windows_executable_has_timeout_and_redacts_errors(self):
        with mock.patch.object(telemetry.shutil, "which", return_value=r"C:\tools\az.CMD"), \
                mock.patch.object(telemetry.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout='{"value": "ok"}')
            self.assertEqual(telemetry.cli_json(["account", "show"], telemetry.time.monotonic() + 90), {"value": "ok"})
            self.assertEqual(run.call_args.args[0],
                             [r"C:\tools\az.CMD", "account", "show", "--only-show-errors", "-o", "json"])
            self.assertLessEqual(run.call_args.kwargs["timeout"], 60)
            run.return_value = mock.Mock(returncode=1, stderr="must-not-leak")
            with self.assertRaises(telemetry.ReadinessError) as error:
                telemetry.cli_json(["account", "show"], telemetry.time.monotonic() + 90)
            self.assertNotIn("must-not-leak", str(error.exception))

    def test_main_writes_explicit_handoff_without_overwrite_or_credentials(self):
        bootstrap, response = fixture()
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "bootstrap.json"
            target = pathlib.Path(directory) / "native.ready.tfvars.json"
            source.write_text(json.dumps(bootstrap), encoding="utf-8")
            arguments = ["--bootstrap", str(source), "--tfvars", str(target),
                         "--subscription-id", SUBSCRIPTION, "--tenant-id", TENANT]
            with mock.patch.object(telemetry, "cli_json", side_effect=cli_context()) as cli, \
                    mock.patch.object(telemetry, "arm_reader", return_value=mock.Mock(return_value=(200, response))) as reader:
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(telemetry.main(arguments), 0)
                    original = target.read_text(encoding="utf-8")
                    self.assertEqual(telemetry.main(arguments), 2)
                self.assertEqual(target.read_text(encoding="utf-8"), original)
                self.assertEqual(set(json.loads(original)), {"gateway_native_telemetry"})
                self.assertEqual(cli.call_count, 2)
                reader.assert_called_once_with("token-must-not-leak")
                self.assertNotIn("must-not-leak", original + stdout.getvalue() + stderr.getvalue())

    def test_wrong_cli_or_token_context_stops_before_arm(self):
        for stage, key, value in (
            (0, "id", TENANT), (0, "tenantId", SUBSCRIPTION), (0, "environmentName", "AzureUSGovernment"),
            (1, "subscription", TENANT), (1, "tenant", SUBSCRIPTION), (1, "tokenType", "other"),
        ):
            with self.subTest(stage=stage, key=key), tempfile.TemporaryDirectory() as directory:
                bootstrap, _ = fixture()
                source = pathlib.Path(directory) / "bootstrap.json"
                target = pathlib.Path(directory) / "native.ready.tfvars.json"
                source.write_text(json.dumps(bootstrap), encoding="utf-8")
                context = cli_context()
                context[stage][key] = value
                with mock.patch.object(telemetry, "cli_json", side_effect=context) as cli, \
                        mock.patch.object(telemetry, "arm_reader") as reader, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(telemetry.main([
                        "--bootstrap", str(source), "--tfvars", str(target),
                        "--subscription-id", SUBSCRIPTION, "--tenant-id", TENANT,
                    ]), 2)
                    self.assertEqual(cli.call_count, stage + 1)
                    reader.assert_not_called()
                    self.assertFalse(target.exists())

    def test_automatic_tfvars_and_failed_read_never_write_or_echo_body(self):
        for filename, status in (
            ("terraform.tfvars.json", 200), ("unsafe.auto.tfvars.json", 200),
            ("native.ready.tfvars.json", 403),
        ):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                bootstrap, _ = fixture()
                source = pathlib.Path(directory) / "bootstrap.json"
                target = pathlib.Path(directory) / filename
                source.write_text(json.dumps(bootstrap), encoding="utf-8")
                with mock.patch.object(telemetry, "cli_json", side_effect=cli_context()) as cli, \
                        mock.patch.object(telemetry, "arm_reader",
                                          return_value=mock.Mock(return_value=(status, {"error": "must-not-leak"}))):
                    output = io.StringIO()
                    with contextlib.redirect_stderr(output):
                        self.assertEqual(telemetry.main([
                            "--bootstrap", str(source), "--tfvars", str(target),
                            "--subscription-id", SUBSCRIPTION, "--tenant-id", TENANT,
                        ]), 2)
                    self.assertEqual(cli.call_count, 2 if status == 403 else 0)
                    self.assertFalse(target.exists())
                    self.assertNotIn("must-not-leak", output.getvalue())


if __name__ == "__main__":
    unittest.main()
