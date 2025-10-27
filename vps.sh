#!/bin/bash
set -e

# 🧹 Clean up old files and containers
rm -rf kami*

echo "=== 🧹 Dọn dẹp container cũ, network và image liên quan ==="
docker rm -f ubuntu-ssh 2>/dev/null || true
docker network prune -f >/dev/null
docker image prune -af >/dev/null
docker volume prune -f >/dev/null

echo "=== 📦 Kéo Ubuntu có sẵn systemd ==="
docker pull jrei/systemd-ubuntu:22.04

echo "=== 🚀 Tạo container Ubuntu mới với systemd, SSH và Docker ==="
docker run -d \
  --privileged \
  --cgroupns=host \
  --name ubuntu-ssh \
  -p 1223:22 \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  jrei/systemd-ubuntu:22.04

echo "=== 🧰 Cài đặt SSH, sudo, git, curl và cấu hình root login ==="
docker exec ubuntu-ssh bash -c "\
  apt update && \
  DEBIAN_FRONTEND=noninteractive apt install -y systemd systemd-sysv openssh-server sudo curl git docker.io && \
  echo 'root:1234' | chpasswd && \
  sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
  sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
  systemctl enable ssh && \
  systemctl start ssh && \
  systemctl enable docker && \
  systemctl start docker && \
  echo '✅ SSH & Docker services started via systemctl'
"

echo "=== ✅ Container Ubuntu SSH + Docker + systemd đã sẵn sàng ==="
echo "Mật khẩu root: 1234"
echo "Cổng SSH: 1223"
echo "Dùng lệnh sau để truy cập:"
echo "ssh root@<YOUR_SERVER_IP> -p 1223"

echo "=== 📥 Tải kami-tunnel ==="
wget -q https://github.com/kami2k1/tunnel/releases/latest/download/kami-tunnel-linux-amd64.tar.gz
tar -xzf kami-tunnel-linux-amd64.tar.gz
chmod +x kami-tunnel

echo "=== ⏳ Đợi 30 giây trước khi khởi động kami-tunnel ==="
sleep 30

echo "=== 🚪 Khởi động kami-tunnel trên cổng 1223 ==="
./kami-tunnel 1223
