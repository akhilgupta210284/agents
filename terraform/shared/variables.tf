variable "aws_region" {
  type        = string
  description = "AWS region for all shared resources"
  default     = "us-east-1"
}

variable "project" {
  type        = string
  description = "Project prefix used in resource names"
  default     = "medical-agent"
}

variable "tf_state_bucket" {
  type        = string
  description = "S3 bucket name for Terraform remote state (must be globally unique)"
}

variable "tf_lock_table" {
  type        = string
  description = "DynamoDB table name for Terraform state locking"
  default     = "medical-agent-tf-lock"
}

variable "github_repo" {
  type        = string
  description = "GitHub repository in owner/repo format (e.g. acme/medical-agent)"
}
