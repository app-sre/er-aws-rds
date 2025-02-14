output "db_host" {
  value = aws_db_instance.rds_instance.address
}

output "db_port" {
  value = aws_db_instance.rds_instance.port
}

output "db_name" {
  value = coalesce(var.output_resource_db_name, aws_db_instance.rds_instance.db_name)
}

# Conditional CA Cert output
output "db_ca_cert" {
  value     = var.ca_cert != null ? var.ca_cert : null
  sensitive = false
}

output "reset_password" {
  value = var.reset_password != null ? var.reset_password : null
}

# Output reset password if applicable
data "terraform_remote_state" "remote_state" {
  count   = var.replica_source != null ? 1 : 0
  backend = "s3"

  config = {
    bucket  = var.provision.tf_state_bucket
    region  = var.provision.tf_state_region
    key     = "aws/${var.provision.provisioner}/rds/${var.replica_source.identifier}/terraform.tfstate"
    profile = "external-resources-state"
  }
}

output "db_user" {
  value     = var.replica_source == null ? aws_db_instance.rds_instance.username : data.terraform_remote_state.remote_state[0].outputs["db_user"]
  sensitive = true
}

output "db_password" {
  value     = var.replica_source == null ? aws_db_instance.rds_instance.password : data.terraform_remote_state.remote_state[0].outputs["db_password"]
  sensitive = true
}
