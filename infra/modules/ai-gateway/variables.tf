variable "subscription_id" {
  description = "Azure subscription containing the application resource groups."
  type        = string
  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "subscription_id must be a UUID."
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

variable "tags" {
  description = "Additional tags for supported Azure resources."
  type        = map(string)
  default     = {}
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
variable "resource_group_id" { type = string }
variable "name" { type = string }
variable "monitoring_location" {
  description = "Region for Log Analytics and Application Insights, independently of the gateway."
  type        = string
}
variable "gateway_backend_subnet_id" {
  description = "Creation-only existing outbound subnet, not private ingress. Must have Microsoft.App/environments delegation in the gateway region."
  type        = string
  default     = ""
  nullable    = false
  validation {
    condition     = var.gateway_backend_subnet_id == "" || can(regex("(?i)^/subscriptions/[0-9a-f-]{36}/resourceGroups/[^/]+/providers/Microsoft.Network/virtualNetworks/[^/]+/subnets/[^/]+$", var.gateway_backend_subnet_id))
    error_message = "Provide an existing subnet ARM ID or an empty string."
  }
}
variable "backend" {
  description = "Optional existing backend. Null creates no provider, backend grant, catalog or aliases. IDs do not become for_each keys."
  type = object({
    account_id     = string
    endpoint       = string
    deployment_ids = map(string)
  })
  default = null
  validation {
    condition = var.backend == null ? true : (
      can(regex("(?i)^/subscriptions/${var.subscription_id}/resourceGroups/[^/]+/providers/Microsoft.CognitiveServices/accounts/[^/]+$", var.backend.account_id)) &&
      can(regex("^https://[^/?#]+/?$", var.backend.endpoint)) &&
      alltrue([for key, id in var.backend.deployment_ids : lower(id) == lower("${var.backend.account_id}/deployments/${key}")])
    )
    error_message = "Backend must be a same-subscription Cognitive Services account with an HTTPS endpoint and matching named deployment IDs. Cross-subscription reuse is not qualified."
  }
}
variable "manage_backend_role_assignment" {
  description = "Exactly one grant owner: true creates the gateway Foundry User grant; false requires an external pregrant."
  type        = bool
  default     = true
  nullable    = false
}
variable "monitoring_public_network_access" {
  description = "Optional monitoring ingestion/query access override; null preserves service defaults."
  type        = string
  default     = null
  validation {
    condition     = var.monitoring_public_network_access == null ? true : contains(["Enabled", "Disabled"], var.monitoring_public_network_access)
    error_message = "Use null, Enabled or Disabled."
  }
}
variable "telemetry_mode" {
  description = "OpenTelemetry enables managed ingestion and waits for an explicit native_telemetry handoff. ApplicationInsights is an explicit legacy compatibility mode, not a native dashboard integration."
  type        = string
  default     = "OpenTelemetry"
  nullable    = false
  validation {
    condition     = contains(["OpenTelemetry", "ApplicationInsights"], var.telemetry_mode)
    error_message = "Use OpenTelemetry or the explicit ApplicationInsights legacy mode."
  }
}
variable "native_telemetry" {
  description = "Nonsecret service-returned readiness handoff. Null leaves native export pending. The second stage rechecks Insights before granting DCR access or configuring the exporter."
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
  validation {
    condition = var.native_telemetry == null ? true : try(
      var.telemetry_mode == "OpenTelemetry" && var.native_telemetry.version == 1 &&
      can(regex("(?i)^/subscriptions/${var.subscription_id}/resourceGroups/[a-z0-9_.()-]+/providers/Microsoft\\.Insights/dataCollectionRules/[a-z0-9_.()-]+$", var.native_telemetry.data_collection_rule_id)) &&
      alltrue([for endpoint in [
        var.native_telemetry.metrics_endpoint, var.native_telemetry.logs_endpoint, var.native_telemetry.traces_endpoint
      ] : can(regex("^https://[A-Za-z0-9][A-Za-z0-9.-]*(?::443)?(/[^?#\\\\[:space:][:cntrl:]]*)?(\\?api-version=[0-9]{4}-[0-9]{2}-[0-9]{2}(-preview)?)?$", endpoint))]),
      false
    )
    error_message = "Native telemetry requires OpenTelemetry mode, handoff version 1, a same-subscription DCR and credential-free HTTPS endpoints (only an optional api-version query is accepted)."
  }
}
variable "model_deployments" {
  description = "Foundry deployments keyed by ARM-safe deployment name. Select model versions, deployment SKUs, and quota available to your subscription. Optional content_safety_severity applies Low/Medium/High to all four gateway categories; null omits that policy."
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
  default  = {}
  nullable = false
  validation {
    condition = (var.backend == null ? length(var.model_deployments) == 0 : (
      length(var.model_deployments) > 0 &&
      toset(keys(var.backend.deployment_ids)) == toset(keys(var.model_deployments))
      )) && alltrue([
      for name, model in var.model_deployments :
      can(regex("^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$", name)) &&
      length(trimspace(model.model_name)) > 0 &&
      length(trimspace(model.model_version)) > 0 &&
      model.capacity >= 1 && floor(model.capacity) == model.capacity &&
      model.token_limit >= 1 && floor(model.token_limit) == model.token_limit &&
      length(model.endpoints) > 0
    ])
    error_message = "With a backend, provide matching deployment keys, ARM-safe names, explicit model name/version, positive integer capacity/token_limit, and endpoints. Without a backend, leave model_deployments empty."
  }
  validation {
    condition = alltrue([for model in var.model_deployments :
      model.cost_limit == null ? true : model.cost_limit > 0
    ])
    error_message = "An optional monthly cost_limit must be positive. This preview policy is not an Azure billing budget."
  }
  validation {
    condition = alltrue([for model in var.model_deployments :
      model.content_safety_severity == null ? true : contains(["Low", "Medium", "High"], model.content_safety_severity)
    ])
    error_message = "An optional content_safety_severity must be Low, Medium or High."
  }
  validation {
    condition = alltrue([for model in var.model_deployments :
      model.request_limit == null ? true : (

        model.request_limit >= 1 && floor(model.request_limit) == model.request_limit
      )
    ])
    error_message = "request_limit is an optional positive integer requests-per-minute limit for the standalone 2026 entry."
  }
}
variable "model_aliases" {
  description = "Optional aliases keyed by ARM name. Null preserves one alias per deployment. Explicit routes use unique deployment keys, priority 0-100 and relative weight 1-100."
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
          contains(keys(var.model_deployments), backend.deployment) &&
          backend.priority >= 0 && backend.priority <= 100 && floor(backend.priority) == backend.priority &&
          backend.weight >= 1 && backend.weight <= 100 && floor(backend.weight) == backend.weight
        ]), false
      )])
    )
    error_message = "Aliases require unique callable names, ARM-safe keys, 1-30 distinct existing deployments, integer priority 0-100 and integer weight 1-100."
  }
  validation {
    condition = var.model_aliases == null ? true : alltrue([for alias in var.model_aliases : try(
      length(distinct([for backend in alias.backend_models : var.model_deployments[backend.deployment].api_format])) == 1 &&
      length(setintersection([for backend in alias.backend_models : toset(var.model_deployments[backend.deployment].endpoints)]...)) > 0,
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
