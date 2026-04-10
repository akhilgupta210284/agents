terraform {
  backend "s3" {
    # bucket         = "medical-agent-tf-state-<ACCOUNT_ID>"
    # key            = "environments/qa/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "medical-agent-tf-lock"
    # encrypt        = true
  }
}
