resource "aws_vpc" "automobile_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.app_name}-vpc"
  }
}

resource "aws_internet_gateway" "automobile_igw" {
  vpc_id = aws_vpc.automobile_vpc.id

  tags = {
    Name = "${var.app_name}-igw"
  }
}

resource "aws_subnet" "automobile_subnet" {
  vpc_id                  = aws_vpc.automobile_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "ap-south-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.app_name}-subnet"
  }
}

resource "aws_route_table" "automobile_public_rt" {
  vpc_id = aws_vpc.automobile_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.automobile_igw.id
  }

  tags = {
    Name = "${var.app_name}-public-rt"
  }
}

resource "aws_route_table_association" "automobile_public_assoc" {
  subnet_id      = aws_subnet.automobile_subnet.id
  route_table_id = aws_route_table.automobile_public_rt.id
}
