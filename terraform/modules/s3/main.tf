# ─────────────────────────────────────────────────────────────────────────────
# S3 module
# Provisions:
#   • Medical documents bucket  (source for ETL pipeline)
#   • Audit log bucket          (immutable HIPAA audit trail — Object Lock)
# ─────────────────────────────────────────────────────────────────────────────

# ── Documents bucket ──────────────────────────────────────────────────────────

resource "aws_s3_bucket" "documents" {
  bucket = "${var.project}-${var.environment}-documents-${var.account_id}"
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle: move older versions to Glacier after 90 days
resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    id     = "archive-old-versions"
    status = "Enabled"
    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }
    noncurrent_version_expiration {
      noncurrent_days = var.data_retention_days
    }
  }
}

# Domain prefixes
resource "aws_s3_object" "domain_prefixes" {
  for_each = {
    "medical-docs/disease-study/"   = "disease-study-prefix"
    "medical-docs/medicine-study/"  = "medicine-study-prefix"
    "medical-docs/medicine-expiry/" = "medicine-expiry-prefix"
    "medical-docs/equipment-study/" = "equipment-study-prefix"
  }
  bucket  = aws_s3_bucket.documents.id
  key     = each.key
  content = ""
}

# ── Audit log bucket (HIPAA §164.312 — immutable trail via Object Lock) ───────

resource "aws_s3_bucket" "audit" {
  bucket = "${var.project}-${var.environment}-audit-${var.account_id}"

  # Object Lock must be enabled at bucket creation — cannot be added later
  object_lock_enabled = true
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    default_retention {
      mode  = "COMPLIANCE"         # Cannot be deleted even by root
      days  = var.data_retention_days
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
