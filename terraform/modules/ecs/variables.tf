variable "project"     { type = string }
variable "environment" { type = string }

# IAM
variable "ecs_exec_role_arn" { type = string }
variable "ecs_task_role_arn" { type = string }
variable "kms_key_arn"       { type = string }

# Container image
variable "ecr_etl_image_url" { type = string }
variable "etl_image_tag"     { type = string; default = "latest" }

# AWS / ETL config
variable "bedrock_embed_model_id" { type = string }
variable "embed_dimensions"       { type = number; default = 1024 }
variable "opensearch_endpoint"    { type = string }
variable "s3_documents_bucket"    { type = string }
variable "s3_audit_bucket"        { type = string }
variable "chunk_size"             { type = number; default = 512 }
variable "chunk_overlap"          { type = number; default = 50 }

# Sizing
variable "etl_cpu"    { type = number; default = 1024 }
variable "etl_memory" { type = number; default = 2048 }

variable "log_retention_days" { type = number; default = 90 }
