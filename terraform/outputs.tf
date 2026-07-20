output "ec2_public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_instance.automobile_app.public_ip
}

output "ec2_public_dns" {
  description = "Public DNS of the EC2 instance"
  value       = aws_instance.automobile_app.public_dns
}

output "ecr_repository_url" {
  description = "Full ECR repository URL for docker push/pull"
  value       = aws_ecr_repository.automobile_app.repository_url
}

output "ecr_repository_name" {
  description = "ECR repository name"
  value       = aws_ecr_repository.automobile_app.name
}

output "app_url" {
  description = "Application URL"
  value       = "http://${aws_instance.automobile_app.public_ip}"
}
