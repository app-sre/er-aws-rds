output "__db_host" {
  value = aws_db_instance.this.address
}

output "__db_port" {
  value = aws_db_instance.this.port
}

output "__db_name" {
  value = coalesce(var.output_resource_db_name, aws_db_instance.this.db_name)
}

# Conditional CA Cert output
output "__db_ca_cert" {
  value     = var.ca_cert != null ? var.ca_cert : null
  sensitive = false
}

output "__reset_password" {
  value = var.reset_password != null && var.reset_password != "" ? var.reset_password : null
}

# Output reset password if applicable
data "terraform_remote_state" "replica_source" {
  count   = var.replica_source != null ? 1 : 0
  backend = "s3"

  config = {
    bucket  = var.provision.tf_state_bucket
    region  = var.provision.tf_state_region
    key     = "aws/${var.provision.provisioner}/rds/${var.replica_source.identifier}/terraform.tfstate"
    profile = "external-resources-state"
  }
}

output "__db_user" {
  value     = var.replica_source == null ? aws_db_instance.this.username : data.terraform_remote_state.replica_source[0].outputs["db_user"]
  sensitive = true
}

output "__db_password" {
  value     = var.replica_source == null ? aws_db_instance.this.password : data.terraform_remote_state.replica_source[0].outputs["db_password"]
  sensitive = true
}
