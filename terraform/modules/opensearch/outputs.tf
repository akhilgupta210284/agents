output "domain_endpoint" {
  value       = aws_opensearch_domain.this.endpoint
  description = "HTTPS endpoint for the OpenSearch domain (no scheme prefix)"
}
output "domain_arn"  { value = aws_opensearch_domain.this.arn }
output "domain_name" { value = aws_opensearch_domain.this.domain_name }
