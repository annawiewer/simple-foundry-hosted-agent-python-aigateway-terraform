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

module "component" {
  source                        = "../../modules/foundry-agents"
  subscription_id               = var.subscription_id
  resource_group_id             = azapi_resource.resource_group.id
  name                          = "aiagents-${local.token}"
  location                      = var.location
  tags                          = local.tags
  storage_public_network_access = var.storage_public_network_access
  enable_monitoring_integration = var.enable_monitoring_integration

  names = { project = "proj-${local.token}", storage = "st${local.token}", registry = "acr${local.token}" }

}
