output "gateway_id" { value = azapi_resource.gateway.id }
output "gateway_endpoint" { value = local.gateway_endpoint }
output "gateway_principal_id" { value = azapi_resource.gateway.identity[0].principal_id }
output "gateway_workspace_id" { value = local.gateway_workspace_id }
output "gateway_api_key_id" {
  description = "Resource ID only. No runtime key value is read or exported."
  value       = azapi_resource.runtime_api_key.id
}
output "gateway_api_versions" {
  value = {
    gateway   = local.gateway_api_version
    catalog   = local.gateway_api_version
    aliases   = local.gateway_api_version
    api_keys  = local.gateway_api_version
    telemetry = local.gateway_telemetry_api_version
  }
}
output "gateway_monitoring" {
  description = "Configuration metadata, not proof of correlated telemetry delivery."
  value = {
    kind                    = local.native_telemetry_enabled ? "openTelemetry" : "applicationInsights"
    configuration_status    = local.native_telemetry_enabled ? (local.native_telemetry_ready ? "configured" : "pending") : "legacy"
    insights_id             = azapi_resource.insights.id
    log_analytics_id        = azapi_resource.logs.id
    exporter_id             = try(azapi_resource.telemetry_exporter[0].id, null)
    data_collection_rule_id = try(azapi_resource.telemetry_publisher[0].parent_id, null)
  }
}
output "gateway_telemetry_bootstrap" {
  description = "Nonsecret input to the separate GET-only readiness helper. Does not authorize apply or prove telemetry delivery."
  value = {
    version              = 1
    subscription_id      = var.subscription_id
    mode                 = var.telemetry_mode
    gateway_id           = azapi_resource.gateway.id
    gateway_principal_id = azapi_resource.gateway.identity[0].principal_id
    insights_id          = azapi_resource.insights.id
    log_analytics_id     = azapi_resource.logs.id
  }
}
output "model_api_configuration" {
  description = "Non-secret API metadata used to check compatibility before running the sample's chat-completions probes."
  value = { for key, model in var.model_deployments : key => {
    api_format = model.api_format
    endpoints  = model.endpoints
  } }
}
output "model_alias_configuration" {
  description = "Callable aliases, catalog routes and common API metadata. Alias ARM names and deployment names need not be the same."
  value = { for key, alias in local.gateway_aliases : key => {
    alias_name = alias.alias_name
    api_format = try(var.model_deployments[alias.backend_models[0].deployment].api_format, null)
    endpoints = try(sort(tolist(setintersection([
      for backend in alias.backend_models : toset(var.model_deployments[backend.deployment].endpoints)
    ]...))), [])
    backend_models = alias.backend_models
  } }
}
