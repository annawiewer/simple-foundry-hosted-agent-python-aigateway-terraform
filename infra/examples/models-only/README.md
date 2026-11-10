# Models only

Runnable fresh root for [foundry-models](../../modules/foundry-models/README.md).
Owns one new group, a model account and the bundled
[profile's](../../model-profile.json) serialized deployments/filter bindings.
Creates no gateway, project, provider/catalog/aliases or hosted agent.

Follow the [canonical offline/preparation route](../../docs/architecture.md#offline-and-deployment-preparation),
setting `$TerraformRoot = 'infra\examples\models-only'`. Edit the
local copy of [`terraform.tfvars.example`](terraform.tfvars.example):
`subscription_id` and `location` are required; `environment_name` defaults to
`models-only`, and `tags` is optional. `model_deployments = null` selects the
bundled profile; supply a typed map to select another deployment profile.
Qualify all selected versions/SKUs/quota.

The `backend` output contains `{ account_id, endpoint, deployment_ids }` for
explicit composition with the gateway module. Referencing that object is not
automatic resource adoption or a configured gateway.

Keep its state/backend key separate from other roots. Historical deployment
configuration/inference proof is not acceptance of this example; see the
[evidence map](../../docs/evidence-map.md).
