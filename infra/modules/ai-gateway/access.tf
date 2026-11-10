resource "azapi_resource" "backend_role_assignment" {
  count     = var.backend != null && var.manage_backend_role_assignment ? 1 : 0
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
  name      = uuidv5("url", "${var.backend.account_id}/${azapi_resource.gateway.identity[0].principal_id}/53ca6127-db72-4b80-b1b0-d745d6d5456d")
  parent_id = var.backend.account_id
  body = {
    properties = {
      principalId      = azapi_resource.gateway.identity[0].principal_id
      principalType    = "ServicePrincipal"
      roleDefinitionId = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"
    }
  }
}
locals {
  role_bindings = { for key, principal in var.gateway_access_principals : "gateway-models-user-${key}" => {
    scope          = azapi_resource.gateway.id
    principal_id   = principal.principal_id
    principal_type = principal.principal_type
    role_id        = "a6b68e3d-a1f0-4c60-8678-237c050cf4ea"
  } }
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
