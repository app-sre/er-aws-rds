variable "region" {}

provider "aws" {
  region = var.region
  default_tags {
    tags = var.tags
  }
}

provider "aws" {
  region = try(var.replica_source.region, var.region)
  alias  = "replica_source_provider"
  default_tags {
    tags = var.tags
  }
}

provider "random" {}
