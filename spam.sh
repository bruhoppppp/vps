#!/usr/bin/env bash
# benign_spammer.sh
# Continuously runs harmless commands at random intervals.
# Only run on systems you own / have permission to use.

LOGFILE="$HOME/benign_spammer.log"
# Ensure logfile exists
mkdir -p "$(dirname "$LOGFILE")"
touch "$LOGFILE"

# Safe command list (no destructive commands)
commands=(
  'date'
  'uptime'
  'whoami'
  'hostname'
  'pwd'
  'ls -la $HOME | head -n 20'
  'ps aux | head -n 10'
  'free -h'
  'df -h | head -n 10'
  'ip -brief addr || ip addr show'
  'echo "Random note: $(head -c 20 /dev/urandom | base64 | tr -d /=+)"'
  'printf "CPU load: "; cat /proc/loadavg'
  'echo "Open files count: $(ls /proc/$$/fd 2>/dev/null | wc -l)"'
  'uname -a'
  'w | head -n 10'
)

# How long to sleep between commands (seconds). We'll choose a random value in this range.
SLEEP_MIN=3
SLEEP_MAX=12

running=true

cleanup() {
  running=false
  echo "[$(date --iso-8601=seconds)] Received stop signal, exiting." | tee -a "$LOGFILE"
  exit 0
}

# Trap common termination signals so script exits cleanly
trap cleanup SIGINT SIGTERM

echo "[$(date --iso-8601=seconds)] benign_spammer started." | tee -a "$LOGFILE"

while $running; do
  # pick a random command
  idx=$((RANDOM % ${#commands[@]}))
  cmd="${commands[$idx]}"

  # expand variables inside the selected command safely
  # (use 'eval' because some commands include pipes or variable expansions)
  echo "[$(date --iso-8601=seconds)] >>> $cmd" | tee -a "$LOGFILE"
  eval "$cmd" 2>&1 | sed 's/^/    /' | tee -a "$LOGFILE"

  # random sleep
  sleep_time=$(( SLEEP_MIN + RANDOM % (SLEEP_MAX - SLEEP_MIN + 1) ))
  echo "[$(date --iso-8601=seconds)] sleeping ${sleep_time}s" | tee -a "$LOGFILE"
  sleep "$sleep_time"
done
