mock_provider "azapi" {
  override_during = plan
  mock_resource "azapi_resource" {
    defaults = {
      id       = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/models/providers/Microsoft.CognitiveServices/accounts/models"
      location = "eastus2"
      output   = { properties = { endpoint = "https://models.example.invalid/" } }
    }
  }
  mock_data "azapi_resource" {
    defaults = { output = { allowProjectManagement = false } }
  }
}
override_resource {
  target          = azapi_resource.models
  override_during = plan
  values = {
    id     = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/models/providers/Microsoft.CognitiveServices/accounts/models"
    output = { properties = { endpoint = "https://models.example.invalid/" } }
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-000000000003"
      tenant_id    = "00000000-0000-0000-0000-000000000004"
      identity_ids = []
    }
  }
}
variables {
  subscription_id   = "00000000-0000-0000-0000-000000000001"
  resource_group_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/models"
  name              = "models-fixture"
  location          = "eastus2"
  model_deployments = jsondecode(file("model-profile.json")).model_deployments
}
run "models_module" {
  command = plan
  module { source = "./modules/foundry-models" }
  assert {
    condition     = toset(keys(output.backend.deployment_ids)) == toset(keys(var.model_deployments)) && output.backend.endpoint == "https://models.example.invalid/"
    error_message = "Models module must publish stable logical deployment keys and selected endpoint."
  }
  assert {
    condition     = !azapi_resource.models.body.properties.allowProjectManagement
    error_message = "The model-only account must not enable project management."
  }
}

run "models_account_readback" {
  command   = apply
  state_key = "models-account"
  module { source = "./modules/foundry-models" }
  assert {
    condition = (
      data.azapi_resource.models_readback.output.allowProjectManagement == false &&
      data.azapi_resource.models_readback.resource_id == azapi_resource.models.id &&
      output.account_id == azapi_resource.models.id &&
      output.endpoint == "https://models.example.invalid/" &&
      output.backend.endpoint == output.endpoint &&
      output.backend.deployment_ids == output.deployment_ids &&
      toset(keys(output.deployment_ids)) == toset(keys(var.model_deployments))
    )
    error_message = "A confirmed model-only account must preserve the deployment and backend handoff."
  }
}

run "reject_models_project_enabled_readback" {
  command   = apply
  state_key = "models-project-enabled"
  module { source = "./modules/foundry-models" }
  variables { developer_principal_id = "00000000-0000-0000-0000-000000000002" }
  override_data {
    target = data.azapi_resource.models_readback
    values = { output = { allowProjectManagement = true } }
  }
  expect_failures = [data.azapi_resource.models_readback]
}

run "reject_models_missing_readback" {
  command   = apply
  state_key = "models-missing"
  module { source = "./modules/foundry-models" }
  override_data {
    target = data.azapi_resource.models_readback
    values = { output = {} }
  }
  expect_failures = [data.azapi_resource.models_readback]
}

run "reject_models_null_readback" {
  command   = apply
  state_key = "models-null"
  module { source = "./modules/foundry-models" }
  override_data {
    target = data.azapi_resource.models_readback
    values = { output = { allowProjectManagement = null } }
  }
  expect_failures = [data.azapi_resource.models_readback]
}

run "reject_models_string_readback" {
  command   = apply
  state_key = "models-string"
  module { source = "./modules/foundry-models" }
  override_data {
    target = data.azapi_resource.models_readback
    values = { output = { allowProjectManagement = "false" } }
  }
  expect_failures = [data.azapi_resource.models_readback]
}

run "reject_fractional_capacity" {
  command = plan
  module { source = "./modules/foundry-models" }
  variables {
    model_deployments = { bad = { model_name = "synthetic", model_version = "1", capacity = 1.5, token_limit = 10 } }
  }
  expect_failures = [var.model_deployments]
}
run "reject_empty_model_profile" {
  command = plan
  module { source = "./modules/foundry-models" }
  variables { model_deployments = {} }
  expect_failures = [var.model_deployments]
}

run "models_gateway_safety_metadata" {
  command = plan
  module { source = "./modules/foundry-models" }
  variables {
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, { content_safety_severity = "Medium" })
    }
  }
  assert {
    condition = alltrue([for deployment in azapi_resource.model_deployment :
      !contains(keys(deployment.body.properties), "raiPolicyName") &&
      !can(deployment.body.properties.policies)
    ])
    error_message = "Gateway safety metadata must not select a backend RAI policy or add gateway policies to Cognitive Services deployments."
  }
}

run "reject_invalid_model_safety" {
  command = plan
  module { source = "./modules/foundry-models" }
  variables {
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, { content_safety_severity = "medium" })
    }
  }
  expect_failures = [var.model_deployments]
}

run "reject_zero_request_limit" {
  command = plan
  module { source = "./modules/foundry-models" }
  variables {
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, { request_limit = 0 })
    }
  }
  expect_failures = [var.model_deployments]
}

run "reject_fractional_request_limit" {
  command = plan
  module { source = "./modules/foundry-models" }
  variables {
    model_deployments = {
      for key, model in jsondecode(file("model-profile.json")).model_deployments :
      key => merge(model, { request_limit = 1.5 })
    }
  }
  expect_failures = [var.model_deployments]
}
