# Make sure to create state bucket beforehand
terraform {
  required_version = ">= 1.0"
  backend "s3" {
    bucket  = "my-tf-bucket-ahm-amm"
    key     = "mlops-zoomcamp-prj-stg.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current_identity" {}

locals {
  account_id = data.aws_caller_identity.current_identity.account_id
}

# model bucket
module "s3_bucket" {
  source = "./modules/s3"
  bucket_name = "${var.model_bucket}-${var.project_id}"
}

output "model_bucket" {
  value = module.s3_bucket.name
}

module "rds_instance" {
  source = "./modules/rds"
  db_name = "mlflowdatabasetf"
}

