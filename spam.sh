#!/bin/bash

# --- Random 24/7 Command Spammer ---
# This script runs forever and prints random fake commands
# purely for terminal simulation or fun (harmless).

commands=(
  "sudo apt update"
  "ping google.com"
  "htop"
  "curl example.com"
  "ls -la /home"
  "df -h"
  "free -m"
  "top"
  "git pull origin main"
  "systemctl restart nginx"
  "echo Hello World"
  "ps aux | grep python"
  "npm install"
  "python3 app.py"
  "docker ps -a"
  "journalctl -xe"
  "netstat -tulnp"
)

echo "[+] Starting random terminal spammer (24/7 mode)..."
echo "Press Ctrl+C to stop."

while true; do
  # Pick a random command from the list
  cmd="${commands[$RANDOM % ${#commands[@]}]}"
  
  # Print it with a timestamp
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running: $cmd"
  
  # Wait random time between 1 and 5 seconds
  sleep $((RANDOM % 5 + 1))
done
