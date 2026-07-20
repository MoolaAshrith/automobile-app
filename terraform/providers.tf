terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "automobile-tfstate-bucket"
    key            = "automobile-app/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "automobile-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
