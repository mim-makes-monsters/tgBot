import json
import logging
import os
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

DATA_DIR = Path("data")
APPS_FILE = DATA_DIR / "apps.json"
REQUESTS_FILE = DATA_DIR / "requests.json"

DATA_DIR.mkdir(exist_ok=True)

WAITING_FOR_APK = 1


def load_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


apps = load_json(APPS_FILE)
requests_data = load_json(REQUESTS_FILE)


def is_admin(user_id):
    return user_id == ADMIN_ID


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("APK Store", callback_data="store")],
        [InlineKeyboardButton("Request APK", callback_data="request_apk")],
    ])


def app_list_keyboard():
    buttons = []
    for name in sorted(apps):
        buttons.append([InlineKeyboardButton(name, callback_data=f"app_{name}")])
    buttons.append([InlineKeyboardButton("Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def app_detail_keyboard(name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Download", callback_data=f"download_{name}")],
        [InlineKeyboardButton("Back to Store", callback_data="store")],
    ])


# ---------- User Commands ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Welcome to APK Store, {user.first_name}!\n\n"
        "Browse and download APKs, or request one that's missing.",
        reply_markup=main_menu(),
    )


# ---------- Callback Queries ----------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "back_main":
        await query.edit_message_text(
            "Choose an option:",
            reply_markup=main_menu(),
        )

    elif data == "store":
        if not apps:
            await query.edit_message_text(
                "No apps available yet.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back", callback_data="back_main")]
                ]),
            )
            return
        await query.edit_message_text(
            "Available apps:",
            reply_markup=app_list_keyboard(),
        )

    elif data.startswith("app_"):
        name = data[4:]
        info = apps[name]
        size = _format_size(info["size"])
        added = _format_dt(info["added_at"])
        text = (
            f"**{name}**\n\n"
            f"Size: {size}\n"
            f"Added: {added}\n"
            f"Downloads: {info.get('downloads', 0)}"
        )
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=app_detail_keyboard(name),
        )

    elif data.startswith("download_"):
        name = data[9:]
        info = apps.get(name)
        if not info:
            await query.edit_message_text(
                "This app is no longer available.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back to Store", callback_data="store")]
                ]),
            )
            return

        info["downloads"] = info.get("downloads", 0) + 1
        save_json(APPS_FILE, apps)

        try:
            await query.message.reply_document(
                document=info["file_id"],
                filename=info["file_name"],
                caption=f"Here's your requested file: {name}",
            )
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            await query.message.reply_text(
                "Sorry, this file is unavailable right now. Try again later."
            )

    elif data == "request_apk":
        await query.edit_message_text(
            "Send me the **name** of the APK you're looking for.\n\n"
            "Example: `Spotify Premium`\n\n"
            "I'll notify the admin about your request.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel", callback_data="cancel_request")]
            ]),
        )
        context.user_data["awaiting_request"] = True

    elif data == "cancel_request":
        context.user_data.pop("awaiting_request", None)
        await query.edit_message_text(
            "Request cancelled. Anything else?",
            reply_markup=main_menu(),
        )


async def handle_request_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_request"):
        return

    context.user_data.pop("awaiting_request", None)
    app_name = update.message.text.strip()
    user = update.effective_user

    if app_name in apps:
        await update.message.reply_text(
            f"**{app_name}** is already in the store!\n"
            "Use /start and check the APK Store to download it.",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    rid = str(len(requests_data) + 1)
    requests_data[rid] = {
        "app_name": app_name,
        "user_id": user.id,
        "username": user.username or user.first_name,
        "requested_at": datetime.utcnow().isoformat(),
        "status": "pending",
    }
    save_json(REQUESTS_FILE, requests_data)

    await update.message.reply_text(
        f"Your request for **{app_name}** has been sent to the admin!\n"
        "You'll be notified when it's added.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

    if ADMIN_ID:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"New APK request!\n\n"
                f"App: **{app_name}**\n"
                f"By: {user.first_name} (@{user.username or 'N/A'})\n"
                f"ID: {user.id}\n\n"
                f"Use /addapp {app_name} to add it."
            ),
            parse_mode="Markdown",
        )


# ---------- Admin Commands ----------

async def admin_addapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /addapp <app name>\nExample: /addapp MyApp v1.0")
        return

    name = " ".join(context.args)
    context.user_data["addapp_name"] = name
    context.user_data["addapp_step"] = "waiting_file"

    await update.message.reply_text(
        f"App name: **{name}**\n\nNow send me the APK file.",
        parse_mode="Markdown",
    )


async def handle_admin_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if context.user_data.get("addapp_step") != "waiting_file":
        return

    name = context.user_data.get("addapp_name")
    if not name:
        return

    if not update.message.document:
        await update.message.reply_text("Please send the file as a document.")
        return

    doc = update.message.document
    file_id = doc.file_id
    file_name = doc.file_name or f"{name}.apk"
    file_size = doc.file_size or 0

    apps[name] = {
        "file_id": file_id,
        "file_name": file_name,
        "size": file_size,
        "added_by": update.effective_user.id,
        "added_at": datetime.utcnow().isoformat(),
        "downloads": 0,
    }
    save_json(APPS_FILE, apps)

    context.user_data.pop("addapp_name", None)
    context.user_data.pop("addapp_step", None)

    await update.message.reply_text(
        f"**{name}** added to the store successfully!\n\n"
        f"File: {file_name}\n"
        f"Size: {_format_size(file_size)}",
        parse_mode="Markdown",
    )

    pending = [
        r for r in requests_data.values()
        if r["app_name"].lower() == name.lower() and r["status"] == "pending"
    ]
    for req in pending:
        req["status"] = "fulfilled"
        try:
            await context.bot.send_message(
                chat_id=req["user_id"],
                text=f"Good news! **{name}** has been added to the store!\n"
                     "Use /start to download it.",
                parse_mode="Markdown",
            )
        except Exception:
            pass
    save_json(REQUESTS_FILE, requests_data)


async def admin_delapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /delapp <app name>")
        return

    name = " ".join(context.args)
    if name not in apps:
        await update.message.reply_text(f"App '{name}' not found.")
        return

    del apps[name]
    save_json(APPS_FILE, apps)
    await update.message.reply_text(f"**{name}** removed from the store.", parse_mode="Markdown")


async def admin_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not apps:
        await update.message.reply_text("No apps in the store.")
        return

    lines = []
    for i, (name, info) in enumerate(sorted(apps.items()), 1):
        dl = info.get("downloads", 0)
        lines.append(f"{i}. **{name}** — {_format_size(info['size'])} — {dl} downloads")

    await update.message.reply_text(
        "Apps in store:\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    pending = [r for r in requests_data.values() if r["status"] == "pending"]
    if not pending:
        await update.message.reply_text("No pending requests.")
        return

    lines = []
    for i, r in enumerate(pending, 1):
        lines.append(f"{i}. **{r['app_name']}** — by {r['username']} (ID: {r['user_id']})")

    await update.message.reply_text(
        "Pending requests:\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


# ---------- Helpers ----------

def _format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _format_dt(iso_str):
    try:
        return datetime.fromisoformat(iso_str).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


# ---------- Main ----------

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return
    if not ADMIN_ID:
        logger.warning("ADMIN_ID not set. Admin commands will be disabled.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addapp", admin_addapp))
    app.add_handler(CommandHandler("delapp", admin_delapp))
    app.add_handler(CommandHandler("apps", admin_apps))
    app.add_handler(CommandHandler("requests", admin_requests))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.User(ADMIN_ID), handle_admin_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_request_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot started...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


import asyncio

if __name__ == "__main__":
    asyncio.run(main())
