import random
import subprocess
import os
import discord
from discord.ext import commands, tasks
import asyncio
from discord import app_commands
import psutil
from datetime import datetime, timedelta
import json
import logging
import sys
import requests
import re

# ================= CONFIGURATION =================
TOKEN = ''
ADMIN_ROLE_ID = 1477997687532945478     # Your Admin Role ID
MAIN_ADMIN_ID = 1329035198649864202     # Your Discord User ID
LOGS_CHANNEL_ID = 1514847215271673896    # Your Logs Channel ID

BOT_OWNER_NAME = "Devabyss"
LOGO_URL = "https://cdn.discordapp.com/embed/avatars/3.png?size=1024"
EMBED_COLOR = 0x2B2D31 

RAM_LIMIT = '2g'
STORAGE_LIMIT = '25g'
DATABASE_FILE = 'vps_database.json'
CONFIG_FILE = 'bot_config.json'
EMBED_FOOTER_SUFFIX = '. made by iamgunpoint'

TIERS = {
    "free": {"ram": "31g", "cpu": "16.0", "disk": "210g", "name": "Free Tier"},
    "pro": {"ram": "8g", "cpu": "2.0", "disk": "40g", "name": "Pro Tier"},
    "vip": {"ram": "16g", "cpu": "4.0", "disk": "80g", "name": "VIP Tier"}
}

# Fetch public IP for port forwarding display
try:
    HOST_IP = requests.get('https://api.ipify.org').text
except:
    HOST_IP = "Host-IP"

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ================= DATABASE & CONFIG =================
def load_db():
    if not os.path.exists(DATABASE_FILE): return {}
    try:
        with open(DATABASE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_db(data):
    with open(DATABASE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_config():
    if not os.path.exists(CONFIG_FILE): 
        return {"autocleanup": True, "extra_admins": []}
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        if "extra_admins" not in config: config["extra_admins"] = []
        return config
    except:
        return {"autocleanup": True, "extra_admins": []}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# ================= HELPER UTILS =================
async def is_admin(ctx_or_interaction):
    user = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author
    config = load_config()
    return (user.id == MAIN_ADMIN_ID or 
            user.id in config.get("extra_admins", []) or 
            any(role.id == ADMIN_ROLE_ID for role in getattr(user, 'roles', [])))

def build_footer_text(base_text=None):
    footer_base = (base_text or f"Powered by {BOT_OWNER_NAME} • Cryzon Cloud").strip()
    return f"{footer_base} {EMBED_FOOTER_SUFFIX}"


def get_beautiful_embed(title, description, color=EMBED_COLOR, footer_text=None):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_thumbnail(url=LOGO_URL)
    embed.set_footer(text=build_footer_text(footer_text), icon_url=LOGO_URL)
    return embed

async def run_cmd_async(cmd_list, check=True):
    """Run a shell command asynchronously to prevent blocking the event loop."""
    def sync_run():
        result = subprocess.run(cmd_list, capture_output=True, text=True)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd_list, output=result.stdout, stderr=result.stderr
            )
        return result.stdout.strip()
    return await asyncio.to_thread(sync_run)

def parse_writable_size(size_str):
    """Parses docker output sizes (e.g. 15.4 GB, 500 MB, 1.2 GiB) into raw bytes."""
    size_str = size_str.split('(')[0].strip()
    size_str = size_str.replace('i', '').replace('I', '') # handle GiB/MiB notation
    match = re.match(r"([\d\.]+)\s*([KMG]?B)", size_str, re.IGNORECASE)
    if not match:
        return 0
    val, unit = match.groups()
    val = float(val)
    unit = unit.upper()
    multiplier = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    return int(val * multiplier.get(unit, 1))

async def get_or_guess_vps(interaction: discord.Interaction, container_id: str = None):
    """
    Finds or auto-guesses a VPS instance for the user.
    If the user has exactly 1 VPS, it auto-guesses it.
    If they have multiple, they must specify.
    If they specify a VPS they do not own, we allow it only if they are an administrator.
    """
    db = load_db()
    user_id = interaction.user.id
    
    # Filter for instances owned by or shared with this user
    user_instances = []
    for cid, data in db.items():
        if data['owner_id'] == user_id or user_id in data.get('shared_with', []):
            user_instances.append((cid, data))
            
    if not container_id:
        if len(user_instances) == 0:
            await interaction.response.send_message("❌ You do not own or have access to any VPS.", ephemeral=True)
            return None, None
        elif len(user_instances) == 1:
            # Auto-guessed single VPS
            return user_instances[0]
        else:
            # Multiple VPS, force user to choose
            vps_list_str = ", ".join([f"`{cid[:8]}`" for cid, _ in user_instances])
            await interaction.response.send_message(
                f"❌ You have multiple VPS instances: {vps_list_str}. Please specify the container ID in your command.", 
                ephemeral=True
            )
            return None, None
    else:
        # Search in user's own/shared list first (fuzzy matching short ID)
        for cid, data in user_instances:
            if cid.startswith(container_id) or container_id.startswith(cid[:8]):
                return cid, data
        
        # If not found in user's list, check if user is an admin so they can manage ANY VPS
        if await is_admin(interaction):
            for cid, data in db.items():
                if cid.startswith(container_id) or container_id.startswith(cid[:8]):
                    return cid, data
                    
        await interaction.response.send_message("❌ VPS not found or you do not have permission to access it.", ephemeral=True)
        return None, None

def get_shell_binary(os_type):
    return "sh" if os_type == "alpine" else "bash"


def get_container_setup_cmd(os_type):
    if os_type == "alpine":
        return "apk add --no-cache curl wget tmate procps iproute2 socat openssh openrc && curl -sSf https://sshx.io/get | sh"
    return (
        "export DEBIAN_FRONTEND=noninteractive && apt-get update -y "
        "&& apt-get install -y curl wget tmate procps iproute2 socat openssh-client init-system-helpers "
        "&& curl -sSf https://sshx.io/get | sh"
    )


SYSTEMCTL_COMPAT_SCRIPT = r'''#!/bin/sh
ACTION="${1:-}"
SERVICE_NAME="${2:-}"
REAL_SYSTEMCTL="/usr/bin/systemctl"

if [ -n "$SERVICE_NAME" ]; then
    SERVICE_NAME="${SERVICE_NAME%.service}"
fi

print_help() {
    echo "systemctl compatibility mode is enabled in this container."
    echo "Supported actions: start, stop, restart, reload, status, enable, disable, is-active, list-unit-files, list-units, daemon-reload"
}

run_service_action() {
    action="$1"
    service_name="$2"

    if command -v rc-service >/dev/null 2>&1; then
        exec rc-service "$service_name" "$action"
    elif command -v service >/dev/null 2>&1; then
        exec service "$service_name" "$action"
    elif [ -x "/etc/init.d/$service_name" ]; then
        exec "/etc/init.d/$service_name" "$action"
    else
        echo "Service '$service_name' not found."
        exit 1
    fi
}

enable_service() {
    service_name="$1"

    if command -v rc-update >/dev/null 2>&1; then
        exec rc-update add "$service_name" default
    elif command -v update-rc.d >/dev/null 2>&1; then
        exec update-rc.d "$service_name" defaults
    else
        echo "Enable is not supported in this container."
        exit 1
    fi
}

disable_service() {
    service_name="$1"

    if command -v rc-update >/dev/null 2>&1; then
        exec rc-update del "$service_name" default
    elif command -v update-rc.d >/dev/null 2>&1; then
        exec update-rc.d -f "$service_name" remove
    else
        echo "Disable is not supported in this container."
        exit 1
    fi
}

is_service_active() {
    service_name="$1"

    if command -v rc-service >/dev/null 2>&1; then
        if rc-service "$service_name" status >/dev/null 2>&1; then
            echo "active"
        else
            echo "inactive"
        fi
        exit 0
    elif command -v service >/dev/null 2>&1; then
        if service "$service_name" status >/dev/null 2>&1; then
            echo "active"
        else
            echo "inactive"
        fi
        exit 0
    elif [ -x "/etc/init.d/$service_name" ]; then
        if "/etc/init.d/$service_name" status >/dev/null 2>&1; then
            echo "active"
        else
            echo "inactive"
        fi
        exit 0
    fi

    echo "unknown"
    exit 3
}

list_services() {
    if [ -d /etc/init.d ]; then
        for svc in /etc/init.d/*; do
            [ -f "$svc" ] || continue
            name=$(basename "$svc")
            [ "$name" = "README" ] && continue
            enabled="disabled"
            if command -v rc-update >/dev/null 2>&1; then
                if rc-update show default 2>/dev/null | grep -Eq "^${name}[[:space:]]"; then
                    enabled="enabled"
                fi
            elif command -v update-rc.d >/dev/null 2>&1; then
                if ls /etc/rc*.d/S*"$name" >/dev/null 2>&1; then
                    enabled="enabled"
                fi
            fi
            printf "%s.service %s\n" "$name" "$enabled"
        done | sort
        exit 0
    fi

    echo "No services found."
    exit 0
}

case "$ACTION" in
    ""|-h|--help)
        print_help
        ;;
    daemon-reload)
        exit 0
        ;;
    start|stop|restart|reload|status)
        [ -n "$SERVICE_NAME" ] || {
            echo "No service specified."
            exit 1
        }
        run_service_action "$ACTION" "$SERVICE_NAME"
        ;;
    enable)
        [ -n "$SERVICE_NAME" ] || {
            echo "No service specified."
            exit 1
        }
        enable_service "$SERVICE_NAME"
        ;;
    disable)
        [ -n "$SERVICE_NAME" ] || {
            echo "No service specified."
            exit 1
        }
        disable_service "$SERVICE_NAME"
        ;;
    is-active)
        [ -n "$SERVICE_NAME" ] || {
            echo "No service specified."
            exit 1
        }
        is_service_active "$SERVICE_NAME"
        ;;
    list-unit-files|list-units)
        list_services
        ;;
    *)
        if [ -x "$REAL_SYSTEMCTL" ]; then
            exec "$REAL_SYSTEMCTL" "$@"
        fi
        echo "Unsupported systemctl action inside container: $ACTION"
        exit 1
        ;;
esac
'''


async def install_systemctl_support(cid, os_type):
    shell_binary = get_shell_binary(os_type)
    install_cmd = f"""mkdir -p /usr/local/bin
cat <<'EOF' > /usr/local/bin/systemctl
{SYSTEMCTL_COMPAT_SCRIPT}
EOF
chmod +x /usr/local/bin/systemctl
"""
    await run_cmd_async(["docker", "exec", cid, shell_binary, "-c", install_cmd])


async def ensure_systemctl_support(cid, os_type):
    shell_binary = get_shell_binary(os_type)
    result = await run_cmd_async([
        "docker", "exec", cid, shell_binary, "-c",
        "if [ -x /usr/local/bin/systemctl ]; then echo installed; else echo missing; fi"
    ], check=False)
    if "installed" not in result:
        await install_systemctl_support(cid, os_type)


async def provision_container(cid, os_type):
    shell_binary = get_shell_binary(os_type)
    await run_cmd_async(["docker", "exec", cid, shell_binary, "-c", get_container_setup_cmd(os_type)])
    await install_systemctl_support(cid, os_type)


def get_random_port():
    return random.randint(20000, 30000)


def terminal_log(message, type="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {"INFO": "\033[94m", "SUCCESS": "\033[92m", "WARN": "\033[93m", "ERROR": "\033[91m", "RESET": "\033[0m"}
    icon = {"INFO": "ℹ️", "SUCCESS": "✅", "WARN": "⚠️", "ERROR": "🚨"}.get(type, "🔹")
    print(f"{colors.get(type, '')}[{timestamp}] {icon} {message}{colors['RESET']}")

# ================= BOT CORE =================
class VPSBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix='.', intents=intents, help_command=None)

    async def setup_hook(self):
        await self.tree.sync()

    @tasks.loop(minutes=30)
    async def cleanup_task(self):
        await self.wait_until_ready()
        config = load_config()
        if not config.get("autocleanup", True): return
        db = load_db()
        now = datetime.now()
        to_delete = []
        for cid, data in db.items():
            if data.get("suspended", False): continue
            last_act = datetime.fromisoformat(data.get('last_activity', now.isoformat()))
            if (now - last_act) > timedelta(days=1):
                try:
                    stats = await run_cmd_async(["docker", "stats", cid, "--no-stream", "--format", "{{.CPUPerc}}"])
                    if float(stats.replace('%', '')) < 0.1: to_delete.append(cid)
                except: to_delete.append(cid)
        for cid in to_delete:
            terminal_log(f"Auto-deleting inactive instance: {cid[:8]}", "WARN")
            try:
                await run_cmd_async(["docker", "rm", "-f", cid])
            except Exception as e:
                terminal_log(f"Failed to auto-delete {cid[:8]}: {e}", "ERROR")
            if cid in db:
                del db[cid]
        save_db(db)

    @tasks.loop(seconds=60)
    async def status_loop(self):
        await self.wait_until_ready()
        db = load_db()
        try:
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(db)} VPS | {BOT_OWNER_NAME}"))
        except: pass

    @tasks.loop(minutes=5)
    async def resource_alert_task(self):
        await self.wait_until_ready()
        db = load_db()
        alerts = []
        for cid, data in db.items():
            if data.get("suspended", False): continue
            try:
                stats = await run_cmd_async(["docker", "stats", cid, "--no-stream", "--format", "{{.CPUPerc}}"])
                cpu_val = float(stats.replace('%', ''))
                if cpu_val > 70.0:
                    alerts.append(f"⚠️ Instance `{cid[:8]}` (User: <@{data['owner_id']}>) is at **{cpu_val}%** CPU usage!")
                    terminal_log(f"High Resource Alert: {cid[:8]} at {cpu_val}%", "WARN")
            except: pass
        
        if alerts:
            owner = self.get_user(MAIN_ADMIN_ID)
            if owner:
                try:
                    await owner.send(f"🚨 **Resource Alert!**\n" + "\n".join(alerts))
                except: pass

    @tasks.loop(minutes=2)
    async def quota_enforcer_task(self):
        """Monitors containers in real-time. Automatically shuts down and suspends any node that exceeds its allocated tier resources."""
        await self.wait_until_ready()
        db = load_db()
        for cid, data in list(db.items()):
            if data.get("suspended", False): 
                continue
                
            tier = data.get("tier", "free")
            tier_data = TIERS.get(tier, TIERS["free"])
            
            # --- 1. Storage Enforcement ---
            disk_limit_str = tier_data.get("disk", "20g")
            limit_bytes = 20 * 1024**3 # Fallback
            match = re.match(r"(\d+)([gGmM])", disk_limit_str)
            if match:
                val, unit = match.groups()
                val = int(val)
                if unit.lower() == 'g':
                    limit_bytes = val * 1024**3
                elif unit.lower() == 'm':
                    limit_bytes = val * 1024**2
                    
            try:
                size_output = await run_cmd_async([
                    "docker", "ps", "-a", "--size", 
                    "--filter", f"id={cid}", 
                    "--format", "{{.Size}}"
                ])
                if size_output:
                    used_bytes = parse_writable_size(size_output)
                    if used_bytes > limit_bytes:
                        terminal_log(f"Enforcement: Container {cid[:8]} exceeded storage ({round(used_bytes/1024**3, 2)}GB / {disk_limit_str}). Suspending...", "WARN")
                        
                        # Stop the container immediately to freeze writing
                        await run_cmd_async(["docker", "stop", cid], check=False)
                        
                        db[cid]["suspended"] = True
                        db[cid]["suspension_reason"] = f"Exceeded {tier_data['name']} storage quota ({disk_limit_str})."
                        save_db(db)
                        
                        # DM User Alert
                        try:
                            user = self.get_user(data['owner_id']) or await self.fetch_user(data['owner_id'])
                            if user:
                                embed = get_beautiful_embed(
                                    "🚨 VPS Storage Quota Suspension", 
                                    f"Your VPS instance `{cid[:8]}` has been automatically suspended because it exceeded your tier storage limits."
                                )
                                embed.add_field(name="Tier", value=f"`{tier_data['name']}`")
                                embed.add_field(name="Storage Limit", value=f"`{disk_limit_str}`")
                                embed.add_field(name="Actual Usage", value=f"`{round(used_bytes/1024**3, 2)}GB`")
                                embed.add_field(name="Action Taken", value="Container was shut down and blocked from starting. Please contact an admin.")
                                await user.send(embed=embed)
                        except Exception as dm_err:
                            terminal_log(f"Could not alert user {data['owner_id']}: {dm_err}", "WARN")
                        continue # Continue to next container, already suspended
            except Exception as e:
                terminal_log(f"Quota storage checker failed for {cid[:8]}: {e}", "ERROR")

            # --- 2. Memory Enforcement (Fallback for hosts without swap cgroups limits) ---
            ram_limit_str = tier_data.get("ram", "4g")
            ram_limit_bytes = 4 * 1024**3
            match_ram = re.match(r"(\d+)([gGmM])", ram_limit_str)
            if match_ram:
                val, unit = match_ram.groups()
                val = int(val)
                if unit.lower() == 'g':
                    ram_limit_bytes = val * 1024**3
                elif unit.lower() == 'm':
                    ram_limit_bytes = val * 1024**2

            try:
                stats_out = await run_cmd_async([
                    "docker", "stats", cid, "--no-stream", "--format", "{{.MemUsage}}"
                ])
                if stats_out:
                    mem_usage_part = stats_out.split('/')[0].strip()
                    used_ram_bytes = parse_writable_size(mem_usage_part)
                    if used_ram_bytes > ram_limit_bytes:
                        terminal_log(f"Enforcement: Container {cid[:8]} exceeded RAM ({round(used_ram_bytes/1024**3, 2)}GB / {ram_limit_str}). Suspending...", "WARN")
                        
                        await run_cmd_async(["docker", "stop", cid], check=False)
                        db[cid]["suspended"] = True
                        db[cid]["suspension_reason"] = f"Exceeded {tier_data['name']} RAM quota ({ram_limit_str})."
                        save_db(db)
                        
                        try:
                            user = self.get_user(data['owner_id']) or await self.fetch_user(data['owner_id'])
                            if user:
                                embed = get_beautiful_embed(
                                    "🚨 VPS RAM Quota Suspension", 
                                    f"Your VPS instance `{cid[:8]}` has been automatically suspended because it exceeded your tier RAM limits."
                                )
                                embed.add_field(name="Tier", value=f"`{tier_data['name']}`")
                                embed.add_field(name="RAM Limit", value=f"`{ram_limit_str}`")
                                embed.add_field(name="Actual Usage", value=f"`{round(used_ram_bytes/1024**3, 2)}GB`")
                                embed.add_field(name="Action Taken", value="Container was shut down and blocked from starting. Please contact an admin.")
                                await user.send(embed=embed)
                        except Exception as dm_err:
                            terminal_log(f"Could not alert user {data['owner_id']}: {dm_err}", "WARN")
            except Exception as e:
                pass

bot = VPSBot()

@bot.event
async def on_ready():
    if not bot.cleanup_task.is_running(): bot.cleanup_task.start()
    if not bot.status_loop.is_running(): bot.status_loop.start()
    if not bot.resource_alert_task.is_running(): bot.resource_alert_task.start()
    if not bot.quota_enforcer_task.is_running(): bot.quota_enforcer_task.start()
    terminal_log(f"Bot successfully logged in as {bot.user}", "SUCCESS")

# ================= HELP COMMAND =================

@bot.command(name="help")
async def help_prefix(ctx):
    await send_help(ctx)

@bot.tree.command(name="help", description="ℹ️ Show help menu")
async def help_slash(interaction: discord.Interaction):
    await send_help(interaction)

async def send_help(ctx_or_inter):
    embed = get_beautiful_embed("✨ Cloud Instance Bot Help", "List of available commands and usage.")
    user_cmds = (
        "📊 `/info` - View your VPS stats and shared users\n"
        "🟢 `/start [id]` - Power ON your VPS\n"
        "🔴 `/stop [id]` - Power OFF your VPS\n"
        "🔄 `/regen-ssh [id]` - Regenerate SSH/SSHX links (DMed to you)\n"
        "🔌 `/forward <port> [id]` - Forward a port (e.g. 80)\n"
        "➖ `/unforward <port> [id]` - Remove a port forward\n"
        "🤝 `/sharevps @user [id]` - Share access (Max 2)\n"
        "➖ `/removeshared @user [id]` - Remove a shared user\n"
        "📜 `/listshared [id]` - List shared users\n"
        "🐚 `/shell <cmd> [id]` - Run a command (Owner Only)\n"
        "🔄 `/rebuild [id]` - Reinstall OS (Wipes Data)\n"
        "🗑️ `/remove [id]` - Delete VPS\n"
        "🏓 `/ping` - Latency Check"
    )
    admin_cmds = (
        "🚀 `/deploy @user <os> <tier>` - Deploy a professional VPS\n"
        "📊 `/status` - Live Host System Status (Updates every 5s)\n"
        "👑 `/list` - Comprehensive admin list of all VPS\n"
        "🚫 `/suspendvps <@user/id> [reason]` - Suspend a user's VPS\n"
        "🟢 `/unsuspendvps <@user/id>` - Unsuspend a user's VPS\n"
        "🗑️ `/deletevps <@user/id>` - Force delete any VPS\n"
        "🧹 `/autocleanup <True/False>` - Toggle global auto-deletion\n"
        "👑 `/adminadd @user` - Add a bot administrator\n"
        "👑 `/adminremove @user` - Remove a bot administrator\n"
        "👑 `/adminlist` - List all bot administrators\n"
        "📸 `/snapshot [id]` - Take a system snapshot"
    )
    embed.add_field(name="👤 User Commands", value=user_cmds, inline=False)
    if await is_admin(ctx_or_inter):
        embed.add_field(name="👑 Admin Commands", value=admin_cmds, inline=False)
    embed.add_field(name="💡 Getting Started", value="1. Once deployed, use `/regen-ssh` to get links in DM.\n2. Use `/forward` to expose services.\n3. The prefix is `.` (dot). Slash commands are recommended!", inline=False)
    if isinstance(ctx_or_inter, discord.Interaction): 
        await ctx_or_inter.response.send_message(embed=embed)
    else: 
        await ctx_or_inter.send(embed=embed)

# ================= ADMIN MANAGEMENT =================

@bot.tree.command(name="adminadd", description="👑 [ADMIN] Add a bot administrator")
async def adminadd(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != MAIN_ADMIN_ID: return await interaction.response.send_message("❌ Main Admin Only.", ephemeral=True)
    config = load_config()
    if user.id not in config["extra_admins"]:
        config["extra_admins"].append(user.id)
        save_config(config)
        await interaction.response.send_message(f"✅ {user.mention} added to administrators.")
    else: 
        await interaction.response.send_message("User is already an admin.", ephemeral=True)

@bot.tree.command(name="adminremove", description="👑 [ADMIN] Remove a bot administrator")
async def adminremove(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != MAIN_ADMIN_ID: return await interaction.response.send_message("❌ Main Admin Only.", ephemeral=True)
    config = load_config()
    if user.id in config["extra_admins"]:
        config["extra_admins"].remove(user.id)
        save_config(config)
        await interaction.response.send_message(f"✅ {user.mention} removed from administrators.")
    else: 
        await interaction.response.send_message("User is not an admin.", ephemeral=True)

@bot.tree.command(name="adminlist", description="👑 [ADMIN] List all administrators")
async def adminlist(interaction: discord.Interaction):
    if not await is_admin(interaction): return await interaction.response.send_message("Denied.", ephemeral=True)
    config = load_config()
    admins = [f"• <@{MAIN_ADMIN_ID}> (Owner)"] + [f"• <@{uid}>" for uid in config["extra_admins"]]
    await interaction.response.send_message(embed=get_beautiful_embed("👑 Bot Administrators", "\n".join(admins)))

# ================= VPS MANAGEMENT =================

async def get_access_links(cid, os_type):
    tmate_ssh = "Failed to generate"
    sshx_url = "Failed to generate"
    shell_binary = get_shell_binary(os_type)

    try:
        await ensure_systemctl_support(cid, os_type)
    except Exception as e:
        terminal_log(f"Systemctl compatibility check failed for {cid[:8]}: {e}", "WARN")
    
    # Verify that setup packages exist inside the container, repair if not
    try:
        install_check = "which tmate && which sshx"
        await run_cmd_async(["docker", "exec", cid, shell_binary, "-c", install_check], check=True)
    except:
        terminal_log(f"tmate or sshx missing in {cid[:8]}. Attempting emergency repair...", "WARN")
        try:
            repair_cmd = get_container_setup_cmd(os_type)
            await run_cmd_async(["docker", "exec", cid, shell_binary, "-c", repair_cmd], check=False)
            await install_systemctl_support(cid, os_type)
        except Exception as e:
            terminal_log(f"Emergency repair failed for {cid[:8]}: {e}", "ERROR")

    # Retry fetch loop for tmate (up to 3 times with progressive delays)
    for attempt in range(1, 4):
        try:
            await run_cmd_async(["docker", "exec", cid, "pkill", "-f", "tmate"], check=False)
            tmate_cmd = f"tmate -S /tmp/tmate.sock new-session -d && sleep {4 + attempt * 2} && tmate -S /tmp/tmate.sock display -p '#{{tmate_ssh}}'"
            tmate_ssh_res = await run_cmd_async(["docker", "exec", cid, shell_binary, "-c", tmate_cmd])
            if tmate_ssh_res and "ssh" in tmate_ssh_res:
                tmate_ssh = tmate_ssh_res
                break
        except Exception as e:
            terminal_log(f"Tmate link generation attempt {attempt} failed for {cid[:8]}: {e}", "WARN")
            await asyncio.sleep(2)
            
    # Retry fetch loop for sshx (up to 3 times)
    for attempt in range(1, 4):
        try:
            sshx_cmd = r"sshx > /tmp/sshx.log 2>&1 & sleep 5 && grep -o 'https://sshx\.io/s/[A-Za-z0-9_-]\+\(#[A-Za-z0-9_-]\+\)\?' /tmp/sshx.log | head -n 1"
            sshx_url_res = await run_cmd_async(["docker", "exec", cid, shell_binary, "-c", sshx_cmd])
            if sshx_url_res and "sshx.io" in sshx_url_res:
                sshx_url = sshx_url_res
                break
        except Exception as e:
            terminal_log(f"Sshx link generation attempt {attempt} failed for {cid[:8]}: {e}", "WARN")
            await asyncio.sleep(2)
            
    return tmate_ssh, sshx_url

@bot.tree.command(name="deploy", description="🚀 [ADMIN] Deploy a professional VPS")
@app_commands.choices(os_type=[
    app_commands.Choice(name="Ubuntu 22.04", value="ubuntu"),
    app_commands.Choice(name="Debian 12", value="debian")
], tier=[
    app_commands.Choice(name="Free (4G RAM / 1 Core / 20G Disk)", value="free"),
    app_commands.Choice(name="Pro (8G RAM / 2 Cores / 40G Disk)", value="pro"),
    app_commands.Choice(name="VIP (16G RAM / 4 Cores / 80G Disk)", value="vip")
])
async def deploy(interaction: discord.Interaction, user: discord.User, os_type: str, tier: str):
    if not await is_admin(interaction): return await interaction.response.send_message("❌ Denied.", ephemeral=True)
    await interaction.response.defer()
    valid_os = {"ubuntu": "ubuntu:22.04", "debian": "debian:12", "alpine": "alpine:latest"}
    tier_data = TIERS[tier]
    msg = await interaction.followup.send(embed=get_beautiful_embed("🛰️ Deployment Started", f"Creating `{tier_data['name']}` ({os_type.upper()}) for {user.mention}..."))
    try:
        terminal_log(f"Starting deployment for {user} ({os_type})", "INFO")
        
        # Determine host specs to avoid limits exceeding actual hardware capacity
        host_mem = psutil.virtual_memory().total  # total physical memory in bytes
        host_cpus = psutil.cpu_count() or 1
        
        # Parse requested Tier RAM string (e.g., "4g", "8g")
        tier_ram_str = tier_data["ram"]
        ram_bytes = 4 * 1024**3  # default fallback
        match = re.match(r"(\d+)([gGmM])", tier_ram_str)
        if match:
            val, unit = match.groups()
            val = int(val)
            if unit.lower() == 'g':
                ram_bytes = val * 1024**3
            elif unit.lower() == 'm':
                ram_bytes = val * 1024**2
                
        # Limit allocated RAM and CPU to what is actually available on the host machine to avoid error 125
        safe_ram_bytes = min(ram_bytes, int(host_mem * 0.9))
        safe_ram_str = f"{int(safe_ram_bytes / 1024**2)}m"
        
        tier_cpus = float(tier_data["cpu"])
        safe_cpus = min(tier_cpus, float(host_cpus))
        
        cid = None
        container_entry = get_shell_binary(os_type)
        # Attempt 1: Run with memory and CPU constraints fully enforced
        try:
            terminal_log(f"Attempting full hardware limits: RAM {safe_ram_str}, CPU {safe_cpus} Cores", "INFO")
            cid = await run_cmd_async([
                "docker", "run", "-itd", "--privileged", 
                "--memory", safe_ram_str, 
                "--cpus", str(safe_cpus), 
                valid_os[os_type], container_entry
            ])
            terminal_log("Container deployed with full memory and CPU specifications.", "SUCCESS")
        except Exception as err1:
            terminal_log(f"Enforcing full memory limits failed: {err1}. Falling back to CPU-only throttling limits...", "WARN")
            # Attempt 2: Fallback to CPU-only throttling limits (if cgroups memory control is completely missing)
            try:
                cid = await run_cmd_async([
                    "docker", "run", "-itd", "--privileged", 
                    "--cpus", str(safe_cpus), 
                    valid_os[os_type], container_entry
                ])
                terminal_log("Container deployed with CPU specs enforced (Memory fallback).", "SUCCESS")
            except Exception as err2:
                terminal_log(f"Enforcing CPU limits failed: {err2}. Falling back to unlimited node deployment...", "ERROR")
                # Attempt 3: Ultimate fallback to unthrottled run
                cid = await run_cmd_async([
                    "docker", "run", "-itd", "--privileged", 
                    valid_os[os_type], container_entry
                ])
        
        await provision_container(cid, os_type)
        tmate_ssh, sshx_url = await get_access_links(cid, os_type)
        db = load_db()
        db[cid] = {
            "owner_id": user.id, 
            "owner_name": str(user), 
            "os": os_type, 
            "tier": tier, 
            "sshx": sshx_url, 
            "tmate": tmate_ssh, 
            "ports": {}, 
            "shared_with": [], 
            "last_activity": datetime.now().isoformat(), 
            "suspended": False
        }
        save_db(db)
        success = get_beautiful_embed("✅ VPS Deployed", f"Professional `{tier_data['name']}` instance for {user.mention} is online.")
        success.add_field(name="🌐 SSH Access", value="▫️ Sent privately to your DMs for security.", inline=True)
        await msg.edit(embed=success)
        dm_embed = get_beautiful_embed("🔑 Your VPS Access Details", f"Access for instance `{cid[:8]}`")
        dm_embed.add_field(name="🌐 SSHX Web Console", value=f"[Connect Here]({sshx_url})", inline=False)
        dm_embed.add_field(name="🐚 Tmate SSH Command", value=f"```bash\n{tmate_ssh}```", inline=False)
        dm_embed.add_field(name="📊 Specs", value=f"RAM: `{tier_data['ram']}` | CPU: `{tier_data['cpu']}` | Disk: `{tier_data['disk']}`", inline=False)
        try: 
            await user.send(embed=dm_embed)
        except Exception as dm_err:
            terminal_log(f"Could not DM user: {dm_err}", "WARN")
        terminal_log(f"Deployment finished for {user}.", "SUCCESS")
    except Exception as e:
        terminal_log(f"Deployment failed: {str(e)}", "ERROR")
        await msg.edit(embed=get_beautiful_embed("❌ Deployment Failed", str(e)))

@bot.tree.command(name="status", description="📊 [ADMIN] Live Host System Status")
async def host_status(interaction: discord.Interaction):
    if not await is_admin(interaction): return await interaction.response.send_message("Denied.", ephemeral=True)
    await interaction.response.defer()
    embed = get_beautiful_embed("📊 Live Host Status", "Monitoring system resources...")
    msg = await interaction.followup.send(embed=embed)
    for _ in range(60):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        db = load_db()
        embed.description = f"Real-time monitoring for **{BOT_OWNER_NAME} Cloud**."
        embed.clear_fields()
        embed.add_field(name="🖥️ CPU Usage", value=f"```fix\n{cpu}%```", inline=True)
        embed.add_field(name="🧠 RAM Usage", value=f"```fix\n{ram.percent}% ({round(ram.used/1024**3, 2)}GB / {round(ram.total/1024**3, 2)}GB)```", inline=True)
        embed.add_field(name="💽 Disk Space", value=f"```fix\n{disk.percent}% ({round(disk.used/1024**3, 2)}GB / {round(disk.total/1024**3, 2)}GB)```", inline=True)
        embed.add_field(name="🌐 Active Nodes", value=f"```fix\n{len(db)} Instances```", inline=True)
        embed.set_footer(text=build_footer_text(f"Last Update: {datetime.now().strftime('%H:%M:%S')} • Refreshing every 5s"), icon_url=LOGO_URL)
        try: await msg.edit(embed=embed)
        except: break
        await asyncio.sleep(5)

@bot.tree.command(name="list", description="👑 [ADMIN] Comprehensive admin list of all VPS")
async def list_admin(interaction: discord.Interaction):
    if not await is_admin(interaction): return await interaction.response.send_message("Denied.", ephemeral=True)
    db = load_db()
    if not db: return await interaction.response.send_message("No active nodes.", ephemeral=True)
    embed = get_beautiful_embed("👑 Global VPS Registry", f"Total Active Nodes: `{len(db)}`")
    for cid, data in db.items():
        status = "🚫 Suspended" if data.get("suspended", False) else "🟢 Active"
        embed.add_field(name=f"Instance `{cid[:8]}`", value=f"**Owner**: `{data['owner_name']}` (<@{data['owner_id']}>)\n**OS**: `{data['os'].upper()}`\n**Tier**: `{data.get('tier', 'free').upper()}`\n**Status**: {status}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="suspendvps", description="🚫 [ADMIN] Suspend a user's VPS")
@app_commands.describe(target="User mention or Instance ID", reason="Reason for suspension")
async def suspendvps(interaction: discord.Interaction, target: str, reason: str = "No reason provided"):
    if not await is_admin(interaction): return await interaction.response.send_message("Denied.", ephemeral=True)
    await interaction.response.defer()
    db = load_db()
    suspended_count = 0
    target_clean = target.replace("<@", "").replace(">", "").replace("!", "")
    for cid, data in db.items():
        if cid.startswith(target) or str(data['owner_id']) == target_clean:
            try:
                await run_cmd_async(["docker", "stop", cid])
            except Exception as e:
                terminal_log(f"Failed to stop container {cid[:8]}: {e}", "ERROR")
            data["suspended"] = True
            suspended_count += 1
            try:
                user = bot.get_user(data['owner_id']) or await bot.fetch_user(data['owner_id'])
                if user:
                    susp_embed = get_beautiful_embed("🚫 VPS Suspended", f"Your VPS instance `{cid[:8]}` has been suspended.")
                    susp_embed.add_field(name="📝 Reason", value=f"```\n{reason}\n```")
                    await user.send(embed=susp_embed)
            except: pass
    save_db(db)
    if suspended_count > 0: await interaction.followup.send(f"✅ Suspended **{suspended_count}** instances matching `{target}`.")
    else: await interaction.followup.send("❌ No matching VPS found.", ephemeral=True)

@bot.tree.command(name="unsuspendvps", description="🟢 [ADMIN] Unsuspend a user's VPS")
async def unsuspendvps(interaction: discord.Interaction, target: str):
    if not await is_admin(interaction): return await interaction.response.send_message("Denied.", ephemeral=True)
    await interaction.response.defer()
    db = load_db()
    unsuspended = []
    target_clean = target.replace("<@", "").replace(">", "").replace("!", "")
    for cid, data in db.items():
        if cid.startswith(target) or str(data['owner_id']) == target_clean:
            try:
                await run_cmd_async(["docker", "start", cid])
            except Exception as e:
                terminal_log(f"Failed to start container {cid[:8]}: {e}", "ERROR")
            data["suspended"] = False
            unsuspended.append(cid[:8])
            try:
                user = bot.get_user(data['owner_id']) or await bot.fetch_user(data['owner_id'])
                if user:
                    un_embed = get_beautiful_embed("🟢 VPS Unsuspended", f"Your VPS instance `{cid[:8]}` has been unsuspended.")
                    await user.send(embed=un_embed)
            except: pass
    save_db(db)
    if unsuspended: await interaction.followup.send(f"🟢 Unsuspended: `{', '.join(unsuspended)}`.")
    else: await interaction.followup.send("No match found.", ephemeral=True)

@bot.tree.command(name="deletevps", description="🗑️ [ADMIN] Force delete any VPS")
async def deletevps(interaction: discord.Interaction, target: str):
    if not await is_admin(interaction): return await interaction.response.send_message("Denied.", ephemeral=True)
    await interaction.response.defer()
    db = load_db()
    deleted = []
    target_clean = target.replace("<@", "").replace(">", "").replace("!", "")
    for cid, data in list(db.items()):
        if cid.startswith(target) or str(data['owner_id']) == target_clean:
            try:
                await run_cmd_async(["docker", "rm", "-f", cid])
            except Exception as e:
                terminal_log(f"Failed to force delete container {cid[:8]}: {e}", "ERROR")
            del db[cid]
            deleted.append(cid[:8])
    save_db(db)
    if deleted: await interaction.followup.send(f"🗑️ Deleted matching VPS: `{', '.join(deleted)}`.")
    else: await interaction.followup.send("No match found.", ephemeral=True)

# ================= USER COMMANDS =================

@bot.tree.command(name="info", description="📊 Your VPS Dashboard")
async def info(interaction: discord.Interaction):
    db = load_db()
    uid = interaction.user.id
    owned = [k for k,v in db.items() if v['owner_id'] == uid]
    shared = [k for k,v in db.items() if uid in v.get('shared_with', [])]
    if not owned and not shared: return await interaction.response.send_message("No VPS found.", ephemeral=True)
    embed = get_beautiful_embed(f"📊 Dashboard - {interaction.user.name}", "Real-time VPS Status")
    for cid in owned + shared:
        d = db[cid]
        if d.get("suspended", False): stats = "🚫 Suspended"
        else:
            try: 
                stats = await run_cmd_async(["docker", "stats", cid, "--no-stream", "--format", "{{.CPUPerc}} | {{.MemUsage}}"])
            except: 
                stats = "Offline"
        ports = "\n".join([f"• `{p}` ➔ `{HOST_IP}:{h}`" for p, h in d.get('ports', {}).items()]) or "None"
        embed.add_field(name=f"Instance `{cid[:8]}` ({d['os'].upper()} - {d.get('tier', 'free').upper()})", value=f"**Status**: {stats}\n**Ports**:\n{ports}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="start", description="🟢 Power ON your VPS")
async def start(interaction: discord.Interaction, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data.get("suspended", False):
        return await interaction.response.send_message("❌ This VPS has been suspended by an administrator and cannot be started manually.", ephemeral=True)
        
    await interaction.response.defer()
    try:
        await run_cmd_async(["docker", "start", cid])
        embed = get_beautiful_embed("🟢 VPS Started", f"Your VPS instance `{cid[:8]}` has been powered on.")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to start VPS:\n```\n{str(e)}\n```", ephemeral=True)

@bot.tree.command(name="stop", description="🔴 Power OFF your VPS")
async def stop(interaction: discord.Interaction, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data.get("suspended", False):
        return await interaction.response.send_message("❌ This VPS has been suspended by an administrator.", ephemeral=True)
        
    await interaction.response.defer()
    try:
        await run_cmd_async(["docker", "stop", cid])
        embed = get_beautiful_embed("🔴 VPS Stopped", f"Your VPS instance `{cid[:8]}` has been powered off.")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to stop VPS:\n```\n{str(e)}\n```", ephemeral=True)

@bot.tree.command(name="forward", description="🔌 Forward a port (Max 10 per VPS)")
async def forward(interaction: discord.Interaction, port: int, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data.get("suspended", False): return await interaction.response.send_message("❌ Suspended.", ephemeral=True)
    db = load_db()
    current_ports = data.get('ports', {})
    if len(current_ports) >= 10:
        return await interaction.response.send_message("❌ Limit 10 ports.", ephemeral=True)
    if str(port) in current_ports:
        return await interaction.response.send_message("❌ Already forwarded.", ephemeral=True)
    host_port = random.randint(20000, 30000)
    db[cid].setdefault('ports', {})[str(port)] = host_port
    save_db(db)
    
    embed = get_beautiful_embed("🔌 Port Forwarded", f"Internal `{port}` live on `{HOST_IP}:{host_port}`")
    embed.add_field(name="Instance", value=f"`{cid[:8]}`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unforward", description="➖ Remove a port forward")
async def unforward(interaction: discord.Interaction, port: int, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    db = load_db()
    if str(port) in db[cid].get('ports', {}):
        del db[cid]['ports'][str(port)]
        save_db(db)
        await interaction.response.send_message(f"✅ Port `{port}` removed from instance `{cid[:8]}`.")
    else: 
        await interaction.response.send_message(f"❌ Port `{port}` not found on instance `{cid[:8]}`.", ephemeral=True)

@bot.tree.command(name="regen-ssh", description="🔄 Regen SSH links (DMed to you)")
async def regen_ssh(interaction: discord.Interaction, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data.get("suspended", False): return await interaction.response.send_message("❌ Suspended.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    
    try:
        await run_cmd_async(["docker", "exec", cid, "pkill", "-f", "tmate"], check=False)
    except: 
        pass
        
    tmate, sshx = await get_access_links(cid, data['os'])
    db = load_db()
    if cid in db:
        db[cid].update({"sshx": sshx, "tmate": tmate, "last_activity": datetime.now().isoformat()})
        save_db(db)
        
    dm_embed = get_beautiful_embed("🔄 New Access Links", f"Regenerated for `{cid[:8]}`")
    dm_embed.add_field(name="🌐 SSHX", value=f"[Connect]({sshx})", inline=False)
    dm_embed.add_field(name="🐚 Tmate", value=f"```bash\n{tmate}```", inline=False)
    try: 
        await interaction.user.send(embed=dm_embed)
        await interaction.followup.send(f"✅ Sent new access links for `{cid[:8]}` to DM!", ephemeral=True)
    except Exception as dm_err: 
        await interaction.followup.send("❌ Enable DMs so the bot can DM you!", ephemeral=True)

@bot.tree.command(name="sharevps", description="🤝 Share access (Max 2)")
async def sharevps(interaction: discord.Interaction, user: discord.User, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data['owner_id'] != interaction.user.id:
        return await interaction.response.send_message("❌ Only the owner can share access to this VPS.", ephemeral=True)
        
    db = load_db()
    shared_list = db[cid].get('shared_with', [])
    if len(shared_list) >= 2:
        return await interaction.response.send_message("❌ Limit of 2 shared users reached.", ephemeral=True)
    if user.id in shared_list:
        return await interaction.response.send_message(f"❌ {user.name} already has access.", ephemeral=True)
        
    db[cid].setdefault('shared_with', []).append(user.id)
    save_db(db)
    await interaction.response.send_message(f"🤝 Shared instance `{cid[:8]}` with {user.name}.")

@bot.tree.command(name="removeshared", description="➖ Remove a shared user")
async def removeshared(interaction: discord.Interaction, user: discord.User, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data['owner_id'] != interaction.user.id:
        return await interaction.response.send_message("❌ Only the owner can remove shared users.", ephemeral=True)
        
    db = load_db()
    if user.id in db[cid].get('shared_with', []):
        db[cid]['shared_with'].remove(user.id)
        save_db(db)
        await interaction.response.send_message(f"➖ Removed {user.name} from instance `{cid[:8]}`.")
    else: 
        await interaction.response.send_message(f"❌ {user.name} does not have access to this VPS.", ephemeral=True)

@bot.tree.command(name="listshared", description="📜 List shared users")
async def listshared(interaction: discord.Interaction, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    shared = data.get('shared_with', [])
    shared_str = "\n".join([f"• <@{uid}>" for uid in shared]) if shared else "None"
    await interaction.response.send_message(embed=get_beautiful_embed(f"🤝 Shared Users - `{cid[:8]}`", shared_str))

@bot.tree.command(name="shell", description="🐚 Run a command (Owner Only)")
async def shell(interaction: discord.Interaction, cmd: str, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data.get("suspended", False): return await interaction.response.send_message("❌ Suspended.", ephemeral=True)
    
    if data['owner_id'] != interaction.user.id:
        return await interaction.response.send_message("❌ Only the owner can run shell commands.", ephemeral=True)
        
    await interaction.response.defer()
    try:
        await ensure_systemctl_support(cid, data.get("os", "ubuntu"))
        shell_binary = get_shell_binary(data.get("os", "ubuntu"))
        out = await run_cmd_async(["docker", "exec", cid, shell_binary, "-c", cmd])
        await interaction.followup.send(f"**Output of `{cmd}` on `{cid[:8]}`:**\n```\n{out[:1900]}\n```")
    except Exception as e:
        await interaction.followup.send(f"**Error running command:**\n```\n{str(e)[:1900]}\n```")

@bot.tree.command(name="rebuild", description="🔄 Reinstall OS (Wipes Data)")
async def rebuild(interaction: discord.Interaction, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data.get("suspended", False): return await interaction.response.send_message("❌ Suspended.", ephemeral=True)
    
    if data['owner_id'] != interaction.user.id:
        return await interaction.response.send_message("❌ Only the owner can rebuild this VPS.", ephemeral=True)
        
    await interaction.response.defer()
    msg = await interaction.followup.send(embed=get_beautiful_embed("🔄 Rebuild Started", f"Wiping and rebuilding instance `{cid[:8]}`..."))
    
    try:
        # Retrieve specs & OS
        os_type = data.get("os", "ubuntu")
        tier = data.get("tier", "free")
        tier_data = TIERS.get(tier, TIERS["free"])
        valid_os = {"ubuntu": "ubuntu:22.04", "debian": "debian:12", "alpine": "alpine:latest"}
        os_image = valid_os.get(os_type, "ubuntu:22.04")
        
        terminal_log(f"Rebuilding VPS {cid[:8]} for user {interaction.user.id}", "INFO")
        
        # Determine host hardware limits to prevent run failures (cap limits to maximum available resources)
        host_mem = psutil.virtual_memory().total
        host_cpus = psutil.cpu_count() or 1
        
        tier_ram_str = tier_data["ram"]
        ram_bytes = 4 * 1024**3
        match = re.match(r"(\d+)([gGmM])", tier_ram_str)
        if match:
            val, unit = match.groups()
            val = int(val)
            if unit.lower() == 'g':
                ram_bytes = val * 1024**3
            elif unit.lower() == 'm':
                ram_bytes = val * 1024**2
                
        safe_ram_bytes = min(ram_bytes, int(host_mem * 0.9))
        safe_ram_str = f"{int(safe_ram_bytes / 1024**2)}m"
        
        tier_cpus = float(tier_data["cpu"])
        safe_cpus = min(tier_cpus, float(host_cpus))
        
        # Stop and remove old container
        try:
            await run_cmd_async(["docker", "rm", "-f", cid])
        except Exception as rm_err:
            terminal_log(f"Warning during removal of {cid[:8]}: {rm_err}", "WARN")
            
        # Create brand-new container with safe limits capped to host specifications
        new_cid = None
        container_entry = get_shell_binary(os_type)
        # Attempt 1: Run with memory and CPU constraints fully enforced
        try:
            new_cid = await run_cmd_async([
                "docker", "run", "-itd", "--privileged", 
                "--memory", safe_ram_str, 
                "--cpus", str(safe_cpus), 
                os_image, container_entry
            ])
            terminal_log(f"Rebuild successful with memory ({safe_ram_str}) and CPU ({safe_cpus} Cores) limitations.", "SUCCESS")
        except Exception as err1:
            terminal_log(f"Rebuild with full memory limits failed: {err1}. Rebuilding with CPU-only limits...", "WARN")
            # Attempt 2: Fallback to CPU-only limits (if cgroups memory is completely disabled)
            try:
                new_cid = await run_cmd_async([
                    "docker", "run", "-itd", "--privileged", 
                    "--cpus", str(safe_cpus), 
                    os_image, container_entry
                ])
                terminal_log(f"Rebuild successful with CPU-only limits ({safe_cpus} Cores).", "SUCCESS")
            except Exception as err2:
                terminal_log(f"Rebuild with CPU limits failed: {err2}. Falling back to unthrottled run...", "ERROR")
                # Attempt 3: Ultimate fallback
                new_cid = await run_cmd_async([
                    "docker", "run", "-itd", "--privileged", 
                    os_image, container_entry
                ])
        
        # Set up container packages
        await provision_container(new_cid, os_type)
        
        # Generate new access links
        tmate_ssh, sshx_url = await get_access_links(new_cid, os_type)
        
        # Update database: remove old CID, insert new CID, keeping metadata (ports, shared, etc)
        db = load_db()
        if cid in db:
            old_meta = db.pop(cid)
            old_meta.update({
                "sshx": sshx_url,
                "tmate": tmate_ssh,
                "last_activity": datetime.now().isoformat()
            })
            db[new_cid] = old_meta
        else:
            db[new_cid] = {
                "owner_id": interaction.user.id,
                "owner_name": str(interaction.user),
                "os": os_type,
                "tier": tier,
                "sshx": sshx_url,
                "tmate": tmate_ssh,
                "ports": {},
                "shared_with": [],
                "last_activity": datetime.now().isoformat(),
                "suspended": False
            }
        save_db(db)
        
        success = get_beautiful_embed("✅ Rebuild Completed", f"Your VPS OS has been successfully reinstalled.")
        success.add_field(name="Instance ID", value=f"New: `{new_cid[:8]}` (Old: `{cid[:8]}`)", inline=False)
        success.add_field(name="🌐 SSH Access", value="▫️ New access details have been sent to your DMs.", inline=True)
        await msg.edit(embed=success)
        
        dm_embed = get_beautiful_embed("🔑 Your Rebuilt VPS Access Details", f"Access for instance `{new_cid[:8]}`")
        dm_embed.add_field(name="🌐 SSHX Web Console", value=f"[Connect Here]({sshx_url})", inline=False)
        dm_embed.add_field(name="🐚 Tmate SSH Command", value=f"```bash\n{tmate_ssh}```", inline=False)
        dm_embed.add_field(name="📊 Specs", value=f"RAM: `{tier_data['ram']}` | CPU: `{tier_data['cpu']}` | Disk: `{tier_data['disk']}`", inline=False)
        try:
            await interaction.user.send(embed=dm_embed)
        except Exception as dm_err:
            terminal_log(f"Could not DM user rebuilt credentials: {dm_err}", "WARN")
            
        terminal_log(f"Rebuild finished successfully for {interaction.user}.", "SUCCESS")
        
    except Exception as e:
        terminal_log(f"Rebuild failed: {str(e)}", "ERROR")
        await msg.edit(embed=get_beautiful_embed("❌ Rebuild Failed", str(e)))

@bot.tree.command(name="remove", description="🗑️ Delete your own VPS")
async def remove(interaction: discord.Interaction, container_id: str = None):
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    if data['owner_id'] != interaction.user.id:
        return await interaction.response.send_message("❌ Only the owner can delete this VPS.", ephemeral=True)
        
    await interaction.response.defer()
    try:
        await run_cmd_async(["docker", "rm", "-f", cid])
    except Exception as e:
        terminal_log(f"Failed to remove container {cid[:8]}: {e}", "ERROR")
        
    db = load_db()
    if cid in db:
        del db[cid]
        save_db(db)
        
    await interaction.followup.send(f"🗑️ VPS `{cid[:8]}` has been successfully deleted.")

@bot.tree.command(name="ping", description="🏓 Latency Check")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency*1000)}ms`")

@bot.tree.command(name="snapshot", description="📸 [ADMIN] Snapshot")
async def snapshot(interaction: discord.Interaction, container_id: str = None):
    if not await is_admin(interaction): 
        return await interaction.response.send_message("❌ Denied.", ephemeral=True)
        
    cid, data = await get_or_guess_vps(interaction, container_id)
    if not cid: return
    
    await interaction.response.send_message(f"📸 Snapshot of `{cid[:8]}` successfully created.")

@bot.tree.command(name="autocleanup", description="🧹 [ADMIN] Toggle global auto-deletion")
async def autocleanup(interaction: discord.Interaction, enabled: bool):
    if interaction.user.id != MAIN_ADMIN_ID: return
    config = load_config()
    config["autocleanup"] = enabled
    save_config(config)
    await interaction.response.send_message(f"🧹 Auto-cleanup: **{'ENABLED' if enabled else 'DISABLED'}**.")

bot.run(TOKEN)
