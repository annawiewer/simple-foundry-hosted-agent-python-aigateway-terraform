# Preparation, contracts and ownership

One Terraform composition root calls three independent capability modules.
The opt-in [application flow](application-flow.md) connects its staged handoffs
to the root Python agent and a separately enabled routine, without invoking Bicep
provisioning. The current-source hosted digest, model-only backend cutover,
bounded cost rejection and one creator-readable scheduled digest have separate
accepted evidence. Native safety denial, historical response access and the
recurring MCP authorization error remain unresolved; broader lifecycle
guarantees are not established. See the
[acceptance matrix](evidence-map.md#acceptance-matrix).

## Offline and deployment preparation

From the repository root, use PowerShell 7, Python 3 and Terraform 1.11.4 with
the checked-in AzAPI 2.13.0 locks:

```powershell
pwsh -NoProfile -File infra\scripts\Test-Offline.ps1

$TerraformRoot = 'infra'
# Or one directory under infra\examples.
Copy-Item "$TerraformRoot\terraform.tfvars.example" "$TerraformRoot\terraform.tfvars"
```

Do not overwrite existing deployment inputs. The runner uses mocked providers,
backend-disabled initialization and read-only locks. It makes no Azure calls;
registry access may be needed for uncached providers. Use host-native path
separators on non-Windows systems.

Replace the synthetic subscription and choose unique names. Qualify service
enablement, locations, model versions/SKUs and quota for the actual target.
The full root requires `subscription_id`, `location` and `gateway_location`.
Examples require `subscription_id` and `location`; `existing-models` also needs
its real backend descriptor.

Before Azure-enabled planning, select fresh state and an authorized target.
Do not reuse old wrapper state, backend keys or deployed names. Authenticate a
principal permitted to create the declared resources and scoped roles; keep
credentials out of tfvars, command output and Git. Each independent example
needs unique names and its own state/backend key.

Local state is the single-operator default. Shared use requires a separately
reviewed remote backend with authenticated, locked storage; no backend bootstrap
is included. State, saved plans and `.terraform` data can contain connection
strings even though the published outputs are nonsecret.

After reviewing the target and ownership:

```powershell
terraform "-chdir=$TerraformRoot" init -input=false -lockfile=readonly
terraform "-chdir=$TerraformRoot" plan -input=false
```

These are Azure-enabled commands, not part of the offline check. Review the
current plan before authorizing apply; no automatic deployment is implied.
Continue according to the selected root:

- **Models-only or agent-support-only:** separately authorize that root's apply
  with the same workspace and inputs, then use the outputs in the
  [models-only](../examples/models-only/README.md) or
  [agent-support-only](../examples/agent-support-only/README.md) README.
  These examples have no gateway telemetry or application stages.
- **Full root, gateway-only or existing-models:** native gateway telemetry
  defaults to a pending first stage. Follow the
  [native telemetry guide](native-telemetry.md) for both applies, the explicit
  readiness handoff and a fresh second-stage plan. Keep the same root/workspace
  and original inputs; the initial plan is not a completed exporter plan.
  If deliberately retaining legacy telemetry, follow its
  [compatibility guidance](native-telemetry.md#legacy-compatibility) instead.

Only the **full root** optionally continues to the
[guided application sequence](application-flow.md) for the tool handoffs,
isolated offline preparation and separately authorized agent and schedule
operations. It never substitutes native azd Terraform provisioning for this
locked, explicit plan/apply process.

## Ownership and graph

| Owner | Scope |
|---|---|
| Composition root | Naming/tags, three new workload groups, module composition, default Foundry gateway grants, opt-in deployed-agent runtime grants, optional RemoteTool and outputs |
| [foundry-models](../modules/foundry-models/README.md) | Model account, serialized deployments, backend filters and optional developer grants |
| [ai-gateway](../modules/ai-gateway/README.md) | Gateway/identity, key resource, monitoring/exporter, backend grant, provider/catalog/aliases and selected model callers |
| [foundry-agents](../modules/foundry-agents/README.md) | Account/project, Storage/ACR, monitoring, internal grants and three support connections |
| Explicit [tool runner](toolchain.md), outside Terraform | Whole GitHub ToolServer/credential lifecycle and one Foundry Toolbox; no overlapping connection writer |
| Explicit [application helper](application-flow.md), outside Terraform | Isolated azd app workspace, one agent deployment attempt and a separately authorized routine; no infrastructure, connection, tool or role writer |
| External owner | Referenced existing model resources, outbound subnet/private connectivity and optional backend pregrant |

The service owns the default gateway workspace. The root configures providers;
child modules only declare requirements. All configuration dependencies are
bundled here.

```text
root -> model account -> independent flag GET -> serialized deployments -> backend descriptor
root -> gateway + identity
gateway monitoring -> GET-only readiness handoff -> fresh plan -> DCR grant -> exporter
backend descriptor + gateway identity -> backend grant -> provider -> catalog -> aliases
root -> agent account/project -> support grants -> Storage/ACR connections
tool runner -> ToolServer -> explicit endpoint handoff -> Terraform RemoteTool -> tool runner Toolbox
applied contract + connected bootstrap + Toolbox receipt -> offline app workspace -> agent
agent-version identity readback -> opt-in runtime grants -> on-demand acceptance -> explicit schedule gate
```

The gateway owns its backend grant to avoid a sibling-module RBAC cycle.
Stable keys, not computed IDs, select resource instances. Role creation does
not establish propagation or runtime authorization.

## Root inputs and outputs

| Input | Behavior |
|---|---|
| `model_deployments`, `model_aliases` | Null selects the bundled [profile](../model-profile.json). Custom deployment keys need compatible aliases. Root null aliases select the profile, unlike the gateway module's per-deployment default. |
| `gateway_access_principals` | Explicit gateway-scoped Models User callers; no tool grant |
| `hosted_agent_principals` | Empty by default. Stable labels map to independently verified deployed-agent principal UUIDs for root-owned model/telemetry grants; no automatic role adoption or direct tool grant. |
| `gateway_telemetry_mode`, `gateway_native_telemetry` | Default `OpenTelemetry` with null handoff leaves export pending. The [staged path](native-telemetry.md) creates the DCR publisher/exporter; explicit `ApplicationInsights` retains legacy compatibility. |
| `developer_principal_id`, `developer_principal_type` | Optional model/agent developer grants, not gateway tool access |
| `api2026_resource_group_name` | Optional single **new owned** group; not adoption, consolidation or migration |
| `gateway_backend_subnet_id` | Existing creation-only outbound subnet, delegated to `Microsoft.App/environments` in the gateway region; no private ingress or network provisioning |
| `standalone_backend_public_network_access` | Disabling backends requires the outbound subnet and independently working private connectivity |
| `agent_storage_public_network_access` | Storage-only override; otherwise inherits the global setting, then Enabled. Disabled creates no private endpoint/DNS or working hosted-compute path. |
| `backend_revision` | Deliberately changes backend names/replacement without renaming the gateway; not automatic recovery |

[`outputs.tf`](../outputs.tf) defines the nonsecret version-1
`deployment_contract`: IDs, endpoints, principals, aliases, selected integration
metadata and deferred ownership. It contains no runtime key value, GitHub
credential or invented ToolServer/Toolbox endpoint. Use `gateway_api_versions`
for actual API pins. Historical `2026` compatibility labels, naming salts and
`api2026_resource_group_name` are retained to avoid renaming existing resources;
they are not API-version selectors.
The separate root-only `gateway_toolchain_bootstrap` output carries the exact
gateway/project and selected connection metadata to the opt-in tool runner.
No new tool resource, role or default behavior is introduced by this output.

## Optional application integration

The application root enables model access, project-only tool access, Foundry
monitoring and registry sharing by default. Each can be disabled independently.
Reusable modules and standalone examples retain their minimal defaults.
These settings do not deploy an application or provision its tools.

| Setting | Root default | Managed change |
|---|---|---|
| `enable_foundry_gateway_model_access` | `true` | Root-owned gateway-scoped Models User grants for account/project and any explicit `hosted_agent_principals`. Do not duplicate these bindings in `gateway_access_principals`. |
| `enable_foundry_gateway_tool_access` | `true` | One root-owned gateway-scoped Tools User grant for the project only. No account/developer tool permission or ToolServer creation. |
| `enable_foundry_monitoring_integration` | `true` | In-place project Insights connection switch to managed identity and publisher grants for account/project and any explicit `hosted_agent_principals` at agent Insights scope. No second connection owner. |
| `share_foundry_registry_connection` | `true` | Request sharing on the existing project-managed-identity registry connection, matching Bicep. Explicit false supports project-local compatibility; neither choice changes registry admin or the registry-scoped project AcrPull grant. |
| `share_foundry_remote_tool_connection` | `true` | Request sharing on the project-owned RemoteTool, matching Bicep. Explicit false supports independently verified project-local compatibility without changing authentication, target or gateway tool permissions. |
| `gateway_remote_tool_endpoint` | `null` | Explicit service-established HTTPS MCP URL on this gateway; creates the project-owned `aigw-github` RemoteTool with managed-identity auth and the selected sharing request. No guessed URL, credential or Toolbox. |

**Upgrading an existing root:** omitted switches now select five additional
scoped grants and managed-identity/shared-connection bodies. Review a fresh plan
against the original inputs; names and Terraform resource addresses are unchanged.
To omit these application integrations, explicitly set:

```hcl
enable_foundry_gateway_model_access   = false
enable_foundry_gateway_tool_access    = false
enable_foundry_monitoring_integration = false
share_foundry_registry_connection     = false
```

These switches do not disable the bundled root profile's `Medium` gateway model
content safety. To retain previous policy omission, supply a complete deployment
map with null severities; see [content-safety defaults and opt-outs](../README.md#model-content-safety).

Changing these values on an already configured deployment can remove grants or
change connection authentication/sharing. No state adoption or automatic
migration is included. The nonsecret contract reports integration settings,
including `integration.registry_connection_shared`, which reports the configured
sharing request rather than independent Azure readback. Review RemoteTool
sharing in the saved plan and independent connection readback.

A selected RemoteTool waits for the selected tools grant, not for proven
propagation. Model access is independent. The connection API remains
`2025-06-01`, with provider schema validation disabled for its auth contract.
The monitoring option affects **Foundry agent monitoring**, not the gateway's
separate native OpenTelemetry stages. Omitting ApiKey credentials in the
managed-identity body does not establish stored credential erasure.

The actual hosted Agent Identity is a separate postdeployment input, not a
substitute for either support identity. Follow the
[identity handoff and existing-role import boundary](application-flow.md#3-bind-the-deployed-agent-identity).
With the default empty map, the root still owns the same 37 stage-one resources
and 11 scoped roles; no hosted identity is inferred and no permission is added.

### Project-local registry compatibility

The root retains the Bicep-matching sharing request by default. In the
November 6, 2026 deployment, Azure returned `isSharedToAll=false` despite that
request, while the project's connections API listed the exact owned registry
connection with its expected target and registry ID. This observation does not
establish why the service returned false or how every region/API behaves.

The November 7 qualification isolated a further difference: a full PATCH
retained sharing/default=true, but a subsequent Terraform PUT reset sharing.
Shared mode now orders a non-owning PATCH after the sole connection owner,
then verifies both flags through a blocking GET postcondition. Owner changes
rerun the PATCH; ordinary refresh still detects drift. This does not change
the API, add a connection owner or broaden access. Target-specific acceptance
completed at 21:17:22 UTC on November 7: both endpoint GETs retained true/true,
an ordinary refreshed plan had no pending changes, and the existing runtime
and permissions were preserved. This qualifies the infrastructure repair,
independently of application deployment. A subsequent integrated container
source build deployed version 5, whose digest and all three tools passed
runtime qualification with the shared/default connection preserved. See the
[source-build evidence](evidence-map.md#shared-registry-source-build-qualification).
Neither result certifies a fresh-from-empty deployment.

**Project-local mode remains an explicit alternative, not a required workaround.**
If that is the intended scope, independently verify the project-local connection
and its scoped permissions, then select:

```hcl
share_foundry_registry_connection = false
```

Keep all original inputs and applied handoffs on the fresh plan; a separate
compatibility tfvars file can make this choice explicit. Review every proposed
change before a separately approved apply. Do not ignore the drift, change the
connection API, create another owner or broaden access to force sharing.

The application helper accepts either boolean sharing choice, but requires
`agents.registry_connection_id` to match the declared project and exact
connection name. Older version-1 exports remain valid for the standalone
environment adapter but must be re-exported before application preparation.
Neither the connection ID nor the configured sharing flag proves current
Azure state, working image pulls or role propagation.

Official [existing-project ACR selection](https://github.com/Azure/azure-dev/blob/2021ef8fbc8a06771199b3f99e49f868e130a3aa/cli/azd/extensions/azure.ai.agents/internal/cmd/init_foundry_resources_helpers.go)
discovers the project's ContainerRegistry connections and validates the registry
target and selected name without requiring a sharing flag in that path. This
source evidence and project visibility support the compatibility choice; they
do not replace hosted build/image-pull acceptance.

### Project-local RemoteTool compatibility

On November 7, 2026, independent project and account connection GETs returned
`isSharedToAll=false` for the owned `aigw-github` connection, while its project
ownership, managed-identity authentication, audience and gateway target matched.
A refreshed plan otherwise tried to restore the default sharing request.
This is a target-specific observation, not a general service guarantee.

After verifying those fields and the project-scoped tool path, retain this
explicit input alongside every original input and applied handoff:

```hcl
share_foundry_remote_tool_connection = false
```

The default remains Bicep-aligned `true`. This independent setting changes
neither registry sharing nor any role grant. Review a new ordinary plan: do not
hide drift with `ignore_changes`, recreate the connection or add another owner.
The [Toolbox runner](toolchain.md#4-create-the-toolbox-and-review-its-runtime-values)
already accepts either explicit boolean, but a working tool invocation is still
required to establish runtime access.

### Nonsecret environment handoff

The [environment adapter](../scripts/export_environment.py) accepts a nonsecret
version-1 contract or an explicitly nonsensitive `terraform output -json`
envelope:

```powershell
python -B infra\scripts\export_environment.py .\deployment-contract.json
```

It prints an allow-listed JSON mapping for review. It never calls Azure,
Terraform or azd, writes an env file, selects credentials or runs hooks.
For custom profiles, use `--model-alias-key` and `--mini-model-alias-key`.
Both selected aliases must support `/openai/v1/responses`; Chat-Completions-only
aliases are rejected because the shared application uses Responses.

The adapter checks gateway group/ID and agent account/project ID/URL
relationships. Gateway and registry hostname syntax is not independent proof
of resource ownership; service-generated registry hostnames remain valid.
No GitHub credential/repository, Toolbox value or runtime readiness is supplied.
Do not pass state as adapter input.

The [application helper](application-flow.md) reuses that adapter and separately
validates the connected tool bootstrap/receipt. It supplies the repository and
versioned Toolbox endpoint from those handoffs, plus the endpoint alias needed
by the agent extension. It omits infrastructure-owning azd services and disables
automatic developer-role repair. Terraform's `deferred_integrations` still
describes work owned outside Terraform, not missing helper source or evidence
that those external stages have run.

## Preserved contracts and deliberate differences

Gateway, catalog, aliases, key and telemetry resources now use
`2025-09-01-preview`, aligned with the [upstream gateway Bicep](https://github.com/Azure-Samples/simple-foundry-hosted-agent-python-aigateway/blob/4ac828155315607141ed4e1ea692c766fff4c123/infra/ai-gateway/main.bicep).
Foundry account/project/deployment resources use `2025-04-01-preview`.
The gateway SKU remains omitted. Preview deployment/API availability still
requires target-specific qualification; an earlier 2026 deployment is not proof.
Matching source defaults do not certify service availability or upgrade
behavior; use a fresh target-specific plan and independent live readbacks.

The gateway retains create-only headers, backend-replacement semantics and
`prevent_destroy`. This is not an Azure deletion lock. Alias body changes still
require replacement; model deployments serialize on their account.

| Surface | Behavior or qualification |
|---|---|
| Gateway/MCP safety | The bundled root selects `Medium` on all models; explicit profiles allow overrides/omission and standalone defaults remain opt-in. The external tool runner also requests Medium for MCP. Selected-API blocking enforcement remains unqualified; backend filtering is a separate control. |
| Backend filtering | Both paths omit an explicit `raiPolicyName`. Omission neither proves the effective backend policy nor disables filtering; verify the selected deployment independently. |
| Model request rate | Both bundled profiles omit a default request-rate policy while retaining token/cost controls. An explicit Terraform replacement profile can still configure request limits. |
| Model account | Both paths request `allowProjectManagement = false` on the model-only account and retain project support on the agent account. Terraform independently GETs the model account after writes and blocks dependent work unless the flag is exactly false. The November 8 existing-account update retained true despite a successful apply; strict live alignment is not accepted. An existing project-enabled AIServices account needs an explicitly reviewed migration, not repeated in-place updates or ignored drift. See the [guard and partial-state boundary](../modules/foundry-models/README.md) and [qualification](evidence-map.md#model-account-alignment-and-readback). |
| Registry sharing | Shared by default in the application root, matching Bicep; standalone support remains unshared. The ordered owner/PATCH/GET repair passed live infrastructure acceptance with sharing/default true. The subsequent integrated source-build deployment and version 5 digest also passed, without the registry opt-out. The earlier digest-pinned version 3 used project-local compatibility. See the [qualified scope](evidence-map.md#shared-registry-source-build-qualification); this is not fresh-from-empty certification. |
| Foundry access/monitoring | Enabled by default in the application root, with narrower separate model/tool roles instead of broad AI Gateway User grants |
| Insights connection | One project-level Terraform owner, using managed identity by default in the application root; not a claim of identical Bicep account-level topology |
| Gateway telemetry | Native OpenTelemetry is a two-stage Terraform path with an external GET-only readiness helper, not the Bicep mutation hook. Native gateway and agent traces were correlated for the accepted run; exporter migration and the Portal dashboard remain unqualified. |
| Tool/application lifecycle | The explicit-credential tool runner requires exclusive ownership; creation is not atomic. The app-only azd helper deploys the agent, followed by explicit runtime identity binding and on-demand acceptance before the separate schedule gate. Current-source digest and routine dispatch are accepted; the routine is paused. Terraform remains staged, not wrapped in native `azd up`. Wall-clock scheduling, full credential rotation and teardown remain unqualified. |

Do not run Bicep mutating hooks against Terraform-owned resources. Exporter
kind migration can require deletion/recreation and is not automatic or approved
by these source changes. State adoption, live credential rotation/recovery and
teardown need separately reviewed ownership-aware procedures. Do not remove `prevent_destroy`
or mutate state to bypass a stop.
