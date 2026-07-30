# File Host Bot

A Telegram bot that lets you upload files with custom names and serves them via HTTP download links.

## Features

- Upload any file with a caption (caption becomes the file name)
- Get direct download links for each file
- List all uploaded files
- Delete files
- Built-in HTTP server serves files to anyone with the link
- Web UI at the root URL listing all files

## Setup

1. Create a bot on Telegram via [@BotFather](https://t.me/BotFather) and get your token.

2. Clone and install:
```bash
git clone <repo-url> && cd file-host-bot
pip install -r requirements.txt
```

3. Run:
```bash
export BOT_TOKEN=your_token_here
export PUBLIC_URL=https://your-domain.com   # the public URL where files will be served
python bot.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/list` | List all uploaded files |
| `/info <name>` | Get file details and download link |
| `/delete <name>` | Delete a file |

## How to Upload

Send any file (document, photo, video) with a **caption**. The caption becomes the file's name.

Example: Send an APK file with caption `myapp-v1.0.apk` -> accessible at `https://your-url/d/myapp-v1.0.apk`

## Free Hosting Options

### Option 1: Render.com (Recommended)

1. Push this repo to GitHub/GitLab.
2. Go to [render.com](https://render.com) -> New + -> Web Service.
3. Connect your repo, set:
   - Name: `file-host-bot`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Plan: **Free**
4. Add Environment Variables:
   - `BOT_TOKEN` = your bot token
   - `PUBLIC_URL` = `https://file-host-bot.onrender.com`
5. Deploy.

**Limitations**: Free tier spins down after 15 min of inactivity. Wakes up on request. Data is ephemeral (lost on restart).

### Option 2: Koyeb

1. Push to GitHub.
2. Go to [koyeb.com](https://koyeb.com) -> Create App.
3. Select your repo, set:
   - Builder: `Dockerfile` or use their Python buildpack
   - Port: `8000`
   - Env vars: `BOT_TOKEN`, `PUBLIC_URL`
4. Deploy.

**Limitations**: Same as Render - spins down and data is ephemeral.

### Option 3: Fly.io

1. Push to GitHub.
2. Install `flyctl` and run `fly launch`.
3. Set up env vars with `fly secrets set BOT_TOKEN=... PUBLIC_URL=...`.
4. Deploy: `fly deploy`.

**Limitations**: Free tier gives 3 VMs with 256MB RAM. VM sleeps after inactivity unless you set `fly.toml` with `auto_stop_machines = false`.

### Option 4: PythonAnywhere (Always-On)

1. Upload code via Git or web UI.
2. Create a `bot.py` task in the "Tasks" tab.
3. Set env vars in your `.bashrc` or the task command.
4. Schedule the task to run "always".

**Limitations**: No persistent HTTP server on free tier (files can only be downloaded via Telegram).

### Option 5: VPS (Oracle Cloud Free Tier)

1. Get a free AMD VM at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) (24GB RAM, 200GB storage, always free).
2. Install Python, upload code, set up with systemd for auto-restart.
3. This gives you persistent storage and 24/7 uptime.

## Persistence Note

Most free PaaS (Render, Koyeb, Fly.io) have **ephemeral storage** - uploaded files are lost on restart/deploy.

**For production with file persistence**, use:
- **Oracle Cloud Free Tier** (always-free VPS with persistent disk)
- Or add S3/Cloudflare R2 storage integration

## Docker Support

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "bot.py"]
```

Then build and run:
```bash
docker build -t file-host-bot .
docker run -e BOT_TOKEN=xxx -e PUBLIC_URL=http://... -p 8000:8000 file-host-bot
```
