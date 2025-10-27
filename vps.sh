#!/bin/bash
set -e

echo "=== 🧹 Cleaning up old containers and networks ==="
docker rm -f kaesyrlabs 2>/dev/null || true
docker network prune -f >/dev/null || true
docker volume prune -f >/dev/null || true

echo "=== 📦 Building Ubuntu 22.04 with working systemd & SSH ==="

# --- Create Dockerfile ---
cat > Dockerfile.systemd <<'EOF'
FROM ubuntu:22.04

ENV container docker
ENV DEBIAN_FRONTEND=noninteractive

# Install base and systemd components
RUN apt-get update && \
    apt-get install -y systemd systemd-sysv dbus dbus-user-session openssh-server sudo curl git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN echo 'root:1234' | chpasswd && \
    mkdir -p /var/run/sshd /root/.ssh && \
    sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's@^#Port.*@Port 22@' /etc/ssh/sshd_config

# Disable policy blocking systemd services during build
RUN printf '#!/bin/sh\nexit 0' > /usr/sbin/policy-rc.d

# Enable SSH at boot
RUN systemctl enable ssh

EXPOSE 22
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
EOF

# --- Build image ---
docker build -t kaesyrlabs-systemd -f Dockerfile.systemd .

echo "=== 🚀 Starting container (systemd + SSH) ==="
docker run -d \
  --name kaesyrlabs \
  --hostname KaesyrLabs \
  --privileged \
  -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  -p 1223:22 \
  kaesyrlabs-systemd

echo "=== 🧩 Checking container startup... ==="
sleep 10
docker exec -it kaesyrlabs systemctl start ssh
docker exec -it kaesyrlabs systemctl enable ssh >/dev/null 2>&1

echo "=== ✅ SSH should now be ready ==="
echo "   → Hostname: KaesyrLabs"
echo "   → SSH command: ssh root@<your_server_ip> -p 1223"
echo "   → Password: 1234"

echo "=== ⏳ Installing kami-tunnel ==="
wget -q https://github.com/kami2k1/tunnel/releases/latest/download/kami-tunnel-linux-amd64.tar.gz
tar -xzf kami-tunnel-linux-amd64.tar.gz
chmod +x kami-tunnel

echo "=== ⏱ Waiting 30 seconds before tunnel start... ==="
sleep 30

echo "=== 🚪 Starting kami-tunnel on port 1223 ==="
./kami-tunnel 1223
