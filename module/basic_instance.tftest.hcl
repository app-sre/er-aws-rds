variables {
  rds_instance = {
    identifier                   = "test-instance"
    engine                       = "postgres"
    allow_major_version_upgrade  = true
    monitoring_interval          = 60
    apply_immediately            = true
    multi_az                     = false
    backup_retention_period      = 7
    db_subnet_group_name         = "app-sre rds subnet group"
    storage_encrypted            = true
    username                     = "postgres"
    instance_class               = "db.t4g.medium"
    allocated_storage            = 100
    auto_minor_version_upgrade   = false
    skip_final_snapshot          = true
    storage_type                 = "gp3"
    engine_version               = "16.1"
    maintenance_window           = "Sun:05:00-Sun:07:00"
    backup_window                = "03:00-04:00"
    performance_insights_enabled = true
    deletion_protection          = true
    ca_cert_identifier           = "rds-ca-rsa2048-g1"
    blue_green_update            = { enabled = true }
    db_name                      = "custom_database"
  }

  parameter_groups = [
    {
      family      = "postgres15"
      name        = "test-instance-new-pg"
      description = "Parameter Group for PostgreSQL 15"
      parameters = [
        { name = "log_min_duration_statement", value = "-1", apply_method = "immediate" },
        { name = "log_statement", value = "none", apply_method = "immediate" },
        { name = "shared_preload_libraries", value = "pg_stat_statements", apply_method = "pending-reboot" }
      ]
    },
    {
      family      = "postgres16"
      name        = "test-instance-pg"
      description = "Parameter Group for PostgreSQL 16"
      parameters = [
        { name = "log_min_duration_statement", value = "-1", apply_method = "immediate" },
        { name = "log_statement", value = "none", apply_method = "immediate" },
        { name = "shared_preload_libraries", value = "pg_stat_statements", apply_method = "pending-reboot" }
      ]
    }
  ]

  reset_password           = ""
  enhanced_monitoring_role = "test-instance-enhanced-monitoring"

  tags = {
    managed_by_integration = "external_resources"
    cluster                = "test-cluster"
    namespace              = "test-namespace"
    environment            = "stage"
    app                    = "test-app"
  }

  region = "us-east-1"

  provision = {
    provision_provider = "aws"
    provisioner        = "test-account"
    provider           = "rds"
    identifier         = "test-instance"
    target_cluster     = "test-cluster"
    target_namespace   = "test-namespace"
    target_secret_name = "test-db-creds"
    module_provision_data = {
      tf_state_bucket         = "external-resources-state"
      tf_state_region         = "us-east-1"
      tf_state_dynamodb_table = "external-resources-terraform-lock"
      tf_state_key            = "aws/test-account/rds/test-instance/terraform.tfstate"
    }
  }
}

run "parameter_groups" {
  command = plan

  assert {
    condition     = length(aws_db_parameter_group.this) == 2
    error_message = "Parameter groups are not created as expected."
  }
}


run "replica_does_not_have_password" {
  command = plan

  variables {
    rds_instance = {
      identifier          = "test-instance"
      engine              = "postgres"
      instance_class      = "db.t4g.medium"
      allocated_storage   = 100
      storage_type        = "gp3"
      engine_version      = "16.1"
      deletion_protection = true
      replicate_source_db = "test"
    }
  }

  assert {
    condition     = length(random_password.this) == 0
    error_message = "The password object exists when it shuold not."
  }
}
