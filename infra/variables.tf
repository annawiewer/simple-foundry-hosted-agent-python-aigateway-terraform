variable "subscription_id" {
  description = "Azure subscription containing the application resource groups."
  type        = string
  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "subscription_id must be a UUID."
  }
}

variable "environment_name" {
  description = "Short environment label used in the shared resource group name and tags."
  type        = string
  default     = "api2026gateway"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,31}$", var.environment_name))
    error_message = "Use 1-32 lowercase letters, numbers, or hyphens, starting with a letter."
  }
}

variable "backend_revision" {
  description = "Optional stable revision for deliberate backend recreation with fresh names. Does not rename the gateway or shared group. Changing it replaces backend resources."
  type        = string
  default     = ""
  validation {
    condition     = var.backend_revision == "" || can(regex("^[a-z0-9][a-z0-9-]{0,31}$", var.backend_revision))
    error_message = "backend_revision must be empty or 1-32 lowercase letters, digits or hyphens, starting with a letter or digit."
  }
}

variable "model_account_name" {
  description = "Optional model-account name and custom subdomain. Null preserves generated naming; other backend names are unchanged. Changing an existing account's name requires a separately planned migration."
  type        = string
  default     = null
  validation {
    condition     = var.model_account_name == null || can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}[a-zA-Z0-9]$", var.model_account_name))
    error_message = "model_account_name must be null or 2-64 letters, digits or hyphens, starting and ending with a letter or digit."
  }
}

variable "location" {
  description = "Region supporting Foundry hosted agents, the selected models, storage, ACR, and monitoring. Confirm availability before applying."
  type        = string
  validation {
    condition     = length(trimspace(var.location)) > 0
    error_message = "location must not be empty."
  }
}

variable "gateway_location" {
  description = "Region in which the subscription is enabled for the selected gateway resource family and SKU."
  type        = string
  validation {
    condition     = length(trimspace(var.gateway_location)) > 0
    error_message = "gateway_location must not be empty."
  }
}

variable "gateway_telemetry_mode" {
  description = "OpenTelemetry uses two explicit Terraform stages. Existing legacy exporters require ApplicationInsights compatibility mode until a separately reviewed migration."
  type        = string
  default     = "OpenTelemetry"
  nullable    = false
}
variable "gateway_native_telemetry" {
  description = "Nonsecret readiness-helper handoff for the second stage; null leaves native gateway telemetry pending."
  type = object({
    version                 = number
    gateway_id              = string
    gateway_principal_id    = string
    insights_id             = string
    log_analytics_id        = string
    data_collection_rule_id = string
    metrics_endpoint        = string
    logs_endpoint           = string
    traces_endpoint         = string
  })
  default = null
}

variable "enable_foundry_gateway_model_access" {
  description = "Create root-owned AI Gateway Models User grants for Foundry account/project identities and explicitly supplied hosted_agent_principals at exact gateway scope. Enabled for the application root; set false to omit. Does not configure tools or prove runtime authentication."
  type        = bool
  default     = true
  nullable    = false
}

variable "enable_foundry_gateway_tool_access" {
  description = "Create a root-owned AI Gateway Tools User grant for only the Foundry project identity at exact gateway scope. Enabled for the application root; set false to omit. Independent of model grants and the RemoteTool reference; creates no ToolServer or Toolbox and proves no invocation."
  type        = bool
  default     = true
  nullable    = false
}

variable "enable_foundry_monitoring_integration" {
  description = "Use ProjectManagedIdentity on the existing owned Foundry AppInsights connection and create Insights-scoped publisher grants for account/project identities and explicitly supplied hosted_agent_principals. Enabled for the application root; false selects the legacy ApiKey body without these publisher grants. Not gateway OpenTelemetry or tracing-delivery acceptance."
  type        = bool
  default     = true
  nullable    = false
}

variable "share_foundry_registry_connection" {
  description = "Request sharing on the existing project-managed-identity registry connection, matching the Bicep application root. Set false for project-local compatibility when Azure returns it unshared; sharing is not an application-preparation requirement. Does not enable registry admin credentials or broaden the project AcrPull role. Verify the selected request with Azure readback and a fresh plan."
  type        = bool
  default     = true
  nullable    = false
}

variable "share_foundry_remote_tool_connection" {
  description = "Request sharing on the project-managed-identity RemoteTool connection, matching Bicep. Set false for independently verified project-local compatibility. Does not change the connection owner, authentication, target or gateway Tools User grant. Retain the selected value on subsequent plans."
  type        = bool
  default     = true
  nullable    = false
}

variable "gateway_remote_tool_endpoint" {
  description = "Explicit independently verified HTTPS tool endpoint returned by this gateway's ToolServer. Null creates no RemoteTool connection. No MCP route, ToolServer or Toolbox is inferred or provisioned."
  type        = string
  default     = null
  validation {
    condition     = var.gateway_remote_tool_endpoint == null || can(regex("^https://[A-Za-z0-9][A-Za-z0-9.-]*(?::443)?/[^?#[:space:]\\\\]*$", var.gateway_remote_tool_endpoint))
    error_message = "Use an absolute HTTPS endpoint with a path, no credentials, query, fragment or non-443 port; or null to disable the connection."
  }
}

variable "gateway_access_principals" {
  description = "Optional caller identities granted AI Gateway Models User at gateway scope. Additive Entra access for all gateway models; API keys and existing agent/test-VM authentication remain unchanged."
  type = map(object({
    principal_id   = string
    principal_type = optional(string, "ServicePrincipal")
  }))
  default  = {}
  nullable = false
  validation {
    condition = alltrue([for principal in var.gateway_access_principals : try(
      can(regex("(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", principal.principal_id)) &&
      contains(["User", "Group", "ServicePrincipal"], principal.principal_type), false
    )])
    error_message = "Each gateway caller requires an Entra object UUID and principal_type User, Group or ServicePrincipal."
  }
  validation {
    condition = try(
      length(distinct([for principal in var.gateway_access_principals : lower(principal.principal_id)])) == length(var.gateway_access_principals),
      false
    )
    error_message = "Each gateway caller object ID must appear only once, regardless of letter case."
  }
}

variable "hosted_agent_principals" {
  description = "Opt-in postdeployment map of stable labels to actual agent-version instance_identity.principal_id UUIDs, not account/project identities or client IDs. Adds gateway Models User and agent Insights publisher roles under their respective integration flags. Empty preserves existing ownership; import independently verified existing assignments before applying."
  type        = map(string)
  default     = {}
  nullable    = false
  validation {
    condition = alltrue([
      for principal_id in var.hosted_agent_principals :
      can(regex("(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", principal_id))
    ])
    error_message = "Each hosted agent principal must be an independently verified Entra object UUID."
  }
  validation {
    condition = try(
      length(distinct([for principal_id in var.hosted_agent_principals : lower(principal_id)])) == length(var.hosted_agent_principals),
      false
    )
    error_message = "Each hosted agent principal must appear only once, regardless of letter case."
  }
}

variable "developer_principal_id" {
  description = "Optional Entra object ID for development access. Empty disables all developer role assignments."
  type        = string
  default     = ""
  validation {
    condition     = var.developer_principal_id == "" || can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.developer_principal_id))
    error_message = "developer_principal_id must be empty or a UUID."
  }
}

variable "developer_principal_type" {
  description = "Entra principal type for optional development access."
  type        = string
  default     = "User"
  validation {
    condition     = contains(["User", "Group", "ServicePrincipal"], var.developer_principal_type)
    error_message = "Use User, Group, or ServicePrincipal."
  }
}

variable "project_display_name" {
  description = "Display name for the Foundry hosted-agent project."
  type        = string
  default     = "AI Gateway hosted agents"
}

variable "project_description" {
  description = "Description of the hosted-agent project."
  type        = string
  default     = "Hosted-agent infrastructure with a separate Foundry model account and AI Gateway."
}

variable "tags" {
  description = "Additional tags for supported Azure resources."
  type        = map(string)
  default     = {}
}
variable "api2026_resource_group_name" {
  description = "Fresh standalone deployments only: exact name of one owned RG for all workloads. Null preserves the three-group layout; never use this to consolidate an existing state."
  type        = string
  default     = null
  validation {
    condition = var.api2026_resource_group_name == null ? true : (
      can(regex("^[A-Za-z0-9][A-Za-z0-9_().-]{0,89}$", var.api2026_resource_group_name)) &&
      !endswith(var.api2026_resource_group_name, ".")
    )
    error_message = "api2026_resource_group_name is standalone-only: use 1-90 letters, digits, underscores, parentheses, hyphens or periods, starting alphanumeric and without a trailing period."
  }
}
variable "gateway_backend_subnet_id" {
  description = "Optional externally managed creation-only outbound subnet; delegation/region are checked by the gateway module."
  type        = string
  default     = ""
  nullable    = false
}
variable "standalone_backend_public_network_access" {
  description = "Optional backend and monitoring public access override. Disabled needs separately provisioned private connectivity and an external gateway subnet; this root does not provision that extension."
  type        = string
  default     = null
  validation {
    condition = var.standalone_backend_public_network_access == null ? true : (
      contains(["Enabled", "Disabled"], var.standalone_backend_public_network_access) &&
      (var.standalone_backend_public_network_access != "Disabled" || var.gateway_backend_subnet_id != "")
    )
    error_message = "Use null, Enabled or Disabled; Disabled requires an existing gateway outbound subnet and separately owned private connectivity."
  }
}
variable "agent_storage_public_network_access" {
  description = "Optional agent Storage-only public access override. Null inherits the existing backend setting; Disabled does not configure private connectivity or require a gateway subnet."
  type        = string
  default     = null
  validation {
    condition     = var.agent_storage_public_network_access == null ? true : contains(["Enabled", "Disabled"], var.agent_storage_public_network_access)
    error_message = "Use null, Enabled or Disabled."
  }
}

variable "model_deployments" {
  description = "Optional complete replacement of the pinned bundled model profile, which uses Medium gateway content safety. In a replacement map, content_safety_severity is Low/Medium/High; null or omission leaves that model's gateway safety policy absent. If deployment keys change, also supply matching model_aliases; region/quota remain a deployment gate."
  type = map(object({
    model_name              = string
    model_version           = string
    model_format            = optional(string, "OpenAI")
    sku_name                = optional(string, "GlobalStandard")
    capacity                = number
    token_limit             = number
    api_format              = optional(string, "OpenAIChatCompletions")
    endpoints               = optional(list(string), ["/openai/v1/chat/completions", "/openai/v1/responses"])
    description             = optional(string, "Foundry model routed through AI Gateway.")
    cost_limit              = optional(number)
    request_limit           = optional(number)
    content_safety_severity = optional(string)
  }))
  default = null
}

variable "model_aliases" {
  description = "Optional complete replacement of the bundled primary/mini aliases. Routes use unique deployment keys, integer priority 0-100 and relative weight 1-100."
  type = map(object({
    alias_name  = string
    description = optional(string, "Foundry models routed through AI Gateway.")
    backend_models = list(object({
      deployment = string
      priority   = optional(number, 0)
      weight     = optional(number, 100)
    }))
  }))
  default = null
  validation {
    condition = var.model_aliases == null ? true : (
      length(var.model_aliases) > 0 &&
      length(distinct([for alias in var.model_aliases : alias.alias_name])) == length(var.model_aliases) &&
      alltrue([for name, alias in var.model_aliases : try(
        can(regex("^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$", name)) &&
        length(trimspace(alias.alias_name)) > 0 &&
        length(alias.backend_models) >= 1 && length(alias.backend_models) <= 30 &&
        length(distinct([for backend in alias.backend_models : backend.deployment])) == length(alias.backend_models) &&
        alltrue([for backend in alias.backend_models :
          contains(keys(local.model_deployments), backend.deployment) &&
          backend.priority >= 0 && backend.priority <= 100 && floor(backend.priority) == backend.priority &&
          backend.weight >= 1 && backend.weight <= 100 && floor(backend.weight) == backend.weight
        ]), false
      )])
    )
    error_message = "Aliases require unique callable names, ARM-safe keys, 1-30 distinct existing deployments, integer priority 0-100 and integer weight 1-100."
  }
  validation {
    condition = var.model_aliases == null ? true : alltrue([for alias in var.model_aliases : try(
      length(distinct([for backend in alias.backend_models : local.model_deployments[backend.deployment].api_format])) == 1 &&
      length(setintersection([for backend in alias.backend_models : toset(local.model_deployments[backend.deployment].endpoints)]...)) > 0,
      false
    )])
    error_message = "Every alias must route to models with the same API format and at least one common supported endpoint."
  }
}
variable "model_allowed_client_cidrs" {
  description = "Optional standalone model-call IP allow list. Empty omits the policy. Use approved caller egress IPv4/IPv6 CIDRs; this is not private ingress or a management/MCP firewall."
  type        = list(string)
  default     = []
  nullable    = false
  validation {
    condition = alltrue([
      for cidr in var.model_allowed_client_cidrs :
      can(cidrhost(cidr, 0)) && try(tonumber(split("/", cidr)[1]) > 0, false)
    ])
    error_message = "Each model_allowed_client_cidrs entry must be a valid IPv4/IPv6 CIDR with a nonzero prefix; use /32 or /128 for a single address."
  }
}
