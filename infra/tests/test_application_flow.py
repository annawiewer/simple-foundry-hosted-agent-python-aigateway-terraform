"""Exercise the real offline application bridge with fake azd processes only."""

import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_environment_adapter import CONTRACT
from test_toolchain import SUBSCRIPTION, TENANT, bootstrap, receipt

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("application_flow", SCRIPTS / "application_flow.py")
flow = importlib.util.module_from_spec(SPEC)
with mock.patch.object(sys, "path", [str(SCRIPTS), *sys.path]):
    SPEC.loader.exec_module(flow)

KEY = "synthetic-gateway-runtime-key"
GITHUB_KEY = "synthetic-unselected-github-key"
AGENT = "fixture-digest"
IMAGE = "registry.azurecr.io/team/digest@sha256:" + "a" * 64
HOST_SHELL = shutil.which("pwsh" if os.name == "nt" else "sh")
RUN_GUARD = subprocess.run


class ApplicationFlowTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "application"
        self.contract_path = self.root / "contract.json"
        self.bootstrap_path = self.root / "bootstrap.json"
        self.receipt_path = self.root / "tool.receipt.jsonl"
        self.bootstrap = bootstrap(connected=True)
        self.contract = copy.deepcopy(CONTRACT)
        self.contract["agents"]["registry_connection_id"] = (
            self.contract["agents"]["project_id"] + "/connections/"
            + self.contract["agents"]["registry_connection_name"]
        )
        self.contract["gateway"].update(
            id=self.bootstrap["gateway_id"], endpoint=self.bootstrap["gateway_endpoint"],
            monitoring={"configuration_status": "configured"},
        )
        self.contract["integration"] = {
            "gateway_model_access_enabled": True, "gateway_tool_access_enabled": True,
            "registry_connection_shared": False,
            "remote_tool_connection_id": self.bootstrap["remote_tool_connection_id"],
            "remote_tool_endpoint": self.bootstrap["remote_tool_endpoint"],
        }
        self.receipt = receipt(connected=True)
        self.receipt["operation"] = "create-toolbox"
        self.receipt["toolbox"] = flow.tools.toolbox_metadata(self.bootstrap, "digest", "7")
        self.process = mock.patch.object(flow.subprocess, "run",
                                         side_effect=AssertionError("Unexpected CLI invocation")).start()
        mock.patch.object(flow.shutil, "which", return_value="azd.exe").start()
        mock.patch.dict(os.environ, {
            "SELECTED_GATEWAY_KEY": KEY, "GITHUB_TOKEN": GITHUB_KEY,
            "AZURE_CLIENT_SECRET": "synthetic-unselected-client-secret",
            "AZURE_AI_GATEWAY_API_KEY": "synthetic-ambient-gateway-key",
            "AZD_DEBUG": "true", flow.SCHEDULE_GATE: "true",
        }).start()

    def call(self, operation, extra=()):
        args = [operation, "--workspace", str(self.workspace), "--subscription-id", SUBSCRIPTION,
                "--tenant-id", TENANT, *extra]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = flow.main(args)
            except SystemExit as error:
                code = error.code
        output = stdout.getvalue() + stderr.getvalue()
        for secret in (KEY, GITHUB_KEY, "synthetic-ambient-gateway-key"):
            self.assertNotIn(secret, output)
        return code, output

    def prepare(self, extra=()):
        self.contract_path.write_text(json.dumps(self.contract), encoding="utf-8")
        self.bootstrap_path.write_text(json.dumps(self.bootstrap), encoding="utf-8")
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")
        return self.call("prepare", [
            "--contract", str(self.contract_path), "--bootstrap", str(self.bootstrap_path),
            "--tool-receipt", str(self.receipt_path), "--repository", "example/repository",
            "--agent-name", AGENT, *extra,
        ])

    def spec(self):
        return json.loads((self.workspace / "prepared.json").read_text(encoding="utf-8"))

    def dotenv(self):
        return self.workspace / ".azure" / "fixture" / ".env"

    def records(self, stage="agent"):
        return [json.loads(line) for line in
                (self.workspace / f"{stage}.receipt.jsonl").read_text(encoding="utf-8").splitlines()]

    def fake_cli(self, command, **kwargs):
        self.assertEqual(kwargs["cwd"], self.workspace.resolve())
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertGreaterEqual(kwargs["stderr"], 0)
        self.assertGreater(kwargs["timeout"], 0)
        environment = kwargs["env"]
        for name in ("SELECTED_GATEWAY_KEY", "GITHUB_TOKEN", "AZURE_CLIENT_SECRET",
                     "AZURE_AI_GATEWAY_API_KEY", "AZD_DEBUG"):
            self.assertNotIn(name, environment)
        if command[1] == "version":
            self.assertNotIn(flow.KEY_VARIABLE, environment)
            return subprocess.CompletedProcess(command, 0, stdout="azd version 1.37.2 (commit fixture)\n")
        if command[1:3] == ["extension", "list"]:
            self.assertNotIn(flow.KEY_VARIABLE, environment)
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps([
                {"id": name, "version": "99.0.0", "installedVersion": version}
                for name, version in flow.EXTENSIONS.items()
            ]))
        self.assertEqual(command[1], "deploy")
        self.assertEqual(command[3:], ["--environment", "fixture", "--no-prompt"])
        self.assertGreaterEqual(kwargs["stdout"], 0)
        if command[2] == AGENT:
            self.assertEqual(environment[flow.AGENT_GATE], "true")
            self.assertEqual(environment[flow.SCHEDULE_GATE], "false")
            self.assertEqual(environment[flow.STAGE_VARIABLE], "agent")
            self.assertEqual(self.records()[-1]["status"], "pending")
            prefix = "AGENT_FIXTURE_DIGEST_"
            values = {
                "NAME": AGENT, "VERSION": "1",
                "ENDPOINT": self.bootstrap["project_endpoint"] + f"/agents/{AGENT}/versions/1",
                "RESPONSES_ENDPOINT": self.bootstrap["project_endpoint"] + "/openai/responses?agent=name&api-version=v1",
            }
            with self.dotenv().open("a", encoding="utf-8") as stream:
                stream.write("ENABLE_HOSTED_AGENTS=true\nENABLE_CAPABILITY_HOST=false\n")
                stream.writelines(f"{prefix}{key}={value if key == 'VERSION' else json.dumps(value)}\n"
                                  for key, value in values.items())
                stream.write('SERVICE_FIXTURE_DIGEST_IMAGE_NAME="registry.azurecr.io/digest@sha256:0123456789"\n')
        else:
            self.assertEqual(command[2], AGENT + "-daily")
            self.assertEqual(environment[flow.AGENT_GATE], "false")
            self.assertEqual(environment[flow.SCHEDULE_GATE], "true")
            self.assertEqual(environment[flow.STAGE_VARIABLE], "schedule")
            self.assertNotIn(flow.KEY_VARIABLE, environment)
            self.assertEqual(self.records("schedule")[-1]["status"], "pending")
        return subprocess.CompletedProcess(command, 0, stdout=KEY, stderr=GITHUB_KEY)

    def launch_agent(self, authentication=("--managed-identity",)):
        self.process.side_effect = self.fake_cli
        return self.call("deploy-agent", ["--confirm-agent-deployment", *authentication])

    def test_prepare_is_offline_and_copies_only_application_build_files(self):
        self.contract["discarded_secret"] = KEY
        self.assertEqual(self.prepare()[0], 0)
        self.process.assert_not_called()
        self.assertEqual({path.name for path in (self.workspace / "app").iterdir()}, set(flow.APP_FILES))
        for name in flow.APP_FILES:
            self.assertEqual((self.workspace / "app" / name).read_bytes(), (flow.SOURCE / name).read_bytes())
        for path in self.workspace.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes())
                self.assertNotIn(GITHUB_KEY.encode(), path.read_bytes())
        spec = self.spec()
        self.assertEqual(spec["environment"]["AZD_AGENT_SKIP_ROLE_ASSIGNMENTS"], "true")
        self.assertEqual(spec["environment"]["USE_EXISTING_AI_PROJECT"], "true")
        self.assertNotIn("AZURE_AI_GATEWAY_API_KEY", spec["environment"])
        self.assertNotIn(flow.KEY_VARIABLE, spec["environment"])
        manifest = json.loads((self.workspace / "azure.yaml").read_text())
        self.assertEqual(set(manifest["services"]), {AGENT, AGENT + "-daily"})
        self.assertNotIn("infra", manifest)
        self.assertEqual(set(manifest["hooks"]), {"preprovision", "predown"})
        agent = manifest["services"][AGENT]
        self.assertNotIn("config", agent)
        self.assertEqual(agent["startupCommand"], "uv run --frozen --no-dev python main.py")
        self.assertNotIn("prebuilt_image", spec)
        self.assertEqual(agent["docker"], {"remoteBuild": True})
        self.assertNotIn("image", agent)
        self.assertNotIn("registryConnectionId", agent)
        self.assertNotIn("uses", agent)
        self.assertNotIn("environmentVariables", agent)
        self.assertEqual(agent["env"]["AZURE_AI_GATEWAY_API_KEY"], "${" + flow.KEY_VARIABLE + "}")
        routine = manifest["services"][AGENT + "-daily"]
        self.assertEqual(routine["condition"], "${" + flow.SCHEDULE_GATE + "}")
        self.assertEqual(routine["action"]["agentName"], AGENT)
        self.assertIn("example/repository", routine["action"]["input"])
        self.assertEqual(set(routine["triggers"]["default"]), {"type", "cronExpression", "timeZone"})

    def test_prebuilt_image_prepares_pinned_passthrough_without_changing_shared_files(self):
        self.contract["agents"]["registry_connection_id"] = (
            self.contract["agents"]["registry_connection_id"].upper()
        )
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE])[0], 0)
        self.process.assert_not_called()
        spec = self.spec()
        self.assertEqual(spec["prebuilt_image"], IMAGE)
        self.assertIs(spec["use_default_acr"], True)
        manifest = json.loads((self.workspace / "azure.yaml").read_text())
        agent = manifest["services"][AGENT]
        self.assertNotIn("config", agent)
        self.assertEqual(agent["startupCommand"], "uv run --frozen --no-dev python main.py")
        self.assertEqual(agent["image"], IMAGE)
        self.assertEqual(agent["docker"], {"imagePassthrough": True})
        self.assertNotIn("registryConnectionId", agent)
        self.assertEqual(spec["environment"]["AZD_AGENT_SKIP_ROLE_ASSIGNMENTS"], "true")
        self.assertEqual(spec["environment"]["USE_EXISTING_AI_PROJECT"], "true")
        self.assertNotIn("image", manifest["services"][AGENT + "-daily"])
        self.assertNotIn(IMAGE, self.dotenv().read_text())
        self.assertEqual({path.name for path in (self.workspace / "app").iterdir()}, set(flow.APP_FILES))
        for name in flow.APP_FILES:
            self.assertEqual((self.workspace / "app" / name).read_bytes(), (flow.SOURCE / name).read_bytes())

    def test_prebuilt_image_uses_declared_registry_host_not_inferred_arm_name(self):
        self.contract["agents"]["registry_endpoint"] = "registry-a1b2c3d4.azurecr.io"
        self.assertNotEqual(self.prepare(["--prebuilt-image", IMAGE])[0], 0)
        self.assertFalse(self.workspace.exists())
        image = IMAGE.replace("registry.azurecr.io", "registry-a1b2c3d4.azurecr.io")
        self.assertEqual(self.prepare(["--prebuilt-image", image])[0], 0)
        self.process.assert_not_called()

    def test_default_acr_omits_only_the_registry_reference_and_deploys_once(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE, "--use-default-acr"])[0], 0)
        self.process.assert_not_called()
        spec = self.spec()
        self.assertIs(spec["use_default_acr"], True)
        expected = flow.manifest(AGENT, "example/repository", IMAGE,
                                 spec["environment"]["AZURE_AI_PROJECT_ACR_CONNECTION_NAME"])
        del expected["services"][AGENT]["registryConnectionId"]
        self.assertEqual(json.loads((self.workspace / "azure.yaml").read_text()), expected)
        self.assertEqual(self.launch_agent()[0], 0)
        self.assertEqual(self.records()[-1]["prepared_sha256"], flow.fingerprint(spec))
        self.assertNotEqual(self.launch_agent()[0], 0)
        self.assertEqual(self.process.call_count, 3)
        self.assertFalse((self.workspace / "schedule.receipt.jsonl").exists())

    def test_default_acr_requires_a_prebuilt_image_before_side_effects(self):
        self.assertNotEqual(self.prepare(["--use-default-acr"])[0], 0)
        self.assertFalse(self.workspace.exists())
        self.process.assert_not_called()

    def test_legacy_named_registry_snapshot_remains_unchanged_during_deploy(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE])[0], 0)
        spec = self.spec()
        spec.pop("use_default_acr", None)
        manifest_path = self.workspace / "azure.yaml"
        document = json.loads(manifest_path.read_text())
        document["services"][AGENT]["registryConnectionId"] = (
            spec["environment"]["AZURE_AI_PROJECT_ACR_CONNECTION_NAME"]
        )
        manifest_path.write_text(json.dumps(document), encoding="utf-8")
        spec["files"] = flow.fixed_hashes(self.workspace)
        spec_path = self.workspace / "prepared.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        before = (manifest_path.read_bytes(), spec_path.read_bytes())
        self.assertEqual(self.launch_agent()[0], 0)
        self.assertEqual((manifest_path.read_bytes(), spec_path.read_bytes()), before)
        self.assertEqual(self.records()[-1]["prepared_sha256"], flow.fingerprint(spec))

    def test_default_acr_preserves_registry_ownership_and_image_checks(self):
        original = self.contract["agents"]["registry_connection_id"]
        for connection in (None, original + "-other", original.replace("/projects/", "/other/")):
            with self.subTest(connection=connection):
                self.contract["agents"]["registry_connection_id"] = connection
                self.assertNotEqual(self.prepare(["--prebuilt-image", IMAGE, "--use-default-acr"])[0], 0)
                self.assertFalse(self.workspace.exists())
        self.contract["agents"]["registry_connection_id"] = original
        image = IMAGE.replace("registry.azurecr.io", "other.azurecr.io")
        self.assertNotEqual(self.prepare(["--prebuilt-image", image, "--use-default-acr"])[0], 0)
        self.assertFalse(self.workspace.exists())
        self.process.assert_not_called()

    def test_default_acr_rejects_saved_mode_drift_before_cli(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE, "--use-default-acr"])[0], 0)
        spec_path = self.workspace / "prepared.json"
        original = self.spec()
        for value in (None, False, 1, "true", "default"):
            with self.subTest(value=value):
                spec = copy.deepcopy(original)
                spec["use_default_acr"] = value
                spec_path.write_text(json.dumps(spec), encoding="utf-8")
                self.assertNotEqual(self.launch_agent()[0], 0)
        for field in ("prebuilt_image", "use_default_acr"):
            spec = copy.deepcopy(original)
            del spec[field]
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            self.assertNotEqual(self.launch_agent()[0], 0)
        self.process.assert_not_called()
        self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())

    def test_default_acr_rejects_reintroduced_reference_even_with_updated_file_hash(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE, "--use-default-acr"])[0], 0)
        manifest_path = self.workspace / "azure.yaml"
        document = json.loads(manifest_path.read_text())
        document["services"][AGENT]["registryConnectionId"] = (
            self.contract["agents"]["registry_connection_name"]
        )
        manifest_path.write_text(json.dumps(document), encoding="utf-8")
        spec = self.spec()
        spec["files"] = flow.fixed_hashes(self.workspace)
        (self.workspace / "prepared.json").write_text(json.dumps(spec), encoding="utf-8")
        self.assertNotEqual(self.launch_agent()[0], 0)
        self.process.assert_not_called()
        self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())

    def test_prebuilt_registry_arm_id_is_rejected_even_with_updated_file_hash(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE])[0], 0)
        manifest_path = self.workspace / "azure.yaml"
        manifest = json.loads(manifest_path.read_text())
        manifest["services"][AGENT]["registryConnectionId"] = self.contract["agents"]["registry_connection_id"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        spec = self.spec()
        spec["files"] = flow.fixed_hashes(self.workspace)
        (self.workspace / "prepared.json").write_text(json.dumps(spec), encoding="utf-8")
        self.assertNotEqual(self.launch_agent()[0], 0)
        self.process.assert_not_called()
        self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())

    def test_prebuilt_image_rejects_unsafe_foreign_and_mutable_references_before_side_effects(self):
        for image in (
            "", "registry.azurecr.io/team/digest:latest",
            IMAGE.replace("registry.azurecr.io", "other.azurecr.io"),
            IMAGE.replace("registry.azurecr.io", "registry.azurecr.io.evil.invalid"),
            IMAGE.replace("registry.azurecr.io", "registry.azurecr.io:443"),
            "https://" + IMAGE, "//" + IMAGE, KEY + "@" + IMAGE,
            IMAGE.replace("/team/", "//team/"), IMAGE.replace("/team/", "/../"),
            IMAGE.replace("/team/", "/Team/"), IMAGE.replace("/team/", "/%74eam/"),
            IMAGE.replace("@sha256:", ":latest@sha256:"),
            IMAGE.replace("@sha256:", "@sha512:"), IMAGE[:-1], IMAGE + "a",
            IMAGE + "?key=" + KEY, IMAGE + "#fragment", " " + IMAGE, IMAGE + "\n",
        ):
            with self.subTest(image=image):
                code, output = self.prepare(["--prebuilt-image", image])
                self.assertNotEqual(code, 0)
                if image:
                    self.assertNotIn(image, output)
                self.assertFalse(self.workspace.exists())
        self.process.assert_not_called()

    def test_prebuilt_image_deploy_preserves_key_isolation_and_single_agent_receipt(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE])[0], 0)
        self.assertEqual(self.launch_agent(("--gateway-key-env", "SELECTED_GATEWAY_KEY"))[0], 0)
        self.assertEqual(self.process.call_count, 3)
        self.assertEqual(self.records()[-1]["prepared_sha256"], flow.fingerprint(self.spec()))
        self.assertEqual(self.records()[-1]["authentication"], "api-key")
        self.assertFalse((self.workspace / "schedule.receipt.jsonl").exists())
        for path in self.workspace.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes())
        self.assertNotEqual(self.launch_agent()[0], 0)
        self.assertEqual(self.process.call_count, 3)

    def test_prebuilt_image_drift_and_invalid_saved_selection_stop_before_cli(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE])[0], 0)
        spec_path = self.workspace / "prepared.json"
        manifest_path = self.workspace / "azure.yaml"
        spec_bytes, manifest_bytes = spec_path.read_bytes(), manifest_path.read_bytes()
        for image in (None, False, "", IMAGE.replace("a" * 64, "b" * 64),
                      IMAGE.replace("registry.azurecr.io", "other.azurecr.io")):
            with self.subTest(image=image):
                spec = json.loads(spec_bytes)
                spec["prebuilt_image"] = image
                spec_path.write_text(json.dumps(spec), encoding="utf-8")
                self.assertNotEqual(self.launch_agent()[0], 0)
        spec_path.write_bytes(spec_bytes)
        manifest = json.loads(manifest_bytes)
        manifest["services"][AGENT]["image"] = IMAGE.replace("a" * 64, "b" * 64)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        spec = json.loads(spec_bytes)
        spec["files"] = flow.fixed_hashes(self.workspace)
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        self.assertNotEqual(self.launch_agent()[0], 0)
        self.process.assert_not_called()
        self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())

    def test_prebuilt_image_change_during_tooling_stops_before_deployment_intent(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE])[0], 0)
        def fake(command, **kwargs):
            result = self.fake_cli(command, **kwargs)
            if command[1:3] == ["extension", "list"]:
                spec = self.spec()
                spec["prebuilt_image"] = IMAGE.replace("a" * 64, "b" * 64)
                manifest_path = self.workspace / "azure.yaml"
                manifest = json.loads(manifest_path.read_text())
                manifest["services"][AGENT]["image"] = spec["prebuilt_image"]
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                spec["files"] = flow.fixed_hashes(self.workspace)
                (self.workspace / "prepared.json").write_text(json.dumps(spec), encoding="utf-8")
            return result
        self.process.side_effect = fake
        self.assertNotEqual(self.call("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"])[0], 0)
        self.assertEqual(self.process.call_count, 2)
        self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())

    def test_prebuilt_image_cannot_be_selected_or_changed_at_deploy_or_schedule(self):
        self.assertEqual(self.prepare(["--prebuilt-image", IMAGE])[0], 0)
        for operation, extra in (
            ("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"]),
            ("enable-schedule", ["--confirm-enable-schedule"]),
        ):
            self.assertNotEqual(self.call(operation, [*extra, "--prebuilt-image", IMAGE])[0], 0)
        self.process.assert_not_called()

    def test_prepare_accepts_nonsensitive_contract_envelope(self):
        self.contract = {"deployment_contract": {"sensitive": False, "value": self.contract},
                         "unrelated_secret": {"sensitive": True, "value": KEY}}
        self.assertEqual(self.prepare()[0], 0)
        self.assertNotIn(KEY, (self.workspace / "prepared.json").read_text())

    def test_prepare_preserves_a_legacy_toolbox_receipt(self):
        legacy = receipt(connected=True, version=1)
        legacy.update(operation="create-toolbox", toolbox=copy.deepcopy(self.receipt["toolbox"]))
        self.receipt = legacy
        self.assertEqual(self.prepare()[0], 0)
        self.process.assert_not_called()
        self.assertEqual(self.receipt_path.read_text(encoding="utf-8"), json.dumps(legacy) + "\n")

    def test_prepare_accepts_toolbox_receipt_with_explicit_upgrade_provenance(self):
        self.receipt["upgraded_from_sha256"] = "a" * 64
        self.assertEqual(self.prepare()[0], 0)
        self.process.assert_not_called()
        self.assertEqual(json.loads(self.receipt_path.read_text()), self.receipt)

    def test_prepare_accepts_shared_registry_and_case_insensitive_arm_id(self):
        self.contract["integration"]["registry_connection_shared"] = True
        self.contract["agents"]["registry_connection_id"] = (
            self.contract["agents"]["registry_connection_id"].upper()
        )
        self.assertEqual(self.prepare()[0], 0)
        self.process.assert_not_called()

    def test_prepare_requires_owned_registry_connection_for_either_sharing_choice(self):
        agents = self.contract["agents"]
        connection_id = agents.pop("registry_connection_id")
        self.assertNotEqual(self.prepare()[0], 0)
        self.assertFalse(self.workspace.exists())
        for shared in (False, True):
            self.contract["integration"]["registry_connection_shared"] = shared
            for value in (
                None, True, 1, "",
                connection_id.replace("/projects/project/", "/projects/other/"),
                connection_id.replace("/projects/project", ""),
                connection_id.replace("/resourceGroups/agents/", "/resourceGroups/other/"),
                connection_id.replace(SUBSCRIPTION, TENANT),
                connection_id + "-other",
                connection_id + "/child",
                connection_id + "?key=synthetic",
            ):
                with self.subTest(shared=shared, connection_id=value):
                    agents["registry_connection_id"] = value
                    code, output = self.prepare()
                    self.assertNotEqual(code, 0)
                    self.assertIn("registry connection ID", output)
                    self.assertFalse(self.workspace.exists())
        self.process.assert_not_called()

    @unittest.skipUnless(HOST_SHELL, "The host-native shell is not installed.")
    def test_generated_hooks_enforce_operation_and_infrastructure_boundaries(self):
        platform = "windows" if os.name == "nt" else "posix"
        checks = [(flow.guard(), None, False), (flow.guard("agent"), None, False),
                  (flow.guard("agent"), "agent", True), (flow.guard("agent"), "schedule", False),
                  (flow.guard("schedule"), None, False), (flow.guard("schedule"), "agent", False),
                  (flow.guard("schedule"), "schedule", True)]
        for hook, stage, allowed in checks:
            with self.subTest(stage=stage, allowed=allowed, hook=hook[platform]["run"]):
                environment = flow.child_environment()
                if stage is not None:
                    environment[flow.STAGE_VARIABLE] = stage
                command = [HOST_SHELL]
                if os.name == "nt":
                    command += ["-NoProfile", "-NonInteractive", "-Command"]
                else:
                    command += ["-c"]
                result = RUN_GUARD(
                    [*command, hook[platform]["run"]], env=environment, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False,
                )
                self.assertEqual(result.returncode == 0, allowed)
        self.process.assert_not_called()

    def test_prepare_forwards_custom_alias_selection(self):
        aliases = self.contract["models"]["aliases"]
        aliases["custom-primary"] = aliases.pop("primary-router")
        aliases["custom-mini"] = aliases.pop("mini-router")
        aliases["custom-primary"]["alias_name"] = "custom-primary-route"
        aliases["custom-mini"]["alias_name"] = "custom-mini-route"
        self.assertEqual(self.prepare([
            "--model-alias-key", "custom-primary", "--mini-model-alias-key", "custom-mini",
        ])[0], 0)
        values = self.spec()["environment"]
        self.assertEqual(values["AZURE_AI_GATEWAY_MODEL"], "custom-primary-route")
        self.assertEqual(values["AZURE_AI_GATEWAY_MINI_MODEL"], "custom-mini-route")

    def test_prepare_rejects_mismatched_repository_context_and_connection(self):
        for target, key, value in (
            ("contract", "subscription_id", TENANT),
            ("bootstrap", "project_endpoint", "https://other.services.ai.azure.com/api/projects/project"),
            ("bootstrap", "remote_tool_connection_id", None),
            ("integration", "remote_tool_endpoint", "https://gateway.example.invalid/other/mcp"),
            ("integration", "registry_connection_shared", "false"),
            ("integration", "registry_connection_shared", 0),
            ("integration", "registry_connection_shared", 1),
            ("integration", "registry_connection_shared", None),
            ("integration", "gateway_tool_access_enabled", False),
            ("configuration", "repository", "other/repository"),
        ):
            with self.subTest(target=target, key=key):
                source = {"contract": self.contract, "bootstrap": self.bootstrap,
                          "integration": self.contract["integration"],
                          "configuration": self.receipt["configuration"]}[target]
                previous = source[key]
                source[key] = value
                self.assertNotEqual(self.prepare()[0], 0)
                self.assertFalse(self.workspace.exists())
                source[key] = previous
        self.process.assert_not_called()

    def test_prepare_rejects_unconfirmed_unversioned_or_wrong_toolbox(self):
        for change in (
            {"status": "unconfirmed"}, {"toolbox": {"name": "digest"}},
            {"toolbox": {**self.receipt["toolbox"], "endpoint": "https://other.example.invalid/mcp"}},
            {"toolserver": {**self.receipt["toolserver"], "endpoint": "https://gateway.example.invalid/other/mcp"}},
        ):
            with self.subTest(change=tuple(change)):
                previous = copy.deepcopy(self.receipt)
                self.receipt.update(change)
                self.assertNotEqual(self.prepare()[0], 0)
                self.assertFalse(self.workspace.exists())
                self.receipt = previous

    def test_prepare_stops_on_pending_telemetry_and_interpolated_values(self):
        self.contract["gateway"]["monitoring"]["configuration_status"] = "pending"
        self.assertNotEqual(self.prepare()[0], 0)
        self.contract["gateway"]["monitoring"]["configuration_status"] = "configured"
        self.contract["location"] = "${SELECTED_GATEWAY_KEY}"
        self.assertNotEqual(self.prepare()[0], 0)
        self.assertFalse(self.workspace.exists())

    def test_prepare_never_overwrites_or_creates_build_context_inside_repository(self):
        self.assertEqual(self.prepare()[0], 0)
        before = (self.workspace / "prepared.json").read_bytes()
        self.assertNotEqual(self.prepare()[0], 0)
        self.assertEqual(before, (self.workspace / "prepared.json").read_bytes())
        self.workspace = flow.SOURCE / "must-not-create-application-flow-test"
        self.assertNotEqual(self.prepare()[0], 0)
        self.assertFalse(self.workspace.exists())

    def test_explicit_confirmation_and_authentication_are_required_before_cli(self):
        self.assertEqual(self.prepare()[0], 0)
        for extra in ([], ["--managed-identity"], ["--confirm-agent-deployment"],
                      ["--confirm-agent-deployment", "--managed-identity", "--gateway-key-env", "SELECTED_GATEWAY_KEY"],
                      ["--confirm-agent-deployment", "--managed-identity", "--tenant-id", SUBSCRIPTION],
                      ["--confirm-agent-deployment", "--managed-identity", "--subscription-id", TENANT]):
            with self.subTest(extra=extra):
                self.assertNotEqual(self.call("deploy-agent", extra)[0], 0)
        self.process.assert_not_called()
        self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())

    def test_managed_identity_needs_model_grant(self):
        self.contract["integration"]["gateway_model_access_enabled"] = False
        self.assertEqual(self.prepare()[0], 0)
        self.assertNotEqual(self.launch_agent()[0], 0)
        self.process.assert_not_called()

    def test_managed_identity_deploys_only_agent_without_ambient_credentials(self):
        self.assertEqual(self.prepare()[0], 0)
        self.assertEqual(self.launch_agent()[0], 0)
        self.assertEqual(len(self.process.call_args_list), 3)
        self.assertEqual(self.process.call_args.kwargs["env"][flow.KEY_VARIABLE], "")
        self.assertEqual([record["status"] for record in self.records()], ["pending", "cli-completed"])
        self.assertFalse((self.workspace / "schedule.receipt.jsonl").exists())

    def test_process_user_agent_reaches_azd_without_being_persisted(self):
        marker = "synthetic-local-client"
        with mock.patch.dict(os.environ, {"AZURE_DEV_USER_AGENT": marker}):
            self.assertEqual(self.prepare()[0], 0)
            self.assertEqual(self.launch_agent()[0], 0)
        for call in self.process.call_args_list:
            self.assertEqual(call.kwargs["env"].get("AZURE_DEV_USER_AGENT"), marker)
        for path in self.workspace.rglob("*"):
            if path.is_file():
                self.assertNotIn(marker.encode(), path.read_bytes())

    def test_selected_key_reaches_only_agent_process_not_files_or_inspections(self):
        self.assertEqual(self.prepare()[0], 0)
        self.assertEqual(self.launch_agent(("--gateway-key-env", "SELECTED_GATEWAY_KEY"))[0], 0)
        self.assertEqual(self.process.call_args.kwargs["env"][flow.KEY_VARIABLE], KEY)
        self.assertEqual(self.records()[-1]["authentication"], "api-key")
        for path in self.workspace.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes())

    def test_unreviewed_hosted_outputs_leave_receipt_unconfirmed_without_retry(self):
        cases = (
            ("ENABLE_HOSTED_AGENTS", "false"),
            ("ENABLE_HOSTED_AGENTS", "TRUE"),
            ("ENABLE_CAPABILITY_HOST", "true"),
            ("ENABLE_CAPABILITY_HOST", "0"),
            ("ENABLE_OTHER_FEATURE", "true"),
            ("AI_PROJECT_DEPLOYMENTS", "unreviewed"),
        )
        for index, (key, value) in enumerate(cases):
            with self.subTest(key=key, value=value):
                self.workspace = self.root / f"case-{index}"
                self.assertEqual(self.prepare()[0], 0)
                self.process.reset_mock()
                def fake(command, **kwargs):
                    result = self.fake_cli(command, **kwargs)
                    if command[1] == "deploy":
                        lines = [line for line in self.dotenv().read_text().splitlines()
                                 if not line.startswith(key + "=")]
                        self.dotenv().write_text(
                            "\n".join([*lines, f"{key}={json.dumps(value)}"]) + "\n", encoding="utf-8")
                    return result
                self.process.side_effect = fake
                args = ["--confirm-agent-deployment", "--managed-identity"]
                self.assertNotEqual(self.call("deploy-agent", args)[0], 0)
                self.assertEqual([record["status"] for record in self.records()], ["pending", "unconfirmed"])
                self.assertNotEqual(self.call("deploy-agent", args)[0], 0)
                self.assertNotEqual(self.call("enable-schedule", ["--confirm-enable-schedule"])[0], 0)
                self.assertEqual(self.process.call_count, 3)
                self.assertFalse((self.workspace / "schedule.receipt.jsonl").exists())

    def test_reviewed_hosted_outputs_do_not_upgrade_an_unconfirmed_receipt(self):
        self.assertEqual(self.prepare()[0], 0)
        self.assertEqual(self.launch_agent()[0], 0)
        records = self.records()
        records[-1] = {key: value for key, value in records[-1].items() if key not in {"agent", "azd_state"}}
        records[-1]["status"] = "unconfirmed"
        path = self.workspace / "agent.receipt.jsonl"
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        before = path.read_bytes()
        self.process.reset_mock()
        self.assertNotEqual(self.call("enable-schedule", ["--confirm-enable-schedule"])[0], 0)
        self.process.assert_not_called()
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.workspace / "schedule.receipt.jsonl").exists())

    def test_rejects_missing_key_literal_and_tool_credential_selection(self):
        self.assertEqual(self.prepare()[0], 0)
        for selected in ("ABSENT_GATEWAY_KEY", KEY, "GITHUB_TOKEN", "PATH", flow.KEY_VARIABLE):
            with self.subTest(selected=selected):
                self.assertNotEqual(self.launch_agent(("--gateway-key-env", selected))[0], 0)
        self.process.assert_not_called()

    def test_old_prerelease_and_unreviewed_cli_versions_stop_before_intent(self):
        self.assertEqual(self.prepare()[0], 0)
        for version in ("1.35.1", "1.37.0-beta.1", "1.38.0"):
            with self.subTest(version=version):
                self.process.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(
                    command, 0, stdout=f"azd version {version} (commit fixture)")
                self.assertNotEqual(self.call("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"])[0], 0)
                self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())
        self.assertEqual(self.process.call_count, 3)

    def test_catalog_version_cannot_substitute_for_installed_dependency(self):
        self.assertEqual(self.prepare()[0], 0)
        for installed in (None, "1.0.0-beta.18", "1.0.1"):
            with self.subTest(installed=installed):
                def fake(command, **kwargs):
                    if command[1] == "version":
                        return self.fake_cli(command, **kwargs)
                    inventory = [{"id": name, "version": "1.0.0", "installedVersion": version}
                                 for name, version in flow.EXTENSIONS.items()]
                    inventory[0]["installedVersion"] = installed
                    return subprocess.CompletedProcess(command, 0, stdout=json.dumps(inventory))
                self.process.side_effect = fake
                self.assertNotEqual(self.call("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"])[0], 0)
                self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())

    def test_missing_azd_is_not_installed_automatically(self):
        self.assertEqual(self.prepare()[0], 0)
        with mock.patch.object(flow.shutil, "which", return_value=None):
            self.assertNotEqual(self.launch_agent()[0], 0)
        self.process.assert_not_called()

    def test_modified_build_file_manifest_or_extra_file_stops_before_cli(self):
        self.assertEqual(self.prepare()[0], 0)
        for path in (self.workspace / "app" / "main.py", self.workspace / "azure.yaml",
                     self.workspace / "app" / ".env"):
            with self.subTest(path=path.name):
                before = path.read_bytes() if path.exists() else None
                path.write_bytes(b"synthetic-drift")
                self.assertNotEqual(self.launch_agent()[0], 0)
                if before is None:
                    path.unlink()
                else:
                    path.write_bytes(before)
        infrastructure = self.workspace / "infra"
        infrastructure.mkdir()
        (infrastructure / "main.hooks.yaml").write_text(
            "predeploy:\n  shell: sh\n  run: echo should-not-run\n", encoding="utf-8")
        self.assertNotEqual(self.launch_agent()[0], 0)
        self.process.assert_not_called()

    def test_drift_during_tooling_inspection_stops_before_deployment_intent(self):
        self.assertEqual(self.prepare()[0], 0)
        def fake(command, **kwargs):
            result = self.fake_cli(command, **kwargs)
            if command[1:3] == ["extension", "list"]:
                (self.workspace / "app" / "main.py").write_text("synthetic drift", encoding="utf-8")
            return result
        self.process.side_effect = fake
        self.assertNotEqual(self.call("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"])[0], 0)
        self.assertEqual(self.process.call_count, 2)
        self.assertFalse((self.workspace / "agent.receipt.jsonl").exists())

    def test_linked_application_file_is_rejected(self):
        self.assertEqual(self.prepare()[0], 0)
        original = flow.linked
        with mock.patch.object(flow, "linked", side_effect=lambda path: path.name == "main.py" or original(path)):
            self.assertNotEqual(self.launch_agent()[0], 0)
        self.process.assert_not_called()

    def test_modified_initial_dotenv_or_config_stops_before_cli(self):
        self.assertEqual(self.prepare()[0], 0)
        for path in (self.dotenv(), self.dotenv().with_name("config.json")):
            before = path.read_bytes()
            path.write_bytes(before + b" ")
            self.assertNotEqual(self.launch_agent()[0], 0)
            path.write_bytes(before)
        self.process.assert_not_called()

    def test_schedule_requires_confirmation_and_successful_agent_receipt(self):
        self.assertEqual(self.prepare()[0], 0)
        self.assertNotEqual(self.call("enable-schedule")[0], 0)
        self.assertNotEqual(self.call("enable-schedule", ["--confirm-enable-schedule"])[0], 0)
        self.process.assert_not_called()
        self.assertFalse((self.workspace / "schedule.receipt.jsonl").exists())

    def test_schedule_is_separate_and_never_redeploys_agent_or_receives_key(self):
        self.assertEqual(self.prepare()[0], 0)
        self.assertEqual(self.launch_agent(("--gateway-key-env", "SELECTED_GATEWAY_KEY"))[0], 0)
        self.assertEqual(self.call("enable-schedule", ["--confirm-enable-schedule"])[0], 0)
        deployments = [call.args[0][2] for call in self.process.call_args_list if call.args[0][1] == "deploy"]
        self.assertEqual(deployments, [AGENT, AGENT + "-daily"])
        self.assertEqual(self.records("schedule")[-1]["status"], "cli-completed")
        self.process.reset_mock()
        self.assertNotEqual(self.launch_agent()[0], 0)
        self.assertNotEqual(self.call("enable-schedule", ["--confirm-enable-schedule"])[0], 0)
        self.process.assert_not_called()

    def test_schedule_rejects_changed_agent_environment_or_receipt(self):
        self.assertEqual(self.prepare()[0], 0)
        self.assertEqual(self.launch_agent()[0], 0)
        self.process.reset_mock()
        receipt_path = self.workspace / "agent.receipt.jsonl"
        for path in (self.dotenv(), self.dotenv().with_name("config.json"), receipt_path):
            with self.subTest(path=path.name):
                before = path.read_bytes()
                path.write_bytes(before.rstrip(b"\n") + b" ")
                self.assertNotEqual(self.call("enable-schedule", ["--confirm-enable-schedule"])[0], 0)
                path.write_bytes(before)
        self.process.assert_not_called()

    def test_wrong_receipt_binding_cannot_authorize_schedule(self):
        self.assertEqual(self.prepare()[0], 0)
        self.assertEqual(self.launch_agent()[0], 0)
        records = self.records()
        for record in records:
            record["prepared_sha256"] = "0" * 64
        (self.workspace / "agent.receipt.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        self.process.reset_mock()
        self.assertNotEqual(self.call("enable-schedule", ["--confirm-enable-schedule"])[0], 0)
        self.process.assert_not_called()

    def test_failure_retains_uncertain_intent_and_never_retries_or_enables_schedule(self):
        self.assertEqual(self.prepare()[0], 0)
        def fake(command, **kwargs):
            if command[1] == "deploy":
                os.write(kwargs["stdout"], f"ERROR: unsupported nested config block {KEY}\n".encode())
                os.write(kwargs["stderr"], GITHUB_KEY.encode())
                return subprocess.CompletedProcess(command, 1, stdout=KEY, stderr=GITHUB_KEY)
            return self.fake_cli(command, **kwargs)
        self.process.side_effect = fake
        args = ["--confirm-agent-deployment", "--gateway-key-env", "SELECTED_GATEWAY_KEY"]
        code, output = self.call("deploy-agent", args)
        self.assertNotEqual(code, 0)
        self.assertIn("stdout: unsupported service configuration", output)
        self.assertEqual([record["status"] for record in self.records()], ["pending", "unconfirmed"])
        self.assertNotIn(KEY, (self.workspace / "agent.receipt.jsonl").read_text())
        self.assertEqual(self.process.call_count, 3)
        self.assertNotEqual(self.call("deploy-agent", args)[0], 0)
        self.assertNotEqual(self.call("enable-schedule", ["--confirm-enable-schedule"])[0], 0)
        self.assertEqual(self.process.call_count, 3)

    def test_timeout_diagnoses_both_streams_and_receipt_stays_unconfirmed(self):
        self.assertEqual(self.prepare()[0], 0)
        def fake(command, **kwargs):
            if command[1] == "deploy":
                os.write(kwargs["stdout"], f"ERROR: failed to create agent version {KEY}\n".encode())
                os.write(kwargs["stderr"], f"TLS handshake timed out {GITHUB_KEY}\n".encode())
                raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=KEY, stderr=GITHUB_KEY)
            return self.fake_cli(command, **kwargs)
        self.process.side_effect = fake
        code, output = self.call("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"])
        self.assertNotEqual(code, 0)
        self.assertIn("azd timed out", output)
        self.assertIn("stdout: agent creation or deployment failed", output)
        self.assertIn("stderr: network, DNS or TLS failure", output)
        self.assertEqual(self.records()[-1]["status"], "unconfirmed")
        self.assertNotEqual(self.call("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"])[0], 0)
        self.assertEqual(self.process.call_count, 3)

    def test_success_without_matching_registered_agent_is_not_completion(self):
        self.assertEqual(self.prepare()[0], 0)
        def fake(command, **kwargs):
            if command[1] == "deploy":
                return subprocess.CompletedProcess(command, 0)
            return self.fake_cli(command, **kwargs)
        self.process.side_effect = fake
        self.assertNotEqual(self.call("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"])[0], 0)
        self.assertEqual(self.records()[-1]["status"], "unconfirmed")

    def test_unexpected_key_persistence_stops_completion_without_printing_it(self):
        self.assertEqual(self.prepare()[0], 0)
        def fake(command, **kwargs):
            result = self.fake_cli(command, **kwargs)
            if command[1] == "deploy":
                with self.dotenv().open("a", encoding="utf-8") as stream:
                    stream.write(f"AZURE_AI_GATEWAY_API_KEY={json.dumps(KEY)}\n")
            return result
        self.process.side_effect = fake
        self.assertNotEqual(self.call("deploy-agent", [
            "--confirm-agent-deployment", "--gateway-key-env", "SELECTED_GATEWAY_KEY",
        ])[0], 0)
        self.assertEqual(self.records()[-1]["status"], "unconfirmed")
        self.assertNotIn(KEY, (self.workspace / "agent.receipt.jsonl").read_text())

    def test_receipt_must_be_durable_before_deployment_process_starts(self):
        self.assertEqual(self.prepare()[0], 0)
        self.process.side_effect = self.fake_cli
        with mock.patch.object(flow.tools.os, "fsync", side_effect=OSError("synthetic disk failure")):
            self.assertNotEqual(self.call("deploy-agent", ["--confirm-agent-deployment", "--managed-identity"])[0], 0)
        self.assertEqual(self.process.call_count, 2)


class FailureDiagnosticsTests(unittest.TestCase):
    def invoke(self, fake, *, capture=False, environment=None):
        with mock.patch.object(flow.subprocess, "run", side_effect=fake) as process:
            with self.assertRaises(flow.FlowError) as raised:
                flow.invoke("azd.exe", ["deploy", AGENT], Path.cwd(), environment or {},
                            flow.time.monotonic() + 10, capture=capture)
            process.assert_called_once()
        return str(raised.exception)

    def test_nonzero_stdout_only_and_stderr_only_have_actionable_diagnostics(self):
        for stream, payload, expected in (
            ("stdout", b'ERROR: service "private-name" uses the unsupported nested config block\n',
             "stdout: unsupported service configuration"),
            ("stderr", b"HTTP 403: Forbidden\nprivate opaque response text\n",
             "stderr: HTTP 403; authorization denied"),
            ("stderr", b'{"error":{"code":"not_a_registry_connection","message":"private connection"}}\n',
             "stderr: registry connection invalid or missing"),
        ):
            with self.subTest(stream=stream):
                def fake(command, **kwargs):
                    os.write(kwargs[stream], payload)
                    return subprocess.CompletedProcess(command, 1)
                output = self.invoke(fake)
                self.assertIn(expected, output)
                self.assertIn("exited with code 1", output)
                self.assertNotIn("private", output)

    def test_secret_values_are_removed_before_classifying_raw_and_encoded_forms(self):
        secret = "AuthorizationFailed/Forbidden+synthetic="
        for value in (secret, flow.quote(secret, safe="")):
            with self.subTest(encoded=value != secret):
                output = flow.failure_detail(value.encode(), {flow.KEY_VARIABLE: secret})
                self.assertEqual(output, "unrecognized diagnostic; details withheld")
                self.assertNotIn(secret, output)

    def test_auth_headers_tokens_keys_connection_strings_and_arbitrary_text_are_withheld(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzeW50aGV0aWMifQ.c3ludGhldGljc2lnbmF0dXJl"
        github = "ghp_" + "A" * 36
        pat = "github_pat_" + "B" * 82
        key = "c3ludGhldGljLWtleS1ub3QtYS1yZWFsLWNyZWRlbnRpYWw="
        values = (
            f"Authorization: Bearer {jwt}", f'{{"Authorization": "Bearer {jwt}"}}',
            f"Proxy-Authorization: Basic {key}", f"X-Api-Key: {key}",
            f'access_token="{jwt}"', f"refresh_token={key}", f"client_secret={key}",
            f"password={key}", f"Cookie: session={key}", f"Set-Cookie: session={key}",
            f"DefaultEndpointsProtocol=https;AccountName=fixture;AccountKey={key};EndpointSuffix=core.windows.net",
            f"Endpoint=sb://fixture.invalid/;SharedAccessKeyName=Root;SharedAccessKey={key}",
            "InstrumentationKey=11111111-2222-3333-4444-555555555555;IngestionEndpoint=https://fixture.invalid/",
            f"https://user:{key}@fixture.invalid/?sv=2026-01-01&sig={key}",
            f"connection_string=Server=fixture;Password={key};", github, pat, jwt, "sk-" + "C" * 40,
            "unrecognised-private-detail short-secret-value",
        )
        for value in values:
            with self.subTest(form=value.split("=", 1)[0].split(":", 1)[0][:24]):
                output = flow.failure_detail(
                    ("ERROR: unsupported nested config block\n" + value).encode(), {},
                )
                self.assertEqual(output, "unsupported service configuration")
                for private in (key, github, pat, jwt, "private-detail", "short-secret-value"):
                    self.assertNotIn(private, output)

    def test_large_streams_are_drained_and_only_bounded_tail_diagnostics_escape(self):
        def fake(command, **kwargs):
            for stream in ("stdout", "stderr"):
                for _ in range(32):
                    os.write(kwargs[stream], b"private-unstructured-output " * 256)
                os.write(kwargs[stream], b"\nERROR: RESPONSE 429 TooManyRequests\n")
            return subprocess.CompletedProcess(command, 1)
        output = self.invoke(fake)
        self.assertIn("stdout: HTTP 429; quota, capacity or throttling failure", output)
        self.assertIn("stderr: HTTP 429; quota, capacity or throttling failure", output)
        self.assertNotIn("private", output)
        self.assertLessEqual(len(output), flow.DIAGNOSTIC_LIMIT + 50)
        with flow.diagnostic_pipe() as (writer, data, complete):
            os.write(writer, b"x" * (flow.DIAGNOSTIC_BYTES * 3))
        self.assertTrue(complete.is_set())
        self.assertEqual(len(data), flow.DIAGNOSTIC_BYTES)

    def test_local_python_child_failure_and_timeout_capture_both_streams(self):
        source = (
            "import sys,time;"
            "print('RESPONSE 403 Forbidden',flush=True);"
            "print('failed to create agent version',file=sys.stderr,flush=True);"
        )
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                command = ["-E", "-s", "-B", "-c", source + ("time.sleep(30)" if timeout else "sys.exit(1)")]
                with self.assertRaises(flow.FlowError) as raised:
                    flow.invoke(sys.executable, command, Path.cwd(), flow.child_environment(),
                                flow.time.monotonic() + (2 if timeout else 10))
                output = str(raised.exception)
                self.assertIn("timed out" if timeout else "exited with code 1", output)
                self.assertIn("stdout: HTTP 403; authorization denied", output)
                self.assertIn("stderr: agent creation or deployment failed", output)

    def test_inspection_failure_and_timeout_do_not_project_json_or_stderr(self):
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                def fake(command, **kwargs):
                    os.write(kwargs["stderr"], b"RESPONSE 403 Forbidden " + KEY.encode())
                    raw = json.dumps({"secret": KEY, "error": "Unsupported nested config block"})
                    if timeout:
                        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=raw, stderr=GITHUB_KEY)
                    return subprocess.CompletedProcess(command, 1, stdout=raw)
                output = self.invoke(fake, capture=True)
                self.assertIn("Inspection output withheld", output)
                for private in (KEY, GITHUB_KEY, "HTTP 403", "unsupported service configuration"):
                    self.assertNotIn(private, output)

    def test_success_preserves_return_values_without_printing_diagnostics(self):
        for capture in (False, True):
            with self.subTest(capture=capture):
                raw = '{"installedVersion":"1.0.0"}'
                def fake(command, **kwargs):
                    os.write(kwargs["stderr"], KEY.encode())
                    if not capture:
                        os.write(kwargs["stdout"], GITHUB_KEY.encode())
                    return subprocess.CompletedProcess(command, 0, stdout=raw)
                stdout, stderr = io.StringIO(), io.StringIO()
                with mock.patch.object(flow.subprocess, "run", side_effect=fake) as process:
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        result = flow.invoke("azd.exe", ["version"], Path.cwd(), {},
                                             flow.time.monotonic() + 10, capture=capture)
                process.assert_called_once()
                self.assertEqual(result, raw if capture else None)
                self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
