locals {
  cognitive_roles = {
    contributor = "25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68"
    openai-user = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"
    user        = "a97b65f3-24c7-4388-baec-2e87135dc908"
  }
}

locals {
  role_bindings = merge(
    {
      project-storage = {
        scope          = azapi_resource.storage.id
        principal_id   = azapi_resource.project.identity[0].principal_id
        principal_type = "ServicePrincipal"
        role_id        = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
      }
      project-acr-pull = {
        scope          = azapi_resource.registry.id
        principal_id   = azapi_resource.project.identity[0].principal_id
        principal_type = "ServicePrincipal"
        role_id        = "7f951dda-4ed3-4680-a7ca-43fe172d538d"
      }
    },
    { for key, role in local.cognitive_roles : "project-${key}" => {
      scope          = azapi_resource.agents.id
      principal_id   = azapi_resource.project.identity[0].principal_id
      principal_type = "ServicePrincipal"
      role_id        = role
    } },
    var.enable_monitoring_integration ? {
      for key, principal in {
        account = azapi_resource.agents.identity[0].principal_id
        project = azapi_resource.project.identity[0].principal_id
        } : "monitoring-${key}" => {
        scope          = azapi_resource.insights.id
        principal_id   = principal
        principal_type = "ServicePrincipal"
        role_id        = "3913510d-42f4-4e42-8a64-420c390055eb"
      }
    } : {},
    var.developer_principal_id == "" ? {} : merge(
      { for key, role in local.cognitive_roles : "developer-agents-${key}" => {
        scope          = azapi_resource.agents.id
        principal_id   = var.developer_principal_id
        principal_type = var.developer_principal_type
        role_id        = role
      } },
      { developer-storage = {
        scope          = azapi_resource.storage.id
        principal_id   = var.developer_principal_id
        principal_type = var.developer_principal_type
        role_id        = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
      } }
    )
  )
}

resource "azapi_resource" "role_assignment" {
  for_each  = local.role_bindings
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
  name      = uuidv5("url", "${each.value.scope}/${each.value.principal_id}/${each.value.role_id}")
  parent_id = each.value.scope
  body = {
    properties = {
      principalId      = each.value.principal_id
      principalType    = each.value.principal_type
      roleDefinitionId = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${each.value.role_id}"
    }
  }
}
