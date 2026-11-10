locals {
  native_telemetry_enabled = var.telemetry_mode == "OpenTelemetry"
  native_telemetry_ready   = local.native_telemetry_enabled && var.native_telemetry != null
  monitoring_access = var.monitoring_public_network_access == null ? {} : {
    publicNetworkAccessForIngestion = var.monitoring_public_network_access
    publicNetworkAccessForQuery     = var.monitoring_public_network_access
  }
}
resource "azapi_resource" "logs" {
  type      = "Microsoft.OperationalInsights/workspaces@2023-09-01"
  name      = "${var.name}-logs"
  parent_id = var.resource_group_id
  location  = var.monitoring_location
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
  # The managed-ingestion property is absent from the bundled component schema.
  schema_validation_enabled = !local.native_telemetry_enabled
  type                      = "Microsoft.Insights/components@2020-02-02"
  name                      = "${var.name}-insights"
  parent_id                 = var.resource_group_id
  location                  = var.monitoring_location
  tags                      = var.tags
  body = {
    kind = "web"
    properties = merge({
      Application_Type    = "web"
      WorkspaceResourceId = azapi_resource.logs.id
      }, local.native_telemetry_enabled ? {
      AzureMonitorWorkspaceIngestionMode = "Enabled"
      } : {
      IngestionMode = "LogAnalytics"
    }, local.monitoring_access)
  }
  # Stage two uses the managed resource's normal plan refresh, not a second reader.
  response_export_values = local.native_telemetry_enabled ? {
    insights_id             = "id"
    managed_ingestion       = "properties.AzureMonitorWorkspaceIngestionMode"
    log_analytics_id        = "properties.WorkspaceResourceId"
    data_collection_rule_id = "properties.DefaultDataCollectionRuleResourceId || properties.DataCollectionRuleResourceId"
    metrics_endpoint        = "properties.MetricsIngestionEndpoint || properties.OTLPMetricsEndpoint"
    logs_endpoint           = "properties.LogsIngestionEndpoint || properties.OTLPLogsEndpoint"
    traces_endpoint         = "properties.TracesIngestionEndpoint || properties.OTLPTracesEndpoint"
    } : {
    properties = "{ConnectionString: properties.ConnectionString}"
  }
}
