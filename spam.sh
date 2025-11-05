import os
import random
import time
import subprocess
from datetime import datetime

# List of packages to simulate activity
PACKAGES = ['htop', 'git', 'vim', 'tree', 'nmap', 'curl', 'wget', 'python3']

LOG_FILE = "activity.log"

def log(message):
    """Write timestamped messages to a log file."""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} {message}\n")
    print(f"{timestamp} {message}")

def run_command(command):
    """Run a shell command safely and log output."""
    log(f"Running command: {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        if result.stdout:
            log(result.stdout.strip())
        if result.stderr:
            log(f"ERROR: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        log("Command timed out.")
    except Exception as e:
        log(f"Command failed: {e}")

def install_package(package):
    run_command(f"sudo apt-get install -y {package}")

def remove_package(package):
    run_command(f"sudo apt-get remove -y {package}")

def check_neofetch():
    run_command("neofetch || echo 'neofetch not installed'")

def random_sleep():
    """Sleep for a random realistic duration (1–10 minutes)."""
    sleep_time = random.randint(60, 600)
    log(f"Sleeping for {sleep_time // 60} min {sleep_time % 60} sec...")
    time.sleep(sleep_time)

def main():
    log("=== 24/7 Terminal Simulation Started ===")
    while True:
        action = random.choice(['install', 'remove', 'neofetch'])
        package = random.choice(PACKAGES)

        if action == 'install':
            log(f"Installing {package}...")
            install_package(package)
        elif action == 'remove':
            log(f"Removing {package}...")
            remove_package(package)
        else:
            log("Checking system info...")
            check_neofetch()

        random_sleep()

if __name__ == "__main__":
    main()
