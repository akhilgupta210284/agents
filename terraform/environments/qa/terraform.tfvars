# ── QA environment — mirrors prod topology at reduced cost ────────────────────

aws_region  = "us-east-1"
project     = "medical-agent"
environment = "qa"

# Networking
vpc_cidr = "10.20.0.0/16"

# Compliance
kms_deletion_window_days = 14
data_retention_days      = 365
log_retention_days       = 60

# OpenSearch — same engine as prod, smaller instance
opensearch_instance_type   = "t3.medium.search"
opensearch_instance_count  = 1
opensearch_ebs_volume_size = 20

# ECS — ETL batch job only
ecs_etl_cpu    = 1024
ecs_etl_memory = 2048

# Container images
ecr_app_image_url  = "REPLACE_WITH_ECR_REGISTRY/medical-agent-app"
ecr_etl_image_url  = "REPLACE_WITH_ECR_REGISTRY/medical-agent-etl"
app_image_tag      = "latest"
etl_image_tag      = "latest"

# Bedrock
bedrock_model_id       = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
bedrock_embed_model_id = "amazon.titan-embed-text-v2:0"
embed_dimensions       = 1024

# Chunking
chunk_size    = 512
chunk_overlap = 50
