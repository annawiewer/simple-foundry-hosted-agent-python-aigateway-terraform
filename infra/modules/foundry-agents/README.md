# foundry-agents

Independent **agent-support infrastructure**, not a deployed hosted agent.
Creates an account/project with system identities, Storage, Premium ACR,
Log Analytics/ApplicationInsights, internal scoped roles and three project
connections. It does not require gateway outputs.

Required inputs: `subscription_id`, `resource_group_id`, `name` (account),
`location`, and `names = { project, storage, registry }`. Caller owns resource
names, group and provider configuration. Optional: `tags`,
`project_display_name`, `project_description`, `public_network_access`,
`storage_public_network_access`, `monitoring_public_network_access`, and
developer principal ID/type.

`enable_monitoring_integration = true` updates the existing owned
`AppInsights` connection to `ProjectManagedIdentity` and adds two Monitoring Metrics
Publisher grants (`3913510d-42f4-4e42-8a64-420c390055eb`), for the existing
account/project identities at this module's exact Insights scope. It defaults
to false; the connection depends on both grants. Account/project keys remain
known before identity creation. The root exposes this as
`enable_foundry_monitoring_integration` and enables it by default; this reusable
module and the agent-support-only example retain the false default.

The connection retains `accounts/projects/connections@2025-06-01`, its original
Terraform address, project parent and name, unshared, with Bicep's managed-identity
body, target and metadata. This connection's provider schema validation is disabled only for this auth
contract, matching Bicep's suppressed type warning; this is not schema proof.
Default false preserves the original ApiKey body and provider validation.
Read-only inspection found the existing connection also exposed through the
account route with matching creation time, auth, target and metadata. This
suggests mirrored backing resources, not a fully specified alias contract;
creating a second same-name account-route owner is deliberately prohibited.
The controlled single-owner update subsequently appeared through both routes
under the original resource IDs. Azure reset both creation timestamps, so a
Terraform in-place plan is not proof of unchanged service-internal backing.
The opt-in omits ApiKey credentials; omission alone does not prove that the
service erases previously stored values. No Insights local-auth setting,
registry-sharing setting, credential hook or application instrumentation is
changed by the monitoring switch.
This does not enforce Entra-only ingestion or prove trace delivery.

`storage_public_network_access` accepts null (inherit `public_network_access`),
`Enabled` or `Disabled`. An explicit value overrides only Storage's public
access and default ACL action, including an explicit `Enabled` with other
backends disabled. It creates no private connectivity and has no gateway
subnet requirement. The configured Storage `AzureServices` bypass remains;
the override is not proof of private-only runtime operation.

Storage `networkAcls.resourceAccessRules` is service-owned: Azure/Defender can add
its StorageDataScanner rule after provisioning. Terraform preserves only this
field on subsequent plans/updates. Public-network access, default ACL action,
`AzureServices` bypass, VNet rules, TLS and public-blob/shared-key settings remain
managed; no scanner permission is added or removed by this module.

The project receives Storage data access, ACR pull access and account-scoped
Cognitive Services roles. Storage and registry connections depend on their
grants. ACR uses a project-managed-identity connection, unshared by default;
`share_registry_connection = true` requests `isSharedToAll` on that same connection.
It does not enable registry admin credentials or broaden the project AcrPull
grant. The application root enables sharing through
`share_foundry_registry_connection`; standalone support does not.
The same connection explicitly requests `isDefault=true` for either sharing
choice. In the November 7, 2026 target-specific repair, a sharing-only PATCH
reset the observed default flag; explicitly including both fields restored
sharing and default selection through both project/account readback routes.
A subsequent ordinary Terraform PUT reset sharing to false even though its
planned body contained both true flags. A successful apply alone is therefore
not sufficient evidence.
The pinned `2025-04-01-preview` ARM schema omits `isDefault`, so provider schema
validation is disabled on this resource only. That exception is not a published
API guarantee: verify both flags after applying and require a refreshed no-op
plan. It does not create an account-route owner or bypass Azure authorization.
Both flags are explicitly exported from the service response. This also makes
the initial configuration update observable to the pinned provider rather than
letting its no-op optimization retain the older body without `isDefault`.

Shared mode follows the owner with a non-owning `azapi_resource_action` PATCH
using the same API, connection ID and managed-identity payload, explicitly
preserving both flags. `replace_triggered_by` reruns that action whenever the
owner changes, including when a refresh detects sharing drift. The action
does not create another connection or delete the connection when removed.
A separate GET then checks both returned flags with a blocking postcondition;
an action's stored response is not a substitute for that readback. The
project-local opt-out creates neither the sharing action nor its readback.
There is no registry drift mask or external provisioner.

This ordered reconciliation passed target-specific live acceptance on
November 7, 2026: project/account GETs retained both flags, an ordinary refreshed
plan reported no pending changes, and the existing runtime and grants were preserved.
The owner's exported response can describe its earlier, pre-PATCH GET; use
the final readback and a refreshed plan, not that intermediate snapshot.
Sharing is not a prerequisite for the application helper's project-local
connection check. Independently compare the requested flag with Azure readback
and a normal refreshed plan; see [project-local compatibility](../../docs/architecture.md#project-local-registry-compatibility).
Hosted image pulls still need runtime acceptance. AppInsights is
an unshared project-local ApiKey connection unless explicitly opted in above.
These are the reusable module's defaults, not the application root's defaults
or a claim of complete upstream runtime equivalence.

Outputs include account/project IDs and principals, project endpoint,
registry ID/endpoint/connection name/connection ID, the configured sharing
request, Storage name/ID and monitoring IDs. `registry_connection_shared`
reports the configured request, not independent Azure readback.
`monitoring_connection_id` exposes the existing project-owned connection ID only
when the monitoring opt-in is enabled; otherwise it is null.
The project endpoint is constructed from the supplied account/project names;
it is not live endpoint-readiness proof. See [`outputs.tf`](outputs.tf).

No gateway model/tool invocation grants, direct model-backend grants, RemoteTool,
ToolServer, Toolbox, image build, hosted Responses agent or routine are created.
Connection strings occur in managed payloads: protect state and plans even
though published outputs are nonsecret. Public-access overrides do not create
private networking.

Use [agent-support-only](../../examples/agent-support-only/README.md) or the
[composition root](../../README.md), following the
[canonical preparation/state route](../../docs/architecture.md#offline-and-deployment-preparation).
Configuration is not hosted-runtime or tracing-delivery acceptance; see the
[evidence map](../../docs/evidence-map.md).
