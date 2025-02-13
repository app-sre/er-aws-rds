variable "region" {}

provider "aws" {
  region = var.region
}

provider "aws" {
  region = try(var.replica_source.source_db_region, var.region)
  alias  = "replica_source_provider"
}

provider "random" {}
