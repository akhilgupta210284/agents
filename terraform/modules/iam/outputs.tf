output "kms_key_arn"           { value = aws_kms_key.this.arn }
output "kms_key_id"            { value = aws_kms_key.this.key_id }
output "agentcore_role_arn"    { value = aws_iam_role.agentcore_execution.arn }
output "ecs_exec_role_arn"     { value = aws_iam_role.ecs_exec.arn }
output "ecs_task_role_arn"     { value = aws_iam_role.ecs_task.arn }
