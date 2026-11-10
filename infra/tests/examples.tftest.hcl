mock_provider "azapi" {
  override_during = plan
  mock_resource "azapi_resource" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/example/providers/Microsoft.Insights/components/example"
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
    defaults = { output = { allowProjectManagement = false } }
  }
}
variables {
  subscription_id  = "00000000-0000-0000-0000-000000000001"
  environment_name = "example-fixture"
  location         = "eastus2"
}
run "gateway_only" {
  command = plan
  module { source = "./examples/gateway-only" }
  assert {
    condition     = output.gateway_endpoint == "https://gateway.example.invalid" && length(output.model_alias_configuration) == 0
    error_message = "Gateway-only must remain a scaffold with no model or agent ownership."
  }
}
run "existing_models" {
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
    condition     = length(output.model_alias_configuration["primary-router"].backend_models) == 3
    error_message = "Existing deployments must still support the real three-tier alias without owning the backend account."
  }
}
run "existing_models_content_safety" {
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
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, { content_safety_severity = "Medium" })
    }
  }
}

run "existing_models_pregranted" {
  command = plan
  module { source = "./examples/existing-models" }
  variables {
    manage_backend_role_assignment = false
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
    condition     = output.gateway_endpoint == "https://gateway.example.invalid"
    error_message = "An external pregrant must not disable actual gateway routing."
  }
}
run "models_only" {
  command = plan
  module { source = "./examples/models-only" }
  override_resource {
    target          = module.component.azapi_resource.models
    override_during = plan
    values = {
      id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/example/providers/Microsoft.CognitiveServices/accounts/models"
      output = { properties = { endpoint = "https://models.example.invalid/" } }
    }
  }
  assert {
    condition     = toset(keys(output.backend.deployment_ids)) == toset(["gpt-latest", "gpt-6-sol", "gpt-mini-latest"])
    error_message = "Models-only must publish real default deployment descriptors."
  }
}
run "existing_models_custom_profile" {
  command = plan
  module { source = "./examples/existing-models" }
  variables {
    backend = {
      account_id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing"
      endpoint       = "https://existing.example.invalid/"
      deployment_ids = { external-only = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/external/providers/Microsoft.CognitiveServices/accounts/existing/deployments/external-only" }
    }
    model_deployments = {
      external-only = { model_name = "synthetic-existing", model_version = "existing", capacity = 1, token_limit = 50 }
    }
    model_aliases = {
      external-route = { alias_name = "external-callable", backend_models = [{ deployment = "external-only" }] }
    }
  }
  assert {
    condition     = toset(keys(output.model_alias_configuration)) == toset(["external-route"]) && output.model_alias_configuration["external-route"].alias_name == "external-callable"
    error_message = "Existing-models custom maps must replace defaults without acquiring any deployment ownership."
  }
}
run "agent_support_only" {
  command = plan
  module { source = "./examples/agent-support-only" }
  assert {
    condition     = output.container_registry_endpoint == "registry.example.invalid" && strcontains(output.project_endpoint, "/api/projects/")
    error_message = "Agent support must publish its project and registry, not a fictional hosted agent."
  }
}

run "agent_support_storage_disabled" {
  command = plan
  module { source = "./examples/agent-support-only" }
  variables { storage_public_network_access = "Disabled" }
}

run "agent_support_monitoring_integration" {
  command = plan
  module { source = "./examples/agent-support-only" }
  variables { enable_monitoring_integration = true }
}
