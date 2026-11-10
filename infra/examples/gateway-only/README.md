# Gateway only

Runnable fresh root for [ai-gateway](../../modules/ai-gateway/README.md) without
model or agent dependencies. Owns one new group, gateway/system identity,
runtime-key resource and monitoring with staged native export. `backend` remains null: **no
provider, model catalog, aliases, backend grant or callable model is created**.

Follow the [canonical offline/preparation route](../../docs/architecture.md#offline-and-deployment-preparation),
setting `$TerraformRoot = 'infra\examples\gateway-only'`. Edit the
local copy of [`terraform.tfvars.example`](terraform.tfvars.example):
`subscription_id` and `location` are required; `environment_name` defaults to
`gateway-only`, and `tags` is optional. Gateway and monitoring use `location`.
Use an isolated state/backend key and fresh names, not the full root's state.

Native telemetry initially reports `pending`. Follow the
[two-stage telemetry guide](../../docs/native-telemetry.md), keeping this example's
root, workspace and original inputs for both stages. Its
`gateway_telemetry_mode` and `gateway_native_telemetry` inputs match the full root;
no external provider or Bicep writer is needed.

Outputs are `gateway_id`, `gateway_endpoint`, `gateway_monitoring`,
`gateway_telemetry_bootstrap` and an empty
`model_alias_configuration`. The key value is not returned. Gateway destruction
is deliberately guarded.

This is not a running digest agent or proof of model/telemetry runtime. See
[historical evidence limits](../../docs/evidence-map.md).
