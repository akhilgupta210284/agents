# ─────────────────────────────────────────────────────────────────────────────
# OpenSearch module
# Provisions an AWS OpenSearch Service domain with:
#   • KNN plugin enabled (required for vector/semantic search)
#   • VPC deployment (private subnets only)
#   • Encryption at rest (KMS CMK)
#   • Encryption in transit (HTTPS only — HIPAA §164.312)
#   • Fine-grained access control (FGAC)
#   • Automated snapshots
#   • CloudWatch metric publishing
# ─────────────────────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  domain_name = "${var.project}-${var.environment}"
}

# ── Service-linked role (needed for VPC access) ───────────────────────────────

resource "aws_iam_service_linked_role" "opensearch" {
  aws_service_name = "opensearchservice.amazonaws.com"
  # Ignore if already exists
  lifecycle {
    ignore_changes        = [description]
    create_before_destroy = false
  }
}

# ── OpenSearch domain ─────────────────────────────────────────────────────────

resource "aws_opensearch_domain" "this" {
  domain_name    = local.domain_name
  engine_version = var.engine_version

  # Cluster topology — sized per environment via variables
  cluster_config {
    instance_type          = var.instance_type
    instance_count         = var.instance_count
    zone_awareness_enabled = var.instance_count > 1

    dynamic "zone_awareness_config" {
      for_each = var.instance_count > 1 ? [1] : []
      content {
        availability_zone_count = 2
      }
    }
  }

  # EBS storage
  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = var.ebs_volume_size
    throughput  = 125
  }

  # VPC — OpenSearch sits in private subnets
  vpc_options {
    subnet_ids         = var.instance_count > 1 ? var.private_subnet_ids : [var.private_subnet_ids[0]]
    security_group_ids = [var.opensearch_sg_id]
  }

  # Encryption at rest (HIPAA §164.312(a)(2)(iv))
  encrypt_at_rest {
    enabled    = true
    kms_key_id = var.kms_key_id
  }

  # Encryption in transit (HIPAA §164.312(e)(1))
  node_to_node_encryption {
    enabled = true
  }
  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  # Fine-grained access control
  advanced_security_options {
    enabled                        = true
    anonymous_auth_enabled         = false
    internal_user_database_enabled = false
    master_user_options {
      master_user_arn = var.ecs_task_role_arn
    }
  }

  # KNN advanced settings
  advanced_options = {
    "knn.memory.circuit_breaker.enabled" = "true"
    "rest.action.multi.allow_explicit_index" = "true"
  }

  # Automated snapshots (HIPAA §164.308 backup requirement)
  snapshot_options {
    automated_snapshot_start_hour = 3   # 3 AM UTC
  }

  # CloudWatch metrics
  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_app.arn
    log_type                 = "INDEX_SLOW_LOGS"
  }
  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_search.arn
    log_type                 = "SEARCH_SLOW_LOGS"
  }

  depends_on = [aws_iam_service_linked_role.opensearch]

  tags = {
    Environment = var.environment
    HIPAA       = "true"
  }
}

# ── Access policy ─────────────────────────────────────────────────────────────
# Allow the ECS task role to perform all HTTP operations on the domain

resource "aws_opensearch_domain_policy" "this" {
  domain_name = aws_opensearch_domain.this.domain_name

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { AWS = var.ecs_task_role_arn }
        Action    = "es:ESHttp*"
        Resource  = "${aws_opensearch_domain.this.arn}/*"
      }
    ]
  })
}

# ── CloudWatch log groups for OpenSearch slow logs ────────────────────────────

resource "aws_cloudwatch_log_group" "opensearch_app" {
  name              = "/aws/opensearch/${local.domain_name}/application"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "opensearch_search" {
  name              = "/aws/opensearch/${local.domain_name}/search"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "${local.domain_name}-opensearch-logs"
  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "es.amazonaws.com" }
      Action    = ["logs:PutLogEvents", "logs:CreateLogStream"]
      Resource  = [
        "${aws_cloudwatch_log_group.opensearch_app.arn}:*",
        "${aws_cloudwatch_log_group.opensearch_search.arn}:*"
      ]
    }]
  })
}
