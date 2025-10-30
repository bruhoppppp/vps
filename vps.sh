#!/bin/bash
set -e

# === ⚙️ Generate random container name + SSH port ===
RAND=$(tr -dc 'a-z0-9' </dev/urandom | head -c 6)
CONTAINER="ubuntu-ssh-$RAND"
SSH_PORT=$(shuf -i 10000-40000 -n 1)

echo "=== 📦 Pulling latest Ubuntu image ==="
docker pull ubuntu:latest

echo "=== 🚀 Creating new Ubuntu container ($CONTAINER, SSH Port: $SSH_PORT) ==="
docker run -d \
  --name $CONTAINER \
  -p ${SSH_PORT}:22 \
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

echo "=== ✅ Ubuntu SSH + Docker container created successfully ==="
echo "Name: $CONTAINER"
echo "SSH Port: $SSH_PORT"
echo "Password: 1234"

echo "=== 📥 Downloading kami-tunnel ==="
wget -q https://github.com/kami2k1/tunnel/releases/latest/download/kami-tunnel-linux-amd64.tar.gz
tar -xzf kami-tunnel-linux-amd64.tar.gz
chmod +x kami-tunnel

echo "=== ⏳ Waiting 30 seconds before starting kami-tunnel ==="
sleep 30

echo "=== 🚪 Starting kami-tunnel on port $SSH_PORT ==="
./kami-tunnel $SSH_PORT
