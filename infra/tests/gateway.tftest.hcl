mock_provider "azapi" {
  override_during = plan
  mock_resource "azapi_resource" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.Insights/components/monitoring"
      output = {
        properties = {
          ConnectionString = "synthetic-only-not-a-credential"
          frontend         = { defaultHostname = "gateway.example.invalid" }
        }
      }
    }
  }
}

override_resource {
  target          = azapi_resource.gateway
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.ApiManagement/aigateways/fixture"
    output = { properties = { frontend = { defaultHostname = "gateway.example.invalid" } } }
  }
}

variables {
  subscription_id     = "00000000-0000-0000-0000-000000000001"
  resource_group_id   = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway"
  name                = "gateway-fixture"
  location            = "swedencentral"
  monitoring_location = "eastus2"
}

run "gateway_module" {
  command = plan
  module { source = "./modules/ai-gateway" }
  assert {
    condition     = output.gateway_endpoint == "https://gateway.example.invalid" && length(output.model_alias_configuration) == 0
    error_message = "The standalone gateway scaffold must expose only its returned frontend and no fabricated aliases."
  }
  assert {
    condition = (
      output.gateway_monitoring.kind == "openTelemetry" &&
      output.gateway_monitoring.configuration_status == "pending" &&
      output.gateway_monitoring.exporter_id == null &&
      output.gateway_monitoring.data_collection_rule_id == null &&
      length(azapi_resource.telemetry_exporter) == 0 &&
      length(azapi_resource.telemetry_publisher) == 0
    )
    error_message = "Stage one must request native ingestion but neither fake readiness nor create an incomplete exporter or DCR grant."
  }
}

run "gateway_legacy_telemetry" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables { telemetry_mode = "ApplicationInsights" }
  assert {
    condition = (
      azapi_resource.insights.body.properties.IngestionMode == "LogAnalytics" &&
      !can(azapi_resource.insights.body.properties.AzureMonitorWorkspaceIngestionMode) &&
      output.gateway_monitoring.configuration_status == "legacy" &&
      azapi_resource.telemetry_exporter[0].name == "appinsights" &&
      azapi_resource.telemetry_exporter[0].body.properties.kind == "ApplicationInsights" &&
      length(azapi_resource.telemetry_publisher) == 0
    )
    error_message = "Explicit compatibility mode must retain the legacy exporter name/body without enabling native managed ingestion or DCR access."
  }
}

run "nullable_frontend_no_legacy_fallback" {
  command = plan
  module { source = "./modules/ai-gateway" }
  override_resource {
    target          = azapi_resource.gateway
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/gateway/providers/Microsoft.ApiManagement/aigateways/fixture"
      output = { properties = { frontend = { defaultHostname = null }, gatewayUrl = "https://legacy.example.invalid" } }
    }
  }
  assert {
    condition     = output.gateway_endpoint == ""
    error_message = "A null standalone frontend must not use a legacy or constructed endpoint."
  }
}

run "missing_insights_destination" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables { telemetry_mode = "ApplicationInsights" }
  override_resource {
    target          = azapi_resource.insights
    override_during = plan
    values          = { output = { properties = {} } }
  }
  expect_failures = [azapi_resource.telemetry_exporter]
}

run "reject_unknown_caller" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    gateway_access_principals = { bad = { principal_id = "not-a-uuid" } }
  }
  expect_failures = [var.gateway_access_principals]
}

run "reject_duplicate_caller" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    gateway_access_principals = {
      first  = { principal_id = "00000000-0000-0000-0000-000000000002" }
      second = { principal_id = "00000000-0000-0000-0000-000000000002" }
    }
  }
  expect_failures = [var.gateway_access_principals]
}

run "existing_outbound_subnet" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    gateway_backend_subnet_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/platform/providers/Microsoft.Network/virtualNetworks/shared/subnets/backend"
  }
  override_data {
    target = data.azapi_resource.gateway_backend_subnet[0]
    values = { output = { properties = { delegations = [{ properties = { serviceName = "Microsoft.App/environments" } }] } } }
  }
  override_data {
    target = data.azapi_resource.gateway_backend_vnet[0]
    values = { output = { location = "Sweden Central" } }
  }
  assert {
    condition = (
      azapi_resource.gateway.body.properties.backend.subnet.id == var.gateway_backend_subnet_id &&
      toset(keys(azapi_resource.gateway.body.properties)) == toset(["backend"]) &&
      !can(azapi_resource.gateway.body.properties.publicNetworkAccess)
    )
    error_message = "External subnet integration must remain creation-only/outbound-only with no invented private ingress."
  }
}

run "reject_legacy_subnet_delegation" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    gateway_backend_subnet_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/platform/providers/Microsoft.Network/virtualNetworks/shared/subnets/backend"
  }
  override_data {
    target = data.azapi_resource.gateway_backend_subnet[0]
    values = { output = { properties = { delegations = [{ properties = { serviceName = "Microsoft.Web/serverFarms" } }] } } }
  }
  override_data {
    target = data.azapi_resource.gateway_backend_vnet[0]
    values = { output = { location = "swedencentral" } }
  }
  expect_failures = [azapi_resource.gateway]
}

run "reject_wrong_subnet_region" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    gateway_backend_subnet_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/platform/providers/Microsoft.Network/virtualNetworks/shared/subnets/backend"
  }
  override_data {
    target = data.azapi_resource.gateway_backend_subnet[0]
    values = { output = { properties = { delegations = [{ properties = { serviceName = "Microsoft.App/environments" } }] } } }
  }
  override_data {
    target = data.azapi_resource.gateway_backend_vnet[0]
    values = { output = { location = "eastus2" } }
  }
  expect_failures = [azapi_resource.gateway]
}

run "reject_cross_subscription_backend" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    model_deployments = jsondecode(file("model-profile.json")).model_deployments
    backend = {
      account_id = "/subscriptions/00000000-0000-0000-0000-000000000099/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing"
      endpoint   = "https://existing.example.invalid/"
      deployment_ids = {
        for key in ["gpt-latest", "gpt-6-sol", "gpt-mini-latest"] :
        key => "/subscriptions/00000000-0000-0000-0000-000000000099/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing/deployments/${key}"
      }
    }
  }
  expect_failures = [var.backend]
}

run "reject_backend_key_mismatch" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    model_deployments = jsondecode(file("model-profile.json")).model_deployments
    backend = {
      account_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing"
      endpoint   = "https://existing.example.invalid/"
      deployment_ids = {
        for key in ["gpt-latest", "gpt-6-sol"] :
        key => "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing/deployments/${key}"
      }
    }
  }
  expect_failures = [var.model_deployments]
}

run "reject_invalid_gateway_safety" {
  command = plan
  module { source = "./modules/ai-gateway" }
  variables {
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, { content_safety_severity = "None" })
    }
    backend = {
      account_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing"
      endpoint   = "https://existing.example.invalid/"
      deployment_ids = {
        for key in ["gpt-latest", "gpt-6-sol", "gpt-mini-latest"] :
        key => "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing/deployments/${key}"
      }
    }
  }
  expect_failures = [var.model_deployments]
}
