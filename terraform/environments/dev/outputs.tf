output "vpc_id"               { value = module.networking.vpc_id }
output "opensearch_endpoint"  { value = module.opensearch.domain_endpoint }
output "agent_runtime_id"     { value = module.agentcore.agent_runtime_id }
output "agent_runtime_arn"    { value = module.agentcore.agent_runtime_arn }
output "etl_cluster_name"     { value = module.ecs.cluster_name }
output "documents_bucket"     { value = module.s3.documents_bucket_name }
output "audit_bucket"         { value = module.s3.audit_bucket_name }
output "kms_key_arn"          { value = module.iam.kms_key_arn }
