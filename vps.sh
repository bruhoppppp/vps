cat > vps.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting VPS Generator Script..."

# Force remove old container silently (always succeeds)
docker ps -a --format '{{.Names}}' | grep -w ubuntu-ssh >/dev/null 2>&1 && \
docker rm -f ubuntu-ssh >/dev/null 2>&1 || true

# Remove unused networks/images silently
docker network prune -f >/dev/null 2>&1 || true
docker image prune -f >/dev/null 2>&1 || true

echo "=== 📦 Pulling the latest Ubuntu image ==="
docker pull ubuntu:latest

echo "=== 🖥️ Creating new Ubuntu container with SSH ==="
docker run -d \
  --name ubuntu-ssh \
  --restart always \
  -p 1223:22 \
  ubuntu:latest tail -f /dev/null

echo "=== 🔧 Setting up SSH and Kami Tunnel inside the container ==="
docker exec ubuntu-ssh bash -c "
  apt update -y && apt install -y openssh-server wget curl sudo &&
  service ssh start &&
  echo 'root:1234' | chpasswd &&
  echo 'service ssh start' >> /root/.bashrc &&
  wget -qO /usr/local/bin/kami https://github.com/kaesyr/kami-tunnel/releases/latest/download/kami-linux-amd64 &&
  chmod +x /usr/local/bin/kami &&
  nohup /usr/local/bin/kami --port 1223 --print-url > /tmp/kami-url.txt 2>&1 &
  sleep 6
"

echo "✅ Ubuntu SSH container is ready!"
echo "🔑 Root password: 1234"
echo "🧩 SSH Port inside container: 1223"

echo "=== 🌐 Fetching your public VPS link from Kami Tunnel ==="
docker exec ubuntu-ssh bash -c "cat /tmp/kami-url.txt" | grep -Eo 'https?://[^ ]+' || echo "⚠️ Public URL not found. Check logs using: docker logs ubuntu-ssh"

echo "🎉 VPS created successfully!"
echo "You can connect using:"
echo "ssh root@<PUBLIC_URL> -p 1223"
EOF

chmod +x vps.sh
bash vps.sh
