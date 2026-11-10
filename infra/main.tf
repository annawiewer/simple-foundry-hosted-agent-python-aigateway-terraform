locals {
  default_profile = jsondecode(file("${path.module}/model-profile.json"))
  model_deployments = var.model_deployments == null ? tomap({
    for key, model in local.default_profile.model_deployments : key => merge(model, { content_safety_severity = "Medium" })
  }) : var.model_deployments
  model_aliases       = var.model_aliases == null ? local.default_profile.model_aliases : var.model_aliases
  resource_token      = substr(sha256("${var.subscription_id}:${var.environment_name}:${var.location}:api2026gateway"), 0, 12)
  backend_token       = var.backend_revision == "" ? local.resource_token : substr(sha256("${local.resource_token}:${var.backend_revision}"), 0, 12)
  tags                = merge(var.tags, { environment = var.environment_name, "gateway-contract" = "api2026gateway" })
  resource_group_keys = { for key in ["gateway", "models", "agents"] : key => var.api2026_resource_group_name == null ? key : "gateway" }
  names = {
    gateway  = "aigw-${local.resource_token}"
    models   = var.model_account_name == null ? "aimodels-${local.backend_token}" : var.model_account_name
    agents   = "aiagents-${local.backend_token}"
    project  = "proj-${local.backend_token}"
    storage  = "st${local.backend_token}"
    registry = "acr${local.backend_token}"
  }
}
resource "azapi_resource" "resource_group" {
  for_each  = toset(var.api2026_resource_group_name == null ? ["gateway", "models", "agents"] : ["gateway"])
  type      = "Microsoft.Resources/resourceGroups@2021-04-01"
  name      = var.api2026_resource_group_name == null ? "rg-${var.environment_name}-${local.resource_token}-${each.key}" : var.api2026_resource_group_name
  parent_id = "/subscriptions/${var.subscription_id}"
  location  = var.location
  tags      = local.tags
  body      = { properties = {} }
}
module "foundry_models" {
  source                   = "./modules/foundry-models"
  subscription_id          = var.subscription_id
  resource_group_id        = azapi_resource.resource_group[local.resource_group_keys.models].id
  name                     = local.names.models
  location                 = var.location
  tags                     = local.tags
  public_network_access    = coalesce(var.standalone_backend_public_network_access, "Enabled")
  model_deployments        = local.model_deployments
  developer_principal_id   = var.developer_principal_id
  developer_principal_type = var.developer_principal_type
}
module "ai_gateway" {
  source                           = "./modules/ai-gateway"
  subscription_id                  = var.subscription_id
  resource_group_id                = azapi_resource.resource_group["gateway"].id
  name                             = local.names.gateway
  location                         = var.gateway_location
  monitoring_location              = var.location
  tags                             = local.tags
  gateway_backend_subnet_id        = var.gateway_backend_subnet_id
  backend                          = module.foundry_models.backend
  model_deployments                = local.model_deployments
  model_aliases                    = local.model_aliases
  model_allowed_client_cidrs       = var.model_allowed_client_cidrs
  gateway_access_principals        = var.gateway_access_principals
  monitoring_public_network_access = var.standalone_backend_public_network_access
  telemetry_mode                   = var.gateway_telemetry_mode
  native_telemetry                 = var.gateway_native_telemetry
}
module "foundry_agents" {
  source                           = "./modules/foundry-agents"
  subscription_id                  = var.subscription_id
  resource_group_id                = azapi_resource.resource_group[local.resource_group_keys.agents].id
  name                             = local.names.agents
  names                            = { project = local.names.project, storage = local.names.storage, registry = local.names.registry }
  location                         = var.location
  tags                             = local.tags
  public_network_access            = coalesce(var.standalone_backend_public_network_access, "Enabled")
  storage_public_network_access    = var.agent_storage_public_network_access
  enable_monitoring_integration    = var.enable_foundry_monitoring_integration
  share_registry_connection        = var.share_foundry_registry_connection
  monitoring_public_network_access = var.standalone_backend_public_network_access
  developer_principal_id           = var.developer_principal_id
  developer_principal_type         = var.developer_principal_type
  project_display_name             = var.project_display_name
  project_description              = var.project_description
}
