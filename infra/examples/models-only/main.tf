locals {
  token = substr(sha256("${var.subscription_id}:${var.environment_name}:${var.location}:api2026gateway"), 0, 12)
  tags  = merge(var.tags, { environment = var.environment_name, "gateway-contract" = "api2026gateway" })
  default_model_deployments = tomap({
    for key, model in jsondecode(file("${path.module}/../../model-profile.json")).model_deployments :
    key => merge(model, { content_safety_severity = null })
  })
}
resource "azapi_resource" "resource_group" {
  type      = "Microsoft.Resources/resourceGroups@2021-04-01"
  name      = "rg-${var.environment_name}-${local.token}"
  parent_id = "/subscriptions/${var.subscription_id}"
  location  = var.location
  tags      = local.tags
  body      = { properties = {} }
}

module "component" {
  source            = "../../modules/foundry-models"
  subscription_id   = var.subscription_id
  resource_group_id = azapi_resource.resource_group.id
  name              = "aimodels-${local.token}"
  location          = var.location
  tags              = local.tags

  model_deployments = var.model_deployments == null ? local.default_model_deployments : var.model_deployments

}
