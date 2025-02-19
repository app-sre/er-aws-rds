variable "rds_instance" {}
variable "reset_password" { default = null }

variable "enhanced_monitoring_role" { default = null }

variable "replica_source" { default = null }

variable "parameter_groups" { default = null }


variable "ca_cert" { default = null }
variable "output_resource_db_name" { default = null }

variable "tags" {}
variable "provision" {}
