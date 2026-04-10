variable "project"     { type = string }
variable "environment" { type = string }
variable "s3_documents_bucket" {
  type        = string
  description = "Name of the S3 bucket that holds medical documents"
}
variable "s3_audit_bucket" {
  type        = string
  description = "Name of the S3 bucket for HIPAA audit logs"
}
variable "kms_deletion_window_days" {
  type        = number
  description = "Days before KMS key is deleted after destroy (7–30)"
  default     = 30
}
