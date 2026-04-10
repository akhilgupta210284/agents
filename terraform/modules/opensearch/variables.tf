variable "project"     { type = string }
variable "environment" { type = string }

variable "engine_version" {
  type    = string
  default = "OpenSearch_2.11"
}
variable "instance_type" {
  type        = string
  description = "e.g. t3.small.search (dev/qa) or r6g.large.search (prod)"
  default     = "t3.small.search"
}
variable "instance_count" {
  type    = number
  default = 1
}
variable "ebs_volume_size" {
  type        = number
  description = "EBS volume size in GiB"
  default     = 20
}
variable "private_subnet_ids"  { type = list(string) }
variable "opensearch_sg_id"    { type = string }
variable "kms_key_id"          { type = string }
variable "ecs_task_role_arn"   { type = string }
variable "log_retention_days" {
  type    = number
  default = 90
}
