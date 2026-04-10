terraform {
  backend "s3" {
    # Values are supplied via -backend-config flags in CI (see cd.yml)
    # or via a backend.hcl file locally.
    # bucket         = "medical-agent-tf-state-<ACCOUNT_ID>"
    # key            = "environments/dev/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "medical-agent-tf-lock"
    # encrypt        = true
    # kms_key_id     = "alias/medical-agent-shared"
  }
}
