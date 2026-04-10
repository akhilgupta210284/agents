# Shared layer configuration — update before first apply
aws_region      = "us-east-1"
project         = "medical-agent"
tf_state_bucket = "medical-agent-tf-state-<ACCOUNT_ID>"   # must be globally unique
tf_lock_table   = "medical-agent-tf-lock"
github_repo     = "your-org/your-repo"                    # replace with actual repo
