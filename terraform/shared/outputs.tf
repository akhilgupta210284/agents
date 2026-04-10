output "tf_state_bucket" {
  value       = aws_s3_bucket.tf_state.id
  description = "S3 bucket name for Terraform remote state"
}

output "tf_lock_table" {
  value       = aws_dynamodb_table.tf_lock.id
  description = "DynamoDB table name for state locking"
}

output "ecr_app_repository_url" {
  value       = aws_ecr_repository.app.repository_url
  description = "ECR repository URL for the app image"
}

output "ecr_etl_repository_url" {
  value       = aws_ecr_repository.etl.repository_url
  description = "ECR repository URL for the ETL image"
}

output "github_oidc_provider_arn" {
  value       = aws_iam_openid_connect_provider.github.arn
  description = "ARN of the GitHub Actions OIDC provider"
}

output "deploy_role_arns" {
  value = {
    for env, role in aws_iam_role.deploy : env => role.arn
  }
  description = "Map of environment → deploy IAM role ARN"
}
