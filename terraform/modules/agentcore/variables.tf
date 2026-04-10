variable "project"     { type = string }
variable "environment" { type = string }

# Network
variable "private_subnet_ids" { type = list(string) }
variable "agentcore_sg_id"    { type = string }

# IAM / KMS
variable "agentcore_role_arn" { type = string }
variable "kms_key_arn"        { type = string }

# Container image
variable "ecr_app_image_url" { type = string }
variable "app_image_tag"     { type = string; default = "latest" }

# AWS / App config
variable "bedrock_model_id"       { type = string }
variable "bedrock_embed_model_id" { type = string }
variable "embed_dimensions"       { type = number; default = 1024 }
variable "opensearch_endpoint"    { type = string }
variable "s3_documents_bucket"    { type = string }
variable "s3_audit_bucket"        { type = string }
variable "chunk_size"             { type = number; default = 512 }
variable "chunk_overlap"          { type = number; default = 50 }

variable "log_retention_days" { type = number; default = 90 }
