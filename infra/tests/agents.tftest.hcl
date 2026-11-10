mock_provider "azapi" {
  override_during = plan
  mock_resource "azapi_resource" {
    defaults = {
      id       = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/agents/providers/Microsoft.Insights/components/monitoring"
      location = "eastus2"
      output = {
        properties = {
          ConnectionString = "synthetic-only-not-a-credential"
          primaryEndpoints = { blob = "https://storage.example.invalid/" }
          loginServer      = "registry.example.invalid"
        }
      }
    }
  }
  mock_data "azapi_resource" {
    defaults = { output = { isDefault = true, isSharedToAll = true } }
  }
  mock_resource "azapi_resource_action" {
    defaults = {
      id    = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/agents/providers/Microsoft.CognitiveServices/accounts/agents/projects/project/connections/registry-conn"
      exist = true
    }
  }
}
override_resource {
  target          = azapi_resource.agents
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/agents/providers/Microsoft.CognitiveServices/accounts/agents"
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-000000000002"
      tenant_id    = "00000000-0000-0000-0000-000000000003"
      identity_ids = []
    }
  }
}
override_resource {
  target          = azapi_resource.project
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/agents/providers/Microsoft.CognitiveServices/accounts/agents/projects/project"
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-000000000004"
      tenant_id    = "00000000-0000-0000-0000-000000000003"
      identity_ids = []
    }
  }
}
override_resource {
  target          = azapi_resource.storage
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/agents/providers/Microsoft.Storage/storageAccounts/storage"
    output = { properties = { primaryEndpoints = { blob = "https://storage.example.invalid/" } } }
  }
}
override_resource {
  target          = azapi_resource.registry
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/agents/providers/Microsoft.ContainerRegistry/registries/registry"
    output = { properties = { loginServer = "registry.example.invalid" } }
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-000000000007"
      tenant_id    = "00000000-0000-0000-0000-000000000003"
      identity_ids = []
    }
  }
}
override_resource {
  target          = azapi_resource.registry_connection
  override_during = plan
  values = {
    id       = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/agents/providers/Microsoft.CognitiveServices/accounts/agents/projects/project/connections/registry-conn"
    location = "eastus2"
  }
}
variables {
  subscription_id   = "00000000-0000-0000-0000-000000000001"
  resource_group_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/agents"
  name              = "agents-fixture"
  location          = "eastus2"
  names             = { project = "project-fixture", storage = "storagefixture", registry = "registryfixture" }
}
run "agents_module" {
  command = plan
  module { source = "./modules/foundry-agents" }
  assert {
    condition     = output.project_endpoint == "https://agents-fixture.services.ai.azure.com/api/projects/project-fixture" && output.container_registry_endpoint == "registry.example.invalid"
    error_message = "Agent support must publish its project and registry handoff without claiming a deployed application."
  }
  assert {
    condition     = azapi_resource.project_insights_connection.body.properties.authType == "ApiKey" && length(azapi_resource.role_assignment) == 5 && output.monitoring_connection_id == null
    error_message = "Monitoring integration must remain absent from the retained default support graph."
  }
  assert {
    condition     = azapi_resource.registry_connection.body.properties.isDefault && !azapi_resource.registry_connection.body.properties.isSharedToAll
    error_message = "The project-local registry must explicitly retain default selection without enabling sharing."
  }
  assert {
    condition     = length(azapi_resource_action.registry_connection_sharing) == 0 && length(data.azapi_resource.registry_connection_readback) == 0
    error_message = "The project-local opt-out must not execute a sharing PATCH."
  }
}

run "agents_shared_registry" {
  command = plan
  module { source = "./modules/foundry-agents" }
  variables { share_registry_connection = true }
  assert {
    condition = (
      azapi_resource.registry_connection.body.properties.isDefault &&
      azapi_resource.registry_connection.body.properties.isSharedToAll &&
      azapi_resource.registry_connection.parent_id == azapi_resource.project.id &&
      azapi_resource.registry_connection.body.properties.authType == "ManagedIdentity" &&
      azapi_resource.role_assignment["project-acr-pull"].parent_id == azapi_resource.registry.id &&
      length(azapi_resource.role_assignment) == 5
    )
    error_message = "Sharing must retain explicit default selection, the existing owner and the same scoped pull grant."
  }
  assert {
    condition = (
      length(azapi_resource_action.registry_connection_sharing) == 1 &&
      azapi_resource_action.registry_connection_sharing[0].method == "PATCH" &&
      azapi_resource_action.registry_connection_sharing[0].when == "apply" &&
      azapi_resource_action.registry_connection_sharing[0].resource_id == azapi_resource.registry_connection.id &&
      azapi_resource_action.registry_connection_sharing[0].body == azapi_resource.registry_connection.body &&
      data.azapi_resource.registry_connection_readback[0].resource_id == azapi_resource.registry_connection.id
    )
    error_message = "Shared mode must PATCH and independently read back the sole existing connection without changing its payload."
  }
}

run "agents_shared_registry_readback" {
  command   = apply
  state_key = "registry-shared"
  module { source = "./modules/foundry-agents" }
  variables { share_registry_connection = true }
  assert {
    condition     = data.azapi_resource.registry_connection_readback[0].output.isDefault && data.azapi_resource.registry_connection_readback[0].output.isSharedToAll
    error_message = "The final shared-registry readback must retain both flags."
  }
}

run "reject_registry_unshared_readback" {
  command   = apply
  state_key = "registry-unshared"
  module { source = "./modules/foundry-agents" }
  variables { share_registry_connection = true }
  override_data {
    target = data.azapi_resource.registry_connection_readback[0]
    values = { output = { isDefault = true, isSharedToAll = false } }
  }
  expect_failures = [data.azapi_resource.registry_connection_readback[0]]
}

run "reject_registry_nondefault_readback" {
  command   = apply
  state_key = "registry-nondefault"
  module { source = "./modules/foundry-agents" }
  variables { share_registry_connection = true }
  override_data {
    target = data.azapi_resource.registry_connection_readback[0]
    values = { output = { isDefault = false, isSharedToAll = true } }
  }
  expect_failures = [data.azapi_resource.registry_connection_readback[0]]
}

run "reject_registry_missing_readback" {
  command   = apply
  state_key = "registry-missing"
  module { source = "./modules/foundry-agents" }
  variables { share_registry_connection = true }
  override_data {
    target = data.azapi_resource.registry_connection_readback[0]
    values = { output = { isDefault = true } }
  }
  expect_failures = [data.azapi_resource.registry_connection_readback[0]]
}

run "agents_monitoring_integration" {
  command = plan
  module { source = "./modules/foundry-agents" }
  variables { enable_monitoring_integration = true }
  assert {
    condition = (
      length(azapi_resource.role_assignment) == 7 &&
      azapi_resource.project_insights_connection.parent_id == azapi_resource.project.id &&
      azapi_resource.project_insights_connection.body.properties.authType == "ProjectManagedIdentity" &&
      !contains(keys(azapi_resource.project_insights_connection.body.properties), "credentials") &&
      output.monitoring_connection_id == azapi_resource.project_insights_connection.id &&
      azapi_resource.role_assignment["monitoring-account"].body.properties.principalId == azapi_resource.agents.identity[0].principal_id &&
      azapi_resource.role_assignment["monitoring-project"].body.properties.principalId == azapi_resource.project.identity[0].principal_id &&
      alltrue([for key in ["monitoring-account", "monitoring-project"] :
        azapi_resource.role_assignment[key].parent_id == azapi_resource.insights.id &&
        azapi_resource.role_assignment[key].body.properties.roleDefinitionId == "/subscriptions/00000000-0000-0000-0000-000000000001/providers/Microsoft.Authorization/roleDefinitions/3913510d-42f4-4e42-8a64-420c390055eb"
      ])
    )
    error_message = "Monitoring opt-in must change only the existing connection body and add two exact Insights grants, without a second Terraform connection owner."
  }
}
run "agents_disabled_backend_network" {
  command = plan
  module { source = "./modules/foundry-agents" }
  variables {
    public_network_access            = "Disabled"
    monitoring_public_network_access = "Disabled"
  }
  assert {
    condition = (
      azapi_resource.agents.body.properties.networkAcls.defaultAction == "Deny" &&
      azapi_resource.storage.body.properties.networkAcls.defaultAction == "Deny" &&
      azapi_resource.storage.body.properties.networkAcls.bypass == "AzureServices" &&
      azapi_resource.registry.body.properties.publicNetworkAccess == "Disabled" &&
      azapi_resource.logs.body.properties.publicNetworkAccessForIngestion == "Disabled" &&
      azapi_resource.insights.body.properties.publicNetworkAccessForQuery == "Disabled"
    )
    error_message = "Explicit backend disablement must cover owned support and monitoring without inventing private connectivity."
  }
}

run "agents_storage_enabled_override" {
  command = plan
  module { source = "./modules/foundry-agents" }
  variables {
    public_network_access         = "Disabled"
    storage_public_network_access = "Enabled"
  }
  assert {
    condition = (
      azapi_resource.storage.body.properties.publicNetworkAccess == "Enabled" &&
      azapi_resource.storage.body.properties.networkAcls.defaultAction == "Allow" &&
      !can(azapi_resource.storage.body.properties.networkAcls.resourceAccessRules) &&
      azapi_resource.agents.body.properties.publicNetworkAccess == "Disabled" &&
      azapi_resource.agents.body.properties.networkAcls.defaultAction == "Deny" &&
      azapi_resource.registry.body.properties.publicNetworkAccess == "Disabled" &&
      !can(azapi_resource.logs.body.properties.publicNetworkAccessForIngestion) &&
      !can(azapi_resource.insights.body.properties.publicNetworkAccessForQuery)
    )
    error_message = "An explicit Storage override must take precedence over the shared backend switch without changing unrelated support/monitoring."
  }
}

run "reject_storage_network_enum" {
  command = plan
  module { source = "./modules/foundry-agents" }
  variables { storage_public_network_access = "Private" }
  expect_failures = [var.storage_public_network_access]
}
