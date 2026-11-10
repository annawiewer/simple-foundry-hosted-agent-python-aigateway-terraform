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
variable "resource_group_id" {
  description = "Existing resource group ARM ID; referenced, never adopted."
  type        = string
}
variable "name" {
  description = "Explicit component account or gateway resource name."
  type        = string
}
variable "public_network_access" {
  description = "Backend PaaS public access. Disabled requires separately owned private connectivity."
  type        = string
  default     = "Enabled"
  validation {
    condition     = contains(["Enabled", "Disabled"], var.public_network_access)
    error_message = "Use Enabled or Disabled."
  }
}

variable "model_deployments" {
  description = "Foundry deployments keyed by ARM-safe deployment name. Select model versions, deployment SKUs, and quota available to your subscription. Optional content_safety_severity is gateway metadata only; this module does not send a backend RAI policy name."
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
  validation {
    condition = length(var.model_deployments) > 0 && alltrue([
      for name, model in var.model_deployments :
      can(regex("^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$", name)) &&
      length(trimspace(model.model_name)) > 0 &&
      length(trimspace(model.model_version)) > 0 &&
      model.capacity >= 1 && floor(model.capacity) == model.capacity &&
      model.token_limit >= 1 && floor(model.token_limit) == model.token_limit &&
      length(model.endpoints) > 0
    ])
    error_message = "Provide at least one model with an ARM-safe name, explicit model name/version, positive integer capacity/token_limit, and at least one endpoint."
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
    error_message = "request_limit is an optional positive integer requests-per-minute limit for the standalone gateway."
  }
}
