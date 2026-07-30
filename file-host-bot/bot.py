import asyncio
import hashlib
import json
import logging
import os
import secrets
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
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

DATA_DIR = Path("data")
FILES_DIR = Path("files")
METADATA_FILE = DATA_DIR / "metadata.json"

DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)

sessions = {}


def load_metadata():
    if METADATA_FILE.exists():
        with open(METADATA_FILE) as f:
            return json.load(f)
    return {}


def save_metadata(metadata):
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)


metadata = load_metadata()


def _format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _format_dt(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str


def _get_icon(mime):
    if not mime:
        return "file"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if "pdf" in mime:
        return "pdf"
    if "zip" in mime or "rar" in mime or "tar" in mime or "gzip" in mime:
        return "archive"
    if "apk" in mime or "android" in mime:
        return "android"
    return "file"


def _check_admin(request):
    cookie = request.cookies.get("session")
    if cookie and cookie in sessions:
        return sessions[cookie]
    return None


def _public_page(title, content, extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - File Host</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; min-height: 100vh; }}
.topbar {{ background: linear-gradient(135deg, #1a73e8, #0d47a1); color: #fff; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
.topbar h1 {{ font-size: 22px; font-weight: 600; }}
.topbar a {{ color: #fff; text-decoration: none; font-size: 14px; opacity: 0.85; }}
.topbar a:hover {{ opacity: 1; }}
.container {{ max-width: 960px; margin: 0 auto; padding: 24px 16px; }}
.card {{ background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 24px; margin-bottom: 20px; }}
.card h2 {{ font-size: 18px; margin-bottom: 16px; color: #1a73e8; }}
.btn {{ display: inline-block; padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 500; text-decoration: none; cursor: pointer; border: none; transition: all 0.2s; }}
.btn-primary {{ background: #1a73e8; color: #fff; }}
.btn-primary:hover {{ background: #1557b0; }}
.btn-danger {{ background: #dc3545; color: #fff; }}
.btn-danger:hover {{ background: #b02a37; }}
.btn-secondary {{ background: #6c757d; color: #fff; }}
.btn-secondary:hover {{ background: #5a6268; }}
input[type=text], input[type=password], input[type=file] {{ width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; margin-bottom: 12px; }}
input[type=text]:focus, input[type=password]:focus {{ outline: none; border-color: #1a73e8; }}
.file-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }}
.file-card {{ background: #f8f9fa; border-radius: 10px; padding: 16px; transition: all 0.2s; border: 1px solid #eee; }}
.file-card:hover {{ border-color: #1a73e8; box-shadow: 0 2px 8px rgba(26,115,232,0.15); }}
.file-card .name {{ font-size: 15px; font-weight: 600; word-break: break-all; margin-bottom: 6px; }}
.file-card .name a {{ color: #1a73e8; text-decoration: none; }}
.file-card .name a:hover {{ text-decoration: underline; }}
.file-card .meta {{ font-size: 12px; color: #888; }}
.file-card .actions {{ margin-top: 10px; display: flex; gap: 8px; }}
.empty {{ text-align: center; padding: 40px 20px; color: #999; }}
.empty p {{ font-size: 16px; margin-bottom: 8px; }}
.alert {{ padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }}
.alert-success {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
.alert-error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
tr:hover td {{ background: #f8f9fa; }}
@media (max-width: 600px) {{ .file-grid {{ grid-template-columns: 1fr; }} }}
</style>
{extra}
</head>
<body>
{content}
</body>
</html>"""


def _admin_page(title, content, extra=""):
    return _public_page(title, f"""
<div class="topbar">
  <h1>File Host Admin</h1>
  <div>
    <a href="/">Public View</a> &middot;
    <a href="/admin/panel">Panel</a> &middot;
    <a href="/admin/logout">Logout</a>
  </div>
</div>
<div class="container">{content}</div>
""", extra)


# ---------- Telegram Bot Handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to File Host Bot!\n\n"
        "Commands:\n"
        "/list - List all uploaded files\n"
        "/info <name> - Get info about a file\n"
        "/delete <name> - Delete a file\n\n"
        "How to upload:\n"
        "Send any file with a caption. The caption becomes the file name.\n"
        "Example: Send a file with caption 'myapp.apk'\n\n"
        f"Web UI: {PUBLIC_URL}"
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("Please add a caption (file name) to your upload.")
        return

    name = update.message.caption.strip()
    if not name:
        await update.message.reply_text("Caption cannot be empty.")
        return

    file_obj = (
        update.message.document
        or update.message.video
        or (update.message.photo[-1] if update.message.photo else None)
        or update.message.audio
        or update.message.voice
        or update.message.animation
    )

    if not file_obj:
        await update.message.reply_text("Unsupported file type. Please send a document.")
        return

    file_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

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
        "uploaded_by": str(update.effective_user.id),
        "uploaded_at": timestamp,
        "source": "telegram",
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
        f"Uploaded: {_format_dt(info['uploaded_at'])}\n"
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

    _remove_file(name)
    await update.message.reply_text(f"File '{name}' deleted.")


# ---------- HTTP Handlers ----------

def _remove_file(name):
    info = metadata.pop(name, None)
    if info:
        local_path = FILES_DIR / info["file_id"]
        if local_path.exists():
            local_path.unlink()
        save_metadata(metadata)


async def handle_download(request):
    name = request.match_info.get("name", "")
    info = metadata.get(name)
    if not info:
        return web.Response(text="File not found", status=404)

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
    msg = request.query.get("msg", "")
    err = request.query.get("err", "")

    cards = []
    for name in sorted(metadata):
        info = metadata[name]
        cards.append(f"""<div class="file-card">
  <div class="name"><a href="/d/{name}">{name}</a></div>
  <div class="meta">{_format_size(info['size'])} &middot; {info['mime_type']}</div>
</div>""")

    grid = '<div class="file-grid">' + "".join(cards) + "</div>" if cards else '<div class="empty"><p>No files uploaded yet.</p></div>'

    upload_form = f"""<form method="post" action="/upload" enctype="multipart/form-data" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
  <div style="flex:1;min-width:180px">
    <input type="text" name="name" placeholder="File name (e.g. myapp.apk)" required>
    <input type="file" name="file" required style="margin-bottom:0">
  </div>
  <button type="submit" class="btn btn-primary">Upload</button>
</form>"""

    alerts = ""
    if msg:
        alerts += f'<div class="alert alert-success">{msg}</div>'
    if err:
        alerts += f'<div class="alert alert-error">{err}</div>'

    count = len(metadata)
    total_size = sum(v["size"] for v in metadata.values())

    content = f"""
<div class="topbar">
  <h1>File Host</h1>
  <div>
    <span style="font-size:13px;opacity:0.8">{count} files &middot; {_format_size(total_size)}</span>
    &middot;
    <a href="/admin">Admin</a>
  </div>
</div>
<div class="container">
  {alerts}
  <div class="card">
    <h2>Upload File</h2>
    {upload_form}
  </div>
  <div class="card">
    <h2>Files</h2>
    {grid}
  </div>
</div>"""
    return web.Response(text=_public_page("File Host", content), content_type="text/html")


async def handle_public_upload(request):
    data = await request.post()
    name = data.get("name", "").strip()
    field = data.get("file")

    if not name:
        raise web.HTTPFound("/?err=File name is required")
    if not field or not hasattr(field, "filename") or not field.filename:
        raise web.HTTPFound("/?err=No file selected")

    content = await field.read()
    file_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    ext = Path(field.filename).suffix

    if name in metadata:
        old = metadata[name]
        old_path = FILES_DIR / old["file_id"]
        if old_path.exists():
            old_path.unlink()

    local_path = FILES_DIR / f"{file_id}{ext}"
    local_path.write_bytes(content)

    metadata[name] = {
        "file_id": f"{file_id}{ext}",
        "original_name": field.filename,
        "mime_type": field.content_type or "application/octet-stream",
        "size": len(content),
        "uploaded_by": "web",
        "uploaded_at": timestamp,
        "source": "web",
    }
    save_metadata(metadata)

    raise web.HTTPFound(f"/?msg=File '{name}' uploaded successfully")


async def handle_admin_login_page(request):
    user = _check_admin(request)
    if user:
        raise web.HTTPFound("/admin/panel")

    err = request.query.get("err", "")
    alert = f'<div class="alert alert-error">{err}</div>' if err else ""

    content = f"""
<div class="container" style="max-width:400px;margin-top:60px">
  <div class="card">
    <h2 style="text-align:center;margin-bottom:20px">Admin Login</h2>
    {alert}
    <form method="post" action="/admin/login">
      <input type="text" name="username" placeholder="Username" required>
      <input type="password" name="password" placeholder="Password" required>
      <button type="submit" class="btn btn-primary" style="width:100%">Login</button>
    </form>
  </div>
</div>"""
    return web.Response(text=_public_page("Admin Login", content), content_type="text/html")


async def handle_admin_login(request):
    data = await request.post()
    username = data.get("username", "")
    password = data.get("password", "")

    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        raise web.HTTPFound("/admin/login?err=Invalid credentials")

    token = secrets.token_hex(32)
    sessions[token] = {"username": username}

    resp = web.HTTPFound("/admin/panel")
    resp.set_cookie("session", token, max_age=86400, path="/", httponly=True)
    raise resp


async def handle_admin_logout(request):
    cookie = request.cookies.get("session")
    if cookie and cookie in sessions:
        del sessions[cookie]
    resp = web.HTTPFound("/admin/login")
    resp.del_cookie("session", path="/")
    raise resp


async def handle_admin_panel(request):
    user = _check_admin(request)
    if not user:
        raise web.HTTPFound("/admin/login")

    msg = request.query.get("msg", "")
    err = request.query.get("err", "")

    alerts = ""
    if msg:
        alerts += f'<div class="alert alert-success">{msg}</div>'
    if err:
        alerts += f'<div class="alert alert-error">{err}</div>'

    rows = []
    for name in sorted(metadata):
        info = metadata[name]
        rows.append(f"""<tr>
  <td><a href="/d/{name}">{name}</a></td>
  <td>{_format_size(info['size'])}</td>
  <td>{info['mime_type']}</td>
  <td>{info.get('source', '-')}</td>
  <td style="white-space:nowrap">{_format_dt(info['uploaded_at'])}</td>
  <td>
    <a href="/admin/confirm-delete/{name}" class="btn btn-danger" style="padding:4px 12px;font-size:12px">Delete</a>
  </td>
</tr>""")

    table = """<table>
  <thead><tr><th>Name</th><th>Size</th><th>Type</th><th>Source</th><th>Uploaded</th><th>Action</th></tr></thead>
  <tbody>""" + "".join(rows) + "</tbody></table>" if rows else '<div class="empty"><p>No files uploaded yet.</p></div>'

    content = f"""
{alerts}
<div class="card">
  <h2>Upload File</h2>
  <form method="post" action="/admin/upload" enctype="multipart/form-data">
    <input type="text" name="name" placeholder="File name (e.g. myapp.apk)" required>
    <input type="file" name="file" required>
    <button type="submit" class="btn btn-primary">Upload</button>
  </form>
</div>
<div class="card">
  <h2>All Files ({len(metadata)})</h2>
  <div style="overflow-x:auto">{table}</div>
</div>"""
    return web.Response(text=_admin_page("Panel", content), content_type="text/html")


async def handle_admin_upload(request):
    user = _check_admin(request)
    if not user:
        raise web.HTTPFound("/admin/login")

    data = await request.post()
    name = data.get("name", "").strip()
    field = data.get("file")

    if not name:
        raise web.HTTPFound("/admin/panel?err=File name is required")
    if not field or not hasattr(field, "filename") or not field.filename:
        raise web.HTTPFound("/admin/panel?err=No file selected")

    content = await field.read()
    file_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    ext = Path(field.filename).suffix

    if name in metadata:
        old = metadata[name]
        old_path = FILES_DIR / old["file_id"]
        if old_path.exists():
            old_path.unlink()

    local_path = FILES_DIR / f"{file_id}{ext}"
    local_path.write_bytes(content)

    metadata[name] = {
        "file_id": f"{file_id}{ext}",
        "original_name": field.filename,
        "mime_type": field.content_type or "application/octet-stream",
        "size": len(content),
        "uploaded_by": user["username"],
        "uploaded_at": timestamp,
        "source": "admin",
    }
    save_metadata(metadata)

    raise web.HTTPFound(f"/admin/panel?msg=File '{name}' uploaded successfully")


async def handle_admin_confirm_delete(request):
    user = _check_admin(request)
    if not user:
        raise web.HTTPFound("/admin/login")

    name = request.match_info.get("name", "")
    info = metadata.get(name)
    if not info:
        raise web.HTTPFound("/admin/panel?err=File not found")

    content = f"""
<div class="card" style="max-width:500px;margin:60px auto;text-align:center">
  <h2 style="margin-bottom:16px">Delete "{name}"?</h2>
  <p style="margin-bottom:20px;color:#666">This action cannot be undone.</p>
  <a href="/admin/do-delete/{name}" class="btn btn-danger" style="margin-right:8px">Yes, Delete</a>
  <a href="/admin/panel" class="btn btn-secondary">Cancel</a>
</div>"""
    return web.Response(text=_admin_page("Confirm Delete", content), content_type="text/html")


async def handle_admin_do_delete(request):
    user = _check_admin(request)
    if not user:
        raise web.HTTPFound("/admin/login")

    name = request.match_info.get("name", "")
    if name not in metadata:
        raise web.HTTPFound("/admin/panel?err=File not found")

    _remove_file(name)
    raise web.HTTPFound(f"/admin/panel?msg=File '{name}' deleted")


# ---------- Server Setup ----------

async def run_web_server():
    app = web.Application()

    app.router.add_get("/", handle_index)
    app.router.add_post("/upload", handle_public_upload)
    app.router.add_get("/d/{name}", handle_download)

    app.router.add_get("/admin", handle_admin_login_page)
    app.router.add_get("/admin/login", handle_admin_login_page)
    app.router.add_post("/admin/login", handle_admin_login)
    app.router.add_get("/admin/logout", handle_admin_logout)
    app.router.add_get("/admin/panel", handle_admin_panel)
    app.router.add_post("/admin/upload", handle_admin_upload)
    app.router.add_get("/admin/confirm-delete/{name}", handle_admin_confirm_delete)
    app.router.add_get("/admin/do-delete/{name}", handle_admin_do_delete)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    logger.info(f"HTTP server running on {HOST}:{PORT}")
    return runner


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")

    web_runner = await run_web_server()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_files))
    app.add_handler(CommandHandler("info", info_file))
    app.add_handler(CommandHandler("delete", delete_file))
    app.add_handler(MessageHandler(filters.ATTACHMENT, handle_file))

    logger.info("Bot started polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
