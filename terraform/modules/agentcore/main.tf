# ─────────────────────────────────────────────────────────────────────────────
# AgentCore module
# Provisions:
#   • CloudWatch log group (KMS-encrypted, controlled retention)
#   • AgentCore Runtime — container-based, VPC mode, all app env vars injected
# ─────────────────────────────────────────────────────────────────────────────

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "app" {
  name              = "/agentcore/${var.project}/${var.environment}/app"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
}

# ── AgentCore Runtime ─────────────────────────────────────────────────────────
# agent_runtime_name must match pattern [a-zA-Z][a-zA-Z0-9_]{0,47}
# (no hyphens), so we normalise the project name.

locals {
  runtime_name = "${replace(var.project, "-", "_")}_${var.environment}"
}

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = local.runtime_name
  description        = "Medical Document Intelligence agent — ${var.environment}"
  role_arn           = var.agentcore_role_arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${var.ecr_app_image_url}:${var.app_image_tag}"
    }
  }

  # VPC mode — runtime ENIs are placed in private subnets so the agent can
  # reach the OpenSearch domain without traversing the public internet.
  network_configuration {
    network_mode = "VPC"

    network_mode_config {
      subnets         = var.private_subnet_ids
      security_groups = [var.agentcore_sg_id]
    }
  }

  environment_variables = {
    AWS_REGION             = data.aws_region.current.name
    BEDROCK_MODEL_ID       = var.bedrock_model_id
    BEDROCK_EMBED_MODEL_ID = var.bedrock_embed_model_id
    EMBED_DIMENSIONS       = tostring(var.embed_dimensions)
    OPENSEARCH_HOST        = var.opensearch_endpoint
    OPENSEARCH_PORT        = "443"
    OPENSEARCH_USE_SSL     = "true"
    OPENSEARCH_SERVICE     = "es"
    S3_BUCKET              = var.s3_documents_bucket
    AUDIT_LOG_BUCKET       = var.s3_audit_bucket
    AUDIT_LOG_PREFIX       = "audit-logs/"
    CHUNK_SIZE             = tostring(var.chunk_size)
    CHUNK_OVERLAP          = tostring(var.chunk_overlap)
    DATA_RETENTION_DAYS    = "2555"
  }

  tags = { Environment = var.environment }

  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }
}
