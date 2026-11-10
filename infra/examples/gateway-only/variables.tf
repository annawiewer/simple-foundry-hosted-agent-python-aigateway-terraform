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
  default     = "gateway-only"
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
