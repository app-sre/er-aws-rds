data "aws_partition" "this" {}
data "aws_db_instance" "replica_source" {
  count                  = try(var.replica_source.identifier, null) != null ? 1 : 0
  db_instance_identifier = var.replica_source.identifier
  provider               = aws.replica_source_provider
}

data "aws_kms_key" "this" {
  count  = try(var.rds_instance.kms_key_id, null) != null ? 1 : 0
  key_id = startswith(try(var.rds_instance.kms_key_id, ""), "arn:") ? var.rds_instance.kms_key_id : "alias/${var.rds_instance.kms_key_id}"
}

data "aws_sns_topic" "this" {
  for_each = { for k, v in try(var.rds_instance.event_subscriptions, []) : k => v.destination }
  name     = each.value
}

resource "aws_iam_role" "this" {
  count = var.enhanced_monitoring_role != null ? 1 : 0
  name  = var.enhanced_monitoring_role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "this" {
  count      = var.enhanced_monitoring_role != null ? 1 : 0
  role       = aws_iam_role.this[0].name
  policy_arn = "arn:${data.aws_partition.this.partition}:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

locals {
  parameter_groups             = { for pg in try(var.parameter_groups, []) : pg.name => pg }
  parameter_group_name         = try(var.rds_instance.parameter_group_name, null)
  parameter_group_managed      = local.parameter_group_name != null ? contains(keys(local.parameter_groups), local.parameter_group_name) : false
  aws_db_instance_needs_engine = try(var.rds_instance.replicate_source_db, null) == null && try(var.rds_instance.snapshot_identifier, null) == null ? true : false
}

resource "aws_db_parameter_group" "this" {
  for_each    = local.parameter_groups
  name        = each.value.name
  family      = each.value.family
  description = each.value.description

  dynamic "parameter" {
    for_each = each.value.parameters
    content {
      name         = parameter.value.name
      value        = parameter.value.value
      apply_method = try(parameter.value.apply_method, null)
    }
  }

  tags = var.tags
  lifecycle {
    create_before_destroy = true
  }
}

resource "random_password" "this" {
  count       = var.replica_source == null && try(var.rds_instance.replicate_source_db, null) == null ? 1 : 0
  length      = 20
  special     = false
  min_numeric = 0
  keepers = {
    reset_password = try(var.reset_password, "")
  }
}

resource "aws_db_event_subscription" "this" {
  for_each   = data.aws_sns_topic.this
  sns_topic  = each.value.arn
  source_ids = [aws_db_instance.this.id]
  tags       = var.tags
}

resource "aws_db_instance" "this" {
  allocated_storage                     = try(var.rds_instance.allocated_storage, null)
  allow_major_version_upgrade           = try(var.rds_instance.allow_major_version_upgrade, null)
  apply_immediately                     = try(var.rds_instance.apply_immediately, null)
  auto_minor_version_upgrade            = try(var.rds_instance.auto_minor_version_upgrade, null)
  availability_zone                     = try(var.rds_instance.availability_zone, null)
  backup_retention_period               = try(var.rds_instance.backup_retention_period, null)
  backup_target                         = try(var.rds_instance.backup_target, null)
  backup_window                         = try(var.rds_instance.backup_window, null)
  ca_cert_identifier                    = try(var.rds_instance.ca_cert_identifier, null)
  character_set_name                    = try(var.rds_instance.character_set_name, null)
  copy_tags_to_snapshot                 = try(var.rds_instance.copy_tags_to_snapshot, null)
  custom_iam_instance_profile           = try(var.rds_instance.custom_iam_instance_profile, null)
  db_name                               = try(var.rds_instance.db_name, null)
  db_subnet_group_name                  = try(var.rds_instance.db_subnet_group_name, null)
  dedicated_log_volume                  = try(var.rds_instance.dedicated_log_volume, null)
  delete_automated_backups              = try(var.rds_instance.delete_automated_backups, null)
  deletion_protection                   = try(var.rds_instance.deletion_protection, null)
  domain                                = try(var.rds_instance.domain, null)
  domain_auth_secret_arn                = try(var.rds_instance.domain_auth_secret_arn, null)
  domain_dns_ips                        = try(var.rds_instance.domain_dns_ips, null)
  domain_fqdn                           = try(var.rds_instance.domain_fqdn, null)
  domain_iam_role_name                  = try(var.rds_instance.domain_iam_role_name, null)
  domain_ou                             = try(var.rds_instance.domain_ou, null)
  enabled_cloudwatch_logs_exports       = try(var.rds_instance.enabled_cloudwatch_logs_exports, null)
  engine                                = local.aws_db_instance_needs_engine ? var.rds_instance.engine : null
  engine_version                        = try(var.rds_instance.engine_version, null)
  final_snapshot_identifier             = try(var.rds_instance.final_snapshot_identifier, null)
  iam_database_authentication_enabled   = try(var.rds_instance.iam_database_authentication_enabled, null)
  identifier                            = try(var.rds_instance.identifier, null)
  identifier_prefix                     = try(var.rds_instance.identifier_prefix, null)
  instance_class                        = try(var.rds_instance.instance_class, null)
  iops                                  = try(var.rds_instance.iops, null)
  kms_key_id                            = try(data.aws_kms_key.this[0].arn, null)
  license_model                         = try(var.rds_instance.license_model, null)
  maintenance_window                    = try(var.rds_instance.maintenance_window, null)
  manage_master_user_password           = try(var.rds_instance.manage_master_user_password, null)
  master_user_secret_kms_key_id         = try(var.rds_instance.master_user_secret_kms_key_id, null)
  max_allocated_storage                 = try(var.rds_instance.max_allocated_storage, null)
  monitoring_interval                   = try(var.rds_instance.monitoring_interval, null)
  monitoring_role_arn                   = try(var.rds_instance.monitoring_role_arn, aws_iam_role.this[0].arn, null)
  multi_az                              = try(var.rds_instance.multi_az, null)
  network_type                          = try(var.rds_instance.network_type, null)
  option_group_name                     = try(var.rds_instance.option_group_name, null)
  parameter_group_name                  = local.parameter_group_managed ? aws_db_parameter_group.this[local.parameter_group_name].name : local.parameter_group_name
  password                              = try(random_password.this[0].result, null)
  performance_insights_enabled          = try(var.rds_instance.performance_insights_enabled, null)
  performance_insights_kms_key_id       = try(var.rds_instance.performance_insights_kms_key_id, null)
  performance_insights_retention_period = try(var.rds_instance.performance_insights_retention_period, null)
  port                                  = try(var.rds_instance.port, null)
  publicly_accessible                   = try(var.rds_instance.publicly_accessible, null)
  replica_mode                          = try(var.rds_instance.replica_mode, null)

  replicate_source_db = try(var.rds_instance.replicate_source_db, null) != null ? var.rds_instance.replicate_source_db : var.replica_source != null ? data.aws_db_instance.replica_source[0].db_instance_arn : null

  dynamic "restore_to_point_in_time" {
    for_each = try(length(var.rds_instance.restore_to_point_in_time), 0) > 0 ? [var.rds_instance.restore_to_point_in_time] : []
    content {
      restore_time                             = try(var.rds_instance.restore_to_point_in_time.restore_time, null)
      source_db_instance_identifier            = try(var.rds_instance.restore_to_point_in_time.source_db_instance_identifier, null)
      source_db_instance_automated_backups_arn = try(var.rds_instance.restore_to_point_in_time.source_db_instance_automated_backups_arn, null)
      source_dbi_resource_id                   = try(var.rds_instance.restore_to_point_in_time.source_dbi_resource_id, null)
      use_latest_restorable_time               = try(var.rds_instance.restore_to_point_in_time.use_latest_restorable_time, null)
    }
  }
  dynamic "s3_import" {
    for_each = try(length(var.rds_instance.s3_import), 0) > 0 ? [var.rds_instance.s3_import] : []
    content {
      source_engine         = try(var.rds_instance.s3_import.source_engine, null)
      source_engine_version = try(var.rds_instance.s3_import.source_engine_version, null)
      bucket_name           = try(var.rds_instance.s3_import.bucket_name, null)
      bucket_prefix         = try(var.rds_instance.s3_import.bucket_prefix, null)
      ingestion_role        = try(var.rds_instance.s3_import.ingestion_role, null)
    }
  }
  skip_final_snapshot = try(var.rds_instance.skip_final_snapshot, null)
  snapshot_identifier = try(var.rds_instance.snapshot_identifier, null)
  storage_encrypted   = try(var.rds_instance.storage_encrypted, null)
  storage_type        = try(var.rds_instance.storage_type, null)
  storage_throughput  = try(var.rds_instance.storage_throughput, null)
  tags                = try(var.tags, null)
  timeouts {
    create = try(var.rds_instance.timeouts.create, null)
    update = try(var.rds_instance.timeouts.update, null)
    delete = try(var.rds_instance.timeouts.delete, null)
  }
  timezone               = try(var.rds_instance.timezone, null)
  username               = try(var.rds_instance.username, null)
  vpc_security_group_ids = try(var.rds_instance.vpc_security_group_ids, null)
}
