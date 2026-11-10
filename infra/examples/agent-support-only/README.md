# Agent support only

Runnable fresh root for [foundry-agents](../../modules/foundry-agents/README.md).
Owns one new group and independent account/project, Storage/ACR, monitoring,
internal grants and support connections. **No agent code/image, model account,
gateway, RemoteTool, ToolServer, Toolbox or routine is deployed.**

Follow the [canonical offline/preparation route](../../docs/architecture.md#offline-and-deployment-preparation),
setting `$TerraformRoot = 'infra\examples\agent-support-only'`. Edit
the local copy of [`terraform.tfvars.example`](terraform.tfvars.example):
`subscription_id` and `location` are required; `environment_name` defaults to
`agent-support-only`, and `tags` is optional. Component names derive from those
inputs. Use fresh names and a distinct state/backend key.

Optional `storage_public_network_access` accepts null (retain public-access
defaults), `Enabled` or `Disabled`. It changes only Storage configuration, not
the account, registry or monitoring, and creates no private connectivity.
Disabled Storage does not require a gateway/subnet; runtime access must be
qualified separately and the configured `AzureServices` bypass is retained.

Outputs: `project_id`, constructed `project_endpoint` and
`container_registry_endpoint`. These are infrastructure handoffs, not proof of
image access, hosted-runtime readiness or tracing delivery.

Optional `enable_monitoring_integration = true` updates the existing owned
Insights connection to ProjectManagedIdentity in place and adds two Insights-scoped publisher
grants. Default false preserves the original graph and project-local ApiKey
connection. See the [module's single-owner and proof boundaries](../../modules/foundry-agents/README.md).
This example has offline coverage, not an independent live deployment receipt.

Application/credential integration is a later increment; existing azd/Bicep
defaults are not redirected here. See [evidence limits](../../docs/evidence-map.md).
