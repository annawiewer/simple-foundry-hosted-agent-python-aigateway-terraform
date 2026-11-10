resource "azapi_resource" "models" {
  type      = "Microsoft.CognitiveServices/accounts@2025-04-01-preview"
  name      = var.name
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags
  identity { type = "SystemAssigned" }
  body = {
    kind = "AIServices"
    sku  = { name = "S0" }
    properties = {
      allowProjectManagement = false
      customSubDomainName    = var.name
      disableLocalAuth       = true
      publicNetworkAccess    = var.public_network_access
      networkAcls = {
        defaultAction       = var.public_network_access == "Disabled" ? "Deny" : "Allow"
        virtualNetworkRules = []
        ipRules             = []
      }
    }
  }
  response_export_values = ["properties.endpoint"]
}

data "azapi_resource" "models_readback" {
  type        = azapi_resource.models.type
  resource_id = azapi_resource.models.id
  response_export_values = {
    allowProjectManagement = "properties.allowProjectManagement"
  }
  # A successful account update can leave project management enabled.
  depends_on = [azapi_resource.models]
  lifecycle {
    postcondition {
      condition     = try(self.output.allowProjectManagement == false, false)
      error_message = "Azure did not confirm allowProjectManagement=false on the model-only account. Stop before deploying models; review an explicit migration for an existing project-enabled AIServices account."
    }
  }
}

resource "azapi_resource" "model_deployment" {
  for_each  = var.model_deployments
  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview"
  name      = each.key
  parent_id = azapi_resource.models.id
  # Cognitive Services permits only one deployment operation per account at a time.
  locks = [azapi_resource.models.id]
  body = {
    sku = {
      name     = each.value.sku_name
      capacity = each.value.capacity
    }
    properties = {
      model = {
        name    = each.value.model_name
        version = each.value.model_version
        format  = each.value.model_format
      }
    }
  }
  depends_on = [data.azapi_resource.models_readback]
}
