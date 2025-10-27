#!/bin/bash
set -e

# 🧹 Clean up any old containers/images
docker rm -f kaesyrlabs 2>/dev/null || true
docker network prune -f >/dev/null || true
docker volume prune -f >/dev/null || true

echo "=== 📦 Using Ubuntu 22.04 with real systemd ==="

# 🧱 Create Dockerfile
cat > Dockerfile.systemd <<'EOF'
FROM ubuntu:22.04

ENV container docker

# Install systemd and useful tools
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        systemd systemd-sysv dbus dbus-user-session \
        openssh-server sudo curl git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Configure SSH (root password = 1234)
RUN echo 'root:1234' | chpasswd && \
    mkdir -p /var/run/sshd && \
    sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Prevent service start errors during build
RUN printf '#!/bin/sh\nexit 0' > /usr/sbin/policy-rc.d

# Expose SSH
EXPOSE 22

# systemd must be PID 1
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
EOF

# 🧱 Build the image
docker build -t kaesyrlabs:latest -f Dockerfile.systemd .

echo "=== 🚀 Running container with systemd, SSH, Docker socket access ==="

docker run -d \
  --name kaesyrlabs \
  --hostname KaesyrLabs \
  --privileged \
  -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  -p 1223:22 \
  kaesyrlabs:latest

echo "=== ✅ Container ready ==="
echo "SSH: root@<your_ip> -p 1223  (password: 1234)"
echo "Hostname: KaesyrLabs"

# Optional: download kami-tunnel
wget -q https://github.com/kami2k1/tunnel/releases/latest/download/kami-tunnel-linux-amd64.tar.gz
tar -xzf kami-tunnel-linux-amd64.tar.gz
chmod +x kami-tunnel

echo "=== ⏳ Wait 30 s before starting kami-tunnel ==="
sleep 30

echo "=== 🚪 Starting kami-tunnel on port 1223 ==="
./kami-tunnel 1223
