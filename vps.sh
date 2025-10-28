#!/bin/bash
set -e

# (Removed: Clean up old kami files and containers)

echo "=== 📦 Pulling the latest Ubuntu image ==="
docker pull ubuntu:latest

echo "=== 🚀 Creating new Ubuntu container with SSH and Docker ==="
docker run -d \
  --name ubuntu-ssh \
  -p 1223:22 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  ubuntu:latest \
  bash -c "\
    apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y openssh-server sudo curl git && \
    echo 'root:1234' | chpasswd && \
    sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    mkdir /var/run/sshd && \
    service ssh start && \
    echo 'service ssh start' >> /root/.bashrc && \
    tail -f /dev/null"

echo "=== ✅ Ubuntu SSH + Docker container is ready ==="
echo "Root password: 1234, SSH port: 1223"

echo "=== 📥 Downloading kami-tunnel ==="
wget -q https://github.com/kami2k1/tunnel/releases/latest/download/kami-tunnel-linux-amd64.tar.gz
tar -xzf kami-tunnel-linux-amd64.tar.gz
chmod +x kami-tunnel

echo "=== ⏳ Waiting 30 seconds before starting kami-tunnel ==="
sleep 30

echo "=== 🚪 Starting kami-tunnel on port 1223 ==="
./kami-tunnel 1223
