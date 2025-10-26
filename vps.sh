#!/bin/bash
set -e

# Clean up old kami files
rm -rf kami*

echo "=== 🧹 Dọn dẹp container cũ, network và image liên quan ==="
docker rm -f ubuntu-ssh 2>/dev/null || true
docker network prune -f >/dev/null
docker image prune -af >/dev/null
docker volume prune -f >/dev/null

echo "=== 📦 Kéo Ubuntu mới nhất ==="
docker pull ubuntu:latest

echo "=== 🚀 Tạo container Ubuntu mới với SSH, Docker và hostname KaesyrLabs ==="
docker run -d \
  --name ubuntu-ssh \
  --hostname KaesyrLabs \
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
    tail -f /dev/null"

echo "=== ✅ Container Ubuntu SSH + Docker đã sẵn sàng ==="
echo "Mật khẩu root: 1234, cổng SSH: 1223, hostname: KaesyrLabs"

echo "=== 📥 Tải kami-tunnel ==="
wget -q https://github.com/kami2k1/tunnel/releases/latest/download/kami-tunnel-linux-amd64.tar.gz
tar -xzf kami-tunnel-linux-amd64.tar.gz
chmod +x kami-tunnel

echo "=== ⏳ Đợi 30 giây trước khi khởi động kami-tunnel ==="
sleep 30

echo "=== 🚪 Khởi động kami-tunnel trên cổng 1223 ==="
./kami-tunnel 1223
