locals {
  token = substr(sha256("${var.subscription_id}:${var.environment_name}:${var.location}:api2026gateway"), 0, 12)
  tags  = merge(var.tags, { environment = var.environment_name, "gateway-contract" = "api2026gateway" })
}
resource "azapi_resource" "resource_group" {
  type      = "Microsoft.Resources/resourceGroups@2021-04-01"
  name      = "rg-${var.environment_name}-${local.token}"
  parent_id = "/subscriptions/${var.subscription_id}"
  location  = var.location
  tags      = local.tags
  body      = { properties = {} }
}

locals {
  profile = jsondecode(file("${path.module}/../../model-profile.json"))
  default_model_deployments = tomap({
    for key, model in local.profile.model_deployments : key => merge(model, { content_safety_severity = null })
  })
}

module "component" {
  source            = "../../modules/ai-gateway"
  subscription_id   = var.subscription_id
  resource_group_id = azapi_resource.resource_group.id
  name              = "aigw-${local.token}"
  location          = var.location
  tags              = local.tags

  monitoring_location = var.location
  telemetry_mode      = var.gateway_telemetry_mode
  native_telemetry    = var.gateway_native_telemetry

  backend                        = var.backend
  manage_backend_role_assignment = var.manage_backend_role_assignment
  model_deployments              = var.model_deployments == null ? local.default_model_deployments : var.model_deployments
  model_aliases                  = var.model_aliases == null ? local.profile.model_aliases : var.model_aliases

}
