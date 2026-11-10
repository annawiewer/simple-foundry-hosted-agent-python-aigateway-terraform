locals {
  gateway_type                  = "Microsoft.ApiManagement/aigateways"
  gateway_api_version           = "2025-09-01-preview"
  gateway_telemetry_api_version = "2025-09-01-preview"
  gateway_uses_existing_subnet  = var.gateway_backend_subnet_id != ""
  gateway_workspace_id          = "${azapi_resource.gateway.id}/workspaces/default"
  gateway_hostname              = try(trimspace(azapi_resource.gateway.output.properties.frontend.defaultHostname), "")
  gateway_endpoint              = local.gateway_hostname == "" ? "" : "https://${local.gateway_hostname}"
}
resource "azapi_resource" "gateway" {
  # AzAPI 2.13 does not include the standalone gateway schema.
  schema_validation_enabled = false
  type                      = "${local.gateway_type}@${local.gateway_api_version}"
  name                      = var.name
  parent_id                 = var.resource_group_id
  location                  = var.location
  tags                      = var.tags
  identity { type = "SystemAssigned" }

  body = {
    properties = var.gateway_backend_subnet_id == "" ? {} : {
      backend = { subnet = { id = var.gateway_backend_subnet_id } }
    }
  }
  response_export_values = ["properties.frontend.defaultHostname"]
  create_headers         = { "If-None-Match" = "*" }
  replace_triggers_refs  = ["properties.backend"]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition = !local.gateway_uses_existing_subnet || try(contains([
        for delegation in data.azapi_resource.gateway_backend_subnet[0].output.properties.delegations :
        lower(delegation.properties.serviceName)
      ], "microsoft.app/environments"), false)
      error_message = "The existing backend subnet must be delegated to Microsoft.App/environments. The workload does not modify platform-owned subnet configuration."
    }
    precondition {
      condition = !local.gateway_uses_existing_subnet || try(
        lower(replace(data.azapi_resource.gateway_backend_vnet[0].output.location, " ", "")) == lower(replace(var.location, " ", "")),
        false
      )
      error_message = "The backend subnet VNet must be in gateway_location."
    }
  }
  timeouts {
    create = "60m"
    update = "60m"
    delete = "60m"
  }
}

resource "azapi_resource" "runtime_api_key" {
  # This preview type is not yet present in AzAPI's bundled schema.
  schema_validation_enabled = false
  type                      = "${local.gateway_type}/apiKeys@${local.gateway_api_version}"
  name                      = "default"
  parent_id                 = azapi_resource.gateway.id
  body                      = { properties = { displayName = "All APIs subscription" } }
  response_export_values    = []
}

data "azapi_resource" "gateway_backend_subnet" {
  count                  = local.gateway_uses_existing_subnet ? 1 : 0
  type                   = "Microsoft.Network/virtualNetworks/subnets@2024-05-01"
  resource_id            = var.gateway_backend_subnet_id
  response_export_values = ["properties.delegations"]
}

data "azapi_resource" "gateway_backend_vnet" {
  count                  = local.gateway_uses_existing_subnet ? 1 : 0
  type                   = "Microsoft.Network/virtualNetworks@2024-05-01"
  resource_id            = join("/", slice(split("/", var.gateway_backend_subnet_id), 0, 9))
  response_export_values = ["location"]
}
