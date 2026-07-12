FROM codercom/code-server:latest

USER root

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    PORT=7860 \
    PASSWORD=shivanshbro \
    container=docker

# Install VPS utilities
RUN apt-get update && \
    apt-get install -y \
        systemd \
        systemd-sysv \
        dbus \
        dbus-user-session \
        openssh-server \
        sudo \
        curl \
        wget \
        iproute2 \
        nano \
        tmate \
        neofetch \
        gnupg \
        lsb-release \
        ca-certificates && \
    mkdir -p /run/sshd && \
    echo "root:root" | chpasswd && \
    printf '#!/bin/sh\nexit 0\n' > /usr/sbin/policy-rc.d && \
    chmod +x /usr/sbin/policy-rc.d && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Cloudflared
RUN mkdir -p --mode=0755 /usr/share/keyrings && \
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
        gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/cloudflared.list && \
    apt-get update && \
    apt-get install -y cloudflared && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create startup script
RUN cat >/usr/local/bin/start.sh <<'EOF'
#!/bin/bash
set -e

# Start SSH
mkdir -p /run/sshd
/usr/sbin/sshd

# Start code-server
exec code-server \
    --bind-addr 0.0.0.0:${PORT} \
    --auth password
EOF

RUN chmod +x /usr/local/bin/start.sh

EXPOSE 22 7860

ENTRYPOINT ["/usr/local/bin/start.sh"]
