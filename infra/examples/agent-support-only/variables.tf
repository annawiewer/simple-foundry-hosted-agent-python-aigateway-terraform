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
  default     = "agent-support-only"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,31}$", var.environment_name))
    error_message = "Use 1-32 lowercase letters, digits or hyphens, starting with a letter."
  }

}

variable "enable_monitoring_integration" {
  description = "Switch the existing owned Insights connection to ProjectManagedIdentity in place and add two exact publisher grants; no additional connection owner."
  type        = bool
  default     = false
  nullable    = false
}

variable "storage_public_network_access" {
  description = "Optional Storage-only public access override. Null preserves the existing agent-support defaults; Disabled does not configure private connectivity."
  type        = string
  default     = null
  validation {
    condition     = var.storage_public_network_access == null ? true : contains(["Enabled", "Disabled"], var.storage_public_network_access)
    error_message = "Use null, Enabled or Disabled."
  }
}
