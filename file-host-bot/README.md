# File Host Bot

A Telegram bot + Web UI that lets you upload files with custom names and serves them via HTTP download links.

## Features

- **Telegram Bot** - Upload files via chat with captions as names
- **Web UI** - Upload/download files from the browser
- **Admin Panel** - Password-protected dashboard to manage all files
- **Direct Links** - Every file gets a direct download URL

## Quick Start

```bash
export BOT_TOKEN=your_telegram_bot_token
export PUBLIC_URL=https://your-domain.com
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=your_secure_password
pip install -r requirements.txt
python bot.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | - | Telegram Bot token from @BotFather |
| `PUBLIC_URL` | Yes | `http://localhost:8000` | Public URL for download links |
| `ADMIN_USERNAME` | No | `admin` | Admin panel login username |
| `ADMIN_PASSWORD` | No | `admin123` | Admin panel login password |
| `PORT` | No | `8000` | HTTP server port |
| `HOST` | No | `0.0.0.0` | HTTP server bind address |

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/list` | List all uploaded files |
| `/info <name>` | Get file details and download link |
| `/delete <name>` | Delete a file |

## Web UI

- **`/`** - Public page: upload files, browse and download all files
- **`/d/{name}`** - Direct download link for a file
- **`/admin`** - Admin login
- **`/admin/panel`** - Admin dashboard: manage all files (upload, delete)

## How to Upload via Telegram

Send any file with a **caption**. The caption becomes the file's name.

Example: Send an APK file with caption `myapp-v1.0.apk` -> accessible at `https://your-url/d/myapp-v1.0.apk`

## Free Hosting on justrunmyapp

Since you're using justrunmyapp.com:

1. Zip the project files (excluding `.gitignore`, `data/`, `files/` if empty).
2. Upload the zip on justrunmyapp.
3. Set environment variables in their dashboard:
   - `BOT_TOKEN`
   - `PUBLIC_URL` = your justrunmyapp assigned URL
   - `ADMIN_PASSWORD` = a strong password
4. Set the start command to: `python bot.py`
5. Port: `8000`

### Other Free Hosting Options

| Host | Notes |
|------|-------|
| **Render.com** | Web Service, free tier, spin-down after inactivity |
| **Koyeb** | Free tier, better uptime than Render |
| **Fly.io** | 3 free VMs, 256MB RAM each |
| **Oracle Cloud** | Always-free AMD VM, 24GB RAM, 200GB disk |

## Persistence Note

Most free PaaS have **ephemeral storage** - files are lost on restart. For production use, add S3/Cloudflare R2 or use a VPS (Oracle Cloud free tier).

## Docker

```bash
docker build -t file-host-bot .
docker run -e BOT_TOKEN=xxx -e PUBLIC_URL=http://... -e ADMIN_PASSWORD=xxx -p 8000:8000 file-host-bot
```
