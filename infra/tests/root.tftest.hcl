mock_provider "azapi" {
  override_during = plan
  mock_resource "azapi_resource" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/mock/providers/Microsoft.Insights/components/mock"
      # Stabilize optional/computed metadata across isolated naming scenarios.
      location = "synthetic-location"
      output = {
        properties = {
          ConnectionString = "synthetic-only-not-a-credential"
          endpoint         = "https://models.example.invalid/"
          frontend         = { defaultHostname = "gateway.example.invalid" }
          primaryEndpoints = { blob = "https://storage.example.invalid/" }
          loginServer      = "registry.example.invalid"
        }
      }
    }
  }
  mock_data "azapi_resource" {
    defaults = { output = { isDefault = true, isSharedToAll = true, allowProjectManagement = false } }
  }
}

variables {
  subscription_id  = "00000000-0000-0000-0000-000000000001"
  environment_name = "offline-fixture"
  location         = "eastus2"
  gateway_location = "swedencentral"
}

# Literal mock IDs must follow the names generated from these synthetic inputs.
override_resource {
  target          = azapi_resource.resource_group["gateway"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway" }
}
override_resource {
  target          = azapi_resource.resource_group["models"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models" }
}
override_resource {
  target          = azapi_resource.resource_group["agents"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents" }
}
override_resource {
  target          = module.ai_gateway.azapi_resource.gateway
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957"
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
  target          = module.foundry_models.azapi_resource.models
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957"
    output = { properties = { endpoint = "https://models.example.invalid/" } }
  }
}
override_resource {
  target          = module.foundry_models.azapi_resource.model_deployment["gpt-latest"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957/deployments/gpt-latest" }
}
override_resource {
  target          = module.foundry_models.azapi_resource.model_deployment["gpt-6-sol"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957/deployments/gpt-6-sol" }
}
override_resource {
  target          = module.foundry_models.azapi_resource.model_deployment["gpt-mini-latest"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957/deployments/gpt-mini-latest" }
}
override_resource {
  target          = module.foundry_agents.azapi_resource.agents
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.CognitiveServices/accounts/aiagents-470daa23c957"
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-000000000007"
      tenant_id    = "00000000-0000-0000-0000-000000000003"
      identity_ids = []
    }
  }
}
override_resource {
  target          = module.foundry_agents.azapi_resource.project
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.CognitiveServices/accounts/aiagents-470daa23c957/projects/proj-470daa23c957"
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-000000000004"
      tenant_id    = "00000000-0000-0000-0000-000000000003"
      identity_ids = []
    }
  }
}
override_resource {
  target          = module.foundry_agents.azapi_resource.storage
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.Storage/storageAccounts/st470daa23c957"
    output = { properties = { primaryEndpoints = { blob = "https://storage.example.invalid/" } } }
  }
}
override_resource {
  target          = module.foundry_agents.azapi_resource.registry
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.ContainerRegistry/registries/acr470daa23c957"
    output = { properties = { loginServer = "registry.example.invalid" } }
  }
}
override_resource {
  target          = module.ai_gateway.azapi_resource.insights
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.Insights/components/gateway"
    output = { properties = { ConnectionString = "synthetic-only-not-a-credential" } }
  }
}
override_resource {
  target          = module.ai_gateway.azapi_resource.logs
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.OperationalInsights/workspaces/aigw-470daa23c957-logs" }
}
override_resource {
  target          = module.ai_gateway.azapi_resource.foundry_provider[0]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957/workspaces/default/modelProviders/foundry" }
}
override_resource {
  target          = module.ai_gateway.azapi_resource.catalog_model["gpt-latest"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957/workspaces/default/modelProviders/foundry/models/gpt-latest" }
}
override_resource {
  target          = module.ai_gateway.azapi_resource.catalog_model["gpt-6-sol"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957/workspaces/default/modelProviders/foundry/models/gpt-6-sol" }
}
override_resource {
  target          = module.ai_gateway.azapi_resource.catalog_model["gpt-mini-latest"]
  override_during = plan
  values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957/workspaces/default/modelProviders/foundry/models/gpt-mini-latest" }
}
override_resource {
  target          = module.foundry_agents.azapi_resource.insights
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.Insights/components/agents"
    output = { properties = { ConnectionString = "synthetic-only-not-a-credential" } }
  }
}

run "root_default" {
  command = plan
  assert {
    condition     = local.names.models == "aimodels-470daa23c957"
    error_message = "A null model-account override must preserve the existing generated name."
  }
  assert {
    condition = (
      output.gateway_monitoring.configuration_status == "pending" &&
      output.gateway_monitoring.exporter_id == null &&
      output.gateway_telemetry_bootstrap.mode == "OpenTelemetry" &&
      output.gateway_telemetry_bootstrap.gateway_principal_id == output.deployment_contract.gateway.principal_id &&
      contains(output.deployment_contract.deferred_integrations, "native gateway telemetry readiness")
    )
    error_message = "The default root must expose native bootstrap metadata and explicitly defer its exporter until stage two."
  }
  assert {
    condition = (
      length(azapi_resource.foundry_gateway_model_access) == 2 &&
      length(azapi_resource.foundry_gateway_tool_access) == 1 &&
      length(azapi_resource.hosted_agent_runtime_access) == 0 &&
      length(azapi_resource.gateway_remote_tool) == 0 &&
      output.deployment_contract.integration.gateway_model_access_enabled &&
      output.deployment_contract.integration.gateway_tool_access_enabled &&
      output.deployment_contract.integration.monitoring_enabled &&
      output.deployment_contract.integration.registry_connection_shared &&
      output.deployment_contract.integration.insights_connection_id != null &&
      output.deployment_contract.integration.remote_tool_connection_id == null
    )
    error_message = "The application root must default to scoped Foundry model/tool access, monitoring and shared registry support without inventing a RemoteTool."
  }
  assert {
    condition = (
      output.gateway_endpoint == "https://gateway.example.invalid" &&
      output.gateway_contract.name == "2026" &&
      alltrue([for k in ["gateway", "catalog", "aliases", "api_keys"] : output.gateway_api_versions[k] == "2025-09-01-preview"]) &&
      output.gateway_api_versions.telemetry == "2025-09-01-preview" &&
      length(distinct(values(output.resource_groups))) == 3 &&
      output.model_alias_configuration["primary-router"].alias_name == "gpt-latest" &&
      length(output.model_alias_configuration["primary-router"].backend_models) == 3 &&
      output.model_alias_configuration["mini-router"].alias_name == "gpt-mini-latest" &&
      alltrue([for k in ["models", "agents", "storage", "registry"] : output.backend_public_network_access[k] == "Enabled"]) &&
      output.backend_public_network_access.monitoring_ingestion == "Unspecified"
    )
    error_message = "Fresh root must compose the pinned 2025 gateway API, three workload groups and real routed profile."
  }
  assert {
    condition = (
      output.deployment_contract.version == 1 &&
      !strcontains(jsonencode(output.deployment_contract), "synthetic-only-not-a-credential") &&
      !strcontains(jsonencode(output.deployment_contract), "connectionString") &&
      contains(output.deployment_contract.deferred_integrations, "ToolServer") &&
      contains(output.deployment_contract.deferred_integrations, "RemoteTool")
    )
    error_message = "The handoff is an allow-listed nonsecret infrastructure contract, not fabricated application parity."
  }
}

run "root_optional_request_limits" {
  command = plan
  variables {
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(
        { for field, value in model : field => value if field != "request_limit" },
        { content_safety_severity = "Medium" },
        {
          gpt-latest      = { request_limit = 1 }
          gpt-6-sol       = { request_limit = null }
          gpt-mini-latest = {}
        }[key]
      )
    }
  }
}

run "root_content_safety_overrides" {
  command = plan
  variables {
    model_allowed_client_cidrs = ["203.0.113.42/32", "2001:db8:1234::/48", "203.0.113.42/32"]
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, {
        content_safety_severity = {
          gpt-latest      = "Low"
          gpt-6-sol       = "High"
          gpt-mini-latest = null
        }[key]
      })
    }
  }
}

run "root_content_safety_disabled" {
  command = plan
  variables {
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, { content_safety_severity = null })
    }
  }
}

run "root_native_telemetry" {
  command = plan
  variables {
    gateway_native_telemetry = {
      version                 = 1
      gateway_id              = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957"
      gateway_principal_id    = "00000000-0000-0000-0000-000000000002"
      insights_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.Insights/components/gateway"
      log_analytics_id        = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.OperationalInsights/workspaces/aigw-470daa23c957-logs"
      data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
      metrics_endpoint        = "https://metrics.example.invalid/otlp/v1/metrics"
      logs_endpoint           = "https://logs.example.invalid/otlp/v1/logs"
      traces_endpoint         = "https://logs.example.invalid/otlp/v1/traces"
    }
  }
  override_resource {
    target          = module.ai_gateway.azapi_resource.insights
    override_during = plan
    values = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.Insights/components/gateway"
      output = {
        insights_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.Insights/components/gateway"
        log_analytics_id        = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.OperationalInsights/workspaces/aigw-470daa23c957-logs"
        managed_ingestion       = "Enabled"
        data_collection_rule_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/managed-monitoring/providers/Microsoft.Insights/dataCollectionRules/native"
        metrics_endpoint        = "https://metrics.example.invalid/otlp/v1/metrics"
        logs_endpoint           = "https://logs.example.invalid/otlp/v1/logs"
        traces_endpoint         = "https://logs.example.invalid/otlp/v1/traces"
      }
    }
  }
  assert {
    condition = (
      output.gateway_monitoring.configuration_status == "configured" &&
      output.gateway_monitoring.data_collection_rule_id == var.gateway_native_telemetry.data_collection_rule_id &&
      !contains(output.deployment_contract.deferred_integrations, "native gateway telemetry readiness")
    )
    error_message = "The second-stage root handoff must reach the gateway module and remove only the completed configuration gate."
  }
}

run "root_legacy_telemetry" {
  command = plan
  variables { gateway_telemetry_mode = "ApplicationInsights" }
  assert {
    condition     = output.gateway_monitoring.configuration_status == "legacy" && output.gateway_monitoring.kind == "applicationInsights"
    error_message = "The root must forward the explicit legacy compatibility choice."
  }
}

run "root_minimal" {
  command = plan
  variables {
    enable_foundry_gateway_model_access   = false
    enable_foundry_gateway_tool_access    = false
    enable_foundry_monitoring_integration = false
    share_foundry_registry_connection     = false
  }
  assert {
    condition = (
      length(azapi_resource.foundry_gateway_model_access) == 0 &&
      length(azapi_resource.foundry_gateway_tool_access) == 0 &&
      length(azapi_resource.gateway_remote_tool) == 0 &&
      !output.deployment_contract.integration.gateway_model_access_enabled &&
      !output.deployment_contract.integration.gateway_tool_access_enabled &&
      !output.deployment_contract.integration.monitoring_enabled &&
      !output.deployment_contract.integration.registry_connection_shared &&
      output.deployment_contract.integration.insights_connection_id == null &&
      output.deployment_contract.integration.remote_tool_connection_id == null
    )
    error_message = "Explicit opt-outs must preserve the previous minimal root behavior and unshared registry connection."
  }
}

run "root_foundry_gateway_model_access" {
  command = plan
  variables {
    enable_foundry_gateway_model_access   = true
    enable_foundry_gateway_tool_access    = false
    enable_foundry_monitoring_integration = false
    share_foundry_registry_connection     = false
  }
  assert {
    condition = (
      toset(keys(azapi_resource.foundry_gateway_model_access)) == toset(["account", "project"]) &&
      azapi_resource.foundry_gateway_model_access["account"].body.properties.principalId == "00000000-0000-0000-0000-000000000007" &&
      azapi_resource.foundry_gateway_model_access["project"].body.properties.principalId == "00000000-0000-0000-0000-000000000004" &&
      alltrue([for role in azapi_resource.foundry_gateway_model_access :
        role.parent_id == module.ai_gateway.gateway_id &&
        role.body.properties.principalType == "ServicePrincipal" &&
        role.body.properties.roleDefinitionId == "/subscriptions/00000000-0000-0000-0000-000000000001/providers/Microsoft.Authorization/roleDefinitions/a6b68e3d-a1f0-4c60-8678-237c050cf4ea"
      ]) &&
      length(azapi_resource.gateway_remote_tool) == 0
    )
    error_message = "Selected model grants must use stable account/project keys and exact caller principals/role at gateway scope, independently of tools."
  }
}

run "root_foundry_gateway_tool_access" {
  command = plan
  variables {
    enable_foundry_gateway_model_access   = false
    enable_foundry_gateway_tool_access    = true
    enable_foundry_monitoring_integration = false
    share_foundry_registry_connection     = false
  }
  assert {
    condition = (
      toset(keys(azapi_resource.foundry_gateway_tool_access)) == toset(["project"]) &&
      azapi_resource.foundry_gateway_tool_access["project"].parent_id == module.ai_gateway.gateway_id &&
      azapi_resource.foundry_gateway_tool_access["project"].body.properties.principalId == "00000000-0000-0000-0000-000000000004" &&
      azapi_resource.foundry_gateway_tool_access["project"].body.properties.principalType == "ServicePrincipal" &&
      azapi_resource.foundry_gateway_tool_access["project"].body.properties.roleDefinitionId == "/subscriptions/00000000-0000-0000-0000-000000000001/providers/Microsoft.Authorization/roleDefinitions/dce03f8d-857f-4e40-a90d-67770fa6ecd2" &&
      output.deployment_contract.integration.gateway_tool_access_enabled &&
      !output.deployment_contract.integration.gateway_model_access_enabled &&
      length(azapi_resource.foundry_gateway_model_access) == 0 &&
      length(azapi_resource.gateway_remote_tool) == 0
    )
    error_message = "Selected tool access must grant only the project Tools User at gateway scope, without creating model grants or a RemoteTool."
  }
}

run "root_tool_access_with_model_caller" {
  command = plan
  variables {
    enable_foundry_gateway_model_access   = false
    enable_foundry_gateway_tool_access    = true
    enable_foundry_monitoring_integration = false
    share_foundry_registry_connection     = false
    gateway_access_principals = {
      project = { principal_id = "00000000-0000-0000-0000-000000000004" }
    }
  }
  assert {
    condition = (
      length(azapi_resource.foundry_gateway_tool_access) == 1 &&
      length(azapi_resource.foundry_gateway_model_access) == 0 &&
      length(azapi_resource.gateway_remote_tool) == 0
    )
    error_message = "An explicit Models User caller may share the project principal with the separately owned Tools User grant."
  }
}

run "reject_duplicate_foundry_gateway_owners" {
  command = plan
  variables {
    enable_foundry_gateway_model_access = true
    enable_foundry_gateway_tool_access  = true
    gateway_access_principals = {
      account = { principal_id = "00000000-0000-0000-0000-000000000007" }
      project = { principal_id = "00000000-0000-0000-0000-000000000004" }
    }
  }
  expect_failures = [azapi_resource.foundry_gateway_model_access]
}

run "root_hosted_agent_runtime_access" {
  command = plan
  variables {
    hosted_agent_principals = {
      digest = "00000000-0000-0000-0000-00000000000A"
      second = "00000000-0000-0000-0000-00000000000b"
    }
  }
  assert {
    condition = (
      toset(keys(azapi_resource.hosted_agent_runtime_access)) == toset([
        "models-digest", "monitoring-digest", "models-second", "monitoring-second"
      ]) &&
      azapi_resource.hosted_agent_runtime_access["models-digest"].body.properties.principalId == "00000000-0000-0000-0000-00000000000a" &&
      alltrue([for key, role in azapi_resource.hosted_agent_runtime_access :
        role.body.properties.principalType == "ServicePrincipal" &&
        (startswith(key, "models-") ?
          role.parent_id == module.ai_gateway.gateway_id &&
          endswith(role.body.properties.roleDefinitionId, "/a6b68e3d-a1f0-4c60-8678-237c050cf4ea") :
          role.parent_id == module.foundry_agents.application_insights_id &&
          endswith(role.body.properties.roleDefinitionId, "/3913510d-42f4-4e42-8a64-420c390055eb")
        )
      ])
    )
    error_message = "Actual hosted identities require only gateway Models User and agent-Insights publisher, with stable label keys and normalized principal IDs."
  }
}

run "root_hosted_agent_runtime_access_disabled" {
  command = plan
  variables {
    enable_foundry_gateway_model_access   = false
    enable_foundry_monitoring_integration = false
    hosted_agent_principals = {
      digest = "00000000-0000-0000-0000-00000000000a"
    }
  }
  assert {
    condition     = length(azapi_resource.hosted_agent_runtime_access) == 0 && length(azapi_resource.foundry_gateway_tool_access) == 1
    error_message = "Disabling model and monitoring integration must omit all hosted grants without coupling them to the project-only tool grant."
  }
}

run "root_hosted_agent_models_only" {
  command = plan
  variables {
    enable_foundry_gateway_tool_access    = false
    enable_foundry_monitoring_integration = false
    hosted_agent_principals = {
      digest = "00000000-0000-0000-0000-00000000000a"
    }
  }
  assert {
    condition     = toset(keys(azapi_resource.hosted_agent_runtime_access)) == toset(["models-digest"])
    error_message = "A hosted model caller must not implicitly enable monitoring or direct tool access."
  }
}

run "root_hosted_agent_monitoring_only" {
  command = plan
  variables {
    enable_foundry_gateway_model_access = false
    enable_foundry_gateway_tool_access  = false
    hosted_agent_principals = {
      digest = "00000000-0000-0000-0000-00000000000A"
    }
    gateway_access_principals = {
      separately_owned_models = { principal_id = "00000000-0000-0000-0000-00000000000a" }
    }
  }
  assert {
    condition     = toset(keys(azapi_resource.hosted_agent_runtime_access)) == toset(["monitoring-digest"])
    error_message = "Hosted telemetry must work independently, including a Models User grant owned through the separate caller map."
  }
}

run "reject_hosted_agent_invalid_principal" {
  command = plan
  variables {
    hosted_agent_principals = { digest = "not-a-principal-uuid" }
  }
  expect_failures = [var.hosted_agent_principals]
}

run "reject_hosted_agent_duplicate_principals" {
  command = plan
  variables {
    hosted_agent_principals = {
      digest = "00000000-0000-0000-0000-00000000000A"
      second = "00000000-0000-0000-0000-00000000000a"
    }
  }
  expect_failures = [var.hosted_agent_principals]
}

run "reject_hosted_agent_account_identity" {
  command = plan
  variables {
    hosted_agent_principals = { digest = "00000000-0000-0000-0000-000000000007" }
  }
  expect_failures = [azapi_resource.hosted_agent_runtime_access]
}

run "reject_hosted_agent_project_identity" {
  command = plan
  variables {
    hosted_agent_principals = { digest = "00000000-0000-0000-0000-000000000004" }
  }
  expect_failures = [azapi_resource.hosted_agent_runtime_access]
}

run "reject_duplicate_hosted_gateway_owners" {
  command = plan
  variables {
    hosted_agent_principals = { digest = "00000000-0000-0000-0000-00000000000A" }
    gateway_access_principals = {
      separately_owned_models = { principal_id = "00000000-0000-0000-0000-00000000000a" }
    }
  }
  expect_failures = [azapi_resource.hosted_agent_runtime_access]
}

run "root_remote_tool" {
  command = plan
  variables {
    enable_foundry_gateway_model_access   = false
    enable_foundry_gateway_tool_access    = false
    enable_foundry_monitoring_integration = false
    share_foundry_registry_connection     = false
    gateway_remote_tool_endpoint          = "https://service-managed-123.gateway.example.invalid/caller-verified-tool-endpoint"
  }
  override_resource {
    target          = module.ai_gateway.azapi_resource.gateway
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-gateway/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957"
      output = { properties = { frontend = { defaultHostname = "service-managed-123.gateway.example.invalid" } } }
      identity = {
        type         = "SystemAssigned"
        principal_id = "00000000-0000-0000-0000-000000000002"
        tenant_id    = "00000000-0000-0000-0000-000000000003"
        identity_ids = []
      }
    }
  }
  assert {
    condition = (
      length(azapi_resource.foundry_gateway_model_access) == 0 &&
      length(azapi_resource.foundry_gateway_tool_access) == 0 &&
      length(azapi_resource.gateway_remote_tool) == 1 &&
      azapi_resource.gateway_remote_tool[0].parent_id == module.foundry_agents.project_id &&
      azapi_resource.gateway_remote_tool[0].body.properties.target == var.gateway_remote_tool_endpoint &&
      azapi_resource.gateway_remote_tool[0].body.properties.authType == "ProjectManagedIdentity" &&
      azapi_resource.gateway_remote_tool[0].body.properties.audience == "https://azure-api.net/aigateway" &&
      azapi_resource.gateway_remote_tool[0].body.properties.metadata.type == "custom_MCP" &&
      azapi_resource.gateway_remote_tool[0].body.properties.isSharedToAll &&
      !contains(output.deployment_contract.deferred_integrations, "RemoteTool") &&
      contains(output.deployment_contract.deferred_integrations, "ToolServer") &&
      contains(output.deployment_contract.deferred_integrations, "Toolbox")
    )
    error_message = "Only the explicit endpoint creates the upstream project-identity RemoteTool; service-managed hostnames need not equal ARM names."
  }
}

run "root_both_integrations" {
  command = plan
  variables {
    enable_foundry_gateway_model_access   = true
    enable_foundry_gateway_tool_access    = false
    enable_foundry_monitoring_integration = false
    share_foundry_registry_connection     = false
    gateway_remote_tool_endpoint          = "https://gateway.example.invalid:443/caller-verified-tool-endpoint"
  }
  assert {
    condition     = length(azapi_resource.foundry_gateway_model_access) == 2 && length(azapi_resource.gateway_remote_tool) == 1
    error_message = "Explicit model access and tool connection must compose independently, including the default HTTPS port."
  }
}

run "root_monitoring_integration" {
  command = plan
  variables {
    enable_foundry_gateway_model_access   = false
    enable_foundry_gateway_tool_access    = false
    enable_foundry_monitoring_integration = true
    share_foundry_registry_connection     = false
  }
  assert {
    condition = (
      output.deployment_contract.integration.monitoring_enabled &&
      length(azapi_resource.foundry_gateway_model_access) == 0 &&
      length(azapi_resource.foundry_gateway_tool_access) == 0 &&
      length(azapi_resource.gateway_remote_tool) == 0
    )
    error_message = "Selected monitoring must reach the support module independently of gateway model or tool access and registry sharing."
  }
}

run "root_all_integrations" {
  command = plan
  variables {
    enable_foundry_monitoring_integration = true
    enable_foundry_gateway_model_access   = true
    enable_foundry_gateway_tool_access    = true
    gateway_remote_tool_endpoint          = "https://gateway.example.invalid/caller-verified-tool-endpoint"
  }
  assert {
    condition = (
      output.deployment_contract.integration.monitoring_enabled &&
      output.deployment_contract.integration.gateway_model_access_enabled &&
      output.deployment_contract.integration.gateway_tool_access_enabled &&
      length(azapi_resource.foundry_gateway_model_access) == 2 &&
      length(azapi_resource.foundry_gateway_tool_access) == 1 &&
      length(azapi_resource.gateway_remote_tool) == 1
    )
    error_message = "All explicit integrations must compose without hidden feature coupling or broader ownership."
  }
}

run "root_project_local_registry" {
  command = plan
  variables {
    share_foundry_registry_connection = false
    gateway_remote_tool_endpoint      = "https://gateway.example.invalid/caller-verified-tool-endpoint"
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.registry_connection
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.CognitiveServices/accounts/aiagents-470daa23c957/projects/proj-470daa23c957/connections/acr470daa23c957-conn" }
  }
  assert {
    condition = (
      !output.deployment_contract.integration.registry_connection_shared &&
      output.deployment_contract.agents.registry_connection_id == "${output.deployment_contract.agents.project_id}/connections/${output.deployment_contract.agents.registry_connection_name}" &&
      output.deployment_contract.integration.monitoring_enabled &&
      output.deployment_contract.integration.gateway_model_access_enabled &&
      output.deployment_contract.integration.gateway_tool_access_enabled &&
      length(azapi_resource.gateway_remote_tool) == 1
    )
    error_message = "Project-local registry compatibility must retain exact connection ownership and all selected application integrations."
  }
}

run "root_project_local_remote_tool" {
  command = plan
  variables {
    share_foundry_remote_tool_connection = false
    gateway_remote_tool_endpoint         = "https://gateway.example.invalid/caller-verified-tool-endpoint"
  }
  assert {
    condition = (
      !azapi_resource.gateway_remote_tool[0].body.properties.isSharedToAll &&
      azapi_resource.gateway_remote_tool[0].parent_id == module.foundry_agents.project_id &&
      azapi_resource.gateway_remote_tool[0].body.properties.authType == "ProjectManagedIdentity" &&
      azapi_resource.gateway_remote_tool[0].body.properties.audience == "https://azure-api.net/aigateway" &&
      azapi_resource.gateway_remote_tool[0].body.properties.target == var.gateway_remote_tool_endpoint &&
      length(azapi_resource.foundry_gateway_tool_access) == 1 &&
      azapi_resource.foundry_gateway_tool_access["project"].parent_id == module.ai_gateway.gateway_id &&
      output.deployment_contract.integration.registry_connection_shared
    )
    error_message = "Project-local RemoteTool sharing must preserve the project owner, managed-identity tool access and independent registry setting."
  }
}

run "reject_remote_tool_http" {
  command = plan
  variables { gateway_remote_tool_endpoint = "http://gateway.example.invalid/caller-verified-tool-endpoint" }
  expect_failures = [var.gateway_remote_tool_endpoint]
}

run "reject_remote_tool_credentials" {
  command = plan
  variables { gateway_remote_tool_endpoint = "https://user:password@gateway.example.invalid/caller-verified-tool-endpoint" }
  expect_failures = [var.gateway_remote_tool_endpoint]
}

run "reject_remote_tool_query" {
  command = plan
  variables { gateway_remote_tool_endpoint = "https://gateway.example.invalid/caller-verified-tool-endpoint?key=synthetic" }
  expect_failures = [var.gateway_remote_tool_endpoint]
}

run "reject_remote_tool_origin" {
  command = plan
  variables { gateway_remote_tool_endpoint = "https://unrelated.example.invalid/caller-verified-tool-endpoint" }
  expect_failures = [azapi_resource.gateway_remote_tool]
}

run "root_custom" {
  command = plan
  variables {
    model_allowed_client_cidrs = ["203.0.113.42/32", "2001:db8:1234::/48", "203.0.113.42/32"]
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, { cost_limit = null, request_limit = 7 })
    }
    developer_principal_id   = "00000000-0000-0000-0000-000000000005"
    developer_principal_type = "Group"
    gateway_access_principals = {
      caller = { principal_id = "00000000-0000-0000-0000-000000000006", principal_type = "ServicePrincipal" }
    }
    tags = { fixture = "forwarded" }
  }
  assert {
    condition     = output.model_api_configuration["gpt-latest"].api_format == "OpenAIChatCompletions"
    error_message = "Custom policies must not change probe protocol metadata."
  }
}

run "root_single_group" {
  command = plan
  variables { api2026_resource_group_name = "single-fixture" }
  override_resource {
    target          = azapi_resource.resource_group["gateway"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture" }
  }
  override_resource {
    target          = module.ai_gateway.azapi_resource.gateway
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957"
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
    target          = module.ai_gateway.azapi_resource.insights
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.Insights/components/gateway"
      output = { properties = { ConnectionString = "synthetic-only-not-a-credential" } }
    }
  }
  override_resource {
    target          = module.ai_gateway.azapi_resource.foundry_provider[0]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957/workspaces/default/modelProviders/foundry" }
  }
  override_resource {
    target          = module.ai_gateway.azapi_resource.catalog_model["gpt-latest"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957/workspaces/default/modelProviders/foundry/models/gpt-latest" }
  }
  override_resource {
    target          = module.ai_gateway.azapi_resource.catalog_model["gpt-6-sol"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957/workspaces/default/modelProviders/foundry/models/gpt-6-sol" }
  }
  override_resource {
    target          = module.ai_gateway.azapi_resource.catalog_model["gpt-mini-latest"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.ApiManagement/aigateways/aigw-470daa23c957/workspaces/default/modelProviders/foundry/models/gpt-mini-latest" }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.models
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957"
      output = { properties = { endpoint = "https://models.example.invalid/" } }
    }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-latest"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957/deployments/gpt-latest" }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-6-sol"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957/deployments/gpt-6-sol" }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-mini-latest"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957/deployments/gpt-mini-latest" }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.agents
    override_during = plan
    values = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.CognitiveServices/accounts/aiagents-470daa23c957"
      identity = {
        type         = "SystemAssigned"
        principal_id = "00000000-0000-0000-0000-000000000007"
        tenant_id    = "00000000-0000-0000-0000-000000000003"
        identity_ids = []
      }
    }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.project
    override_during = plan
    values = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.CognitiveServices/accounts/aiagents-470daa23c957/projects/proj-470daa23c957"
      identity = {
        type         = "SystemAssigned"
        principal_id = "00000000-0000-0000-0000-000000000004"
        tenant_id    = "00000000-0000-0000-0000-000000000003"
        identity_ids = []
      }
    }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.storage
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.Storage/storageAccounts/st470daa23c957"
      output = { properties = { primaryEndpoints = { blob = "https://storage.example.invalid/" } } }
    }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.registry
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.ContainerRegistry/registries/acr470daa23c957"
      output = { properties = { loginServer = "registry.example.invalid" } }
    }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.insights
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/single-fixture/providers/Microsoft.Insights/components/agents"
      output = { properties = { ConnectionString = "synthetic-only-not-a-credential" } }
    }
  }
  assert {
    condition     = length(distinct(values(output.resource_groups))) == 1 && output.gateway_contract.single_resource_group && !output.gateway_contract.private_lab
    error_message = "Single-group composition is explicit and must not silently enable the excluded private lab."
  }
}

run "alias_protocol_intersection" {
  command = plan
  variables {
    model_deployments = merge(jsondecode(file("model-profile.json")).model_deployments, {
      gpt-6-sol = merge(jsondecode(file("model-profile.json")).model_deployments["gpt-6-sol"], {
        endpoints = ["/openai/v1/responses"]
      })
    })
  }
  assert {
    condition     = output.model_alias_configuration["primary-router"].endpoints == tolist(["/openai/v1/responses"])
    error_message = "Alias metadata must advertise only the intersection of routed backend protocols."
  }
}

run "root_replacement_profile" {
  command = plan
  variables {
    model_deployments = {
      custom-model = {
        model_name    = "synthetic-model"
        model_version = "test-version"
        capacity      = 7
        token_limit   = 700
        endpoints     = ["/openai/v1/responses"]
      }
    }
    model_aliases = {
      custom-route = { alias_name = "custom-callable", backend_models = [{ deployment = "custom-model", priority = 2, weight = 75 }] }
    }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["custom-model"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-470daa23c957/deployments/custom-model" }
  }
  assert {
    condition = (
      toset(keys(output.model_deployment_ids)) == toset(["custom-model"]) &&
      toset(keys(output.model_alias_configuration)) == toset(["custom-route"]) &&
      output.model_alias_configuration["custom-route"].alias_name == "custom-callable" &&
      output.model_alias_configuration["custom-route"].backend_models[0].priority == 2 &&
      output.model_alias_configuration["custom-route"].backend_models[0].weight == 75
    )
    error_message = "Explicit model/alias maps must replace the entire default maps, not merge old model ownership back in."
  }
}

run "root_model_account_name_override" {
  command = plan
  variables { model_account_name = "aimodels-offline-candidate" }
  override_resource {
    target          = module.foundry_models.azapi_resource.models
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-offline-candidate"
      output = { properties = { endpoint = "https://candidate-models.example.invalid/" } }
    }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-latest"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-offline-candidate/deployments/gpt-latest" }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-6-sol"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-offline-candidate/deployments/gpt-6-sol" }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-mini-latest"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-offline-candidate/deployments/gpt-mini-latest" }
  }
  assert {
    condition = (
      output.foundry_models_id == "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-offline-candidate" &&
      output.deployment_contract.models.endpoint == "https://candidate-models.example.invalid/" &&
      alltrue([for id in values(output.model_deployment_ids) : startswith(id, "${output.foundry_models_id}/deployments/")])
    )
    error_message = "An explicit model-account name must reach the backend and its complete nonsecret handoff."
  }
}

run "reject_empty_model_account_name" {
  command = plan
  variables { model_account_name = "" }
  expect_failures = [var.model_account_name]
}

run "reject_invalid_model_account_name" {
  command = plan
  variables { model_account_name = "models-invalid-" }
  expect_failures = [var.model_account_name]
}

run "reject_long_model_account_name" {
  command = plan
  variables { model_account_name = "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklm" }
  expect_failures = [var.model_account_name]
}

run "root_backend_revision" {
  command = plan
  variables { backend_revision = "rebuild-2" }
  override_resource {
    target          = module.foundry_models.azapi_resource.models
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-1fa30dca0df7"
      output = { properties = { endpoint = "https://models.example.invalid/" } }
    }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-latest"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-1fa30dca0df7/deployments/gpt-latest" }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-6-sol"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-1fa30dca0df7/deployments/gpt-6-sol" }
  }
  override_resource {
    target          = module.foundry_models.azapi_resource.model_deployment["gpt-mini-latest"]
    override_during = plan
    values          = { id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-models/providers/Microsoft.CognitiveServices/accounts/aimodels-1fa30dca0df7/deployments/gpt-mini-latest" }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.agents
    override_during = plan
    values = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.CognitiveServices/accounts/aiagents-1fa30dca0df7"
      identity = {
        type         = "SystemAssigned"
        principal_id = "00000000-0000-0000-0000-000000000007"
        tenant_id    = "00000000-0000-0000-0000-000000000003"
        identity_ids = []
      }
    }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.project
    override_during = plan
    values = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.CognitiveServices/accounts/aiagents-1fa30dca0df7/projects/proj-1fa30dca0df7"
      identity = {
        type         = "SystemAssigned"
        principal_id = "00000000-0000-0000-0000-000000000004"
        tenant_id    = "00000000-0000-0000-0000-000000000003"
        identity_ids = []
      }
    }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.storage
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.Storage/storageAccounts/st1fa30dca0df7"
      output = { properties = { primaryEndpoints = { blob = "https://storage.example.invalid/" } } }
    }
  }
  override_resource {
    target          = module.foundry_agents.azapi_resource.registry
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-offline-fixture-470daa23c957-agents/providers/Microsoft.ContainerRegistry/registries/acr1fa30dca0df7"
      output = { properties = { loginServer = "registry.example.invalid" } }
    }
  }
  assert {
    condition     = local.backend_token != local.resource_token
    error_message = "An explicit backend revision must isolate rebuilt backend names without replacing the gateway."
  }
}

run "root_disabled_backends" {
  command = plan
  variables {
    standalone_backend_public_network_access = "Disabled"
    gateway_backend_subnet_id                = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/platform/providers/Microsoft.Network/virtualNetworks/shared/subnets/backend"
  }
  override_data {
    target = module.ai_gateway.data.azapi_resource.gateway_backend_subnet[0]
    values = { output = { properties = { delegations = [{ properties = { serviceName = "Microsoft.App/environments" } }] } } }
  }
  override_data {
    target = module.ai_gateway.data.azapi_resource.gateway_backend_vnet[0]
    values = { output = { location = "Sweden Central" } }
  }
  assert {
    condition     = alltrue([for access in values(output.backend_public_network_access) : access == "Disabled"])
    error_message = "Explicit private-backend posture must reach every owned PaaS/monitoring dependency, not claim gateway private ingress."
  }
}

run "root_storage_only_disabled" {
  command = plan
  variables { agent_storage_public_network_access = "Disabled" }
  assert {
    condition = (
      output.backend_public_network_access.storage == "Disabled" &&
      alltrue([for k in ["models", "agents", "registry"] : output.backend_public_network_access[k] == "Enabled"]) &&
      output.backend_public_network_access.monitoring_ingestion == "Unspecified" &&
      output.backend_public_network_access.monitoring_query == "Unspecified" &&
      output.gateway_contract.backend_subnet_id == null
    )
    error_message = "A Storage-only override must not disable unrelated backends/monitoring or require gateway subnet integration."
  }
}

run "reject_unrestricted_cidrs" {
  command = plan
  variables { model_allowed_client_cidrs = ["0.0.0.0/00", "::/0"] }
  expect_failures = [var.model_allowed_client_cidrs]
}

run "reject_invalid_cidr" {
  command = plan
  variables { model_allowed_client_cidrs = ["203.0.113.999/32", "2001:db8::/129"] }
  expect_failures = [var.model_allowed_client_cidrs]
}

run "reject_unknown_alias_target" {
  command = plan
  variables {
    model_aliases = { bad = { alias_name = "bad", backend_models = [{ deployment = "missing" }] } }
  }
  expect_failures = [var.model_aliases]
}

run "reject_duplicate_route" {
  command = plan
  variables {
    model_aliases = {
      bad = { alias_name = "bad", backend_models = [{ deployment = "gpt-latest" }, { deployment = "gpt-latest" }] }
    }
  }
  expect_failures = [var.model_aliases]
}

run "reject_invalid_route_numbers" {
  command = plan
  variables {
    model_aliases = { bad = { alias_name = "bad", backend_models = [{ deployment = "gpt-latest", priority = -1, weight = 0 }] } }
  }
  expect_failures = [var.model_aliases]
}

run "reject_private_backends_without_subnet" {
  command = plan
  variables { standalone_backend_public_network_access = "Disabled" }
  expect_failures = [var.standalone_backend_public_network_access]
}
