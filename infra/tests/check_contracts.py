"""Credential-free structural and native Terraform mock-plan contract checks."""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "2025-09-01-preview"
GATEWAY = "Microsoft.ApiManagement/aigateways"
PROFILE_PINS = {
    "gpt-latest": ("gpt-6.1-sol", "2026-09-29", 20),
    "gpt-6-sol": ("gpt-6-sol", "2026-09-22", 20),
    "gpt-mini-latest": ("gpt-5.4-mini", "2026-03-17", 200),
}
REGISTRY_READBACK_RUNS = {
    "agents_shared_registry_readback", "reject_registry_unshared_readback",
    "reject_registry_nondefault_readback", "reject_registry_missing_readback",
}
MODEL_READBACK_RUNS = {
    "models_account_readback", "reject_models_project_enabled_readback",
    "reject_models_missing_readback", "reject_models_null_readback", "reject_models_string_readback",
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def blocks(text, kind):
    """Extract balanced HCL blocks, ignoring braces inside strings/comments."""
    header = re.compile(rf'(?m)^\s*{kind}\s+((?:"[^"]+"\s*)*)\{{')
    token = re.compile(r'"(?:\\.|[^"\\])*"|#[^\n]*|//[^\n]*|/\*.*?\*/|[{}]', re.S)
    for match in header.finditer(text):
        depth = 1
        for item in token.finditer(text, match.end()):
            if item.group() == "{":
                depth += 1
            elif item.group() == "}":
                depth -= 1
            if depth == 0:
                yield re.findall(r'"([^"]+)"', match[1]), text[match.end():item.start()]
                break
        else:
            raise AssertionError(f"Unbalanced {kind} block")


def tf_files():
    return sorted(p for p in ROOT.rglob("*.tf") if ".terraform" not in p.parts)


def source_blocks(kind):
    return [
        (path, names, body)
        for path in tf_files()
        for names, body in blocks(path.read_text(encoding="utf-8-sig"), kind)
    ]


def check_lifecycle_masks(path, text):
    masks = re.findall(r'\bignore_changes\s*=', text)
    allowed = []
    if path == ROOT / "modules" / "foundry-agents" / "main.tf":
        allowed = [
            lifecycle
            for names, body in blocks(text, "resource")
            if names == ["azapi_resource", "storage"]
            for _, lifecycle in blocks(body, "lifecycle")
            if re.fullmatch(
                r'\s*ignore_changes\s*=\s*\[\s*'
                r'body\.properties\.networkAcls\.resourceAccessRules\s*,?\s*\]\s*',
                lifecycle,
            )
        ]
    require(len(masks) == len(allowed) <= 1, f"{path}: broad lifecycle masking forbidden")


def check_test_runs(path, text):
    mocks = list(blocks(text, "mock_provider"))
    require(any(names == ["azapi"] for names, _ in mocks), f"{path}: every test file must mock AzAPI")
    require(not list(blocks(text, "provider")), f"{path}: real provider configuration forbidden")
    runs = list(blocks(text, "run"))
    require(runs, f"{path}: native regression runs missing")
    module, allowed = {
        ROOT / "tests" / "agents.tftest.hcl": ("foundry-agents", REGISTRY_READBACK_RUNS),
        ROOT / "tests" / "models.tftest.hcl": ("foundry-models", MODEL_READBACK_RUNS),
    }.get(path, ("", set()))
    for names, body in runs:
        if re.search(r'\bcommand\s*=\s*plan\b', body):
            continue
        # These GET postconditions are deferred until the preceding mock write.
        require(names[0] in allowed and
                re.search(r'\bcommand\s*=\s*apply\b', body) and
                not re.search(r'\bproviders\s*=', body) and
                len(mocks) == 1 and not re.search(r'\balias\s*=', mocks[0][1]) and
                re.search(rf'\bsource\s*=\s*"\./modules/{module}"', body),
                f"{path}: apply is restricted to the isolated readback mock-provider cases")


def check_structure():
    modules = ROOT / "modules"
    require({p.name for p in modules.iterdir() if p.is_dir()} ==
            {"ai-gateway", "foundry-models", "foundry-agents"}, "Three shallow capability modules required")
    for path, names, body in source_blocks("module"):
        source = re.search(r'\bsource\s*=\s*"([^"]+)"', body)
        require(source is not None, f"{path}: module {names} must have a literal bundled source")
        target = (path.parent / source[1]).resolve()
        require(target.is_relative_to(ROOT) and target.is_dir(),
                f"{path}: module {names} escapes contribution or is missing: {source[1]}")
        require(re.search(r'\bdepends_on\s*=', body) is None,
                f"{path}: blanket module dependency would hide the capability graph")
    for path in tf_files():
        text = path.read_text(encoding="utf-8-sig")
        if path.is_relative_to(modules):
            require(not list(blocks(text, "provider")), f"{path}: child configures a provider")
            require("required_providers" in text or path.name != "versions.tf",
                    f"{path}: child provider requirements missing")
        require(not re.search(r'\b(provisioner|local-exec|remote-exec)\b', text),
                f"{path}: provisioners are outside this baseline")
        check_lifecycle_masks(path, text)
        for function, literal in re.findall(r'\b(file|templatefile|fileset)\s*\(\s*"([^"]+)"', text):
            relative = literal.replace("${path.module}", ".").replace("${path.root}", str(ROOT))
            require("${" not in relative, f"{path}: unverified dynamic {function} dependency")
            require((path.parent / relative).resolve().is_relative_to(ROOT),
                    f"{path}: {function} dependency escapes contribution")
    for path in (ROOT / "tests").rglob("*"):
        require(not re.search(r'\.(tfstate|tfplan)(\.|$)', path.name), f"State/plan fixture forbidden: {path}")
        if path.is_file():
            text = path.read_text(encoding="utf-8-sig")
            require(not re.search(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}", text),
                    f"Credential fixture forbidden: {path}")
            if path.name.endswith(".tftest.hcl"):
                check_test_runs(path, text)
                for source in re.findall(r'\bsource\s*=\s*"([^"]+)"', text):
                    target = (ROOT / source).resolve()
                    require(target.is_relative_to(ROOT) and target.is_dir(),
                            f"{path}: native test module escapes contribution")
    resources = source_blocks("resource")
    gateway = [(p, b) for p, n, b in resources if n == ["azapi_resource", "gateway"]]
    require(len(gateway) == 1, "Exactly one gateway resource definition required")
    require(re.search(r'\bprevent_destroy\s*=\s*true', gateway[0][1]),
            "Gateway destructive-change guard missing")
    exporters = [b for _, n, b in resources if n == ["azapi_resource", "telemetry_exporter"]]
    require(len(exporters) == 1 and re.search(r'\bprevent_destroy\s*=\s*true', exporters[0]),
            "The sole exporter must block deletion and immutable-kind replacement")
    moves = [b for _, _, b in source_blocks("moved")]
    require(any(re.search(r'\bfrom\s*=\s*azapi_resource\.telemetry_exporter\s*\n', b) and
                re.search(r'\bto\s*=\s*azapi_resource\.telemetry_exporter\[0\]', b) for b in moves),
            "The legacy exporter address must move to its counted instance without state surgery")
    deployments = [b for _, n, b in resources if n == ["azapi_resource", "model_deployment"]]
    require(len(deployments) == 1 and re.search(r'\blocks\s*=\s*\[[^\]]*azapi_resource\.models\.id', deployments[0]),
            "Model operations must serialize on their owning account")
    readbacks = [b for _, n, b in source_blocks("data") if n == ["azapi_resource", "models_readback"]]
    require(len(readbacks) == 1 and
            re.search(r'\bdepends_on\s*=\s*\[\s*azapi_resource\.models\s*\]', readbacks[0]),
            "Model readback must wait for account updates even when its ID is unchanged")
    for path, names, body in source_blocks("output"):
        if path.parent == modules / "foundry-models":
            require(re.search(r'\bdepends_on\s*=\s*\[\s*data\.azapi_resource\.models_readback\s*\]', body),
                    f"{names[0]}: model output consumers must wait for the account readback")
    for name, dependency in (
        ("foundry_provider", "backend_role_assignment"),
        ("storage_connection", 'role_assignment["project-storage"]'),
        ("registry_connection", 'role_assignment["project-acr-pull"]'),
        ("gateway_remote_tool", "foundry_gateway_tool_access"),
        ("project_insights_connection", 'role_assignment["monitoring-account"]'),
        ("project_insights_connection", 'role_assignment["monitoring-project"]'),
        ("telemetry_exporter", "telemetry_publisher"),
    ):
        matches = [b for _, n, b in resources if n == ["azapi_resource", name]]
        require(len(matches) == 1, f"Missing sole {name} resource")
        edge = re.search(r'\bdepends_on\s*=\s*\[(.*?)\]\s*(?:\n|$)', matches[0], re.S)
        require(edge and dependency in edge[1], f"{name}: targeted authorization dependency missing")
    root_access = (ROOT / "access.tf").read_text(encoding="utf-8-sig")
    for dependency in ("module.foundry_agents.account_principal_id",
                       "module.foundry_agents.project_principal_id", "module.ai_gateway.gateway_id"):
        require(dependency in root_access, f"Root gateway grant lost identity/scope dependency: {dependency}")
    require("for_each  = local.foundry_gateway_callers" in root_access and
            'account = module.foundry_agents.account_principal_id' in root_access and
            'project = module.foundry_agents.project_principal_id' in root_access,
            "Root integration must use caller-known for_each keys, never computed principal IDs as keys")
    root_connection = (ROOT / "connections.tf").read_text(encoding="utf-8-sig")
    require("module.foundry_agents.project_id" in root_connection and
            "module.ai_gateway.gateway_endpoint" in root_connection and
            "enable_foundry_gateway_model_access" not in root_connection,
            "RemoteTool must depend on its project and deployed gateway origin, not model-access opt-in")
    require("/default/toolservers/" not in root_connection and "credentials" not in root_connection,
            "RemoteTool must not guess legacy routes or store credentials")
    for path in [ROOT] + sorted((ROOT / "examples").iterdir()):
        if not path.is_dir():
            continue
        lock = path / ".terraform.lock.hcl"
        require(lock.is_file(), f"Readonly init requires a committed lock: {path}")
        require(re.search(r'version\s*=\s*"2\.13\.0"', lock.read_text(encoding="utf-8-sig")),
                f"{path}: preserve AzAPI 2.13.0")
    profile = json.loads((ROOT / "model-profile.json").read_text(encoding="utf-8-sig"))
    require({k: (m["model_name"], m["model_version"], m["capacity"])
             for k, m in profile["model_deployments"].items()} == PROFILE_PINS,
            "Bundled default model/profile pins changed")
    print("PASS self-contained sources, sole ownership, provider/CLI baseline, lifecycle and hidden graph edges")


def properties(resource):
    return resource.get("body", {}).get("properties", {})


def resource_map(plan):
    return {r["address"]: r["change"]["after"] for r in plan["resource_changes"] if r["mode"] == "managed"}


def of_type(resources, type_name):
    return {address: body for address, body in resources.items() if body.get("type") == type_name}


def one(resources, type_name):
    selected = of_type(resources, type_name)
    require(len(selected) == 1, f"Expected sole {type_name}, found {list(selected)}")
    return next(iter(selected.values()))


def check_gateway(resources, telemetry="pending"):
    gateway = one(resources, f"{GATEWAY}@{API}")
    prefix = next(address for address in of_type(resources, f"{GATEWAY}@{API}")).removesuffix("azapi_resource.gateway")
    insights = resources[prefix + "azapi_resource.insights"]
    logs = resources[prefix + "azapi_resource.logs"]
    require("sku" not in gateway["body"] and "publicNetworkAccess" not in properties(gateway),
            "Standalone gateway must not inherit legacy SKU or private-ingress claim")
    require(gateway["create_headers"] == {"If-None-Match": "*"} and
            gateway["replace_triggers_refs"] == ["properties.backend"], "Gateway create/replace semantics changed")
    runtime_key = one(resources, f"{GATEWAY}/apiKeys@{API}")
    require(runtime_key["parent_id"] == gateway["id"], "Runtime key parent mismatch")
    require("key" not in properties(runtime_key), "Runtime key value must not be a fixture/output")
    require(properties(insights)["WorkspaceResourceId"] == logs["id"], "Gateway Insights workspace mismatch")
    publishers = [r for address, r in of_type(resources, "Microsoft.Authorization/roleAssignments@2022-04-01").items()
                  if address.startswith(prefix) and properties(r)["roleDefinitionId"].endswith("3913510d-42f4-4e42-8a64-420c390055eb")]
    if telemetry == "legacy":
        require(properties(insights).get("IngestionMode") == "LogAnalytics" and
                "AzureMonitorWorkspaceIngestionMode" not in properties(insights),
                "Legacy compatibility must not enable managed native ingestion")
    else:
        require(properties(insights).get("AzureMonitorWorkspaceIngestionMode") == "Enabled" and
                "IngestionMode" not in properties(insights) and insights["response_export_values"] == {
                    "insights_id": "id",
                    "managed_ingestion": "properties.AzureMonitorWorkspaceIngestionMode",
                    "log_analytics_id": "properties.WorkspaceResourceId",
                    "data_collection_rule_id": "properties.DefaultDataCollectionRuleResourceId || properties.DataCollectionRuleResourceId",
                    "metrics_endpoint": "properties.MetricsIngestionEndpoint || properties.OTLPMetricsEndpoint",
                    "logs_endpoint": "properties.LogsIngestionEndpoint || properties.OTLPLogsEndpoint",
                    "traces_endpoint": "properties.TracesIngestionEndpoint || properties.OTLPTracesEndpoint",
                },
                "Native managed ingestion must not retain the legacy mode or export its connection string")
    if telemetry == "pending":
        require(not of_type(resources, f"{GATEWAY}/workspaces/telemetryExporters@{API}") and not publishers,
                "Pending telemetry must not create an exporter or a guessed publisher scope")
        return gateway
    exporter = one(resources, f"{GATEWAY}/workspaces/telemetryExporters@{API}")
    p = properties(exporter)
    require(exporter["name"] == "appinsights" and exporter["replace_triggers_refs"] == ["properties.kind"] and
            exporter["parent_id"] == gateway["id"] + "/workspaces/default" and p["payloadCapture"] is False,
            "Exporter ownership, immutable kind guard, workspace or payload-capture boundary changed")
    require(p["applicationInsights"]["resourceId"] == insights["id"], "Exporter Insights target mismatch")
    if telemetry == "legacy":
        require(p["kind"] == "ApplicationInsights" and "openTelemetry" not in p and not publishers and
                p["applicationInsights"]["connectionString"] == "synthetic-only-not-a-credential",
                "Explicit legacy export must retain its selected connection-string destination without DCR access")
    else:
        returned = insights["output"]
        require(returned["insights_id"] == insights["id"] and
                returned["log_analytics_id"] == logs["id"], "Native readback must refer to the owned Insights/workspace")
        require(p["kind"] == "OpenTelemetry" and p["applicationInsights"] == {"resourceId": insights["id"]} and
                p["openTelemetry"] == {
                    "metricsEndpoint": returned["metrics_endpoint"],
                    "logsEndpoint": returned["logs_endpoint"],
                    "tracesEndpoint": returned["traces_endpoint"],
                    "credentials": {"managedIdentity": {"resource": "https://monitor.azure.com"}},
                }, "Native exporter must use exactly the service-returned endpoints and monitor audience")
        require(len(publishers) == 1 and publishers[0]["parent_id"] == returned["data_collection_rule_id"] and
                properties(publishers[0]) == {
                    "principalId": gateway["identity"][0]["principal_id"], "principalType": "ServicePrincipal",
                    "roleDefinitionId": "/subscriptions/" + gateway["id"].split("/")[2] +
                    "/providers/Microsoft.Authorization/roleDefinitions/3913510d-42f4-4e42-8a64-420c390055eb",
                }, "Native publishing must be a sole direct role for the gateway identity at the returned DCR only")
    return gateway


def check_models(resources, profile=None):
    deployments = of_type(resources, "Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview")
    require(deployments, "Model module must own actual deployments")
    for deployment in deployments.values():
        p = properties(deployment)
        require("raiPolicyName" not in p,
                "Backend RAI policy selection must be omitted, matching the Bicep deployment request")
        if profile:
            expected = profile["model_deployments"][deployment["name"]]
            require((p["model"]["name"], p["model"]["version"], p["model"]["format"],
                     deployment["body"]["sku"]["name"], deployment["body"]["sku"]["capacity"]) ==
                    (expected["model_name"], expected["model_version"], expected.get("model_format", "OpenAI"),
                     expected.get("sku_name", "GlobalStandard"), expected["capacity"]),
                    f"Model profile drift: {deployment['name']}")


def check_routes(resources, profile):
    gateway = one(resources, f"{GATEWAY}@{API}")
    provider = one(resources, f"{GATEWAY}/workspaces/modelProviders@{API}")
    p = properties(provider)["foundry"]
    require(p["authentication"] == {"kind": "ManagedIdentity",
            "managedIdentity": {"resource": "https://cognitiveservices.azure.com/"}}, "Backend MI audience drift")
    require(provider["parent_id"] == gateway["id"] + "/workspaces/default", "Provider workspace mismatch")
    catalog = {r["name"]: r for r in of_type(resources, f"{GATEWAY}/workspaces/modelProviders/models@{API}").values()}
    require(set(catalog) == set(profile["model_deployments"]), "Catalog stable deployment keys drift")
    for name, model in profile["model_deployments"].items():
        entry = catalog[name]
        p = properties(entry)
        require(entry["parent_id"] == provider["id"], "Catalog provider parent mismatch")
        require(p["deployment"]["modelName"] == name and p["deployment"]["modelVersion"] == model["model_version"],
                "Catalog backend metadata mismatch")
        require(p["deployment"]["resourceId"].lower() ==
                (properties(provider)["foundry"]["resourceIds"][0] + "/deployments/" + name).lower(),
                "Catalog points at wrong backend deployment")
        require(p["apiFormat"] == model["api_format"] and p["supportedEndpoints"] == model["endpoints"],
                "Catalog protocol metadata mismatch")
        policies = {p["type"]: p for p in p["policies"]}
        require(len(policies) == len(p["policies"]), "Model policies must not contain duplicate types")
        severity = model.get("content_safety_severity")
        if severity is None:
            require("contentSafety" not in policies, "Null or omitted gateway safety must omit the policy")
        else:
            require(policies.get("contentSafety") == {
                "type": "contentSafety",
                "hateSeverity": severity, "selfHarmSeverity": severity,
                "sexualSeverity": severity, "violenceSeverity": severity,
            }, "Gateway safety must set exactly the four selected severities without an invented policy ID")
        require(policies["tokenLimit"]["count"] == model["token_limit"] and
                policies["tokenLimit"]["counterKey"] == ["identity"], "Identity token policy drift")
        for field, kind, value in (("cost_limit", "costLimit", "amount"), ("request_limit", "requestRateLimit", "callsPerPeriod")):
            if model.get(field) is None:
                require(kind not in policies, f"Optional {kind} must be omitted")
            else:
                require(policies[kind][value] == model[field] and policies[kind]["counterKey"] == ["identity"],
                        f"Identity {kind} policy drift")
        if "requestRateLimit" in policies:
            require(policies["requestRateLimit"]["periodSeconds"] == 60, "Request limit period drift")
    aliases = {r["name"]: r for r in of_type(resources, f"{GATEWAY}/workspaces/aliases@{API}").values()}
    require(set(aliases) == set(profile["model_aliases"]), "Alias keys must not become one per deployment")
    for name, expected in profile["model_aliases"].items():
        alias = aliases[name]
        require(alias["create_headers"] == {"If-None-Match": "*"} and
                alias["delete_headers"] == {"If-Match": "*"} and
                alias["replace_triggers_refs"] == ["properties"], "Alias PUT/PATCH lifecycle guard drift")
        require(properties(alias)["aliasName"] == expected["alias_name"], "Callable alias changed")
        actual = properties(alias)["backendModels"]
        require(len(actual) == len(expected["backend_models"]), "Alias backend chain truncated")
        for route, backend in zip(actual, expected["backend_models"]):
            require(route["resourceId"] == catalog[backend["deployment"]]["id"] and
                    route.get("priority") == backend.get("priority") and route.get("weight") == backend.get("weight"),
                    "Alias priority/weight/resource routing drift")
    grants = of_type(resources, "Microsoft.Authorization/roleAssignments@2022-04-01")
    backend_grants = [r for r in grants.values() if properties(r)["roleDefinitionId"].endswith("53ca6127-db72-4b80-b1b0-d745d6d5456d")]
    return gateway, properties(provider)["foundry"], backend_grants


def check_roles(resources, custom=False, foundry_gateway_access=False, monitoring=False,
                tool_access=False, extra_model_callers=(), native_dcr_id=None, hosted_agent_principals=()):
    models = resources["module.foundry_models.azapi_resource.models"]
    agents = resources["module.foundry_agents.azapi_resource.agents"]
    project = resources["module.foundry_agents.azapi_resource.project"]
    storage = resources["module.foundry_agents.azapi_resource.storage"]
    registry = resources["module.foundry_agents.azapi_resource.registry"]
    gateway = resources["module.ai_gateway.azapi_resource.gateway"]
    cognitive = {
        "25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68",
        "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd",
        "a97b65f3-24c7-4388-baec-2e87135dc908",
    }
    project_id = project["identity"][0]["principal_id"]
    expected = {(agents["id"], project_id, role, "ServicePrincipal") for role in cognitive}
    expected |= {
        (models["id"], gateway["identity"][0]["principal_id"], "53ca6127-db72-4b80-b1b0-d745d6d5456d", "ServicePrincipal"),
        (storage["id"], project_id, "ba92f5b4-2d11-453d-a403-e96b0029c9fe", "ServicePrincipal"),
        (registry["id"], project_id, "7f951dda-4ed3-4680-a7ca-43fe172d538d", "ServicePrincipal"),
    }
    if foundry_gateway_access:
        expected |= {
            (gateway["id"], identity, "a6b68e3d-a1f0-4c60-8678-237c050cf4ea", "ServicePrincipal")
            for identity in (project_id, agents["identity"][0]["principal_id"])
        }
    if tool_access:
        expected.add((gateway["id"], project_id, "dce03f8d-857f-4e40-a90d-67770fa6ecd2", "ServicePrincipal"))
    for identity in extra_model_callers:
        expected.add((gateway["id"], identity, "a6b68e3d-a1f0-4c60-8678-237c050cf4ea", "ServicePrincipal"))
    for identity in hosted_agent_principals:
        if foundry_gateway_access:
            expected.add((gateway["id"], identity, "a6b68e3d-a1f0-4c60-8678-237c050cf4ea", "ServicePrincipal"))
        if monitoring:
            insights = resources["module.foundry_agents.azapi_resource.insights"]
            expected.add((insights["id"], identity, "3913510d-42f4-4e42-8a64-420c390055eb", "ServicePrincipal"))
    if monitoring:
        insights = resources["module.foundry_agents.azapi_resource.insights"]
        expected |= {
            (insights["id"], identity, "3913510d-42f4-4e42-8a64-420c390055eb", "ServicePrincipal")
            for identity in (project_id, agents["identity"][0]["principal_id"])
        }
    if native_dcr_id is not None:
        expected.add((native_dcr_id, gateway["identity"][0]["principal_id"],
                      "3913510d-42f4-4e42-8a64-420c390055eb", "ServicePrincipal"))
    if custom:
        developer = "00000000-0000-0000-0000-000000000005"
        expected |= {(scope, developer, role, "Group") for scope in (models["id"], agents["id"]) for role in cognitive}
        expected.add((storage["id"], developer, "ba92f5b4-2d11-453d-a403-e96b0029c9fe", "Group"))
        expected.add((gateway["id"], "00000000-0000-0000-0000-000000000006",
                      "a6b68e3d-a1f0-4c60-8678-237c050cf4ea", "ServicePrincipal"))
    actual = {
        (r["parent_id"], properties(r)["principalId"], properties(r)["roleDefinitionId"].split("/")[-1],
         properties(r)["principalType"])
        for r in of_type(resources, "Microsoft.Authorization/roleAssignments@2022-04-01").values()
    }
    require(actual == expected, f"Scoped identity/role contract drift: missing={expected - actual}; extra={actual - expected}")


def check_storage_network(resources, storage_access, other_access):
    storage = one(resources, "Microsoft.Storage/storageAccounts@2024-01-01")
    p = properties(storage)
    require(p["publicNetworkAccess"] == storage_access, "Storage override did not reach actual Storage PNA")
    acl = p["networkAcls"]
    require(acl["defaultAction"] == ("Deny" if storage_access == "Disabled" else "Allow") and
            acl["bypass"] == "AzureServices", "Storage ACL must follow its own effective access setting")
    require((acl.get("resourceAccessRules") == []) if storage_access == "Disabled"
            else "resourceAccessRules" not in acl, "Storage overlay gate must follow its own effective access setting")
    for r in resources.values():
        if r.get("type", "").startswith(("Microsoft.CognitiveServices/accounts@", "Microsoft.ContainerRegistry/registries@")):
            require(properties(r)["publicNetworkAccess"] == other_access,
                    "Storage-only override leaked into another backend")
        if r.get("type", "").startswith(("Microsoft.Insights/components@", "Microsoft.OperationalInsights/workspaces@")):
            require("publicNetworkAccessForIngestion" not in properties(r) and
                    "publicNetworkAccessForQuery" not in properties(r),
                    "Storage-only override changed monitoring defaults")


def check_agents(resources, remote_tool=False, monitoring=False, shared_registry=False, shared_remote_tool=True):
    storage = one(resources, "Microsoft.Storage/storageAccounts@2024-01-01")
    registry = one(resources, "Microsoft.ContainerRegistry/registries@2023-07-01")
    project = one(resources, "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview")
    require(properties(storage)["allowBlobPublicAccess"] is False and properties(storage)["allowSharedKeyAccess"] is False,
            "Storage key/public Blob access regressed")
    require(registry["body"]["sku"]["name"] == "Premium" and properties(registry)["adminUserEnabled"] is False,
            "Registry SKU/admin boundary regressed")
    connections = [r for address, r in resources.items()
                   if "/projects/connections@" in r.get("type", "") and "azapi_resource_action." not in address]
    categories = {"AzureStorageAccount", "ContainerRegistry", "AppInsights"} | ({"RemoteTool"} if remote_tool else set())
    require({properties(r)["category"] for r in connections} == categories,
            "Support connections and optional RemoteTool must have explicit ownership")
    for connection in connections:
        p = properties(connection)
        require(connection["parent_id"] == project["id"], "Support connection must belong to project")
        if p["category"] == "RemoteTool":
            require(connection["type"].endswith("@2025-06-01") and connection["name"] == "aigw-github" and
                    p == {"category": "RemoteTool", "authType": "ProjectManagedIdentity",
                          "audience": "https://azure-api.net/aigateway", "target": p["target"],
                          "isSharedToAll": shared_remote_tool, "metadata": {"type": "custom_MCP"}},
                    "RemoteTool must retain the upstream project-identity auth/metadata without credentials")
        elif p["category"] == "AppInsights":
            require(connection["type"].endswith("@2025-06-01") and
                    p["authType"] == ("ProjectManagedIdentity" if monitoring else "ApiKey") and
                    p["isSharedToAll"] is False and p["metadata"]["ResourceId"] == p["target"] and
                    (("credentials" not in p) if monitoring else
                     p["credentials"]["key"] == "synthetic-only-not-a-credential") and
                    "isDefault" not in p and "sharedUserList" not in p, "Project Insights contract drift")
        elif p["category"] == "ContainerRegistry":
            require(p["authType"] == "ManagedIdentity" and p["isSharedToAll"] is shared_registry and
                    p.get("isDefault") is True and
                    p["target"] == registry["output"]["properties"]["loginServer"] and
                    p["credentials"] == {"clientId": project["identity"][0]["principal_id"],
                                         "resourceId": registry["id"]} and
                    p["metadata"] == {"ResourceId": registry["id"]},
                    "Registry connection identity/sharing/default-selection drift")
        else:
            require(p["authType"] == "AAD", "Storage connection must remain AAD")
    account_connections = of_type(resources, "Microsoft.CognitiveServices/accounts/connections@2025-06-01")
    prefix = next(address for address in
                  of_type(resources, "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview")).removesuffix("azapi_resource.project")
    sharing_actions = [r for address, r in resources.items()
                       if address.startswith(prefix + "azapi_resource_action.registry_connection_sharing[")]
    require(len(sharing_actions) == int(shared_registry), "Registry reconciliation must follow the sharing opt-in")
    if shared_registry:
        owner = resources[prefix + "azapi_resource.registry_connection"]
        action = sharing_actions[0]
        require(action["method"] == "PATCH" and action["when"] == "apply" and
                action["resource_id"] == owner["id"] and action["type"] == owner["type"] and
                action["body"] == owner["body"],
                "Registry reconciliation must preserve the sole owner/API and full managed-identity payload")
    publishers = [r for address, r in of_type(resources, "Microsoft.Authorization/roleAssignments@2022-04-01").items()
                  if address.startswith(prefix) and properties(r)["roleDefinitionId"].endswith("3913510d-42f4-4e42-8a64-420c390055eb")]
    if monitoring:
        require(not account_connections and len(publishers) == 2,
                "Monitoring must retain one project Terraform owner and add exactly two publisher grants")
        connection = next(r for r in connections if properties(r)["category"] == "AppInsights")
        agents = next(r for r in resources.values()
                      if r.get("type") == "Microsoft.CognitiveServices/accounts@2025-04-01-preview" and
                      r["id"] == project["parent_id"])
        insights = next(r for r in resources.values()
                        if r.get("type") == "Microsoft.Insights/components@2020-02-02" and
                        r["id"] == properties(connection)["target"])
        require(connection["parent_id"] == project["id"] and connection["name"] == insights["name"] and
                properties(connection) == {
                    "category": "AppInsights", "authType": "ProjectManagedIdentity",
                    "isSharedToAll": False, "target": insights["id"],
                    "metadata": {"ApiType": "Azure",
                                 "ApplicationInsightsConnectionString": "synthetic-only-not-a-credential",
                                 "ResourceId": insights["id"], "displayName": insights["name"]}},
                "Sole owned Insights connection must retain project parent and match Bicep identity auth/metadata without credentials")
        require({(r["parent_id"], properties(r)["principalId"], properties(r)["principalType"])
                 for r in publishers} == {
                     (insights["id"], r["identity"][0]["principal_id"], "ServicePrincipal")
                     for r in (agents, project)},
                "Publisher assignments must target only account/project identities at exact agent Insights scope")
    else:
        require(not account_connections and not publishers,
                "Monitoring-disabled support must not add an account Insights connection or publisher grants")
    roles = of_type(resources, "Microsoft.Authorization/roleAssignments@2022-04-01")
    for suffix, scope in (("ba92f5b4-2d11-453d-a403-e96b0029c9fe", storage["id"]),
                          ("7f951dda-4ed3-4680-a7ca-43fe172d538d", registry["id"])):
        require(any(properties(r)["roleDefinitionId"].endswith(suffix) and r["parent_id"] == scope for r in roles.values()),
                "Missing scoped project Storage/ACR grant")


def check_model_readback_states(messages):
    """Check dependent writes, not known outputs retained in a failed partial state."""
    states = {m["@testrun"]: m["test_state"] for m in messages if m.get("type") == "test_state"}
    require(MODEL_READBACK_RUNS <= states.keys(), "Model-account mock-apply states missing")
    for run in MODEL_READBACK_RUNS:
        state = states[run]
        owners = {r["address"] for r in state["root_module"].get("resources", []) if r["mode"] == "managed"}
        if run.startswith("reject_"):
            require(owners == {"azapi_resource.models"},
                    f"{run}: failed account readback must block dependent model and developer-grant creation")
        else:
            require(owners == {"azapi_resource.models"} | {
                        f'azapi_resource.model_deployment["{key}"]' for key in PROFILE_PINS
                    } and set(state.get("outputs", {})) == {"account_id", "endpoint", "deployment_ids", "backend"},
                    "Confirmed model-only account must preserve all deployments and outputs")


def check_plans():
    messages = [json.loads(line) for line in sys.stdin if line.strip()]
    plans = {m["@testrun"]: m["test_plan"] for m in messages if m.get("type") == "test_plan"}
    passed_runs = {m["@testrun"] for m in messages
                   if m.get("type") == "test_run" and m["test_run"].get("status") == "pass"}
    require(REGISTRY_READBACK_RUNS <= passed_runs,
            "Registry readback postconditions must be exercised with provider-mocked applies")
    require(MODEL_READBACK_RUNS <= passed_runs,
            "Model-account readback postconditions must be exercised with provider-mocked applies")
    check_model_readback_states(messages)
    expected = {"root_default", "root_minimal", "root_custom", "root_single_group", "gateway_module", "models_module",
                "agents_module", "gateway_only", "existing_models", "existing_models_pregranted",
                "models_only", "agent_support_only", "root_replacement_profile", "root_backend_revision", "existing_models_custom_profile",
                "root_disabled_backends", "existing_outbound_subnet", "root_storage_only_disabled",
                "agents_storage_enabled_override", "reject_storage_network_enum", "agent_support_storage_disabled"}
    expected |= {"root_foundry_gateway_model_access", "root_remote_tool", "root_both_integrations",
                 "reject_remote_tool_http", "reject_remote_tool_credentials", "reject_remote_tool_query",
                 "reject_remote_tool_origin", "reject_duplicate_foundry_gateway_owners"}
    expected |= {"root_foundry_gateway_tool_access", "root_tool_access_with_model_caller"}
    hosted_scenarios = {
        "root_hosted_agent_runtime_access": (
            "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b"
        ),
        "root_hosted_agent_runtime_access_disabled": ("00000000-0000-0000-0000-00000000000a",),
        "root_hosted_agent_models_only": ("00000000-0000-0000-0000-00000000000a",),
        "root_hosted_agent_monitoring_only": ("00000000-0000-0000-0000-00000000000a",),
    }
    expected |= hosted_scenarios.keys() | {
        "reject_hosted_agent_invalid_principal", "reject_hosted_agent_duplicate_principals",
        "reject_hosted_agent_account_identity", "reject_hosted_agent_project_identity",
        "reject_duplicate_hosted_gateway_owners",
    }
    expected |= {"agents_monitoring_integration", "agents_shared_registry", "root_monitoring_integration",
                 "root_all_integrations", "root_project_local_registry", "root_project_local_remote_tool",
                 "agent_support_monitoring_integration", "alias_protocol_intersection"}
    expected |= {"root_content_safety_overrides", "root_content_safety_disabled", "root_optional_request_limits",
                 "existing_models_content_safety", "models_gateway_safety_metadata"}
    expected |= {"root_model_account_name_override", "reject_empty_model_account_name",
                 "reject_invalid_model_account_name", "reject_long_model_account_name"}
    native_ready = {"native_telemetry_ready", "root_native_telemetry", "gateway_only_native", "existing_models_native"}
    legacy = {"gateway_legacy_telemetry", "root_legacy_telemetry"}
    expected |= native_ready | legacy | {
        "reject_native_handoff_identity", "reject_stale_native_endpoints", "reject_unready_native_readback",
        "reject_cross_subscription_native_dcr", "reject_credential_native_endpoint", "reject_legacy_with_native_handoff",
    }
    require(expected <= plans.keys(), f"Missing real mock plans: {sorted(expected - plans.keys())}")
    profile = json.loads((ROOT / "model-profile.json").read_text(encoding="utf-8-sig"))
    # Native test_plan messages omit input variables: keep an independent scenario oracle.
    # Tuple order is model access, tool access, monitoring, registry sharing.
    root_settings = {
        "root_minimal": (False, False, False, False),
        "root_foundry_gateway_model_access": (True, False, False, False),
        "root_foundry_gateway_tool_access": (False, True, False, False),
        "root_tool_access_with_model_caller": (False, True, False, False),
        "root_remote_tool": (False, False, False, False),
        "root_both_integrations": (True, False, False, False),
        "root_monitoring_integration": (False, False, True, False),
        "root_project_local_registry": (True, True, True, False),
        "root_hosted_agent_runtime_access_disabled": (False, True, False, True),
        "root_hosted_agent_models_only": (True, False, False, True),
        "root_hosted_agent_monitoring_only": (False, False, True, True),
    }
    for name, plan in plans.items():
        resources = resource_map(plan)
        telemetry = "native" if name in native_ready else "legacy" if name in legacy else "pending"
        require(not any("/toolServers@" in r.get("type", "") for r in resources.values()),
                "ToolServer ownership belongs to the explicit-credential runner, never Terraform")
        accounts = of_type(resources, "Microsoft.CognitiveServices/accounts@2025-04-01-preview")
        project_parents = {r["parent_id"] for r in
                           of_type(resources, "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview").values()}
        for account in accounts.values():
            require(properties(account)["allowProjectManagement"] is (account["id"] in project_parents) and
                    properties(account)["disableLocalAuth"] is True,
                    f"{name}: only the agent/project account may enable project management; local auth must remain disabled")
        if name.startswith("root_"):
            gateway = check_gateway(resources, telemetry)
            model_access, tool_access, monitoring, shared_registry = root_settings.get(name, (True, True, True, True))
            check_agents(resources, name in {"root_remote_tool", "root_both_integrations", "root_all_integrations",
                                            "root_project_local_registry", "root_project_local_remote_tool"},
                         monitoring, shared_registry, shared_remote_tool=name != "root_project_local_remote_tool")
            check_roles(resources, custom=name == "root_custom",
                        foundry_gateway_access=model_access,
                        monitoring=monitoring, tool_access=tool_access,
                        extra_model_callers={
                            "root_tool_access_with_model_caller": ("00000000-0000-0000-0000-000000000004",),
                            "root_hosted_agent_monitoring_only": ("00000000-0000-0000-0000-00000000000a",),
                        }.get(name, ()),
                        hosted_agent_principals=hosted_scenarios.get(name, ()),
                        native_dcr_id=(resources["module.ai_gateway.azapi_resource.insights"]["output"]["data_collection_rule_id"]
                                       if name in native_ready else None))
            integration = plan["output_changes"]["deployment_contract"]["after"]["integration"]
            require(plan["output_changes"]["deployment_contract"]["after"]["agents"]["registry_connection_id"] ==
                    resources["module.foundry_agents.azapi_resource.registry_connection"]["id"],
                    "The application handoff must export the owned registry connection ID")
            bootstrap = plan["output_changes"]["gateway_toolchain_bootstrap"]["after"]
            agents = resources["module.foundry_agents.azapi_resource.project"]
            require(bootstrap == {
                "version": 1,
                "subscription_id": gateway["id"].split("/")[2],
                "gateway_id": gateway["id"],
                "workspace_id": gateway["id"] + "/workspaces/default",
                "gateway_endpoint": plan["output_changes"]["gateway_endpoint"]["after"],
                "api_version": API,
                "project_id": agents["id"],
                "project_endpoint": plan["output_changes"]["project_endpoint"]["after"],
                "tool_access_enabled": tool_access,
                "remote_tool_connection_id": integration["remote_tool_connection_id"],
                "remote_tool_endpoint": integration["remote_tool_endpoint"],
            }, "Toolchain bootstrap must be an exact nonsecret handoff from the owning resources")
            require(integration["gateway_model_access_enabled"] == model_access and
                    integration["gateway_tool_access_enabled"] == tool_access and
                    integration["registry_connection_shared"] == shared_registry,
                    "Nonsecret output must describe the actually selected model/tool grants and registry sharing")
            require(integration["monitoring_enabled"] == monitoring and
                    (integration["insights_connection_id"] is None if not monitoring else
                     integration["insights_connection_id"] ==
                     resources["module.foundry_agents.azapi_resource.project_insights_connection"]["id"]),
                    "Nonsecret output must describe the actually selected monitoring integration")
            if name == "root_storage_only_disabled":
                check_storage_network(resources, "Disabled", "Enabled")
            if name != "root_replacement_profile":
                check_models(resources, profile)
                selected_profile = json.loads(json.dumps(profile))
                for key, model in selected_profile["model_deployments"].items():
                    model.update(content_safety_severity="Medium", request_limit=None)
                    if name == "root_custom":
                        model.update(cost_limit=None, request_limit=7, content_safety_severity=None)
                    elif name == "root_optional_request_limits":
                        model["request_limit"] = {
                            "gpt-latest": 1, "gpt-6-sol": None, "gpt-mini-latest": None,
                        }[key]
                    elif name == "root_content_safety_disabled":
                        model["content_safety_severity"] = None
                    elif name == "root_content_safety_overrides":
                        model["content_safety_severity"] = {
                            "gpt-latest": "Low", "gpt-6-sol": "High", "gpt-mini-latest": None,
                        }[key]
                _, _, grants = check_routes(resources, selected_profile)
                require(len(grants) == 1, "Gateway must own exactly its backend Foundry User grant")
                require(grants[0]["body"]["properties"]["principalId"] == gateway["identity"][0]["principal_id"],
                        "Backend grant must target gateway MI, never an agent identity")
            if name in {"root_custom", "root_content_safety_overrides"}:
                for entry in of_type(resources, f"{GATEWAY}/workspaces/modelProviders/models@{API}").values():
                    filters = [p for p in properties(entry)["policies"] if p["type"] == "ipFilter"]
                    require(filters == [{"type": "ipFilter", "action": "Allow",
                            "cidrRanges": ["2001:db8:1234::/48", "203.0.113.42/32"]}],
                            "Optional CIDR policy must sort/deduplicate approved addresses")
            if name == "root_custom":
                require(gateway["tags"]["fixture"] == "forwarded", "Root lost explicit caller tags")
            groups = of_type(resources, "Microsoft.Resources/resourceGroups@2021-04-01")
            require(len(groups) == (1 if name == "root_single_group" else 3), "Fresh root group composition drift")
            group_ids = {r["id"] for r in groups.values()}
            for r in resources.values():
                if r.get("type", "").split("@")[0] in {
                    GATEWAY, "Microsoft.CognitiveServices/accounts", "Microsoft.Storage/storageAccounts",
                    "Microsoft.ContainerRegistry/registries", "Microsoft.Insights/components",
                    "Microsoft.OperationalInsights/workspaces",
                }:
                    require(r["parent_id"] in group_ids, "Workload escaped owned groups")
            for address, r in resources.items():
                if r.get("type", "").split("@")[0] in {
                    GATEWAY, "Microsoft.CognitiveServices/accounts", "Microsoft.Storage/storageAccounts",
                    "Microsoft.ContainerRegistry/registries", "Microsoft.Insights/components",
                    "Microsoft.OperationalInsights/workspaces",
                }:
                    group = ("gateway" if name == "root_single_group" or ".ai_gateway." in address
                             else "models" if ".foundry_models." in address else "agents")
                    require(r["parent_id"] == resources[f'azapi_resource.resource_group["{group}"]']["id"],
                            f"Actual three-workload placement drift: {address}")
            for r in resources.values():
                p = properties(r)
                if "publicNetworkAccess" in p:
                    disabled = name == "root_disabled_backends" or (
                        name == "root_storage_only_disabled" and r.get("type", "").startswith("Microsoft.Storage/storageAccounts@"))
                    require(p["publicNetworkAccess"] == ("Disabled" if disabled else "Enabled"),
                            "Explicit backend network posture did not reach actual resources")
                if r.get("type", "").startswith(("Microsoft.Insights/components@", "Microsoft.OperationalInsights/workspaces@")):
                    for flag in ("publicNetworkAccessForIngestion", "publicNetworkAccessForQuery"):
                        require((p.get(flag) == "Disabled") if name == "root_disabled_backends" else flag not in p,
                                "Monitoring must preserve unspecified defaults or explicit disablement")
        elif name in {"gateway_module", "gateway_only", "gateway_only_native", "native_telemetry_ready", "gateway_legacy_telemetry"}:
            check_gateway(resources, telemetry)
            require(not accounts and not any("Microsoft.CognitiveServices/" in r.get("type", "") for r in resources.values()),
                    "Gateway-only must not own models, projects or agents")
            require(not any("/modelProviders" in r.get("type", "") or "/aliases@" in r.get("type", "")
                            for r in resources.values()), "Gateway-only must not invent a backend")
        elif name in {"models_module", "models_only", "models_gateway_safety_metadata"}:
            check_models(resources, profile)
            require(not any("Microsoft.ApiManagement/" in r.get("type", "") or "/projects@" in r.get("type", "")
                            for r in resources.values()), "Models-only acquired gateway/agent ownership")
        elif name in {"agents_module", "agent_support_only", "agents_storage_enabled_override", "agent_support_storage_disabled",
                      "agents_monitoring_integration", "agent_support_monitoring_integration", "agents_shared_registry"}:
            check_agents(resources, monitoring=name.endswith("monitoring_integration"),
                         shared_registry=name == "agents_shared_registry")
            if name == "agents_storage_enabled_override":
                check_storage_network(resources, "Enabled", "Disabled")
            elif name == "agent_support_storage_disabled":
                check_storage_network(resources, "Disabled", "Enabled")
            require(not any("Microsoft.ApiManagement/" in r.get("type", "") or "/deployments@" in r.get("type", "")
                            for r in resources.values()), "Agent support acquired models/gateway ownership")
        elif name == "reject_storage_network_enum":
            require(not any(properties(r).get("publicNetworkAccess") == "Private" for r in resources.values()),
                    "Rejected Storage enum reached a resource plan")
        elif name.startswith("existing_models"):
            gateway = check_gateway(resources, telemetry)
            require(not accounts and not of_type(resources, "Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview"),
                    "Referencing existing models must not adopt/create the account or deployments")
            grants = [r for r in of_type(resources, "Microsoft.Authorization/roleAssignments@2022-04-01").values()
                      if properties(r)["roleDefinitionId"].endswith("53ca6127-db72-4b80-b1b0-d745d6d5456d")]
            require(len(grants) == (0 if name.endswith("pregranted") else 1), "Existing backend grant ownership must be exclusive")
            provider = one(resources, f"{GATEWAY}/workspaces/modelProviders@{API}")
            descriptor = properties(provider)["foundry"]
            require(descriptor["endpoint"] == "https://existing.example.invalid/" and
                    descriptor["resourceIds"] == ["/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing"],
                    "Existing account descriptor did not reach provider")
            if grants:
                require(grants[0]["parent_id"] == descriptor["resourceIds"][0] and
                        properties(grants[0])["principalId"] == gateway["identity"][0]["principal_id"],
                        "Existing-model grant must scope the gateway identity to only the external account")
            if name != "existing_models_custom_profile":
                selected_profile = json.loads(json.dumps(profile))
                if name == "existing_models_content_safety":
                    for model in selected_profile["model_deployments"].values():
                        model["content_safety_severity"] = "Medium"
                check_routes(resources, selected_profile)
    summaries = [m["test_summary"] for m in messages if m.get("type") == "test_summary"]
    require(summaries and summaries[-1]["passed"] > 0 and summaries[-1].get("failed", 0) == 0,
            "No successful native Terraform test summary")
    default = resource_map(plans["root_default"])
    minimal = resource_map(plans["root_minimal"])
    for run, baseline in (
        ("root_content_safety_overrides", "root_default"),
        ("root_content_safety_disabled", "root_default"),
        ("existing_models_content_safety", "existing_models"),
        ("models_gateway_safety_metadata", "models_module"),
    ):
        require(set(resource_map(plans[run])) == set(resource_map(plans[baseline])),
                f"{run}: content safety must not change resource ownership")
    require(len(minimal) == 32 and len(default) == 38,
            "The full root adds five grants and one non-owning registry PATCH; native stage one defers the exporter")
    hosted = resource_map(plans["root_hosted_agent_runtime_access"])
    require(set(hosted) - set(default) == {
                f'azapi_resource.hosted_agent_runtime_access["{role}-{label}"]'
                for role in ("models", "monitoring") for label in ("digest", "second")
            } and not set(default) - set(hosted),
            "Explicit hosted identities must add only their two resource-scoped grants without changing existing owners")
    ready = resource_map(plans["root_native_telemetry"])
    legacy_resources = resource_map(plans["root_legacy_telemetry"])
    require(set(ready) - set(default) == {
                "module.ai_gateway.azapi_resource.telemetry_exporter[0]",
                "module.ai_gateway.azapi_resource.telemetry_publisher[0]",
            } and not set(default) - set(ready), "Native stage two must add only the exporter and direct DCR publisher")
    require(set(legacy_resources) - set(default) == {"module.ai_gateway.azapi_resource.telemetry_exporter[0]"} and
            not set(default) - set(legacy_resources), "Legacy compatibility must retain the exporter without DCR ownership")
    require(set(default) - set(minimal) == {
                'azapi_resource.foundry_gateway_model_access["account"]',
                'azapi_resource.foundry_gateway_model_access["project"]',
                'azapi_resource.foundry_gateway_tool_access["project"]',
                'module.foundry_agents.azapi_resource.role_assignment["monitoring-account"]',
                'module.foundry_agents.azapi_resource.role_assignment["monitoring-project"]',
                'module.foundry_agents.azapi_resource_action.registry_connection_sharing[0]',
            } and not set(minimal) - set(default),
            "Default wiring must preserve every existing owner and add only five grants and the registry PATCH")
    for run, additions in (("root_foundry_gateway_model_access", 2), ("root_foundry_gateway_tool_access", 1),
                           ("root_remote_tool", 1),
                           ("root_both_integrations", 3)):
        resources = resource_map(plans[run])
        added = set(resources) - set(minimal)
        require(len(resources) == 32 + additions and len(added) == additions and
                all(address.startswith(("azapi_resource.foundry_gateway_model_access[",
                                        "azapi_resource.foundry_gateway_tool_access[",
                                        "azapi_resource.gateway_remote_tool[")) for address in added),
                f"{run}: integration must add only root-owned selected resources")
    tool_callers = resource_map(plans["root_tool_access_with_model_caller"])
    require(set(tool_callers) - set(minimal) == {
                'azapi_resource.foundry_gateway_tool_access["project"]',
                'module.ai_gateway.azapi_resource.role_assignment["gateway-models-user-project"]',
            } and not set(minimal) - set(tool_callers),
            "Distinct project model/tool roles must coexist without duplicate ownership or unrelated resources")
    for run, baseline, prefix in (
        ("agents_monitoring_integration", "agents_module", ""),
        ("agent_support_monitoring_integration", "agent_support_only", "module.component."),
        ("root_monitoring_integration", "root_minimal", "module.foundry_agents."),
        ("root_all_integrations", "root_both_integrations", "module.foundry_agents."),
    ):
        resources = resource_map(plans[run])
        retained = resource_map(plans[baseline])
        expected_added = {prefix + address for address in (
            'azapi_resource.role_assignment["monitoring-account"]',
            'azapi_resource.role_assignment["monitoring-project"]',
        )}
        if run == "root_all_integrations":
            expected_added.add('azapi_resource.foundry_gateway_tool_access["project"]')
            expected_added.add(prefix + "azapi_resource_action.registry_connection_sharing[0]")
        require(set(resources) - set(retained) == expected_added and
                not set(retained) - set(resources),
                f"{run}: only selected grants and the sharing action may be added; preserve every existing connection address")
    spec = importlib.util.spec_from_file_location("export_environment", ROOT / "scripts" / "export_environment.py")
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    spec = importlib.util.spec_from_file_location("wait_for_telemetry", ROOT / "scripts" / "wait_for_telemetry.py")
    readiness_helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(readiness_helper)
    for name in native_ready | {"root_default", "root_legacy_telemetry"}:
        plan = plans[name]
        outputs = plan["output_changes"]
        bootstrap = outputs["gateway_telemetry_bootstrap"]["after"]
        monitoring = outputs["gateway_monitoring"]["after"]
        resources = resource_map(plan)
        gateway = one(resources, f"{GATEWAY}@{API}")
        require(bootstrap["gateway_id"] == gateway["id"] and
                bootstrap["gateway_principal_id"] == gateway["identity"][0]["principal_id"] and
                bootstrap["insights_id"] == monitoring["insights_id"] and
                bootstrap["log_analytics_id"] == monitoring["log_analytics_id"],
                f"{name}: bootstrap must describe the actual graph, not unrelated resources")
        if name != "root_legacy_telemetry":
            readiness_helper.validate_bootstrap(bootstrap, bootstrap["subscription_id"])
        require(monitoring["configuration_status"] ==
                ("configured" if name in native_ready else "legacy" if name in legacy else "pending"),
                f"{name}: monitoring output must distinguish pending, configured and legacy")
    application_plans = {name: plan for name, plan in plans.items()
                         if name.startswith("root_") or name == "alias_protocol_intersection"}
    for name, plan in application_plans.items():
        for resource in resource_map(plan).values():
            resource_type = resource["type"].split("@")[0]
            if resource_type == "Microsoft.Resources/resourceGroups":
                resource_path = "/resourceGroups"
            elif resource_type in {GATEWAY, "Microsoft.CognitiveServices/accounts",
                                   "Microsoft.Storage/storageAccounts", "Microsoft.ContainerRegistry/registries"}:
                resource_path = "/providers/" + resource_type
            elif resource_type in {"Microsoft.CognitiveServices/accounts/projects",
                                   "Microsoft.CognitiveServices/accounts/deployments"}:
                resource_path = "/" + resource_type.rsplit("/", 1)[-1]
            else:
                continue
            expected_id = resource["parent_id"] + resource_path + "/" + resource["name"]
            require(resource["id"].lower() == expected_id.lower(),
                    f"{name}: mock ID must match the planned parent, type and name: {resource_type}")
        contract = plan["output_changes"]["deployment_contract"]["after"]
        keys = ("custom-route", "custom-route") if name == "root_replacement_profile" else (
            "primary-router", "mini-router")
        try:
            mapping = adapter.environment_mapping(contract, *keys)
        except (ValueError, KeyError, TypeError) as error:
            raise AssertionError(f"{name}: native output is incompatible with the environment adapter: {error}") from error
        expected_aliases = ("custom-callable", "custom-callable") if name == "root_replacement_profile" else (
            "gpt-latest", "gpt-mini-latest")
        require((mapping["AZURE_AI_GATEWAY_MODEL"], mapping["AZURE_AI_GATEWAY_MINI_MODEL"]) == expected_aliases and
                mapping["AZURE_AI_GATEWAY_ENDPOINT"] == plan["output_changes"]["gateway_endpoint"]["after"] + "/" and
                "TOOLBOX_ENDPOINT" not in mapping and "AZURE_AI_GATEWAY_API_KEY" not in mapping,
                f"{name}: actual root output must feed the explicit nonsecret application adapter")
    print(f"PASS {len(application_plans)} native root environment handoffs, including Responses-only aliases")
    revised = resource_map(plans["root_backend_revision"])
    gateway_address = "module.ai_gateway.azapi_resource.gateway"
    require(default[gateway_address]["name"] == revised[gateway_address]["name"], "Backend revision renamed retained gateway")
    for address in ("module.foundry_models.azapi_resource.models", "module.foundry_agents.azapi_resource.agents"):
        require(default[address]["name"] != revised[address]["name"], "Backend revision failed to isolate rebuilt backend")
    renamed = resource_map(plans["root_model_account_name_override"])
    account_address = "module.foundry_models.azapi_resource.models"
    require(renamed[account_address]["name"] == "aimodels-offline-candidate" and
            properties(renamed[account_address])["customSubDomainName"] == "aimodels-offline-candidate",
            "The model-only override must set the actual account name and custom subdomain")
    require(default.keys() == renamed.keys(), "A model-only name must not change resource ownership")
    affected = {account_address, "module.ai_gateway.azapi_resource.backend_role_assignment[0]",
                "module.ai_gateway.azapi_resource.foundry_provider[0]"} | {
                    f'module.foundry_models.azapi_resource.model_deployment["{key}"]' for key in PROFILE_PINS
                } | {
                    f'module.ai_gateway.azapi_resource.catalog_model["{key}"]' for key in PROFILE_PINS
                }
    for address in default.keys() - affected:
        require(all(default[address].get(field) == renamed[address].get(field)
                    for field in ("name", "parent_id", "location", "tags", "body")),
                f"Model-only naming changed unrelated configuration: {address}")
    owners = {r["address"] for r in plans["root_default"]["resource_changes"]
              if r["mode"] == "managed" and r["type"] == "azapi_resource"}
    counts = {scope: sum(a.startswith("module." + scope + ".") for a in owners)
              for scope in ("foundry_models", "ai_gateway", "foundry_agents")}
    counts["root"] = sum(not a.startswith("module.") for a in owners)
    roles = len(of_type(default, "Microsoft.Authorization/roleAssignments@2022-04-01"))
    print(f"Default root observation: {len(owners)} Azure owners, {len(default) - len(owners)} non-owning action, "
          f"{roles} scoped roles; owners={counts}")
    print(f"PASS {len(plans)} real native mock plans; {summaries[-1]['passed']} Terraform runs; semantic contracts inspected")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structure", action="store_true")
    parser.add_argument("--plans", action="store_true")
    args = parser.parse_args()
    try:
        if args.structure:
            check_structure()
        if args.plans:
            check_plans()
        require(args.structure or args.plans, "Select --structure or --plans")
    except (AssertionError, KeyError, ValueError, TypeError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        sys.exit(1)
