locals {
  storage_public_network_access = coalesce(var.storage_public_network_access, var.public_network_access)
}

resource "azapi_resource" "agents" {
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
      allowProjectManagement = true
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
}

resource "azapi_resource" "storage" {
  type      = "Microsoft.Storage/storageAccounts@2024-01-01"
  name      = var.names.storage
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags
  body = {
    kind = "StorageV2"
    sku  = { name = "Standard_LRS" }
    properties = {
      minimumTlsVersion     = "TLS1_2"
      allowBlobPublicAccess = false
      allowSharedKeyAccess  = false
      publicNetworkAccess   = local.storage_public_network_access
      networkAcls = merge({
        bypass              = "AzureServices"
        defaultAction       = local.storage_public_network_access == "Disabled" ? "Deny" : "Allow"
        virtualNetworkRules = []
        }, local.storage_public_network_access == "Disabled" ? {
        # AzAPI needs this path in the request body to overlay its live value.
        resourceAccessRules = []
      } : {})
    }
  }
  response_export_values = ["properties.primaryEndpoints.blob"]
  lifecycle {
    ignore_changes = [body.properties.networkAcls.resourceAccessRules]
  }
}

resource "azapi_resource" "registry" {
  type      = "Microsoft.ContainerRegistry/registries@2023-07-01"
  name      = var.names.registry
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags
  identity { type = "SystemAssigned" }
  body = {
    sku = { name = "Premium" }
    properties = {
      adminUserEnabled    = false
      publicNetworkAccess = var.public_network_access
      zoneRedundancy      = "Disabled"
    }
  }
  response_export_values = ["properties.loginServer"]
}

resource "azapi_resource" "project" {
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview"
  name      = var.names.project
  parent_id = azapi_resource.agents.id
  location  = var.location
  tags      = var.tags
  identity { type = "SystemAssigned" }
  body = {
    properties = {
      displayName = var.project_display_name
      description = var.project_description
    }
  }
}

resource "azapi_resource" "storage_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name      = var.names.storage
  parent_id = azapi_resource.project.id
  body = {
    properties = {
      category = "AzureStorageAccount"
      target   = azapi_resource.storage.output.properties.primaryEndpoints.blob
      authType = "AAD"
      metadata = {
        ApiType    = "Azure"
        ResourceId = azapi_resource.storage.id
        location   = var.location
      }
    }
  }
  depends_on = [azapi_resource.role_assignment["project-storage"]]
}

resource "azapi_resource" "registry_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name      = "${var.names.registry}-conn"
  parent_id = azapi_resource.project.id
  # The service accepts isDefault, but the pinned preview schema omits it.
  schema_validation_enabled = false
  response_export_values = {
    isDefault     = "properties.isDefault"
    isSharedToAll = "properties.isSharedToAll"
  }
  body = {
    properties = {
      category      = "ContainerRegistry"
      target        = azapi_resource.registry.output.properties.loginServer
      authType      = "ManagedIdentity"
      isSharedToAll = var.share_registry_connection
      isDefault     = true
      credentials = {
        clientId   = azapi_resource.project.identity[0].principal_id
        resourceId = azapi_resource.registry.id
      }
      metadata = { ResourceId = azapi_resource.registry.id }
    }
  }
  depends_on = [azapi_resource.role_assignment["project-acr-pull"]]
}

resource "azapi_resource_action" "registry_connection_sharing" {
  count       = var.share_registry_connection ? 1 : 0
  type        = azapi_resource.registry_connection.type
  resource_id = azapi_resource.registry_connection.id
  method      = "PATCH"
  when        = "apply"
  body = {
    # PUT can reset sharing; PATCH must preserve default selection as well.
    properties = merge(azapi_resource.registry_connection.body.properties, {
      isSharedToAll = true
      isDefault     = true
    })
  }
  lifecycle {
    replace_triggered_by = [azapi_resource.registry_connection]
  }
}

data "azapi_resource" "registry_connection_readback" {
  count       = var.share_registry_connection ? 1 : 0
  type        = azapi_resource.registry_connection.type
  resource_id = azapi_resource.registry_connection.id
  response_export_values = {
    isDefault     = "properties.isDefault"
    isSharedToAll = "properties.isSharedToAll"
  }
  depends_on = [azapi_resource_action.registry_connection_sharing]
  lifecycle {
    postcondition {
      condition     = try(self.output.isSharedToAll == true && self.output.isDefault == true, false)
      error_message = "Azure did not retain the shared, default registry connection. Stop before deploying the hosted agent."
    }
  }
}

resource "azapi_resource" "project_insights_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  name                      = azapi_resource.insights.name
  parent_id                 = azapi_resource.project.id
  schema_validation_enabled = !var.enable_monitoring_integration
  body = {
    properties = merge({
      category      = "AppInsights"
      authType      = var.enable_monitoring_integration ? "ProjectManagedIdentity" : "ApiKey"
      isSharedToAll = false
      target        = azapi_resource.insights.id
      metadata = merge({
        ApiType    = "Azure"
        ResourceId = azapi_resource.insights.id
        }, var.enable_monitoring_integration ? {
        ApplicationInsightsConnectionString = azapi_resource.insights.output.properties.ConnectionString
        displayName                         = azapi_resource.insights.name
      } : { location = var.location })
      }, var.enable_monitoring_integration ? {} : {
      credentials = { key = azapi_resource.insights.output.properties.ConnectionString }
    })
  }
  depends_on = [
    azapi_resource.role_assignment["monitoring-account"],
    azapi_resource.role_assignment["monitoring-project"],
  ]
}
