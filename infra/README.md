# Terraform infrastructure

A self-contained, fresh-deployment Terraform composition for the standalone
AI Gateway and Foundry support infrastructure, with an explicit path through
the root Python application and an optional daily routine. This repository
contains only the Terraform deployment path. The gateway resource family is
`Microsoft.ApiManagement/aigateways`, not classic API Management
`Microsoft.ApiManagement/service`.
Start with the [repository overview](../README.md), then use the staged
guides below. Historical runtime evidence comes from the tested Terraform
baseline; relocating that source does not establish a new live acceptance.

**The shared/default registry and normal container source-build path were
verified on November 7, 2026:** an integrated ACR build deployed agent version 5,
which completed all three GitHub tools through AI Gateway with correlated
agent/gateway telemetry. Its configured image uses a tag, independently checked
against the build digest before and after inference. The earlier digest-pinned
version 3 and manual daily-routine dispatch also remain accepted. A separate
November 8 model-only backend cutover and bounded cost rejection passed;
a November 9 creator-identity timer produced a readable completed digest
without manual dispatch. Its temporary routine was removed and the original
daily routine remains disabled. Native safety denial, the historical
agent-owned response 403 and recurring MCP 499/authorization error remain
unresolved. The gateway API is
`2025-09-01-preview`, aligned with the upstream Bicep path. This is one accepted
runtime path, not certification of every build, credential or lifecycle scenario.
See the [acceptance matrix and precise boundaries](docs/evidence-map.md#acceptance-matrix).

## Start here

Follow the single [offline and deployment-preparation route](docs/architecture.md#offline-and-deployment-preparation).
For the complete staged route through the agent and optional daily schedule,
follow the [guided application flow](docs/application-flow.md). It keeps
Terraform plan/apply explicit and does not invoke Bicep provisioning hooks.
The application helper generates an isolated app-only manifest with supported
camelCase routine-authoring fields and separately gated agent/schedule operations.
There is deliberately no infrastructure-owning `azure.yaml` at the repository root.
The compatibility baseline is Terraform **1.11.4**, locked AzAPI **2.13.0**,
PowerShell 7 and Python 3. Offline checks need no Azure credentials; uncached
locked providers still require registry access.

| Entry | Purpose |
|---|---|
| This root | Three workload groups, three modules, default Foundry access/monitoring/shared registry wiring and nonsecret outputs |
| [Gateway only](examples/gateway-only/README.md) | Gateway scaffold without backend models or agent support |
| [Existing models](examples/existing-models/README.md) | Gateway routing to a referenced, same-subscription backend |
| [Models only](examples/models-only/README.md) | Model account and pinned deployments |
| [Agent support only](examples/agent-support-only/README.md) | Project, Storage, ACR and monitoring; no deployed agent |

Modules: [ai-gateway](modules/ai-gateway/README.md),
[foundry-models](modules/foundry-models/README.md),
[foundry-agents](modules/foundry-agents/README.md).

The application root **enables by default** Foundry model-access grants, a
separate project-only tool-access grant, the managed-identity Insights connection
with two scoped publisher grants, and registry-connection sharing. Each setting
can be disabled independently; reusable modules and standalone examples retain
their minimal defaults. Existing users should review the
[default changes and explicit opt-outs](docs/architecture.md#optional-application-integration)
before planning an upgrade.

Registry sharing remains the Bicep-matching default request, not a requirement
for project-local application access. Shared mode follows the connection owner
with a native PATCH and independent blocking readback. See the
[accepted infrastructure repair and explicit project-local opt-out](docs/architecture.md#project-local-registry-compatibility);
the [normal source-build qualification](docs/evidence-map.md#shared-registry-source-build-qualification)
then verified deployment and runtime use without the project-local registry opt-out.
This is an existing-environment result, not fresh-from-empty certification.

After deploying the agent, its actual identity can differ from both Foundry
support identities. The opt-in `hosted_agent_principals` map supplies that
independently verified principal for gateway Models User and agent-Insights
publisher grants. Its empty default changes no resources. Follow the
[postdeployment identity handoff](docs/application-flow.md#3-bind-the-deployed-agent-identity);
do not duplicate or silently adopt existing operational assignments.

## Model-account naming

The optional `model_account_name` overrides only the models account name and
its custom subdomain. Its default, `null`, preserves the generated name.
Gateway, agent account, project, storage, registry and resource-group names
are unchanged. Use 2-64 letters, digits or hyphens, starting and ending with a
letter or digit; global custom-subdomain availability must still be checked.

This input is **not a migration or retention mechanism**. Changing an existing
account's name can replace it and its dependent resources. A side-by-side
migration needs explicit retained ownership, a separately provisioned backend,
controlled routing changes and rollback. Do not change `backend_revision` for
a model-only migration: that input also renames the agent-side resources.
The model-only account's strict project-management readback remains required.

## Model content safety

**Support caveat:** the [November 10 native support review](docs/evidence-map.md#native-content-safety-support-boundary)
identifies content safety as unsupported for the selected typed gateway/API.
The settings below describe retained configuration, not a supported or
demonstrated protection mechanism.

The application root's **bundled model profile now selects `Medium`** for Hate,
Self-Harm, Sexual and Violence on every gateway catalog model, matching the
[upstream Bicep policy body](https://github.com/Azure-Samples/simple-foundry-hosted-agent-python-aigateway/blob/4ac828155315607141ed4e1ea692c766fff4c123/infra/ai-gateway/main.bicep). Reusable modules and the
existing-models example retain null/omitted defaults.

An explicit `model_deployments` map **replaces**, rather than merges with, that
profile. Set each model's `content_safety_severity` to `Low`, `Medium` or `High`
to select the same severity for all four categories. Null or omission in an
explicit map omits that model's policy; the string `"None"` is not accepted.
To preserve the previous root policy omission, provide your full deployment
map with null severities. Keep deployment keys compatible with `model_aliases`.

This is a gateway model policy, not MCP protection. Both IaC paths omit an
explicit backend `raiPolicyName`; backend filtering remains a separate service
control, and omission does not establish its effective policy or disable it.
Review a fresh plan and the backend policy readback before upgrading. A
disposable selected-2025-API probe returned all four Medium severities; neither
that readback nor the offline contracts prove safety enforcement. See the
[acceptance matrix](docs/evidence-map.md).

The bundled profile also matches Bicep by omitting a request-rate policy;
token and cost limits remain configured. An explicit replacement profile can
still select a positive per-identity `request_limit` in requests per minute.

## Application and telemetry boundaries

A tool role does not create a ToolServer, deliver a credential or establish
working invocation. The RemoteTool still requires an explicit verified endpoint.
The opt-in [GitHub tool runner](docs/toolchain.md) provides the separate
credential-explicit ToolServer/Toolbox lifecycle and nonsecret connection
handoffs. It is not called by Terraform or azd. Real tool invocation and a
bounded synthetic-header control-plane lifecycle were verified separately;
credential rotation and general secret-handling guarantees remain unqualified.
Foundry monitoring is separate from gateway OpenTelemetry. Gateway-bearing roots
now default to the [two-stage native telemetry path](docs/native-telemetry.md):
managed ingestion first, then a GET-only readiness handoff and a fresh plan for
the scoped DCR publisher/exporter. Stage one reports `pending`; existing legacy
exporters require an explicit compatibility choice and separate migration.
The nonsecret JSON
environment adapter and [GET-only live qualification runner](docs/live-readback.md)
remain separate from application deployment.

See [ownership, state and API differences](docs/architecture.md) and the
[validation and acceptance guide](docs/evidence-map.md). One creator-readable
scheduled delivery is demonstrated, not a change to the helper's schedule
identity default or a guarantee of repeated daily delivery. Safety denial,
historical response access, the recurring authorization error, credential
lifecycle guarantees and full teardown remain separate qualification work.
The [application helper](docs/application-flow.md) now provides offline preparation
and separately confirmed app-only azd deployment; it neither replaces Terraform
nor installs tools, grants roles or reuses Bicep hooks. The
[tool contract boundary](docs/tool-credential-boundary.md) explains why existing
credential hooks are not reused. Telemetry
configuration alone is not delivery proof; the evidence map records the
independently correlated hosted-agent, model and GitHub request traces.
