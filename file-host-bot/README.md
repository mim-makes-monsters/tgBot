# APK Store Bot

A Telegram bot where admins upload APKs and users browse/download them.

## How It Works

- **Admin** uses `/addapp <name>` to add an app, then uploads the APK file
- **Users** use `/start` to open the APK Store UI with inline buttons
  - **APK Store** - Browse all apps and download
  - **Request APK** - Request an app that's not in the store

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) and get the token.
2. Get your Telegram user ID (message [@userinfobot](https://t.me/userinfobot)).
3. Set environment variables and run:

```bash
export BOT_TOKEN=your_bot_token
export ADMIN_ID=your_telegram_user_id
pip install -r requirements.txt
python bot.py
```

## Admin Commands

| Command | Description |
|---------|-------------|
| `/addapp <name>` | Add a new app (bot will ask for the APK file) |
| `/delapp <name>` | Remove an app from the store |
| `/apps` | List all apps with download counts |
| `/requests` | View pending APK requests from users |

## Deploy on justrunmyapp

| Setting | Value |
|---------|-------|
| Runtime | Python |
| Start Command | `python bot.py` |
| Bot Token | From @BotFather |
| Admin ID | Your Telegram user ID |

## Files

- `bot.py` — Main bot code (no web server needed)
- `requirements.txt` — Dependencies
- `data/apps.json` — Stored apps (auto-created)
- `data/requests.json` — User requests (auto-created)
