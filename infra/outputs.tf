output "resource_groups" { value = { for key, group in local.resource_group_keys : key => azapi_resource.resource_group[group].name } }
output "gateway_id" { value = module.ai_gateway.gateway_id }
output "gateway_endpoint" { value = module.ai_gateway.gateway_endpoint }
output "gateway_api_key_id" { value = module.ai_gateway.gateway_api_key_id }
output "gateway_api_versions" { value = module.ai_gateway.gateway_api_versions }
output "gateway_monitoring" { value = module.ai_gateway.gateway_monitoring }
output "gateway_telemetry_bootstrap" { value = module.ai_gateway.gateway_telemetry_bootstrap }
output "gateway_toolchain_bootstrap" {
  description = "Nonsecret input to the separately invoked tool lifecycle runner. Does not provision tools, select credentials or authorize execution."
  value = {
    version                   = 1
    subscription_id           = var.subscription_id
    gateway_id                = module.ai_gateway.gateway_id
    workspace_id              = module.ai_gateway.gateway_workspace_id
    gateway_endpoint          = module.ai_gateway.gateway_endpoint
    api_version               = module.ai_gateway.gateway_api_versions.gateway
    project_id                = module.foundry_agents.project_id
    project_endpoint          = module.foundry_agents.project_endpoint
    tool_access_enabled       = var.enable_foundry_gateway_tool_access
    remote_tool_connection_id = try(azapi_resource.gateway_remote_tool[0].id, null)
    remote_tool_endpoint      = var.gateway_remote_tool_endpoint
  }
}
output "gateway_contract" {
  value = {
    name                  = "2026"
    resource_type         = "Microsoft.ApiManagement/aigateways"
    backend_subnet_id     = var.gateway_backend_subnet_id == "" ? null : var.gateway_backend_subnet_id
    single_resource_group = var.api2026_resource_group_name != null
    private_lab           = false
  }
}
output "model_deployment_ids" { value = module.foundry_models.deployment_ids }
output "model_api_configuration" { value = module.ai_gateway.model_api_configuration }
output "model_alias_configuration" { value = module.ai_gateway.model_alias_configuration }
output "foundry_models_id" { value = module.foundry_models.account_id }
output "project_id" { value = module.foundry_agents.project_id }
output "project_endpoint" { value = module.foundry_agents.project_endpoint }
output "container_registry_endpoint" { value = module.foundry_agents.container_registry_endpoint }
output "storage_account_name" { value = module.foundry_agents.storage_account_name }
output "application_insights_ids" {
  value = { gateway = module.ai_gateway.gateway_monitoring.insights_id, agents = module.foundry_agents.application_insights_id }
}
output "backend_public_network_access" {
  value = {
    models               = coalesce(var.standalone_backend_public_network_access, "Enabled")
    agents               = coalesce(var.standalone_backend_public_network_access, "Enabled")
    storage              = coalesce(var.agent_storage_public_network_access, var.standalone_backend_public_network_access, "Enabled")
    registry             = coalesce(var.standalone_backend_public_network_access, "Enabled")
    monitoring_ingestion = coalesce(var.standalone_backend_public_network_access, "Unspecified")
    monitoring_query     = coalesce(var.standalone_backend_public_network_access, "Unspecified")
  }
}
output "deployment_contract" {
  description = "Versioned allow-listed nonsecret infrastructure handoff for explicit environment mapping, not a complete azd/application deployment contract."
  value = {
    version          = 1
    environment_name = var.environment_name
    subscription_id  = var.subscription_id
    location         = var.location
    resource_groups  = { for key, group in local.resource_group_keys : key => azapi_resource.resource_group[group].name }
    gateway = {
      id           = module.ai_gateway.gateway_id
      name         = local.names.gateway
      location     = var.gateway_location
      endpoint     = module.ai_gateway.gateway_endpoint
      principal_id = module.ai_gateway.gateway_principal_id
      workspace_id = module.ai_gateway.gateway_workspace_id
      api_versions = module.ai_gateway.gateway_api_versions
      api_key_id   = module.ai_gateway.gateway_api_key_id
      monitoring   = module.ai_gateway.gateway_monitoring
    }
    models = {
      account_id     = module.foundry_models.account_id
      endpoint       = module.foundry_models.endpoint
      deployment_ids = module.foundry_models.deployment_ids
      aliases        = module.ai_gateway.model_alias_configuration
    }
    agents = {
      account_id               = module.foundry_agents.account_id
      account_principal_id     = module.foundry_agents.account_principal_id
      project_id               = module.foundry_agents.project_id
      project_principal_id     = module.foundry_agents.project_principal_id
      project_endpoint         = module.foundry_agents.project_endpoint
      registry_id              = module.foundry_agents.container_registry_id
      registry_endpoint        = module.foundry_agents.container_registry_endpoint
      registry_connection_name = module.foundry_agents.registry_connection_name
      registry_connection_id   = module.foundry_agents.registry_connection_id
      storage_account_id       = module.foundry_agents.storage_account_id
      application_insights_id  = module.foundry_agents.application_insights_id
      log_analytics_id         = module.foundry_agents.log_analytics_id
    }
    integration = {
      gateway_model_access_enabled = var.enable_foundry_gateway_model_access
      gateway_tool_access_enabled  = var.enable_foundry_gateway_tool_access
      monitoring_enabled           = var.enable_foundry_monitoring_integration
      registry_connection_shared   = module.foundry_agents.registry_connection_shared
      insights_connection_id       = module.foundry_agents.monitoring_connection_id
      remote_tool_endpoint         = var.gateway_remote_tool_endpoint
      remote_tool_connection_id    = try(azapi_resource.gateway_remote_tool[0].id, null)
      environment_adapter          = "scripts/export_environment.py"
    }
    lifecycle_owner = "Terraform infrastructure and selected connection/grants only; credentials, tool provisioning and application lifecycle remain external"
    deferred_integrations = concat(
      var.gateway_remote_tool_endpoint == null ? ["RemoteTool"] : [],
      module.ai_gateway.gateway_monitoring.configuration_status == "pending" ? ["native gateway telemetry readiness"] : [],
      ["ToolServer", "Toolbox", "azd deployment integration", "hosted application", "routine", "runtime identity authentication verification"]
    )
  }
}
