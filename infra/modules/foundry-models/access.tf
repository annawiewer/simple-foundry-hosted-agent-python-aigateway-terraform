locals {
  cognitive_roles = {
    contributor = "25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68"
    openai-user = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"
    user        = "a97b65f3-24c7-4388-baec-2e87135dc908"
  }
}

locals {
  role_bindings = var.developer_principal_id == "" ? {} : {
    for key, role in local.cognitive_roles : "developer-models-${key}" => {
      scope          = azapi_resource.models.id
      principal_id   = var.developer_principal_id
      principal_type = var.developer_principal_type
      role_id        = role
    }
  }
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
  depends_on = [data.azapi_resource.models_readback]
}
