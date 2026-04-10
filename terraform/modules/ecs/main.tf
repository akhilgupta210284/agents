# ─────────────────────────────────────────────────────────────────────────────
# ECS module — ETL pipeline only
# Provisions:
#   • ECS cluster (Fargate capacity provider) — used to run the ETL job
#   • CloudWatch log group for ETL container
#   • ECS task definition for the ETL pipeline (one-shot batch job)
#
# The main app is no longer hosted here; it runs on AgentCore Runtime.
# ─────────────────────────────────────────────────────────────────────────────

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# ── ECS Cluster ───────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "this" {
  name = "${var.project}-${var.environment}-etl"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE_SPOT"
  }
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "etl" {
  name              = "/ecs/${var.project}/${var.environment}/etl"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
}

# ── ETL Task Definition ───────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "etl" {
  family                   = "${var.project}-${var.environment}-etl"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.etl_cpu
  memory                   = var.etl_memory
  execution_role_arn       = var.ecs_exec_role_arn
  task_role_arn            = var.ecs_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "medical-agent-etl"
      image     = "${var.ecr_etl_image_url}:${var.etl_image_tag}"
      essential = true

      environment = [
        { name = "AWS_REGION",             value = data.aws_region.current.name },
        { name = "BEDROCK_EMBED_MODEL_ID", value = var.bedrock_embed_model_id },
        { name = "EMBED_DIMENSIONS",       value = tostring(var.embed_dimensions) },
        { name = "OPENSEARCH_HOST",        value = var.opensearch_endpoint },
        { name = "OPENSEARCH_PORT",        value = "443" },
        { name = "OPENSEARCH_USE_SSL",     value = "true" },
        { name = "OPENSEARCH_SERVICE",     value = "es" },
        { name = "S3_BUCKET",              value = var.s3_documents_bucket },
        { name = "AUDIT_LOG_BUCKET",       value = var.s3_audit_bucket },
        { name = "CHUNK_SIZE",             value = tostring(var.chunk_size) },
        { name = "CHUNK_OVERLAP",          value = tostring(var.chunk_overlap) },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.etl.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "etl"
        }
      }
    }
  ])

  tags = { Environment = var.environment }
}
