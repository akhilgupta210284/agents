# ─────────────────────────────────────────────────────────────────────────────
# Environment root — wires all modules together.
# The same file is used by dev / qa / prod; only terraform.tfvars changes.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.18" }
    tls = { source = "hashicorp/tls", version = "~> 4.0" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

# ── 1. Networking ─────────────────────────────────────────────────────────────

module "networking" {
  source      = "../../modules/networking"
  project     = var.project
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
}

# ── 2. IAM + KMS ─────────────────────────────────────────────────────────────

module "iam" {
  source               = "../../modules/iam"
  project              = var.project
  environment          = var.environment
  s3_documents_bucket  = "${var.project}-${var.environment}-documents-${data.aws_caller_identity.current.account_id}"
  s3_audit_bucket      = "${var.project}-${var.environment}-audit-${data.aws_caller_identity.current.account_id}"
  kms_deletion_window_days = var.kms_deletion_window_days
}

# ── 3. S3 ─────────────────────────────────────────────────────────────────────

module "s3" {
  source              = "../../modules/s3"
  project             = var.project
  environment         = var.environment
  account_id          = data.aws_caller_identity.current.account_id
  kms_key_arn         = module.iam.kms_key_arn
  data_retention_days = var.data_retention_days
}

# ── 4. OpenSearch ─────────────────────────────────────────────────────────────

module "opensearch" {
  source              = "../../modules/opensearch"
  project             = var.project
  environment         = var.environment
  engine_version      = var.opensearch_engine_version
  instance_type       = var.opensearch_instance_type
  instance_count      = var.opensearch_instance_count
  ebs_volume_size     = var.opensearch_ebs_volume_size
  private_subnet_ids  = module.networking.private_subnet_ids
  opensearch_sg_id    = module.networking.opensearch_sg_id
  kms_key_id          = module.iam.kms_key_id
  ecs_task_role_arn   = module.iam.ecs_task_role_arn
  log_retention_days  = var.log_retention_days
}

# ── 5. AgentCore Runtime (replaces the long-running ECS app service) ──────────

module "agentcore" {
  source = "../../modules/agentcore"

  project     = var.project
  environment = var.environment

  private_subnet_ids = module.networking.private_subnet_ids
  agentcore_sg_id    = module.networking.ecs_tasks_sg_id
  agentcore_role_arn = module.iam.agentcore_role_arn
  kms_key_arn        = module.iam.kms_key_arn

  ecr_app_image_url = var.ecr_app_image_url
  app_image_tag     = var.app_image_tag

  bedrock_model_id       = var.bedrock_model_id
  bedrock_embed_model_id = var.bedrock_embed_model_id
  embed_dimensions       = var.embed_dimensions
  opensearch_endpoint    = module.opensearch.domain_endpoint
  s3_documents_bucket    = module.s3.documents_bucket_name
  s3_audit_bucket        = module.s3.audit_bucket_name
  chunk_size             = var.chunk_size
  chunk_overlap          = var.chunk_overlap
  log_retention_days     = var.log_retention_days
}

# ── 6. ECS — ETL pipeline only (one-shot batch job) ──────────────────────────

module "ecs" {
  source = "../../modules/ecs"

  project     = var.project
  environment = var.environment

  ecs_exec_role_arn = module.iam.ecs_exec_role_arn
  ecs_task_role_arn = module.iam.ecs_task_role_arn
  kms_key_arn       = module.iam.kms_key_arn

  ecr_etl_image_url = var.ecr_etl_image_url
  etl_image_tag     = var.etl_image_tag

  bedrock_embed_model_id = var.bedrock_embed_model_id
  embed_dimensions       = var.embed_dimensions
  opensearch_endpoint    = module.opensearch.domain_endpoint
  s3_documents_bucket    = module.s3.documents_bucket_name
  s3_audit_bucket        = module.s3.audit_bucket_name
  chunk_size             = var.chunk_size
  chunk_overlap          = var.chunk_overlap

  etl_cpu            = var.ecs_etl_cpu
  etl_memory         = var.ecs_etl_memory
  log_retention_days = var.log_retention_days
}
