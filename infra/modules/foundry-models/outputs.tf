output "account_id" {
  value      = azapi_resource.models.id
  depends_on = [data.azapi_resource.models_readback]
}
output "endpoint" {
  value      = azapi_resource.models.output.properties.endpoint
  depends_on = [data.azapi_resource.models_readback]
}
output "deployment_ids" {
  value      = { for key, deployment in azapi_resource.model_deployment : key => deployment.id }
  depends_on = [data.azapi_resource.models_readback]
}
output "backend" {
  description = "Typed nonsecret backend descriptor; logical deployment keys remain known during planning."
  value = {
    account_id     = azapi_resource.models.id
    endpoint       = azapi_resource.models.output.properties.endpoint
    deployment_ids = { for key, deployment in azapi_resource.model_deployment : key => deployment.id }
  }
  depends_on = [data.azapi_resource.models_readback]
}
