# ── PROD environment — HA, AgentCore runtime, multi-node OpenSearch ────────────

aws_region  = "us-east-1"
project     = "medical-agent"
environment = "prod"

# Networking
vpc_cidr = "10.30.0.0/16"

# Compliance — full HIPAA 7-year retention
kms_deletion_window_days = 30
data_retention_days      = 2555   # 7 years
log_retention_days       = 365

# OpenSearch — HA two-node cluster on memory-optimised instance
opensearch_instance_type   = "r6g.large.search"
opensearch_instance_count  = 2     # zone awareness across 2 AZs
opensearch_ebs_volume_size = 100

# ECS — ETL batch job only
ecs_etl_cpu    = 2048
ecs_etl_memory = 4096

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
