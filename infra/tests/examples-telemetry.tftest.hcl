mock_provider "azapi" {
  override_during = plan
  mock_resource "azapi_resource" {
    defaults = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/example/providers/Microsoft.Insights/components/mock"
      output = {}
    }
  }
}

variables {
  subscription_id  = "00000000-0000-0000-0000-000000000001"
  environment_name = "example-fixture"
  location         = "eastus2"
  gateway_native_telemetry = {
    version                 = 1
    gateway_id              = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d/providers/Microsoft.ApiManagement/aigateways/aigw-4f8ff0b60a1d"
    gateway_principal_id    = "00000000-0000-0000-0000-000000000002"
    insights_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d/providers/Microsoft.Insights/components/aigw-4f8ff0b60a1d-insights"
    log_analytics_id        = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d/providers/Microsoft.OperationalInsights/workspaces/aigw-4f8ff0b60a1d-logs"
    data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
    metrics_endpoint        = "https://metrics.example.invalid/otlp/v1/metrics"
    logs_endpoint           = "https://logs.example.invalid/otlp/v1/logs"
    traces_endpoint         = "https://logs.example.invalid/otlp/v1/traces"
  }
}

override_resource {
  target          = azapi_resource.resource_group
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d" }
}
override_resource {
  target          = module.component.azapi_resource.gateway
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d/providers/Microsoft.ApiManagement/aigateways/aigw-4f8ff0b60a1d"
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
  target          = module.component.azapi_resource.insights
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d/providers/Microsoft.Insights/components/aigw-4f8ff0b60a1d-insights"
    output = {
      insights_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d/providers/Microsoft.Insights/components/aigw-4f8ff0b60a1d-insights"
      log_analytics_id        = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d/providers/Microsoft.OperationalInsights/workspaces/aigw-4f8ff0b60a1d-logs"
      managed_ingestion       = "Enabled"
      data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
      metrics_endpoint        = "https://metrics.example.invalid/otlp/v1/metrics"
      logs_endpoint           = "https://logs.example.invalid/otlp/v1/logs"
      traces_endpoint         = "https://logs.example.invalid/otlp/v1/traces"
    }
  }
}
override_resource {
  target          = module.component.azapi_resource.logs
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example-fixture-4f8ff0b60a1d/providers/Microsoft.OperationalInsights/workspaces/aigw-4f8ff0b60a1d-logs" }
}

run "gateway_only_native" {
  command = plan
  module { source = "./examples/gateway-only" }
  assert {
    condition = (
      output.gateway_monitoring.configuration_status == "configured" &&
      output.gateway_monitoring.data_collection_rule_id == var.gateway_native_telemetry.data_collection_rule_id &&
      output.gateway_telemetry_bootstrap.gateway_id == var.gateway_native_telemetry.gateway_id &&
      length(output.model_alias_configuration) == 0
    )
    error_message = "Gateway-only must forward native readiness without acquiring a backend."
  }
}

run "existing_models_native" {
  command = plan
  module { source = "./examples/existing-models" }
  variables {
    backend = {
      account_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing"
      endpoint   = "https://existing.example.invalid/"
      deployment_ids = {
        for key in ["gpt-latest", "gpt-6-sol", "gpt-mini-latest"] :
        key => "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing/deployments/${key}"
      }
    }
  }
  assert {
    condition = (
      output.gateway_monitoring.configuration_status == "configured" &&
      output.gateway_monitoring.data_collection_rule_id == var.gateway_native_telemetry.data_collection_rule_id &&
      output.gateway_telemetry_bootstrap.gateway_id == var.gateway_native_telemetry.gateway_id &&
      length(output.model_alias_configuration["primary-router"].backend_models) == 3
    )
    error_message = "Existing-models must forward native readiness and retain routing without adopting the backend."
  }
}
