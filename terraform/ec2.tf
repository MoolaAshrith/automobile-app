resource "aws_instance" "automobile_app" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.automobile_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.automobile_profile.name

  user_data = file("${path.module}/user_data.sh")

  root_block_device {
    volume_size           = 20
    volume_type           = "gp2"
    delete_on_termination = true
  }

  tags = {
    Name        = "${var.app_name}-app-server"
    Environment = var.environment
  }

  lifecycle {
    ignore_changes = [user_data]
  }
}
