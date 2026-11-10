locals {
  gateway_aliases = var.model_aliases != null ? var.model_aliases : {
    for key, model in var.model_deployments : key => {
      alias_name  = key
      description = model.description
      backend_models = [{
        deployment = key
        priority   = null
        weight     = null
      }]
    }
  }
}

resource "azapi_resource" "foundry_provider" {
  count = var.backend == null ? 0 : 1
  # This preview type is not yet present in AzAPI's bundled schema.
  schema_validation_enabled = false
  type                      = "${local.gateway_type}/workspaces/modelProviders@${local.gateway_api_version}"
  name                      = "foundry"
  parent_id                 = local.gateway_workspace_id
  body = {
    properties = {
      kind        = "Foundry"
      displayName = "Foundry"
      description = "Managed-identity access to the dedicated Foundry model account."
      foundry = {
        endpoint    = "${trimsuffix(var.backend.endpoint, "/")}/"
        resourceIds = [var.backend.account_id]
        authentication = {
          kind            = "ManagedIdentity"
          managedIdentity = { resource = "https://cognitiveservices.azure.com/" }
        }
      }
    }
  }
  depends_on = [azapi_resource.backend_role_assignment]
}

resource "azapi_resource" "catalog_model" {
  # This preview type is not yet present in AzAPI's bundled schema.
  schema_validation_enabled = false
  for_each                  = var.model_deployments
  type                      = "${local.gateway_type}/workspaces/modelProviders/models@${local.gateway_api_version}"
  name                      = each.key
  parent_id                 = azapi_resource.foundry_provider[0].id
  body = {
    properties = {
      description        = each.value.description
      displayName        = each.value.model_name
      apiFormat          = each.value.api_format
      supportedEndpoints = each.value.endpoints
      deployment = {
        resourceId   = var.backend.deployment_ids[each.key]
        modelName    = each.key
        modelVersion = each.value.model_version
      }
      policies = concat([{
        type       = "tokenLimit"
        period     = "minute"
        count      = each.value.token_limit
        counterKey = ["identity"]
        }], each.value.cost_limit == null ? [] : [{
        id         = "monthly-caller-budget"
        type       = "costLimit"
        period     = "month"
        amount     = each.value.cost_limit
        counterKey = ["identity"]
        }], each.value.request_limit == null ? [] : [{
        type           = "requestRateLimit"
        callsPerPeriod = each.value.request_limit
        periodSeconds  = 60
        counterKey     = ["identity"]
        }], length(var.model_allowed_client_cidrs) == 0 ? [] : [{
        type       = "ipFilter"
        action     = "Allow"
        cidrRanges = sort(distinct(var.model_allowed_client_cidrs))
        }], each.value.content_safety_severity == null ? [] : [{
        type             = "contentSafety"
        hateSeverity     = each.value.content_safety_severity
        selfHarmSeverity = each.value.content_safety_severity
        sexualSeverity   = each.value.content_safety_severity
        violenceSeverity = each.value.content_safety_severity
      }])
    }
  }
}

resource "azapi_resource" "model_alias" {
  # Runtime routing requires an alias in addition to the provider's catalog entry.
  schema_validation_enabled = false
  for_each                  = local.gateway_aliases
  type                      = "${local.gateway_type}/workspaces/aliases@${local.gateway_api_version}"
  name                      = each.key
  parent_id                 = local.gateway_workspace_id
  body = {
    properties = {
      aliasName   = each.value.alias_name
      description = each.value.description
      backendModels = [for backend in each.value.backend_models : merge({
        resourceId = try(azapi_resource.catalog_model[backend.deployment].id, null)
        },
        backend.priority == null ? {} : { priority = backend.priority },
        backend.weight == null ? {} : { weight = backend.weight }
      )]
    }
  }
  create_headers = { "If-None-Match" = "*" }
  delete_headers = { "If-Match" = "*" }
  # The 2026 alias update route is PATCH; AzAPI resource updates use PUT.
  # Replace changed aliases explicitly instead of pretending PUT implements PATCH.
  replace_triggers_refs = ["properties"]
}
