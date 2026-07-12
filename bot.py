import random
import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
import time
import re

# Configuration
TOKEN = os.getenv('DISCORD_BOT_TOKEN') or 'YOUR_FALLBACK_TOKEN_HERE'
RAM_LIMIT = '2g'
SERVER_LIMIT = 122
LOGS_CHANNEL_ID = 1514847215271673896  
ADMIN_ROLE_ID = 1477997687532945478      

database_file = 'database.txt'
admin_file = 'admins.txt'

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True  

bot = commands.Bot(command_prefix='/', intents=intents)
EMBED_COLOR = 0x9B59B6  

OS_OPTIONS = {
    "ubuntu": {"image": "ubuntu24-systemd", "name": "Ubuntu 24.04 (Systemd)", "emoji": "🐧", "description": "Custom Ubuntu 24.04 with systemd support"},
    "debian": {"image": "debian-vps", "name": "Debian 12", "emoji": "🦕", "description": "Rock-solid stability with large software repository"},
    "alpine": {"image": "alpine-vps", "name": "Alpine Linux", "emoji": "⛰️", "description": "Lightweight and security-focused"},
    "arch": {"image": "arch-vps", "name": "Arch Linux", "emoji": "🎯", "description": "Rolling release with bleeding-edge software"},
    "kali": {"image": "kali-vps", "name": "Kali Linux", "emoji": "💣", "description": "Penetration testing and security auditing"},
    "fedora": {"image": "fedora-vps", "name": "Fedora", "emoji": "🎩", "description": "Innovative features with Red Hat backing"}
}

LOADING_ANIMATION = ["🔄", "⚡", "✨", "🌀", "🌪️", "🌈"]
SUCCESS_ANIMATION = ["✅", "🎉", "✨", "🌟", "💫", "🔥"]
ERROR_ANIMATION = ["❌", "💥", "⚠️", "🚨", "🔴", "🛑"]
DEPLOY_ANIMATION = ["🚀", "🛰️", "🌌", "🔭", "👨‍🚀", "🪐"]

async def is_admin(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    if any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
        return True
    if os.path.exists(admin_file):
        with open(admin_file, 'r') as f:
            admins = [line.strip() for line in f.readlines()]
            if str(interaction.user.id) in admins:
                return True
    return False

def add_to_database(user, container_name, connection_info, status="Active"):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{connection_info}|{status}\n")

def update_database_status(container_id, new_status):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            parts = line.strip().split('|')
            if len(parts) >= 4 and parts[1] == container_id:
                f.write(f"{parts[0]}|{parts[1]}|{parts[2]}|{new_status}\n")
            else:
                f.write(line)

def update_database_connection(container_id, new_conn_str):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            parts = line.strip().split('|')
            if len(parts) >= 4 and parts[1] == container_id:
                f.write(f"{parts[0]}|{parts[1]}|{new_conn_str}|{parts[3]}\n")
            else:
                f.write(line)

def remove_from_database_by_id(container_id):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            parts = line.strip().split('|')
            if len(parts) >= 2 and parts[1] != container_id:
                f.write(line)

async def capture_ssh_session_line(process):
    try:
        while True:
            output = await process.stdout.readline()
            if not output:
                break
            output = output.decode('utf-8').strip()
            if "ssh session:" in output:
                return output.split("ssh session:")[1].strip()
    except Exception as e:
        print(f"Error capturing SSH: {e}")
    return None

async def capture_sshx_link(process):
    try:
        while True:
            output = await process.stdout.readline()
            if not output:
                break
            output = output.decode('utf-8').strip()
            match = re.search(r'(https://sshx\.io/s/[^\s\x1b]+)', output)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Error capturing sshx: {e}")
    return None

async def animate_message(interaction: discord.Interaction, message, embed, animation_frames, duration=5):
    start_time = time.time()
    frame_index = 0
    while time.time() - start_time < duration:
        embed.set_author(name=f"{animation_frames[frame_index]} {message}")
        try:
            await interaction.edit_original_response(embed=embed)
        except discord.NotFound:
            break  
        except Exception:
            pass
        frame_index = (frame_index + 1) % len(animation_frames)
        await asyncio.sleep(0.5)

@bot.event
async def on_ready():
    if not change_status.is_running():
        change_status.start()
    print(f'✨ Bot is ready. Logged in as {bot.user} ✨')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@tasks.loop(seconds=5)
async def change_status():
    try:
        instance_count = len(open(database_file).readlines()) if os.path.exists(database_file) else 0
        statuses = [  
            f"🌠 Managing {instance_count} Cloud Instances",  
            f"⚡ Powering {instance_count} Servers",  
            f"🔮 Watching over {instance_count} VMs"
        ]  
        await bot.change_presence(activity=discord.Game(name=random.choice(statuses)))  
    except Exception as e:  
        print(f"💥 Failed to update status: {e}")

async def send_to_logs(message):
    try:
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        if channel:
            perms = channel.permissions_for(channel.guild.me)
            if perms.send_messages:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await channel.send(f"`[{timestamp}]` {message}")
    except Exception as e:
        print(f"Failed to send logs: {e}")

# ==================== GENERAL INFO COMMANDS ====================

@bot.tree.command(name="help", description="📋 Show complete usage guidelines and command indexes | Made by DevaByss")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="✨ VPS Cloud Management Dashboard Engine", description="Welcome to the terminal interface panel.", color=EMBED_COLOR)
    
    user_cmds = (
        "`/list` - Review all structural cloud configurations allocated to you.\n"
        "`/start` - Power-on your engine node and rebind tunnel sessions.\n"
        "`/stop` - Safely halt running container frameworks and processes.\n"
        "`/rebuild` - Factory reset your cloud block to clear data logs.\n"
        "`/regen_ssh` - Generate fresh remote access routes straight to DMs.\n"
        "`/status` - View local cloud metrics, performance data limits, and status states."
    )
    embed.add_field(name="🚀 General User Utilities", value=user_cmds, inline=False)

    admin_cmds = (
        "`/deploy` - Deploy a customized VPS architecture image node for a client.\n"
        "`/vps_suspend` - Sever target pipeline network link states immediately.\n"
        "`/vps_unsuspend` - Restore core network bridge pathways.\n"
        "`/vps_delete` - Permanently destroy and wipe a user container completely.\n"
        "`/admin_list` - View system registry metrics.\n"
        "`/admin_add` / `/admin_remove` - Modify script admin permission flags."
    )
    embed.add_field(name="👑 Administrative Infrastructure Actions", value=admin_cmds, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="status", description="📊 Inspect active framework run states and configuration limits | Made by DevaByss")
async def status_command(interaction: discord.Interaction):
    user = str(interaction.user)
    my_instances = 0
    total_instances = 0
    
    if os.path.exists(database_file):
        with open(database_file, 'r') as f:
            for line in f:
                total_instances += 1
                if line.strip().split('|')[0] == user:
                    my_instances += 1

    embed = discord.Embed(title="📊 Cloud Cluster System Status", color=EMBED_COLOR)
    embed.add_field(name="📦 Your Active Allocations", value=f"`{my_instances}` Instances Active", inline=True)
    embed.add_field(name="🌍 Total Cluster Loads", value=f"`{total_instances} / {SERVER_LIMIT}` Slots Occupied", inline=True)
    embed.add_field(name="🛠️ Hardware Profiles Assigned", value=f"```RAM Limit: {RAM_LIMIT} per container\nAuto-Purge Window: 4 Hours Inactive```", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== ADMINISTRATIVE COMMANDS ====================

@bot.tree.command(name="admin_add", description="👑 [ADMIN] Register a user to the script admin database file | Made by DevaByss")
@app_commands.describe(user="The user to grant script permissions")
async def admin_add(interaction: discord.Interaction, user: discord.Member):
    if not await is_admin(interaction):
        await interaction.response.send_message("❌ This command is restricted to administrators.", ephemeral=True)
        return

    admins = []
    if os.path.exists(admin_file):
        with open(admin_file, 'r') as f:
            admins = [line.strip() for line in f.readlines()]

    if str(user.id) in admins:
        await interaction.response.send_message(f"ℹ️ {user.mention} is already an administrator.", ephemeral=True)
        return

    with open(admin_file, 'a') as f:
        f.write(f"{user.id}\n")

    await interaction.response.send_message(f"✅ Successfully promoted {user.mention} to script administrator.", ephemeral=True)
    await send_to_logs(f"👑 {interaction.user.mention} added {user.mention} (`ID: {user.id}`) to the administrator registry.")

@bot.tree.command(name="admin_remove", description="👑 [ADMIN] Revoke a user's rights from the script admin database file | Made by DevaByss")
@app_commands.describe(user="The user to revoke script permissions from")
async def admin_remove(interaction: discord.Interaction, user: discord.Member):
    if not await is_admin(interaction):
        await interaction.response.send_message("❌ This command is restricted to administrators.", ephemeral=True)
        return

    if not os.path.exists(admin_file):
        await interaction.response.send_message("ℹ️ No users found inside the administrator registry database.", ephemeral=True)
        return

    with open(admin_file, 'r') as f:
        admins = [line.strip() for line in f.readlines()]

    if str(user.id) not in admins:
        await interaction.response.send_message(f"❌ {user.mention} is not an administrator.", ephemeral=True)
        return

    admins.remove(str(user.id))
    with open(admin_file, 'w') as f:
        for admin in admins:
            f.write(f"{admin}\n")

    await interaction.response.send_message(f"✅ Successfully demoted {user.mention} from script administrator rights.", ephemeral=True)
    await send_to_logs(f"👑 {interaction.user.mention} removed {user.mention} (`ID: {user.id}`) from the administrator registry.")

@bot.tree.command(name="vps_suspend", description="🔒 [ADMIN] Suspend a user's cloud instance network access | Made by DevaByss")
@app_commands.describe(container_id="The instance ID (first 4+ characters)")
async def vps_suspend(interaction: discord.Interaction, container_id: str):
    if not await is_admin(interaction):
        await interaction.response.send_message("❌ This command is restricted to administrators.", ephemeral=True)
        return

    target_id, target_user = None, None
    if os.path.exists(database_file):
        with open(database_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 2 and parts[1].startswith(container_id):
                    target_user, target_id = parts[0], parts[1]
                    break

    if not target_id:
        await interaction.response.send_message("❌ No target instance found matching that ID prefix.", ephemeral=True)
        return

    embed = discord.Embed(title=f"🔒 Suspending Instance {target_id[:12]}", description="Disconnecting container network bridge infrastructure...", color=0xFFA500)
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()

    proc = await asyncio.create_subprocess_exec("docker", "network", "disconnect", "bridge", target_id, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()

    update_database_status(target_id, "Suspended")
    
    embed = discord.Embed(title="🔒 Instance Suspended", description=f"Instance `{target_id[:12]}` (Owned by: `{target_user}`) has been locked down network-side.", color=0xFF0000)
    await msg.edit(embed=embed)
    await send_to_logs(f"🔒 Admin {interaction.user.mention} suspended instance `{target_id[:12]}` belonging to `{target_user}`.")

@bot.tree.command(name="vps_unsuspend", description="🔓 [ADMIN] Restore access to a suspended cloud instance | Made by DevaByss")
@app_commands.describe(container_id="The instance ID (first 4+ characters)")
async def vps_unsuspend(interaction: discord.Interaction, container_id: str):
    if not await is_admin(interaction):
        await interaction.response.send_message("❌ This command is restricted to administrators.", ephemeral=True)
        return

    target_id, target_user = None, None
    if os.path.exists(database_file):
        with open(database_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 2 and parts[1].startswith(container_id):
                    target_user, target_id = parts[0], parts[1]
                    break

    if not target_id:
        await interaction.response.send_message("❌ No target instance found matching that ID prefix.", ephemeral=True)
        return

    embed = discord.Embed(title=f"🔓 Restoring Instance {target_id[:12]}", description="Reconnecting core bridge access lines...", color=0x00FF00)
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()

    proc = await asyncio.create_subprocess_exec("docker", "network", "connect", "bridge", target_id, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()

    update_database_status(target_id, "Active")
    
    embed = discord.Embed(title="🔓 Instance Restored", description=f"Instance `{target_id[:12]}` (Owned by: `{target_user}`) network operational states are back online.", color=0x00FF00)
    await msg.edit(embed=embed)
    await send_to_logs(f"🔓 Admin {interaction.user.mention} unsuspended instance `{target_id[:12]}` belonging to `{target_user}`.")

@bot.tree.command(name="vps_delete", description="🗑️ [ADMIN] Permanently delete and destroy a user's cloud instance | Made by DevaByss")
@app_commands.describe(container_id="The instance ID (first 4+ characters)")
async def vps_delete(interaction: discord.Interaction, container_id: str):
    if not await is_admin(interaction):
        await interaction.response.send_message("❌ This command is restricted to administrators.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=False)

    target_id, target_user = None, None
    if os.path.exists(database_file):
        with open(database_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 2 and parts[1].startswith(container_id):
                    target_user, target_id = parts[0], parts[1]
                    break

    if not target_id:
        await interaction.followup.send("❌ No target instance found matching that ID prefix.", ephemeral=True)
        return

    embed = discord.Embed(title=f"🗑️ Purging Instance {target_id[:12]}", description="Stopping and cleaning host container systems...", color=0xFF0000)
    msg = await interaction.followup.send(embed=embed)

    proc = await asyncio.create_subprocess_exec("docker", "rm", "-f", target_id, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()

    remove_from_database_by_id(target_id)
    
    embed = discord.Embed(title="🗑️ Container Obliterated", description=f"Instance `{target_id[:12]}` allocated to user `{target_user}` has been deleted from host logs.", color=0x00FF00)
    await msg.edit(embed=embed)
    await send_to_logs(f"🗑️ Admin {interaction.user.mention} destroyed instance `{target_id[:12]}` assigned to user `{target_user}`.")

@bot.tree.command(name="admin_list", description="📋 [ADMIN] List every single active container inside the management registry | Made by DevaByss")
async def admin_list(interaction: discord.Interaction):
    if not await is_admin(interaction):
        await interaction.response.send_message("❌ This command is restricted to administrators.", ephemeral=True)
        return

    if not os.path.exists(database_file) or os.path.getsize(database_file) == 0:
        await interaction.response.send_message("ℹ️ No containers found running anywhere in the system registry database.", ephemeral=True)
        return

    embed = discord.Embed(title="📋 System-wide Cloud Instances", color=0x3498DB)
    
    with open(database_file, 'r') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) >= 4:
                owner, c_id, conn_str, status = parts[0], parts[1][:12], parts[2], parts[3]
                
                tmate_val = "N/A"
                sshx_val = "N/A"
                if "tmate:" in conn_str:
                    try:
                        tmate_val = conn_str.split("tmate:")[1].split(",sshx:")[0]
                        sshx_val = conn_str.split(",sshx:")[1]
                    except:
                        tmate_val = conn_str

                embed.add_field(
                    name=f"🆔 `{c_id}` — {owner}",
                    value=f"**Status:** `{status}`\n**tmate:** `{tmate_val[:40]}...`\n**sshx:** {sshx_val}",
                    inline=False
                )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== GENERAL USER VPS CONTROL COMMANDS ====================

@bot.tree.command(name="deploy", description="🚀 [ADMIN] Create a new cloud instance for a user | Made by DevaByss")
@app_commands.describe(user="The user to deploy for", os_choice="The OS to deploy")
async def deploy(interaction: discord.Interaction, user: discord.Member, os_choice: str):
    try:
        if not await is_admin(interaction):
            embed = discord.Embed(title="🚫 Permission Denied", description="This command is restricted to administrators.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        choice = os_choice.lower()
        if choice not in OS_OPTIONS:
            valid_oses = "\n".join([f"{OS_OPTIONS[os_id]['emoji']} **{os_id}** - {OS_OPTIONS[os_id]['description']}" for os_id in OS_OPTIONS.keys()])
            embed = discord.Embed(title="❌ Invalid OS Selection", description=f"**Available OS options:**\n{valid_oses}", color=EMBED_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)

        os_data = OS_OPTIONS[choice]
        embed = discord.Embed(
            title=f"🚀 Launching {os_data['emoji']} {os_data['name']} Instance",
            description=f"```diff\n+ Preparing magical {os_data['name']} experience for {user.display_name}...\n```",
            color=EMBED_COLOR
        )
        embed.add_field(name="🛠️ System Info", value=f"```RAM: {RAM_LIMIT}\nAuto-Delete: 4h Inactivity```", inline=False)
        embed.set_footer(text="This may take 1-2 minutes...")
        
        msg = await interaction.followup.send(embed=embed)
        await animate_message(interaction, "Initializing Deployment", embed, DEPLOY_ANIMATION, 3)

        try:  
            embed.clear_fields()
            embed.description = "```diff\n+ Pulling container image from repository...\n```"
            await msg.edit(embed=embed)
            
            proc = await asyncio.create_subprocess_exec(
                "docker", "run", "-itd", "--privileged", os_data["image"],
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise Exception(stderr.decode().strip())
                
            container_id = stdout.strip().decode('utf-8')  
            await send_to_logs(f"🔧 {interaction.user.mention} deployed {os_data['emoji']} {os_data['name']} for {user.mention} (ID: `{container_id[:12]}`)")
            
            # WARMUP DELAY: Gives network interfaces time to completely bind before generating sshx endpoints
            await asyncio.sleep(3)

            embed.description = "```diff\n+ Configuring remote sharing environments (tmate & sshx)...\n```"
            await msg.edit(embed=embed)
            await animate_message(interaction, "Configuring Access Links", embed, LOADING_ANIMATION, 2)

            tmate_proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container_id, "tmate", "-F",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )  
            
            sshx_proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container_id, "sh", "-c", "curl -sSf https://sshx.io/get | sh -s run",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            ssh_session_line = await capture_ssh_session_line(tmate_proc)
            sshx_link = await capture_sshx_link(sshx_proc)
            
            if ssh_session_line or sshx_link:  
                tmate_display = ssh_session_line if ssh_session_line else "Failed to generate tmate session"
                sshx_display = sshx_link if sshx_link else "Failed to generate sshx session"

                admin_embed = discord.Embed(title=f"🎉 {os_data['emoji']} {os_data['name']} Instance Ready!", description=f"**Successfully deployed for {user.mention}**", color=0x00FF00)
                admin_embed.add_field(name="🔑 tmate SSH Command:", value=f"```{tmate_display}```", inline=False)
                admin_embed.add_field(name="🔗 sshx Web Link:", value=f"```{sshx_display}```", inline=False)
                admin_embed.add_field(name="📦 Container Info", value=f"```ID: {container_id[:12]}\nOS: {os_data['name']}\nStatus: Running```", inline=False)
                await interaction.followup.send(embed=admin_embed, ephemeral=True)
                
                dm_sent = False
                try:
                    user_embed = discord.Embed(title=f"✨ Your {os_data['name']} Instance is Ready!", description=f"Deployed by: {interaction.user.mention}", color=EMBED_COLOR)
                    user_embed.add_field(name="🔑 tmate SSH Command:", value=f"```{tmate_display}```", inline=False)
                    user_embed.add_field(name="🔗 sshx Web Link:", value=f"```{sshx_display}```", inline=False)
                    await user.send(embed=user_embed)
                    dm_sent = True
                except discord.Forbidden:
                    pass
                
                db_connection_string = f"tmate:{tmate_display},sshx:{sshx_display}"
                add_to_database(str(user), container_id, db_connection_string, "Active")  
                
                desc_text = f"**{os_data['emoji']} {os_data['name']}** instance created for {user.mention}!"
                if not dm_sent:
                    desc_text += "\n⚠️ **Notice:** User DMs are closed! Connection parameters could not be directly delivered safely."
                
                embed = discord.Embed(title=f"✅ Deployment Complete! {random.choice(SUCCESS_ANIMATION)}", description=desc_text, color=0x00FF00)  
                await msg.edit(embed=embed)
            else:  
                embed = discord.Embed(title=f"⚠️ Timeout {random.choice(ERROR_ANIMATION)}", description="```diff\n- Remote configuration timed out...\n- Rolling back deployment\n```", color=0xFF0000)  
                await msg.edit(embed=embed)
                await asyncio.create_subprocess_exec("docker", "kill", container_id, stderr=asyncio.subprocess.DEVNULL)  
                await asyncio.create_subprocess_exec("docker", "rm", container_id, stderr=asyncio.subprocess.DEVNULL)
                
        except Exception as e:  
            embed = discord.Embed(title=f"❌ Deployment Failed {random.choice(ERROR_ANIMATION)}", description=f"```diff\n- Error during deployment:\n{e}\n```", color=0xFF0000)  
            await msg.edit(embed=embed)
            await send_to_logs(f"💥 Deployment failed for {user.mention} by {interaction.user.mention}: {e}")
            
    except Exception as e:
        print(f"Error in deploy command: {e}")

@bot.tree.command(name="list", description="📋 View all cloud instances currently registered to you | Made by DevaByss")
async def user_list(interaction: discord.Interaction):
    user = str(interaction.user)
    if not os.path.exists(database_file) or os.path.getsize(database_file) == 0:
        await interaction.response.send_message("❌ You do not have any registered cloud instances.", ephemeral=True)
        return

    embed = discord.Embed(title="Your Cloud Instances", color=EMBED_COLOR)
    found = False

    with open(database_file, 'r') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) >= 4 and parts[0] == user:
                found = True
                c_id, conn_str, status = parts[1][:12], parts[2], parts[3]
                
                tmate_val = "N/A"
                sshx_val = "N/A"
                if "tmate:" in conn_str:
                    try:
                        tmate_val = conn_str.split("tmate:")[1].split(",sshx:")[0]
                        sshx_val = conn_str.split(",sshx:")[1]
                    except:
                        tmate_val = conn_str

                embed.add_field(
                    name=f"📦 Instance ID: `{c_id}`",
                    value=f"**Status:** `{status}`\n**tmate:** `{tmate_val}`\n**sshx:** {sshx_val}",
                    inline=False
                )

    if not found:
        await interaction.response.send_message("❌ You do not have any active cloud instances.", ephemeral=True)
        return

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="start", description="🟢 Start your cloud instance and securely regenerate connectivity strings | Made by DevaByss")
@app_commands.describe(container_id="Your instance ID (first 4+ characters)")
async def start_server(interaction: discord.Interaction, container_id: str):
    try:
        await interaction.response.defer(ephemeral=False)

        user = str(interaction.user)
        container_info = None
        is_suspended = False
        
        if not os.path.exists(database_file):
            await interaction.followup.send("You don't have any active instances!", ephemeral=True)  
            return

        with open(database_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 3 and user == parts[0] and parts[1].startswith(container_id):
                    container_info = parts[1]
                    if len(parts) >= 4 and parts[3] == "Suspended":
                        is_suspended = True
                    break

        if not container_info:  
            await interaction.followup.send("No instance found matching that ID that belongs to you!", ephemeral=True)  
            return  

        if is_suspended:
            await interaction.followup.send("❌ This cloud instance has been suspended by an administrator and cannot be powered on.", ephemeral=True)
            return

        embed = discord.Embed(title=f"🔌 Starting Instance {container_info[:12]}", description="```diff\n+ Powering up your cloud instance...\n```", color=EMBED_COLOR)
        msg = await interaction.followup.send(embed=embed)
        
        await animate_message(interaction, "Booting System", embed, LOADING_ANIMATION, 2)

        proc = await asyncio.create_subprocess_exec("docker", "start", container_info, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        
        if proc.returncode != 0:
            embed = discord.Embed(title="❌ Container Not Found", description="Container doesn't exist or failed to boot.", color=0xFF0000)  
            await msg.edit(embed=embed)
            return

        embed.description = "```diff\n+ Refreshing remote shell environments (tmate & sshx)...\n```"
        await msg.edit(embed=embed)
        
        tmate_proc = await asyncio.create_subprocess_exec("docker", "exec", container_info, "tmate", "-F", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)  
        sshx_proc = await asyncio.create_subprocess_exec("docker", "exec", container_info, "sh", "-c", "curl -sSf https://sshx.io/get | sh -s run", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        ssh_session_line = await capture_ssh_session_line(tmate_proc)
        sshx_link = await capture_sshx_link(sshx_proc)
        
        if ssh_session_line or sshx_link:
            tmate_display = ssh_session_line if ssh_session_line else "Failed to regenerate tmate session"
            sshx_display = sshx_link if sshx_link else "Failed to regenerate sshx session"

            db_connection_string = f"tmate:{tmate_display},sshx:{sshx_display}"
            update_database_connection(container_info, db_connection_string)
            update_database_status(container_info, "Active")
            
            dm_delivered = True
            try:
                dm_embed = discord.Embed(title=f"🟢 Instance {container_info[:12]} Started!", description="Your connection details have successfully refreshed.", color=EMBED_COLOR)
                dm_embed.add_field(name="🔑 tmate SSH Command:", value=f"```{tmate_display}```", inline=False)
                dm_embed.add_field(name="🔗 sshx Web Link:", value=f"```{sshx_display}```", inline=False)
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                dm_delivered = False
            
            desc_content = f"Instance `{container_info[:12]}` is running successfully!"
            if dm_delivered:
                desc_content += "\n🔑 **Check your Direct Messages!** Access links have been confidentially locked inside your DMs."
            else:
                desc_content += "\n⚠️ **Warning:** Could not DM you links because your privacy configuration restricts DM delivery."

            embed = discord.Embed(title=f"🟢 Instance Started {random.choice(SUCCESS_ANIMATION)}", description=desc_content, color=0x00FF00)
            if not dm_delivered:
                embed.add_field(name="🔑 tmate SSH Command:", value=f"```{tmate_display}```", inline=False)
                embed.add_field(name="🔗 sshx Web Link:", value=f"```{sshx_display}```", inline=False)
        else:
            embed = discord.Embed(title="⚠️ Refresh Failed", description="Instance started but connection wrappers failed to bind.", color=0xFFA500)
        
        await msg.edit(embed=embed)  
        await send_to_logs(f"🟢 {interaction.user.mention} started instance `{container_info[:12]}`")
            
    except Exception as e:
        print(f"Error in start_server: {e}")

@bot.tree.command(name="stop", description="🛑 Stop your cloud instance | Made by DevaByss")
@app_commands.describe(container_id="Your instance ID (first 4+ characters)")
async def stop_server(interaction: discord.Interaction, container_id: str):
    try:
        await interaction.response.defer(ephemeral=False)

        user = str(interaction.user)
        container_info = None
        
        if not os.path.exists(database_file):
            await interaction.followup.send("You don't have any active instances!", ephemeral=True)  
            return

        with open(database_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 3 and user == parts[0] and parts[1].startswith(container_id):
                    container_info = parts[1]
                    break

        if not container_info:  
            await interaction.followup.send("No instance found with that ID that belongs to you!", ephemeral=True)  
            return  

        embed = discord.Embed(title=f"⏳ Stopping Instance {container_info[:12]}", description="```diff\n+ Shutting down your cloud instance...\n```", color=EMBED_COLOR)
        msg = await interaction.followup.send(embed=embed)
        
        await animate_message(interaction, "Stopping Services", embed, LOADING_ANIMATION, 2)

        proc = await asyncio.create_subprocess_exec("docker", "stop", container_info, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        
        update_database_status(container_info, "Stopped")

        embed = discord.Embed(title=f"🛑 Instance Stopped {random.choice(SUCCESS_ANIMATION)}", description=f"Instance `{container_info[:12]}` has been successfully stopped!", color=0x00FF00)  
        await msg.edit(embed=embed)  
        await send_to_logs(f"🛑 {interaction.user.mention} stopped instance `{container_info[:12]}`")
            
    except Exception as e:
        print(f"Error in stop_server: {e}")

@bot.tree.command(name="rebuild", description="🔄 Wipe and rebuild your cloud instance completely | Made by DevaByss")
@app_commands.describe(container_id="Your instance ID (first 4+ characters)", os_choice="Select target OS image type")
async def rebuild_server(interaction: discord.Interaction, container_id: str, os_choice: str):
    try:
        await interaction.response.defer(ephemeral=False)

        user = str(interaction.user)
        container_info = None
        
        if not os.path.exists(database_file):
            await interaction.followup.send("You don't have any active instances!", ephemeral=True)  
            return

        choice = os_choice.lower()
        if choice not in OS_OPTIONS:
            await interaction.followup.send("❌ Invalid OS Selection choice pattern.", ephemeral=True)
            return

        with open(database_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 3 and user == parts[0] and parts[1].startswith(container_id):
                    container_info = parts[1]
                    break

        if not container_info:  
            await interaction.followup.send("No valid instance matching that ID sequence belongs to you.", ephemeral=True)  
            return  

        embed = discord.Embed(title=f"⚙️ Rebuilding Instance {container_info[:12]}", description="```diff\n- Purging existing image profiles and system blocks...\n```", color=EMBED_COLOR)
        msg = await interaction.followup.send(embed=embed)
        
        p1 = await asyncio.create_subprocess_exec("docker", "rm", "-f", container_info, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await p1.communicate()
        remove_from_database_by_id(container_info)

        os_data = OS_OPTIONS[choice]
        embed.description = "```diff\n+ Spawning container environments...\n```"
        await msg.edit(embed=embed)
        
        proc = await asyncio.create_subprocess_exec("docker", "run", "-itd", "--privileged", os_data["image"], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        new_container_id = stdout.strip().decode('utf-8')

        # WARMUP DELAY: Fixed! Gives network interfaces time to completely bind before generating sshx endpoints
        await asyncio.sleep(3)

        tmate_proc = await asyncio.create_subprocess_exec("docker", "exec", new_container_id, "tmate", "-F", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)  
        sshx_proc = await asyncio.create_subprocess_exec("docker", "exec", new_container_id, "sh", "-c", "curl -sSf https://sshx.io/get | sh -s run", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        ssh_session_line = await capture_ssh_session_line(tmate_proc)
        sshx_link = await capture_sshx_link(sshx_proc)

        if ssh_session_line or sshx_link:
            tmate_display = ssh_session_line if ssh_session_line else "Failed"
            sshx_display = sshx_link if sshx_link else "Failed"
            
            db_connection_string = f"tmate:{tmate_display},sshx:{sshx_display}"
            add_to_database(user, new_container_id, db_connection_string, "Active")
            
            dm_delivered = True
            try:
                dm_embed = discord.Embed(title=f"🔄 Rebuild Successful: `{new_container_id[:12]}`", description="Your new terminal connections are live.", color=EMBED_COLOR)
                dm_embed.add_field(name="🔑 tmate:", value=f"```{tmate_display}```", inline=False)
                dm_embed.add_field(name="🔗 sshx:", value=f"```{sshx_display}```", inline=False)
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                dm_delivered = False

            embed = discord.Embed(title=f"✅ Rebuild Complete {random.choice(SUCCESS_ANIMATION)}", description=f"Instance `{new_container_id[:12]}` has been wiped clean.", color=0x00FF00)
            if dm_delivered:
                embed.set_footer(text="📬 Check your Direct Messages for new credential properties.")
            else:
                embed.add_field(name="🔑 tmate:", value=f"```{tmate_display}```", inline=False)
                embed.add_field(name="🔗 sshx:", value=f"```{sshx_display}```", inline=False)
        else:
            embed = discord.Embed(title="❌ Rebuild Fail", description="Failed to mount background link modules safely.", color=0xFF0000)

        await msg.edit(embed=embed)
        await send_to_logs(f"🔄 {interaction.user.mention} rebuilt instance `{container_info[:12]}` into `{new_container_id[:12]}`")

    except Exception as e:
        print(f"Error rebuilding engine elements: {e}")

@bot.tree.command(name="regen_ssh", description="🔑 Regenerate clean tmate/sshx sessions and push them straight to DMs | Made by DevaByss")
@app_commands.describe(container_id="Your instance ID (first 4+ characters)")
async def regen_ssh(interaction: discord.Interaction, container_id: str):
    try:
        await interaction.response.defer(ephemeral=True)

        user = str(interaction.user)
        container_info = None
        
        if not os.path.exists(database_file):
            await interaction.followup.send("❌ No registrations found.", ephemeral=True)
            return

        with open(database_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 3 and user == parts[0] and parts[1].startswith(container_id):
                    container_info = parts[1]
                    break

        if not container_info:
            await interaction.followup.send("❌ No matching container matching that prefix owned by you.", ephemeral=True)
            return

        embed = discord.Embed(title="🔑 Regenerating Connection Endpoints", description="Killing old link processes and launching fresh wrappers...", color=EMBED_COLOR)
        msg = await interaction.followup.send(embed=embed, ephemeral=True)

        await asyncio.create_subprocess_exec("docker", "exec", container_info, "pkill", "-f", "tmate", stderr=asyncio.subprocess.DEVNULL)
        await asyncio.create_subprocess_exec("docker", "exec", container_info, "pkill", "-f", "sshx", stderr=asyncio.subprocess.DEVNULL)

        tmate_proc = await asyncio.create_subprocess_exec("docker", "exec", container_info, "tmate", "-F", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        sshx_proc = await asyncio.create_subprocess_exec("docker", "exec", container_info, "sh", "-c", "curl -sSf https://sshx.io/get | sh -s run", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        ssh_session_line = await capture_ssh_session_line(tmate_proc)
        sshx_link = await capture_sshx_link(sshx_proc)

        if ssh_session_line or sshx_link:
            tmate_display = ssh_session_line if ssh_session_line else "Failed"
            sshx_display = sshx_link if sshx_link else "Failed"

            db_connection_string = f"tmate:{tmate_display},sshx:{sshx_display}"
            update_database_connection(container_info, db_connection_string)

            try:
                dm_embed = discord.Embed(title="🔑 Fresh Access Tunnels Regenerated", description=f"Container Target Reference ID: `{container_info[:12]}`", color=EMBED_COLOR)
                dm_embed.add_field(name="🔑 tmate SSH Command:", value=f"```{tmate_display}```", inline=False)
                dm_embed.add_field(name="🔗 sshx Web Link:", value=f"```{sshx_display}```", inline=False)
                await interaction.user.send(embed=dm_embed)
                
                embed.description = "✅ **Success!** Fresh links generated and sent directly to your DMs."
            except discord.Forbidden:
                embed.description = "⚠️ **Links generated, but your DMs are closed!** Access credentials displayed below:"
                embed.add_field(name="🔑 tmate:", value=f"```{tmate_display}```", inline=False)
                embed.add_field(name="🔗 sshx:", value=f"```{sshx_display}```", inline=False)
        else:
            embed.description = "❌ **Error:** Failed to accurately capture shell engine lines."

        await msg.edit(embed=embed)
    except Exception as e:
        print(f"Error executing token regeneration sequences: {e}")

if __name__ == "__main__":
    bot.run(TOKEN)
