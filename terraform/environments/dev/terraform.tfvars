# ── DEV environment — small footprint, AgentCore runtime, single-node OpenSearch

aws_region  = "us-east-1"
project     = "medical-agent"
environment = "dev"

# Networking
vpc_cidr = "10.10.0.0/16"

# Compliance
kms_deletion_window_days = 7     # Short window for fast dev teardown
data_retention_days      = 90    # Lower retention in dev (not HIPAA regulated)
log_retention_days       = 30

# OpenSearch — cheapest single-node instance
opensearch_instance_type   = "t3.small.search"
opensearch_instance_count  = 1
opensearch_ebs_volume_size = 10

# ECS — ETL batch job only
ecs_etl_cpu    = 512
ecs_etl_memory = 1024

# Container images — set by CI/CD pipeline via -var flags
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
