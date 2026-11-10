moved {
  from = azapi_resource.telemetry_exporter
  to   = azapi_resource.telemetry_exporter[0]
}

resource "azapi_resource" "telemetry_publisher" {
  count     = local.native_telemetry_ready ? 1 : 0
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
  name      = uuidv5("url", lower("${azapi_resource.insights.output.data_collection_rule_id}/${azapi_resource.gateway.identity[0].principal_id}/3913510d-42f4-4e42-8a64-420c390055eb"))
  parent_id = azapi_resource.insights.output.data_collection_rule_id
  body = {
    properties = {
      principalId      = azapi_resource.gateway.identity[0].principal_id
      principalType    = "ServicePrincipal"
      roleDefinitionId = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/3913510d-42f4-4e42-8a64-420c390055eb"
    }
  }
  lifecycle {
    precondition {
      condition = try(
        lower(var.native_telemetry.gateway_id) == lower(azapi_resource.gateway.id) &&
        lower(var.native_telemetry.gateway_principal_id) == lower(azapi_resource.gateway.identity[0].principal_id) &&
        lower(var.native_telemetry.insights_id) == lower(azapi_resource.insights.id) &&
        lower(var.native_telemetry.log_analytics_id) == lower(azapi_resource.logs.id),
        false
      )
      error_message = "The native telemetry handoff must belong to this gateway identity, Insights component and Log Analytics workspace."
    }
    precondition {
      condition = try(
        lower(azapi_resource.insights.output.insights_id) == lower(azapi_resource.insights.id) &&
        lower(azapi_resource.insights.output.log_analytics_id) == lower(azapi_resource.logs.id) &&
        (try(azapi_resource.insights.output.managed_ingestion, null) == null || try(azapi_resource.insights.output.managed_ingestion, null) == "Enabled") &&
        lower(azapi_resource.insights.output.data_collection_rule_id) == lower(var.native_telemetry.data_collection_rule_id) &&
        azapi_resource.insights.output.metrics_endpoint == var.native_telemetry.metrics_endpoint &&
        azapi_resource.insights.output.logs_endpoint == var.native_telemetry.logs_endpoint &&
        azapi_resource.insights.output.traces_endpoint == var.native_telemetry.traces_endpoint,
        false
      )
      error_message = "Insights readiness changed or is incomplete. Rerun the GET-only readiness helper and review a fresh plan; do not guess endpoints or broaden the DCR scope."
    }
  }
}

resource "azapi_resource" "telemetry_exporter" {
  count = !local.native_telemetry_enabled || local.native_telemetry_ready ? 1 : 0
  # This preview type is not yet present in AzAPI's bundled schema.
  schema_validation_enabled = false
  type                      = "${local.gateway_type}/workspaces/telemetryExporters@${local.gateway_telemetry_api_version}"
  name                      = "appinsights"
  parent_id                 = local.gateway_workspace_id
  body = {
    properties = merge({
      kind           = var.telemetry_mode
      payloadCapture = false
      applicationInsights = merge(
        { resourceId = azapi_resource.insights.id },
        local.native_telemetry_enabled ? {} : {
          connectionString = try(azapi_resource.insights.output.properties.ConnectionString, null)
        }
      )
      }, local.native_telemetry_enabled ? {
      openTelemetry = {
        metricsEndpoint = azapi_resource.insights.output.metrics_endpoint
        logsEndpoint    = azapi_resource.insights.output.logs_endpoint
        tracesEndpoint  = azapi_resource.insights.output.traces_endpoint
        credentials     = { managedIdentity = { resource = "https://monitor.azure.com" } }
      }
    } : {})
  }
  replace_triggers_refs = ["properties.kind"]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = local.native_telemetry_enabled || try(length(trimspace(azapi_resource.insights.output.properties.ConnectionString)) > 0, false)
      error_message = "The explicit legacy exporter requires the returned gateway Insights ConnectionString; incomplete exporters are rejected."
    }
  }
  depends_on = [azapi_resource.role_assignment, azapi_resource.telemetry_publisher]
}
