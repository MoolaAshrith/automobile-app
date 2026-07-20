variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "app_name" {
  description = "Application name prefix for all resources"
  type        = string
  default     = "automobile"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "instance_type" {
  description = "EC2 instance type — free tier eligible"
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = "Amazon Machine Image ID — Ubuntu 22.04 LTS ap-south-1"
  type        = string
  default     = "ami-0f58b397bc5c1f2e8"
}

variable "key_pair_name" {
  description = "EC2 key pair name for SSH access"
  type        = string
  default     = "automobile-app-key"
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH into EC2"
  type        = string
  default     = "0.0.0.0/0"
}

variable "ecr_image_tag_mutability" {
  description = "ECR image tag mutability setting"
  type        = string
  default     = "MUTABLE"
}
