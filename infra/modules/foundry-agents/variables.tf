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

variable "storage_public_network_access" {
  description = "Optional Storage-only public access override. Null inherits public_network_access; Disabled does not configure private connectivity."
  type        = string
  default     = null
  validation {
    condition     = var.storage_public_network_access == null ? true : contains(["Enabled", "Disabled"], var.storage_public_network_access)
    error_message = "Use null, Enabled or Disabled."
  }
}

variable "names" {
  description = "Explicit names for project, Storage and registry."
  type        = object({ project = string, storage = string, registry = string })
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

variable "enable_monitoring_integration" {
  description = "Switch the existing owned AppInsights connection to Bicep's ProjectManagedIdentity body and add account/project Monitoring Metrics Publisher grants. No second account-route owner, trace-delivery proof or Entra-only enforcement."
  type        = bool
  default     = false
  nullable    = false
}

variable "share_registry_connection" {
  description = "Mark the existing project-managed-identity registry connection shared. Standalone support defaults to unshared; the full application root opts in. Does not enable registry admin credentials or broaden the project AcrPull role."
  type        = bool
  default     = false
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
