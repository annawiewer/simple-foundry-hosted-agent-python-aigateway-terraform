locals {
  gateway_remote_tool_endpoint_valid = can(regex("^https://[A-Za-z0-9][A-Za-z0-9.-]*(?::443)?/[^?#[:space:]\\\\]*$", var.gateway_remote_tool_endpoint))
}

resource "azapi_resource" "gateway_remote_tool" {
  count                     = var.gateway_remote_tool_endpoint == null ? 0 : 1
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  schema_validation_enabled = false
  name                      = "aigw-github"
  parent_id                 = module.foundry_agents.project_id
  body = {
    properties = {
      category      = "RemoteTool"
      authType      = "ProjectManagedIdentity"
      audience      = "https://azure-api.net/aigateway"
      target        = var.gateway_remote_tool_endpoint
      isSharedToAll = var.share_foundry_remote_tool_connection
      metadata      = { type = "custom_MCP" }
    }
  }
  response_export_values = []
  depends_on             = [azapi_resource.foundry_gateway_tool_access]
  lifecycle {
    precondition {
      condition = !local.gateway_remote_tool_endpoint_valid || try(
        lower(replace(regex("^https://[^/]+", var.gateway_remote_tool_endpoint), "/:443$/", "")) == lower(trimsuffix(module.ai_gateway.gateway_endpoint, "/")),
        false
      )
      error_message = "gateway_remote_tool_endpoint must use the deployed gateway HTTPS origin; no runtime route is inferred or provisioned."
    }
  }
}
