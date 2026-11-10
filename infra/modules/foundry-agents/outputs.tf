output "account_id" { value = azapi_resource.agents.id }
output "account_principal_id" { value = azapi_resource.agents.identity[0].principal_id }
output "project_id" { value = azapi_resource.project.id }
output "project_principal_id" { value = azapi_resource.project.identity[0].principal_id }
output "project_endpoint" { value = "https://${var.name}.services.ai.azure.com/api/projects/${var.names.project}" }
output "container_registry_id" { value = azapi_resource.registry.id }
output "container_registry_endpoint" { value = azapi_resource.registry.output.properties.loginServer }
output "registry_connection_name" { value = azapi_resource.registry_connection.name }
output "registry_connection_id" { value = azapi_resource.registry_connection.id }
output "registry_connection_shared" {
  description = "Configured sharing request, not independent Azure readback or proof of image-pull access."
  value       = azapi_resource.registry_connection.body.properties.isSharedToAll
  depends_on  = [data.azapi_resource.registry_connection_readback]
}
output "storage_account_name" { value = azapi_resource.storage.name }
output "storage_account_id" { value = azapi_resource.storage.id }
output "application_insights_id" { value = azapi_resource.insights.id }
output "monitoring_connection_id" { value = var.enable_monitoring_integration ? azapi_resource.project_insights_connection.id : null }
output "log_analytics_id" { value = azapi_resource.logs.id }
