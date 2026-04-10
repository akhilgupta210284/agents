variable "project"     { type = string }
variable "environment" { type = string }
variable "account_id"  { type = string }
variable "kms_key_arn" { type = string }
variable "data_retention_days" {
  type        = number
  description = "Days to retain objects (HIPAA minimum = 2555 / 7 years)"
  default     = 2555
}
