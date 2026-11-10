locals {
  monitoring_access = var.monitoring_public_network_access == null ? {} : {
    publicNetworkAccessForIngestion = var.monitoring_public_network_access
    publicNetworkAccessForQuery     = var.monitoring_public_network_access
  }
}
resource "azapi_resource" "logs" {
  type      = "Microsoft.OperationalInsights/workspaces@2023-09-01"
  name      = "${var.name}-logs"
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags
  body = {
    properties = merge({
      retentionInDays = 30
      features        = { enableLogAccessUsingOnlyResourcePermissions = true }
      sku             = { name = "PerGB2018" }
    }, local.monitoring_access)
  }
}

resource "azapi_resource" "insights" {
  type      = "Microsoft.Insights/components@2020-02-02"
  name      = "${var.name}-insights"
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags
  body = {
    kind = "web"
    properties = merge({
      Application_Type    = "web"
      IngestionMode       = "LogAnalytics"
      WorkspaceResourceId = azapi_resource.logs.id
    }, local.monitoring_access)
  }
  response_export_values = ["properties.ConnectionString"]
}
