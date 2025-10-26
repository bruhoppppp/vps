#!/bin/bash
set -e

# Clean old kami files
rm -rf kami*

echo "=== 🧹 Dọn dẹp container cũ, network và image liên quan ==="
docker rm -f ubuntu-ssh 2>/dev/null || true
docker network prune -f >/dev/null
docker image prune -af >/dev/null
docker volume prune -f >/dev/null

echo "=== 📦 Kéo Ubuntu 22.04 mới nhất ==="
docker pull ubuntu:22.04

echo "=== 🚀 Tạo container Ubuntu mới với SSH, Docker, systemd, và hostname KaesyrLabs ==="
docker run -d \
  --name ubuntu-ssh \
  --hostname KaesyrLabs \
  -p 1223:22 \
  --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  ubuntu:22.04 \
  bash -c "\
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      openssh-server sudo curl git systemd systemd-sysv dbus dbus-user-session && \
    echo 'root:1234' | chpasswd && \
    printf '#!/bin/sh\nexit 0' > /usr/sbin/policy-rc.d && \
    mkdir -p /var/run/sshd && \
    sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    systemctl start systemd-logind || true && \
    service ssh start && \
    echo 'systemctl start systemd-logind' >> /etc/profile && \
    tail -f /dev/null"

echo "=== ✅ Container Ubuntu SSH + Docker + systemd đã sẵn sàng ==="
echo "Mật khẩu root: 1234 | Cổng SSH: 1223 | Hostname: KaesyrLabs"

echo "=== 📥 Tải kami-tunnel ==="
wget -q https://github.com/kami2k1/tunnel/releases/latest/download/kami-tunnel-linux-amd64.tar.gz
tar -xzf kami-tunnel-linux-amd64.tar.gz
chmod +x kami-tunnel

echo "=== ⏳ Đợi 30 giây trước khi khởi động kami-tunnel ==="
sleep 30

echo "=== 🚪 Khởi động kami-tunnel trên cổng 1223 ==="
./kami-tunnel 1223
