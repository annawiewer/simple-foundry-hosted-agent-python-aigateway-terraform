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
variable "environment_name" {
  description = "Fresh state/name boundary for this independent example."
  type        = string
  default     = "existing-models"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,31}$", var.environment_name))
    error_message = "Use 1-32 lowercase letters, digits or hyphens, starting with a letter."
  }
}
variable "gateway_telemetry_mode" {
  description = "OpenTelemetry uses two explicit stages. ApplicationInsights preserves an existing legacy exporter until a separately reviewed migration."
  type        = string
  default     = "OpenTelemetry"
  nullable    = false
}
variable "gateway_native_telemetry" {
  description = "Nonsecret readiness-helper handoff for the second stage; null leaves native telemetry pending."
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
variable "backend" {
  description = "Optional existing backend. Null creates no provider, backend grant, catalog or aliases. IDs do not become for_each keys."
  type = object({
    account_id     = string
    endpoint       = string
    deployment_ids = map(string)
  })
  nullable = false
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

variable "model_deployments" {
  description = "Existing deployments' metadata, not resources to create. Null uses the bundled profile; override this and model_aliases together for other deployment keys."
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
  description = "Alias routes for the existing deployment keys; null uses the bundled profile."
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
}
