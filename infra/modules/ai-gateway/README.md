# ai-gateway

Standalone AI Gateway (`2025-09-01-preview`), system identity, service-owned default workspace,
runtime-key **resource**, Log Analytics/Application Insights and staged native
telemetry. The
module never reads or exports the runtime key value.

Use [gateway-only](../../examples/gateway-only/README.md) for a scaffold or
[existing-models](../../examples/existing-models/README.md) for referenced models.
Provider configuration belongs to the calling root.

## Contract

Required: `subscription_id`, `resource_group_id`, `name`, `location` (gateway
region), `monitoring_location`. `tags` is optional. The group is referenced,
not adopted or deleted by this module.

`backend = null` with empty `model_deployments` and null `model_aliases` creates
no backend grant/provider/catalog/aliases. A routed backend has this shape:

```hcl
backend = {
  account_id     = "<same-subscription Cognitive Services account ARM ID>"
  endpoint       = "https://<account>.cognitiveservices.azure.com/"
  deployment_ids = { "<deployment-key>" = "<account ARM ID>/deployments/<deployment-key>" }
}
```

Supply `model_deployments` separately using the full configuration type in
[`variables.tf`](variables.tf). Its keys must exactly match `deployment_ids`;
IDs remain values, so newly created backend IDs can be unknown during planning.
Required model metadata is `model_name`, `model_version`, `capacity` and
`token_limit`; optional fields cover format/SKU, endpoints, description and
cost/request limits. This module registers routes; it does not create or alter
the referenced account/deployments or bind their backend safety policy.

Optional `content_safety_severity` selects `Low`, `Medium` or `High` for all four
gateway content-safety categories. Null or omission adds no such policy; other
model policies are retained. The [application root](../../README.md#model-content-safety)
selects `Medium` for its bundled profile, but this module has no implicit severity.
This does not configure MCP safety or prove enforcement.

`manage_backend_role_assignment = true` owns the gateway MI's account-scoped
Foundry User grant and orders provider creation after it. False requires a
platform-owned, already-ready grant to the actual gateway principal; it does
not bootstrap or verify propagation of that pregrant. Choose **one owner**.
Cross-subscription backends are rejected.

`model_aliases = null` here creates one direct alias per deployment. Explicit
aliases use ARM-safe keys, a callable `alias_name`, and `backend_models` entries
with deployment key, priority and weight. Backends must share API format and
at least one endpoint. Body changes replace aliases.

Other options: `gateway_access_principals` (explicit gateway model callers),
`model_allowed_client_cidrs` (model calls only), `gateway_backend_subnet_id`
(external delegated outbound subnet, not ingress), and
`monitoring_public_network_access`.

`telemetry_mode` defaults to `OpenTelemetry`; null `native_telemetry` enables
managed ingestion but leaves the DCR grant/exporter absent and status `pending`.
The [two-stage guide](../../docs/native-telemetry.md) covers the GET-only helper,
fresh second-stage plan and retained nonsecret handoff. The module checks the
owned Insights refresh and actual gateway identity before granting publisher
access at the returned DCR only. Explicit `ApplicationInsights` selects legacy
compatibility, not a native migration.

Outputs: gateway ID/endpoint/principal/workspace, key-resource ID, exact API
versions, monitoring IDs/kind/configuration status, `gateway_telemetry_bootstrap`
and model/alias API metadata. See
[`outputs.tf`](outputs.tf).

Gateway and exporter deletion are guarded by `prevent_destroy`. Policy configuration is not
enforcement; backend filtering is not gateway/MCP safety; exporter configuration
is not delivery. No ToolServer, Toolbox, RemoteTool, application or credential
runner is included. See [ownership/preparation](../../docs/architecture.md) and
[evidence boundaries](../../docs/evidence-map.md).
