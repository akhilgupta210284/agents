output "cluster_name"        { value = aws_ecs_cluster.this.name }
output "cluster_arn"         { value = aws_ecs_cluster.this.id }
output "etl_task_definition" { value = aws_ecs_task_definition.etl.family }
output "etl_log_group"       { value = aws_cloudwatch_log_group.etl.name }
