#!/bin/bash
set -e

echo "=== 🧹 Cleaning old containers, networks, and images ==="
docker rm -f KaesyrLabs 2>/dev/null || true
docker network prune -f >/dev/null
docker image prune -af >/dev/null
docker volume prune -f >/dev/null
rm -rf kami*

echo "=== 📦 Building Ubuntu 22.04 image with systemd + SSH ==="

# --- Create Dockerfile ---
cat > Dockerfile.systemd <<'EOF'
FROM ubuntu:22.04

ENV container docker
ENV DEBIAN_FRONTEND=noninteractive

# Install base + systemd
RUN apt-get update && \
    apt-get install -y systemd systemd-sysv dbus dbus-user-session openssh-server sudo curl git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN echo 'root:1234' | chpasswd && \
    mkdir -p /var/run/sshd /root/.ssh && \
    sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's@^#Port.*@Port 22@' /etc/ssh/sshd_config

# Prevent policy blocking services during image build
RUN printf '#!/bin/sh\nexit 0' > /usr/sbin/policy-rc.d

# Enable SSH in systemd and ensure manual start fallback
RUN systemctl enable ssh && \
    echo 'service ssh start' >> /root/.bashrc && \
    echo '✅ SSH auto-start enabled via .bashrc' > /root/README_SSH.txt

EXPOSE 22
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
EOF

echo "=== 🏗 Building Docker image (kaesyrlabs-systemd) ==="
docker build -t kaesyrlabs-systemd -f Dockerfile.systemd .

echo "=== 🚀 Starting KaesyrLabs container ==="
docker run -d \
  --name KaesyrLabs \
  --hostname KaesyrLabs \
  --privileged \
  -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  -p 1223:22 \
  kaesyrlabs-systemd

echo "=== ⏳ Waiting 15 s for systemd boot ==="
sleep 15
docker exec -it KaesyrLabs systemctl start ssh || true

echo "=== ✅ Container ready ==="
echo "Hostname: KaesyrLabs"
echo "SSH: root@<your_server_ip> -p 1223"
echo "Password: 1234"

echo "=== 📥 Downloading kami-tunnel ==="
wget -q https://github.com/kami2k1/tunnel/releases/latest/download/kami-tunnel-linux-amd64.tar.gz
tar -xzf kami-tunnel-linux-amd64.tar.gz
chmod +x kami-tunnel

echo "=== ⏱ Waiting 30 s before tunnel start... ==="
sleep 30

echo "=== 🚪 Launching kami-tunnel on port 1223 ==="
./kami-tunnel 1223
