output "agent_runtime_id"  { value = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id }
output "agent_runtime_arn" { value = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn }
output "app_log_group"     { value = aws_cloudwatch_log_group.app.name }
