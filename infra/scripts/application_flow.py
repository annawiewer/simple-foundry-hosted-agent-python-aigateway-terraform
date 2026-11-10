"""Prepare an isolated application project; explicitly deploy its agent or schedule.

Preparation is offline. Terraform and configure_tools.py retain their existing
ownership. Each cloud operation is attempted once per prepared workspace.
CLI completion is not independent readback or runtime acceptance.
"""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import quote

import configure_tools as tools
from export_environment import environment_mapping

SOURCE = Path(__file__).resolve().parents[2]
APP_FILES = (
    "Dockerfile", ".dockerignore", "pyproject.toml", "uv.lock",
    "main.py", "repo_digest_agent.py", "github_mcp_middleware.py",
)
EXTENSIONS = {
    name: "1.0.0" for name in (
        "azure.ai.agents", "azure.ai.routines", "azure.ai.inspector",
        "azure.ai.projects", "azure.ai.connections", "azure.ai.toolboxes",
    )
}
KEY_VARIABLE = "AIGW_TF_RUNTIME_KEY"
AGENT_GATE = "AIGW_TF_DEPLOY_AGENT"
SCHEDULE_GATE = "AIGW_TF_ENABLE_SCHEDULE"
STAGE_VARIABLE = "AIGW_TF_DEPLOY_STAGE"
ENVIRONMENT_KEYS = {
    "AZURE_ENV_NAME", "AZURE_SUBSCRIPTION_ID", "AZURE_TENANT_ID", "AZURE_LOCATION",
    "AZURE_RESOURCE_GROUP", "AI_GATEWAY_RESOURCE_GROUP", "AI_GATEWAY_LOCATION",
    "AZURE_AI_PROJECT_ENDPOINT", "AZURE_AI_PROJECT_ID", "FOUNDRY_PROJECT_ENDPOINT",
    "AZURE_CONTAINER_REGISTRY_ENDPOINT", "AZURE_CONTAINER_REGISTRY_RESOURCE_ID",
    "AZURE_CONTAINER_REGISTRY_NAME", "AZURE_AI_PROJECT_ACR_CONNECTION_NAME",
    "AI_GATEWAY_NAME", "AI_GATEWAY_RESOURCE_ID", "AZURE_AI_GATEWAY_ENDPOINT",
    "AZURE_AI_GATEWAY_MODEL", "AZURE_AI_GATEWAY_MINI_MODEL", "TOOLBOX_NAME",
    "TOOLBOX_ENDPOINT", "GITHUB_REPOSITORY", "USE_EXISTING_AI_PROJECT",
    "AZD_AGENT_SKIP_ROLE_ASSIGNMENTS",
}
OS_ENVIRONMENT = {
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE",
    "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "TEMP", "TMP", "TMPDIR", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA",
    "LANG", "LC_ALL", "LC_CTYPE", "TERM", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "AZURE_CONFIG_DIR", "AZD_CONFIG_DIR", "AZURE_DEV_USER_AGENT",
}
SAFE_VALUE = r"[A-Za-z0-9_./:=?()-]+"
SAVED_VALUE = r"[A-Za-z0-9_./:=?()@&+,%~-]+"
SHA256 = r"[0-9a-f]{64}"
DIAGNOSTIC_BYTES = 16 * 1024
DIAGNOSTIC_LIMIT = 1024
DIAGNOSTIC_PATTERNS = (
    (r"unsupported (?:nested )?config(?:uration)?(?: block)?", "unsupported service configuration"),
    (r"agent name could not be resolved", "agent metadata missing from environment"),
    (r"(?:missing|required|unset|not set).{0,80}(?:environment variable|project id|subscription)"
     r"|(?:environment variable|project id|subscription).{0,80}(?:missing|required|unset|not set)",
     "required environment configuration missing"),
    (r"\b(?:DefaultAzureCredential|CredentialUnavailable|AuthenticationFailed|Unauthorized)\b"
     r"|authentication failed|invalid credentials|failed to (?:get|acquire).{0,40}token", "authentication failed"),
    (r"\b(?:AuthorizationFailed|AccessDenied|Forbidden)\b|authorization failed|access denied|permission denied",
     "authorization denied"),
    (r"\b(?:ResourceNotFound|DeploymentNotFound|NotFound)\b|resource.{0,60}not found", "resource not found"),
    (r"\b(?:InvalidArgument|InvalidRequest|BadRequest)\b|bad request", "request rejected as invalid"),
    (r"\b(?:QuotaExceeded|InsufficientQuota|TooManyRequests)\b|quota exceeded|insufficient capacity",
     "quota, capacity or throttling failure"),
    (r"\b(?:ImagePullBackOff|ErrImagePull|ManifestUnknown)\b|(?:failed|unable) to pull.{0,40}image"
     r"|manifest unknown", "container image retrieval failed"),
    (r"\bnot_a_registry_connection\b|registry connection.{0,80}(?:missing|not found|invalid)"
     r"|invalid.{0,40}registry connection",
     "registry connection invalid or missing"),
    (r"(?:failed|error|unable).{0,40}(?:creat|deploy).{0,40}agent", "agent creation or deployment failed"),
    (r"\b(?:ServiceUnavailable|InternalServerError)\b", "remote service failure"),
    (r"connection refused|no such host|name resolution|TLS handshake|certificate verify|x509:",
     "network, DNS or TLS failure"),
    (r"deadline exceeded|timed out|timeout", "operation timed out"),
)


class FlowError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FlowError(message)


def linked(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def contents(path, limit=8 * 1024 * 1024):
    require(not linked(path) and path.is_file(), "Expected an ordinary, unlinked workspace file.")
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    require(len(value) <= limit, "Workspace file exceeds the supported size; contents withheld.")
    return value


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fingerprint(document):
    return digest(json.dumps(document, sort_keys=True, separators=(",", ":")).encode())


def write_json(path, document):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")


def guard(stage=None):
    message = "Use application_flow.py; infrastructure and deletion are not owned by this project."
    windows = f"throw '{message}'"
    posix = f"echo '{message}' >&2; exit 1"
    if stage is not None:
        windows = f"if ($env:{STAGE_VARIABLE} -ne '{stage}') {{ {windows} }}"
        posix = f'test "${{{STAGE_VARIABLE}:-}}" = "{stage}" || {{ {posix}; }}'
    return {
        "windows": {"shell": "pwsh", "run": windows},
        "posix": {"shell": "sh", "run": posix},
    }


def validate_prebuilt_image(image, registry):
    component = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
    require(isinstance(image, str) and len(image) <= 512
            and re.fullmatch(
                rf"(?i:{re.escape(registry)})/{component}(?:/{component})*@sha256:{SHA256}", image,
            ) is not None,
            "Use a digest-pinned image from the contract's exact registry; image values withheld.")


def manifest(agent, repository, prebuilt_image=None, registry_connection_name=None, use_default_acr=False):
    runtime = (
        "AZURE_AI_GATEWAY_ENDPOINT", "AZURE_AI_GATEWAY_MODEL", "AZURE_AI_GATEWAY_MINI_MODEL",
        "TOOLBOX_ENDPOINT", "TOOLBOX_NAME", "GITHUB_REPOSITORY",
    )
    result = {
        "name": "terraform-repo-digest",
        "requiredVersions": {
            "azd": ">=1.37.0 <1.38.0",
            "extensions": {key: "=" + value for key, value in EXTENSIONS.items()},
        },
        "hooks": {"preprovision": guard(), "predown": guard()},
        "services": {
            agent: {
                "name": agent, "project": "app", "host": "azure.ai.agent", "language": "docker",
                "condition": "${" + AGENT_GATE + "}", "docker": {"remoteBuild": True},
                "kind": "hosted", "startupCommand": "uv run --frozen --no-dev python main.py",
                "container": {"resources": {"cpu": "0.5", "memory": "1Gi"}},
                "protocols": [{"protocol": "responses", "version": "2.0.0"}],
                "env": {**{key: "${" + key + "}" for key in runtime},
                        "AZURE_AI_GATEWAY_API_KEY": "${" + KEY_VARIABLE + "}"},
                "hooks": {"predeploy": guard("agent")},
            },
            agent + "-daily": {
                "host": "azure.ai.routine", "condition": "${" + SCHEDULE_GATE + "}",
                "enabled": True,
                "description": "Daily repository digest at 9 AM Pacific time.",
                "action": {
                    "agentName": agent, "type": "invoke_agent_responses_api",
                    "input": f"Create a concise daily repo digest for {repository}.",
                },
                "triggers": {"default": {
                    "type": "schedule", "cronExpression": "0 9 * * *", "timeZone": "America/Los_Angeles",
                }},
                "hooks": {"predeploy": guard("schedule")},
            },
        },
    }
    if prebuilt_image is not None:
        result["services"][agent].update({
            "image": prebuilt_image,
            "docker": {"imagePassthrough": True},
        })
        if not use_default_acr:
            result["services"][agent]["registryConnectionId"] = registry_connection_name
    return result


def validate_values(values, bootstrap, box, subscription, tenant):
    require(isinstance(values, dict)
            and ENVIRONMENT_KEYS - {"AI_GATEWAY_LOCATION"} <= values.keys() <= ENVIRONMENT_KEYS
            and all(isinstance(value, str) and re.fullmatch(SAFE_VALUE, value) for value in values.values()),
            "Only the reviewed nonsecret environment mapping is supported.")
    require(re.fullmatch(tools.UUID, tenant) is not None
            and values["AZURE_SUBSCRIPTION_ID"].lower() == subscription.lower()
            and values["AZURE_TENANT_ID"].lower() == tenant.lower(),
            "Explicit subscription or tenant does not match the prepared project.")
    tools.validate_bootstrap(bootstrap, subscription)
    require(bootstrap["tool_access_enabled"] and bootstrap["remote_tool_connection_id"] is not None,
            "The applied, connected tool bootstrap with project tool access is required.")
    for key, source in (
        ("AI_GATEWAY_RESOURCE_ID", "gateway_id"), ("AZURE_AI_PROJECT_ID", "project_id"),
    ):
        require(values[key].lower() == bootstrap[source].lower(), "Infrastructure handoff IDs do not match.")
    require(values["AZURE_AI_GATEWAY_ENDPOINT"].rstrip("/") == bootstrap["gateway_endpoint"].rstrip("/")
            and values["AZURE_AI_PROJECT_ENDPOINT"] == bootstrap["project_endpoint"].rstrip("/")
            and values["FOUNDRY_PROJECT_ENDPOINT"] == values["AZURE_AI_PROJECT_ENDPOINT"],
            "Infrastructure handoff endpoints do not match.")
    require(box == tools.toolbox_metadata(bootstrap, box["name"], box["version"])
            and values["TOOLBOX_NAME"] == box["name"] and values["TOOLBOX_ENDPOINT"] == box["endpoint"],
            "The Toolbox must match the configured project and explicit version.")
    require(values["USE_EXISTING_AI_PROJECT"] == "true"
            and values["AZD_AGENT_SKIP_ROLE_ASSIGNMENTS"] == "true",
            "Existing-project and no-automatic-role-assignment safeguards are required.")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", values["AZURE_ENV_NAME"]) is not None,
            "The environment name must be a safe, single directory name.")
    require(re.fullmatch(rf"{tools.RESOURCE_NAME}/{tools.RESOURCE_NAME}", values["GITHUB_REPOSITORY"]) is not None,
            "Use the repository selected in the tool receipt.")


def fixed_hashes(workspace):
    require({path.name for path in workspace.iterdir()} <= {
        "app", ".azure", "azure.yaml", "prepared.json", "agent.receipt.jsonl", "schedule.receipt.jsonl",
    }, "Unexpected workspace entry; do not add infrastructure, hooks or other inputs to this project.")
    app = workspace / "app"
    require(not linked(app) and app.is_dir() and {path.name for path in app.iterdir()} == set(APP_FILES),
            "The build context must contain only the allow-listed application files.")
    return {"azure.yaml": digest(contents(workspace / "azure.yaml")),
            **{name: digest(contents(app / name)) for name in APP_FILES}}


def environment_directory(workspace, values):
    azure = workspace / ".azure"
    directory = azure / values["AZURE_ENV_NAME"]
    require(not linked(azure) and not linked(directory), "The application environment must not be linked.")
    return directory


def state_hashes(workspace, values):
    directory = environment_directory(workspace, values)
    return {name: digest(contents(path, tools.MAX_BYTES)) for name, path in (
        ("project", workspace / ".azure" / "config.json"),
        ("environment", directory / "config.json"), ("dotenv", directory / ".env"),
    )}


def prepare(args):
    document = json.loads(tools.read_text(args.contract))
    values = environment_mapping(document, args.model_alias_key, args.mini_model_alias_key)
    contract = document["deployment_contract"]["value"] if "deployment_contract" in document else document
    bootstrap = tools.validate_bootstrap(json.loads(tools.read_text(args.bootstrap)), args.subscription_id)
    require(re.fullmatch(tools.UUID, args.tenant_id) is not None, "Select an explicit tenant UUID.")
    receipt = tools.read_receipt(args.tool_receipt, bootstrap, args.tenant_id)
    require(receipt["status"] == "configured" and "toolbox" in receipt and "toolserver" in receipt
            and receipt["toolserver"]["endpoint"] == bootstrap["remote_tool_endpoint"]
            and receipt["configuration"]["repository"] == args.repository,
            "A configured, connected Toolbox receipt for the selected repository is required.")
    box = receipt["toolbox"]
    integration = contract["integration"]
    require(integration["gateway_tool_access_enabled"] is True
            and type(integration["registry_connection_shared"]) is bool
            and integration["remote_tool_connection_id"] == bootstrap["remote_tool_connection_id"]
            and integration["remote_tool_endpoint"] == bootstrap["remote_tool_endpoint"]
            and type(integration["gateway_model_access_enabled"]) is bool,
            "Apply the Terraform tool/registry connections and export matching fresh handoffs first.")
    registry_connection_id = contract["agents"].get("registry_connection_id")
    expected_registry_connection_id = (
        values["AZURE_AI_PROJECT_ID"] + "/connections/" + values["AZURE_AI_PROJECT_ACR_CONNECTION_NAME"]
    )
    require(isinstance(registry_connection_id, str)
            and registry_connection_id.casefold() == expected_registry_connection_id.casefold(),
            "Export a fresh Terraform contract with the registry connection ID matching this project and connection name.")
    require(contract["gateway"]["monitoring"]["configuration_status"] in {"configured", "legacy"},
            "Complete the staged telemetry handoff before preparing the application.")
    require(re.fullmatch(r"[a-z][a-z0-9-]{2,49}", args.agent_name) is not None,
            "Choose an explicit lowercase agent name of 3-50 letters, digits or hyphens.")
    values.update({
        "AZURE_TENANT_ID": args.tenant_id,
        "FOUNDRY_PROJECT_ENDPOINT": values["AZURE_AI_PROJECT_ENDPOINT"],
        "USE_EXISTING_AI_PROJECT": "true", "AZD_AGENT_SKIP_ROLE_ASSIGNMENTS": "true",
        "TOOLBOX_NAME": box["name"], "TOOLBOX_ENDPOINT": box["endpoint"],
        "GITHUB_REPOSITORY": args.repository,
    })
    validate_values(values, bootstrap, box, args.subscription_id, args.tenant_id)
    require(not args.use_default_acr or args.prebuilt_image is not None,
            "Default ACR handling requires an explicitly selected prebuilt image.")
    use_default_acr = args.prebuilt_image is not None
    if args.prebuilt_image is not None:
        validate_prebuilt_image(args.prebuilt_image, values["AZURE_CONTAINER_REGISTRY_ENDPOINT"])
    require(not linked(args.workspace), "Choose a new, unlinked application workspace.")
    workspace = args.workspace.resolve()
    require(not workspace.exists() and workspace.parent.is_dir()
            and not workspace.is_relative_to(SOURCE) and not SOURCE.is_relative_to(workspace),
            "Choose a new workspace outside the repository in an existing private directory.")
    files = {name: contents(SOURCE / name) for name in APP_FILES}
    workspace.mkdir(mode=0o700)
    app = workspace / "app"
    app.mkdir()
    for name, value in files.items():
        (app / name).write_bytes(value)
    write_json(workspace / "azure.yaml", manifest(
        args.agent_name, args.repository, args.prebuilt_image, values["AZURE_AI_PROJECT_ACR_CONNECTION_NAME"],
        use_default_acr,
    ))
    directory = workspace / ".azure" / values["AZURE_ENV_NAME"]
    directory.mkdir(parents=True)
    write_json(workspace / ".azure" / "config.json", {"defaultEnvironment": values["AZURE_ENV_NAME"]})
    write_json(directory / "config.json", {})
    with (directory / ".env").open("x", encoding="utf-8", newline="\n") as stream:
        stream.writelines(f"{key}={json.dumps(value)}\n" for key, value in sorted(values.items()))
    spec = {
        "version": 1, "agent_name": args.agent_name, "environment": values,
        "bootstrap": bootstrap, "toolbox": box,
        "gateway_model_access_enabled": integration["gateway_model_access_enabled"],
        "files": fixed_hashes(workspace), "initial_azd_state": state_hashes(workspace, values),
    }
    if args.prebuilt_image is not None:
        spec["prebuilt_image"] = args.prebuilt_image
    if use_default_acr:
        spec["use_default_acr"] = True
    write_json(workspace / "prepared.json", spec)


def load_prepared(args):
    require(not linked(args.workspace), "The application workspace must not be linked.")
    workspace = args.workspace.resolve()
    spec = json.loads(contents(workspace / "prepared.json", tools.MAX_BYTES))
    required_keys = {
        "version", "agent_name", "environment", "bootstrap", "toolbox",
        "gateway_model_access_enabled", "files", "initial_azd_state",
    }
    require(isinstance(spec, dict) and set(spec) in (
                required_keys, required_keys | {"prebuilt_image"},
                required_keys | {"prebuilt_image", "use_default_acr"},
            )
            and ("use_default_acr" not in spec or spec["use_default_acr"] is True)
            and type(spec["version"]) is int and spec["version"] == 1
            and re.fullmatch(r"[a-z][a-z0-9-]{2,49}", spec["agent_name"]) is not None
            and type(spec["gateway_model_access_enabled"]) is bool,
            "Invalid prepared project; contents withheld.")
    validate_values(spec["environment"], spec["bootstrap"], spec["toolbox"],
                    args.subscription_id, args.tenant_id)
    if "prebuilt_image" in spec:
        validate_prebuilt_image(spec["prebuilt_image"], spec["environment"]["AZURE_CONTAINER_REGISTRY_ENDPOINT"])
    require(fixed_hashes(workspace) == spec["files"]
            and json.loads(contents(workspace / "azure.yaml")) ==
            manifest(spec["agent_name"], spec["environment"]["GITHUB_REPOSITORY"],
                     spec.get("prebuilt_image"), spec["environment"]["AZURE_AI_PROJECT_ACR_CONNECTION_NAME"],
                     spec.get("use_default_acr", False)),
            "Prepared application or manifest changed; do not deploy this workspace.")
    require(set(spec["initial_azd_state"]) == {"project", "environment", "dotenv"}
            and all(isinstance(value, str) and re.fullmatch(SHA256, value)
                    for value in spec["initial_azd_state"].values()),
            "Invalid initial environment fingerprint.")
    return workspace, spec


def read_environment(workspace, spec):
    directory = environment_directory(workspace, spec["environment"])
    result = {}
    for line in contents(directory / ".env", tools.MAX_BYTES).decode("utf-8-sig").splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, raw = line.partition("=")
        require(separator and re.fullmatch(r"[A-Z][A-Z0-9_]*", key) and key not in result,
                "Unexpected or duplicate saved environment entry; contents withheld.")
        value = json.loads(raw) if raw.startswith('"') else raw
        require(isinstance(value, str) and (not value or re.fullmatch(SAVED_VALUE, value)),
                "Unexpected saved environment value; contents withheld.")
        result[key] = value
    expected = spec["environment"]
    prefix = spec["agent_name"].replace("-", "_").upper()
    hosted_outputs = {"ENABLE_HOSTED_AGENTS": "true", "ENABLE_CAPABILITY_HOST": "false"}
    require(all(result.get(key) == value for key, value in expected.items())
            and all(key in expected or key.startswith(("AGENT_" + prefix + "_", "SERVICE_" + prefix + "_"))
                    or key in hosted_outputs and value == hosted_outputs[key]
                    for key, value in result.items()),
            "Saved context changed or contains unexpected values. Do not copy credentials into azd files.")
    return result


def agent_metadata(workspace, spec):
    values = read_environment(workspace, spec)
    prefix = "AGENT_" + spec["agent_name"].replace("-", "_").upper() + "_"
    name, version, endpoint = (values.get(prefix + suffix, "") for suffix in ("NAME", "VERSION", "ENDPOINT"))
    require(name == spec["agent_name"] and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", version)
            and endpoint == spec["environment"]["FOUNDRY_PROJECT_ENDPOINT"] + f"/agents/{name}/versions/{version}",
            "CLI completion lacks matching agent metadata; preserve the receipt and review the remote outcome.")
    return {"name": name, "version": version, "endpoint": endpoint}


def agent_receipt(workspace, spec):
    raw = contents(workspace / "agent.receipt.jsonl", tools.MAX_BYTES).decode("utf-8")
    require(raw.endswith("\n"), "An incomplete agent receipt cannot authorize the daily schedule.")
    records = [json.loads(line) for line in raw.splitlines()]
    require(len(records) == 2, "A complete, single-attempt agent receipt is required.")
    pending, complete = records
    common = {"version": 1, "operation": "deploy-agent", "prepared_sha256": fingerprint(spec)}
    for record in records:
        require(isinstance(record, dict) and all(record.get(key) == value for key, value in common.items())
                and record.get("authentication") in {"managed-identity", "api-key"},
                "Agent receipt belongs to a different project or deployment.")
    require(set(pending) == set(common) | {"authentication", "status"}
            and pending["status"] == "pending"
            and set(complete) == set(pending) | {"agent", "azd_state"}
            and complete["status"] == "cli-completed"
            and complete["authentication"] == pending["authentication"]
            and complete["agent"] == agent_metadata(workspace, spec)
            and complete["azd_state"] == state_hashes(workspace, spec["environment"]),
            "Agent outcome or environment changed; do not enable the schedule without separate review.")
    return complete


def child_environment():
    result = {key: value for key, value in os.environ.items() if key.upper() in OS_ENVIRONMENT}
    result["AZD_DISABLE_TELEMETRY"] = "1"
    return result


@contextlib.contextmanager
def diagnostic_pipe():
    reader, writer = os.pipe()
    data, complete = bytearray(), threading.Event()

    def drain():
        try:
            while chunk := os.read(reader, 4096):
                data.extend(chunk)
                del data[:-DIAGNOSTIC_BYTES]
            complete.set()
        except OSError:
            pass
        finally:
            os.close(reader)

    worker = threading.Thread(target=drain, daemon=True)
    try:
        worker.start()
    except BaseException:
        os.close(reader)
        os.close(writer)
        raise
    try:
        yield writer, data, complete
    finally:
        os.close(writer)
        # A surviving child must not extend the deployment deadline by holding a pipe.
        worker.join(timeout=1)


def failure_detail(data, environment):
    text = bytes(data[-DIAGNOSTIC_BYTES:]).decode("utf-8", errors="replace")
    secrets = {
        value for name, value in environment.items()
        if value and re.search(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH|CONNECTION.?STRING|COOKIE|SAS", name, re.I)
    }
    for secret in sorted(secrets, key=len, reverse=True):
        for value in (secret, json.dumps(secret)[1:-1], quote(secret, safe="")):
            text = text.replace(value, "[redacted]")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(
        r"(?im)^.*(?:authorization|proxy-authorization|api[-_]?key|access[-_]?token|refresh[-_]?token"
        r"|client[-_]?secret|password|cookie|accountkey|sharedaccess(?:key|signature)"
        r"|instrumentationkey|connection[-_]?string)\s*[\"']?\s*[:=].*$", "[redacted]", text,
    )
    text = re.sub(
        r"(?i)\b(?:bearer|basic)\s+\S+|\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]+"
        r"|\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
        r"|\bsk-[A-Za-z0-9_-]+|https?://\S+", "[redacted]", text,
    )
    # Never release free-form text: even unrecognised or encoded credentials remain withheld.
    statuses = re.findall(r"(?i)\b(?:HTTP(?:/\d(?:\.\d)?)?|(?:status|response)(?:[ _-]?code)?)"
                          r"\s*[:=(]?\s*([45]\d\d)\b", text)
    details = [f"HTTP {code}" for code in sorted(set(statuses))[:3]]
    details.extend(message for pattern, message in DIAGNOSTIC_PATTERNS if re.search(pattern, text, re.I))
    return "; ".join(details[:6]) or "unrecognized diagnostic; details withheld"


def invoke(executable, command, workspace, environment, deadline, capture=False):
    timeout = tools.remaining(deadline, 30 if capture else 1800)
    stdout_context = contextlib.nullcontext((subprocess.PIPE, None, None)) if capture else diagnostic_pipe()
    timed_out = False
    with stdout_context as stdout, diagnostic_pipe() as stderr:
        try:
            result = subprocess.run(
                [executable, *command], cwd=workspace, env=environment, stdin=subprocess.DEVNULL,
                stdout=stdout[0], stderr=stderr[0],
                text=True, encoding="utf-8", errors="replace", check=False, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
    if timed_out or result.returncode != 0:
        reason = "timed out" if timed_out else f"exited with code {result.returncode}"
        if capture:
            detail = "Inspection output withheld."
        else:
            detail = " ".join(
                f"{name}: {failure_detail(stream[1], environment) if stream[2].is_set() else 'incomplete capture; details withheld'}."
                for name, stream in (("stdout", stdout), ("stderr", stderr))
            )
        raise FlowError(
            (f"azd {reason}. {detail}")[:DIAGNOSTIC_LIMIT]
            + " Preserve any receipt and review before retrying."
        ) from None
    if capture:
        require(isinstance(result.stdout, str) and len(result.stdout) <= tools.MAX_BYTES,
                "Unexpected azd inspection output; contents withheld.")
        return result.stdout
    return None


def check_tooling(workspace, environment, deadline):
    executable = shutil.which("azd")
    require(executable is not None and Path(executable).suffix.lower() not in {".cmd", ".bat"},
            "An installed azd executable is required; no tool installation is automatic.")
    version = invoke(executable, ["version"], workspace, environment, deadline, capture=True)
    match = re.search(r"\bazd version (1\.37\.\d+)(?:\s|$)", version)
    require(match is not None, "This path supports stable azd 1.37.x only. Upgrade separately after review.")
    extensions = json.loads(invoke(executable, ["extension", "list", "--output", "json", "--no-prompt"],
                                  workspace, environment, deadline, capture=True))
    require(isinstance(extensions, list), "Expected an installed-extension inventory.")
    installed = {}
    for extension in extensions:
        require(isinstance(extension, dict), "Invalid installed-extension inventory.")
        identifier = extension.get("id")
        if identifier in EXTENSIONS:
            require(identifier not in installed, "Ambiguous installed-extension inventory.")
            installed[identifier] = extension.get("installedVersion")
    require(installed == EXTENSIONS,
            "Install the six documented stable 1.0.0 extensions separately; catalog versions are not installed versions.")
    return executable


def deploy(args):
    workspace, spec = load_prepared(args)
    is_agent = args.operation == "deploy-agent"
    receipt_path = workspace / ("agent.receipt.jsonl" if is_agent else "schedule.receipt.jsonl")
    require(not receipt_path.exists() and not linked(receipt_path),
            "This operation already has a receipt. Do not retry or remove it to bypass the single-attempt guard.")
    require(args.confirm_agent_deployment if is_agent else args.confirm_enable_schedule,
            "Explicit confirmation of this cloud operation is required.")
    previous = None
    key = ""
    if is_agent:
        require(not (workspace / "schedule.receipt.jsonl").exists()
                and state_hashes(workspace, spec["environment"]) == spec["initial_azd_state"]
                and read_environment(workspace, spec) == spec["environment"],
                "Agent deployment requires the untouched, newly prepared environment.")
        require(bool(args.managed_identity) != bool(args.gateway_key_env),
                "Explicitly select managed identity or a named process-only gateway-key variable.")
        if args.managed_identity:
            require(spec["gateway_model_access_enabled"], "Managed identity requires the Terraform model-access grant.")
        else:
            selected = args.gateway_key_env
            require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", selected) is not None
                    and selected.upper() not in OS_ENVIRONMENT | ENVIRONMENT_KEYS
                    and selected.upper() not in {KEY_VARIABLE, AGENT_GATE, SCHEDULE_GATE, STAGE_VARIABLE,
                                                 "GH_TOKEN", "GITHUB_TOKEN"},
                    "Select a dedicated gateway-key environment variable, not a credential value or tool credential.")
            key = os.environ.get(selected, "")
            require(re.fullmatch(r"[A-Za-z0-9._~+/=-]{8,4096}", key) is not None,
                    "The explicitly selected gateway key is missing or malformed; no lookup is automatic.")
    else:
        previous = agent_receipt(workspace, spec)
    deadline = time.monotonic() + args.timeout_seconds
    environment = child_environment()
    executable = check_tooling(workspace, environment, deadline)
    current_workspace, current_spec = load_prepared(args)
    require(current_workspace == workspace and current_spec == spec,
            "Prepared inputs changed during tooling inspection; no deployment was started.")
    if is_agent:
        require(state_hashes(workspace, spec["environment"]) == spec["initial_azd_state"],
                "The environment changed during tooling inspection; no deployment was started.")
    else:
        require(agent_receipt(workspace, spec) == previous,
                "The agent receipt changed during tooling inspection; no deployment was started.")
    record = {"version": 1, "operation": args.operation, "prepared_sha256": fingerprint(spec)}
    if is_agent:
        record["authentication"] = "managed-identity" if args.managed_identity else "api-key"
    else:
        record["agent"] = previous["agent"]
    stage = "agent" if is_agent else "schedule"
    environment.update({
        STAGE_VARIABLE: stage, AGENT_GATE: "true" if is_agent else "false",
        SCHEDULE_GATE: "false" if is_agent else "true",
    })
    if is_agent:
        environment[KEY_VARIABLE] = key
    service = spec["agent_name"] + ("" if is_agent else "-daily")
    with receipt_path.open("x", encoding="utf-8", newline="\n") as stream:
        try:
            tools.record_status(stream, record, "pending", [key])
            invoke(executable, ["deploy", service, "--environment", spec["environment"]["AZURE_ENV_NAME"],
                                "--no-prompt"], workspace, environment, deadline)
            require(fixed_hashes(workspace) == spec["files"], "Build context or manifest changed during deployment.")
            if is_agent:
                record["agent"] = agent_metadata(workspace, spec)
            else:
                require(agent_metadata(workspace, spec) == previous["agent"], "Agent metadata changed during schedule deployment.")
            record["azd_state"] = state_hashes(workspace, spec["environment"])
            tools.record_status(stream, record, "cli-completed", [key])
        except BaseException:
            try:
                tools.record_status(stream, record, "unconfirmed", [key])
            except (OSError, ValueError):
                pass
            raise


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid application-flow arguments; values withheld. Use --help.\n")


def arguments(argv):
    parser = SafeParser(description=__doc__)
    operations = parser.add_subparsers(dest="operation", required=True, parser_class=SafeParser)
    for operation in ("prepare", "deploy-agent", "enable-schedule"):
        command = operations.add_parser(operation)
        command.add_argument("--workspace", type=Path, required=True)
        command.add_argument("--subscription-id", required=True)
        command.add_argument("--tenant-id", required=True)
        if operation == "prepare":
            command.add_argument("--contract", type=Path, required=True)
            command.add_argument("--bootstrap", type=Path, required=True)
            command.add_argument("--tool-receipt", type=Path, required=True)
            command.add_argument("--repository", required=True)
            command.add_argument("--agent-name", required=True)
            command.add_argument(
                "--prebuilt-image",
                help="Use an existing image pinned by sha256 in the contract's registry instead of building.",
            )
            command.add_argument(
                "--use-default-acr", action="store_true",
                help="Compatibility flag: new prebuilt ACR workspaces omit the registry selector by default.",
            )
            command.add_argument("--model-alias-key", default="primary-router")
            command.add_argument("--mini-model-alias-key", default="mini-router")
        else:
            command.add_argument("--timeout-seconds", type=int, default=900, choices=range(30, 1801), metavar="30-1800")
            if operation == "deploy-agent":
                command.add_argument(
                    "--confirm-agent-deployment", action="store_true",
                    help="Confirm target/name ownership and no active routine for this name; deployment may create a new version.",
                )
                authentication = command.add_mutually_exclusive_group(required=True)
                authentication.add_argument("--managed-identity", action="store_true")
                authentication.add_argument("--gateway-key-env")
            else:
                command.add_argument("--confirm-enable-schedule", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = arguments(argv)
    try:
        if args.operation == "prepare":
            prepare(args)
            print("PREPARED: isolated nonsecret application project. No Azure call; no schedule deployed.")
        else:
            deploy(args)
            print("CLI-COMPLETED: nonsecret receipt saved. Independent readback and runtime acceptance remain separate.")
        return 0
    except FlowError as error:
        print(str(error), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError, KeyboardInterrupt):
        print("Application flow stopped; sensitive details withheld. Preserve any receipt and review before retrying.",
              file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
