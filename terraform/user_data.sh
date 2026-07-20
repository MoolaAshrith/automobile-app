#!/bin/bash
set -e

# ── System update ──────────────────────────────────────────────────────────────
apt-get update -y
apt-get upgrade -y

# ── Swap (critical for t2.micro — 1GB RAM only) ────────────────────────────────
fallocate -l 1G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo "Swap created."

# ── Docker ─────────────────────────────────────────────────────────────────────
apt-get install -y ca-certificates curl gnupg lsb-release unzip

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

usermod -aG docker ubuntu

# ── AWS CLI v2 ─────────────────────────────────────────────────────────────────
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/awscliv2.zip /tmp/aws

# ── App directory ──────────────────────────────────────────────────────────────
mkdir -p /opt/automobile-app
chown ubuntu:ubuntu /opt/automobile-app

echo "Bootstrap complete — Docker and AWS CLI installed."
