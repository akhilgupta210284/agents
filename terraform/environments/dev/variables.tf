# ─────────────────────────────────────────────────────────────────────────────
# Shared variable declarations — identical across dev / qa / prod.
# Values are set in each environment's terraform.tfvars.
# ─────────────────────────────────────────────────────────────────────────────

variable "aws_region"   { type = string }
variable "project"      { type = string }
variable "environment"  { type = string }

# ── Networking ────────────────────────────────────────────────────────────────
variable "vpc_cidr" { type = string; default = "10.0.0.0/16" }

# ── Compliance ────────────────────────────────────────────────────────────────
variable "kms_deletion_window_days" { type = number; default = 30 }
variable "data_retention_days"      { type = number; default = 2555 }
variable "log_retention_days"       { type = number; default = 90 }

# ── OpenSearch ────────────────────────────────────────────────────────────────
variable "opensearch_engine_version"   { type = string; default = "OpenSearch_2.11" }
variable "opensearch_instance_type"    { type = string }
variable "opensearch_instance_count"   { type = number }
variable "opensearch_ebs_volume_size"  { type = number }

# ── ECS sizing (ETL only — app now runs on AgentCore) ─────────────────────────
variable "ecs_etl_cpu"    { type = number }
variable "ecs_etl_memory" { type = number }

# ── Container images ──────────────────────────────────────────────────────────
variable "ecr_app_image_url"  { type = string }
variable "ecr_etl_image_url"  { type = string }
variable "app_image_tag"      { type = string; default = "latest" }
variable "etl_image_tag"      { type = string; default = "latest" }

# ── Bedrock / App config ──────────────────────────────────────────────────────
variable "bedrock_model_id"       { type = string }
variable "bedrock_embed_model_id" { type = string }
variable "embed_dimensions"       { type = number; default = 1024 }
variable "chunk_size"             { type = number; default = 512 }
variable "chunk_overlap"          { type = number; default = 50 }
