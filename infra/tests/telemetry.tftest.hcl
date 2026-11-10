mock_provider "azapi" {
  override_during = plan
  mock_resource "azapi_resource" {
    defaults = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/mock"
      output = { properties = { ConnectionString = "synthetic-only-not-a-credential" } }
    }
  }
}

variables {
  subscription_id     = "00000000-0000-0000-0000-000000000001"
  resource_group_id   = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway"
  name                = "gateway-fixture"
  location            = "swedencentral"
  monitoring_location = "eastus2"
  native_telemetry = {
    version                 = 1
    gateway_id              = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.ApiManagement/aigateways/gateway-fixture"
    gateway_principal_id    = "00000000-0000-0000-0000-000000000002"
    insights_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/gateway-fixture-insights"
    log_analytics_id        = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.OperationalInsights/workspaces/gateway-fixture-logs"
    data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
    metrics_endpoint        = "https://metrics.example.invalid/otlp/v1/metrics"
    logs_endpoint           = "https://logs.example.invalid/otlp/v1/logs"
    traces_endpoint         = "https://logs.example.invalid/otlp/v1/traces?api-version=2026-01-01-preview"
  }
}

override_resource {
  target          = azapi_resource.gateway
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.ApiManagement/aigateways/gateway-fixture"
    output = { properties = { frontend = { defaultHostname = "gateway.example.invalid" } } }
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-000000000002"
      tenant_id    = "00000000-0000-0000-0000-000000000003"
      identity_ids = []
    }
  }
}
override_resource {
  target          = azapi_resource.insights
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/gateway-fixture-insights"
    output = {
      insights_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/gateway-fixture-insights"
      log_analytics_id        = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.OperationalInsights/workspaces/gateway-fixture-logs"
      managed_ingestion       = "Enabled"
      data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
      metrics_endpoint        = "https://metrics.example.invalid/otlp/v1/metrics"
      logs_endpoint           = "https://logs.example.invalid/otlp/v1/logs"
      traces_endpoint         = "https://logs.example.invalid/otlp/v1/traces?api-version=2026-01-01-preview"
    }
  }
}
override_resource {
  target          = azapi_resource.logs
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.OperationalInsights/workspaces/gateway-fixture-logs" }
}
override_resource {
  target          = azapi_resource.telemetry_exporter[0]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.ApiManagement/aigateways/gateway-fixture/workspaces/default/telemetryExporters/appinsights" }
}

run "native_telemetry_ready" {
  command = plan
  module { source = "./modules/ai-gateway" }
  assert {
    condition = (
      azapi_resource.insights.body.properties.AzureMonitorWorkspaceIngestionMode == "Enabled" &&
      !can(azapi_resource.insights.body.properties.IngestionMode) &&
      output.gateway_monitoring.configuration_status == "configured" &&
      output.gateway_monitoring.data_collection_rule_id == var.native_telemetry.data_collection_rule_id &&
      output.gateway_monitoring.exporter_id == "${output.gateway_workspace_id}/telemetryExporters/appinsights" &&
      azapi_resource.telemetry_exporter[0].body.properties.kind == "OpenTelemetry" &&
      !can(azapi_resource.telemetry_exporter[0].body.properties.applicationInsights.connectionString) &&
      azapi_resource.telemetry_exporter[0].body.properties.openTelemetry.credentials.managedIdentity.resource == "https://monitor.azure.com" &&
      azapi_resource.telemetry_publisher[0].parent_id == var.native_telemetry.data_collection_rule_id &&
      azapi_resource.telemetry_publisher[0].body.properties.principalId == output.gateway_principal_id
    )
    error_message = "Native telemetry must use managed ingestion, exact returned endpoints and the actual gateway identity at DCR scope without a connection-string exporter."
  }
}

run "reject_native_handoff_identity" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    native_telemetry = merge(var.native_telemetry, { gateway_principal_id = "00000000-0000-0000-0000-000000000099" })
  }
  expect_failures = [azapi_resource.telemetry_publisher]
}

run "reject_stale_native_endpoints" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    native_telemetry = merge(var.native_telemetry, { metrics_endpoint = "https://stale.example.invalid/metrics" })
  }
  expect_failures = [azapi_resource.telemetry_publisher]
}

run "reject_unready_native_readback" {
  command = plan
  module { source = "./modules/ai-gateway" }
  override_resource {
    target          = azapi_resource.insights
    override_during = plan
    values = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/gateway-fixture-insights"
      output = {
        insights_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/gateway-fixture-insights"
        log_analytics_id        = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.OperationalInsights/workspaces/gateway-fixture-logs"
        managed_ingestion       = "Enabled"
        data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
        metrics_endpoint        = "https://metrics.example.invalid/otlp/v1/metrics"
        logs_endpoint           = "https://logs.example.invalid/otlp/v1/logs"
        traces_endpoint         = null
      }
    }
  }
  expect_failures = [azapi_resource.telemetry_publisher]
}

run "reject_native_workspace_drift" {
  command = plan
  module { source = "./modules/ai-gateway" }
  override_resource {
    target          = azapi_resource.insights
    override_during = plan
    values = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/gateway-fixture-insights"
      output = {
        insights_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/gateway-fixture-insights"
        log_analytics_id        = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.OperationalInsights/workspaces/other"
        managed_ingestion       = "Enabled"
        data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
        metrics_endpoint        = "https://metrics.example.invalid/otlp/v1/metrics"
        logs_endpoint           = "https://logs.example.invalid/otlp/v1/logs"
        traces_endpoint         = "https://logs.example.invalid/otlp/v1/traces?api-version=2026-01-01-preview"
      }
    }
  }
  expect_failures = [azapi_resource.telemetry_publisher]
}

run "reject_stale_native_dcr" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    native_telemetry = merge(var.native_telemetry, {
      data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/stale"
    })
  }
  expect_failures = [azapi_resource.telemetry_publisher]
}

run "reject_cross_subscription_native_dcr" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    native_telemetry = merge(var.native_telemetry, {
      data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000099/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
    })
  }
  expect_failures = [var.native_telemetry]
}

run "reject_credential_native_endpoint" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    native_telemetry = merge(var.native_telemetry, { metrics_endpoint = "https://metrics.example.invalid/?sig=not-a-credential" })
  }
  expect_failures = [var.native_telemetry]
}

run "reject_legacy_with_native_handoff" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables { telemetry_mode = "ApplicationInsights" }
  expect_failures = [var.native_telemetry]
}
