import asyncio
import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "0.0.0.0")
PUBLIC_URL = os.environ.get("PUBLIC_URL", f"http://localhost:{PORT}")

DATA_DIR = Path("data")
FILES_DIR = Path("files")
METADATA_FILE = DATA_DIR / "metadata.json"

DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)


def load_metadata():
    if METADATA_FILE.exists():
        with open(METADATA_FILE) as f:
            return json.load(f)
    return {}


def save_metadata(metadata):
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)


metadata = load_metadata()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to File Host Bot!\n\n"
        "Commands:\n"
        "/list - List all uploaded files\n"
        "/info <name> - Get info about a file\n"
        "/delete <name> - Delete a file\n\n"
        "How to upload:\n"
        "Send any file with a caption. The caption becomes the file name.\n"
        "Example: Send a file with caption 'myapp.apk'"
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("Please add a caption (file name) to your upload.")
        return

    name = update.message.caption.strip()
    if not name:
        await update.message.reply_text("Caption cannot be empty.")
        return

    file_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    file_obj = (
        update.message.document
        or update.message.video
        or update.message.photo[-1] if update.message.photo else None
        or update.message.audio
        or update.message.voice
        or update.message.animation
    )

    if not file_obj:
        await update.message.reply_text("Unsupported file type. Please send a document.")
        return

    if isinstance(file_obj, dict):
        pass

    if name in metadata:
        old = metadata[name]
        old_path = FILES_DIR / old["file_id"]
        if old_path.exists():
            old_path.unlink()

    new_file = await file_obj.get_file()
    ext = Path(new_file.file_path).suffix if new_file.file_path else ""
    local_path = FILES_DIR / f"{file_id}{ext}"
    await new_file.download_to_drive(local_path)

    file_size = local_path.stat().st_size

    metadata[name] = {
        "file_id": f"{file_id}{ext}",
        "original_name": file_obj.file_name or f"{name}{ext}",
        "mime_type": file_obj.mime_type or "application/octet-stream",
        "size": file_size,
        "uploaded_by": update.effective_user.id,
        "uploaded_at": timestamp,
    }
    save_metadata(metadata)

    download_url = f"{PUBLIC_URL}/d/{name}"
    await update.message.reply_text(
        f"File uploaded successfully!\n\nName: {name}\nSize: {_format_size(file_size)}\n\nDownload link:\n{download_url}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Download", url=download_url)]
        ]),
    )


async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not metadata:
        await update.message.reply_text("No files uploaded yet.")
        return

    lines = []
    for i, (name, info) in enumerate(sorted(metadata.items()), 1):
        lines.append(f"{i}. {name} ({_format_size(info['size'])})")

    await update.message.reply_text("Uploaded files:\n\n" + "\n".join(lines))


async def info_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /info <filename>")
        return

    name = " ".join(context.args)
    if name not in metadata:
        await update.message.reply_text(f"File '{name}' not found.")
        return

    info = metadata[name]
    download_url = f"{PUBLIC_URL}/d/{name}"
    text = (
        f"Name: {name}\n"
        f"Size: {_format_size(info['size'])}\n"
        f"Type: {info['mime_type']}\n"
        f"Uploaded: {info['uploaded_at']}\n"
        f"Link: {download_url}"
    )
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Download", url=download_url)]
        ]),
    )


async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delete <filename>")
        return

    name = " ".join(context.args)
    if name not in metadata:
        await update.message.reply_text(f"File '{name}' not found.")
        return

    info = metadata[name]
    local_path = FILES_DIR / info["file_id"]
    if local_path.exists():
        local_path.unlink()

    del metadata[name]
    save_metadata(metadata)
    await update.message.reply_text(f"File '{name}' deleted.")


def _format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


async def handle_download(request):
    name = request.match_info.get("name", "")
    if name not in metadata:
        return web.Response(text="File not found", status=404)

    info = metadata[name]
    file_path = FILES_DIR / info["file_id"]

    if not file_path.exists():
        return web.Response(text="File not found on disk", status=404)

    return web.FileResponse(
        file_path,
        headers={
            "Content-Disposition": f'attachment; filename="{info["original_name"]}"',
            "Content-Type": info["mime_type"],
        },
    )


async def handle_index(request):
    count = len(metadata)
    total_size = sum(v["size"] for v in metadata.values())

    links = []
    for name in sorted(metadata):
        links.append(f'<li><a href="/d/{name}">{name}</a> ({_format_size(metadata[name]["size"])})</li>')

    html = f"""<!DOCTYPE html>
<html>
<head><title>File Host Bot</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #333; }}
ul {{ list-style: none; padding: 0; }}
li {{ padding: 8px 12px; margin: 4px 0; background: #f5f5f5; border-radius: 6px; }}
a {{ color: #1a73e8; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.stats {{ color: #666; font-size: 14px; }}
</style>
</head>
<body>
<h1>File Host Bot</h1>
<p class="stats">{count} files, {_format_size(total_size)} total</p>
<ul>
{'<li>No files uploaded yet.</li>' if not links else ''.join(links)}
</ul>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/d/{name}", handle_download)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    logger.info(f"HTTP server running on {HOST}:{PORT}")
    return runner


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return

    web_runner = await run_web_server()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_files))
    app.add_handler(CommandHandler("info", info_file))
    app.add_handler(CommandHandler("delete", delete_file))
    app.add_handler(MessageHandler(filters.ATTACHMENT, handle_file))

    logger.info("Bot started polling...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
