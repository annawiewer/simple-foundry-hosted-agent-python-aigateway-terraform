# foundry-models

Creates a dedicated Foundry model-serving account and deployments. It does not
create a project, gateway, provider/catalog routes or hosted agent.

Required inputs: `subscription_id`, `resource_group_id`, `name`, `location` and
`model_deployments`. The caller owns the group and provider configuration.
Optional inputs: `tags`, `public_network_access` (default `Enabled`) and explicit
developer principal ID/type.

Deployment map keys are stable deployment names. The full shared metadata type
is in [`variables.tf`](variables.tf): required model name/version, capacity and
token limit, with optional model format/SKU/API endpoints/description and policy
metadata. Gateway policy fields travel alongside deployment metadata; this
module does **not** enforce gateway token/cost/request limits or content safety.
It accepts optional `content_safety_severity` (`Low`, `Medium`, `High` or null)
for composition with [ai-gateway](../ai-gateway/README.md); accepting metadata
does not create a gateway policy here.

The model-only account requests disabled local authentication and project
management, matching Bicep; the separate agent account supports projects.
An independent [`models_readback` GET](main.tf#L25-L39) runs after account
updates and requires the exact boolean `false` for `allowProjectManagement`.
True, missing, null and string responses fail the operation before dependent
model deployments and [developer grants](access.tf#L20-L33); all
[output consumers](outputs.tf#L1-L21) also depend on this check.

An existing project-enabled AIServices account did **not** disable project
management during the November 8, 2026 in-place qualification, even though
Terraform apply exited successfully and recorded the requested false value.
Do not repeatedly apply that change or hide its drift. HashiCorp's pinned
[account guidance](https://github.com/hashicorp/terraform-provider-azurerm/blob/59eca87035cef81d9c75070b024f2e29e6de2b6d/website/docs/r/cognitive_account.html.markdown)
requires replacement when disabling project management while retaining
AIServices; plan an explicitly approved migration instead of assuming
that a writable API property guarantees an in-place transition.
The [recorded qualification](../../docs/evidence-map.md#model-account-alignment-and-readback)
distinguishes this observation from fresh-account provisioning.

The guard stops dependent work; it does not roll back an account update.
Terraform can retain already-known outputs in a failed partial state.
Never use those outputs as a successful deployment handoff: require a
successful apply and independent readback before publishing or consuming it.

Deployments serialize through an account-scoped AzAPI operation lock and omit
an explicit `raiPolicyName`, matching Bicep. Read back the service's effective
backend policy rather than assuming a policy name or that filtering is disabled.
The operation lock is not a remote state/concurrent-writer lock. Backend filter
configuration is not enforcement proof or gateway/MCP filtering.

Outputs:

- `account_id`, `endpoint`, `deployment_ids` keyed by deployment name.
- `backend = { account_id, endpoint, deployment_ids }`, accepted by
  [ai-gateway](../ai-gateway/README.md). Pass `model_deployments` metadata
  separately; this module never accepts gateway identities.

Use [models-only](../../examples/models-only/README.md) independently, or the
[composition root](../../README.md). Check model availability and quota before
planning a real target. `public_network_access = "Disabled"` does not provision
private connectivity. Existing accounts are not imported through this module;
use the [existing-models example](../../examples/existing-models/README.md).

See the [canonical preparation/state route](../../docs/architecture.md#offline-and-deployment-preparation)
and [historical evidence boundary](../../docs/evidence-map.md).
