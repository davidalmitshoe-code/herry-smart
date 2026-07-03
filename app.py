import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIGURATION ENGINE STATE
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8820217071:AAGltetsRpmnq4OG_osBdHH5pcvL0EJNdG4")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 998942116))
DB_FILE = "umc_database.json"
WEBAPP_URL = "https://davidalmitshoe-code.github.io/herry-smart/"

flask_app = Flask(__name__)
CORS(flask_app)

# Global configuration framework mapping setup
telegram_app = Application.builder().token(BOT_TOKEN).build()

def load_db():
    if not os.path.exists(DB_FILE): return {"users": {}}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except Exception: return {"users": {}}

def save_db(data):
    try:
        with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)
    except Exception as e: logger.error(f"Error saving database structure: {e}")

# --- Core Bot Execution Callbacks ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Start command invoked by user context: {update.effective_user.id}")
    
    # Matches requirements to unlock tg.sendData mechanics seamlessly
    keyboard = [[KeyboardButton(text="🎵 Open UMC Wallet", web_app=WebAppInfo(url=WEBAPP_URL))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        f"Welcome {update.effective_user.first_name} to the Union of Maranatha Choir Portal!\n\n"
        "Look at the bottom of your screen! Click the large 🎵 **Open UMC Wallet** button anytime to process your registrations and allocate your contribution fields.",
        reply_markup=reply_markup
    )

async def process_incoming_mini_app_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        raw_json = update.message.web_app_data.data
        payload = json.loads(raw_json)
        tg_username = f"@{update.effective_user.username}" if update.effective_user.username else "No Username"

        # 1. Deliver detailed metrics validation block straight to admin
        admin_alert_message = (
            "🚨 **NEW PAYMENT SUBMISSION RECEIVED** 🚨\n\n"
            "👤 **MEMBER PROFILE:**\n"
            f"▪️ Name: {payload.get('member_name')}\n"
            f"▪️ Phone Number: {payload.get('member_phone')}\n"
            f"▪️ Choir Dept: {payload.get('member_choir')}\n"
            f"▪️ Telegram Handle: {tg_username}\n\n"
            "📋 **TRANSACTION ALLOCATIONS:**\n"
            f"  {payload.get('selected_items')}\n\n"
            f"💵 **Total Amount:** {payload.get('total_amount')} ETB\n"
            f"🏦 **Paid To Account:** {payload.get('target_account', '1000524648907')}\n"
            f"🆔 **CBE Transaction Reference ID:** {payload.get('txn_id')}\n"
        )

        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=admin_alert_message, parse_mode="Markdown")
        
        # 2. Return a clean delivery receipt template back to the submitting member
        user_confirmation = (
            "✅ **UMC Wallet Submission Successful!**\n\n"
            f"Thank you, **{payload.get('member_name')}**!\n"
            f"Your contribution totaling **{payload.get('total_amount')} ETB** (Ref: `{payload.get('txn_id')}`) "
            "has been submitted for administration approval. We will review it shortly. 🙏"
        )
        await update.message.reply_text(text=user_confirmation, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error compiling webapp data packet layout fields: {e}")
        await update.message.reply_text("⚠️ System parsing error registering payment attributes.")

# Wire application logic blocks tightly
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, process_incoming_mini_app_payment))

# --- Flask Server Architecture Routing ---

@flask_app.route('/')
def serve_index(): 
    return "UMC Engine Online & Operational 🚀", 200

@flask_app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.json or {}
    db = load_db()
    name = data.get("name", "").strip()
    if not name or name in db["users"]: 
        return jsonify({"status": "error", "message": "Invalid name or member profile already exists!"})
    
    user_record = {"name": name, "phone": data.get("phone"), "choir": data.get("choir"), "password": data.get("password"), "avatar": data.get("avatar")}
    db["users"][name] = user_record
    save_db(db)
    return jsonify({"status": "success", "user": user_record})

@flask_app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    db = load_db()
    name = data.get("name", "").strip()
    password = data.get("password", "").strip()
    if name not in db["users"] or db["users"][name]["password"] != password:
        return jsonify({"status": "error", "message": "Invalid credentials specified!"})
    return jsonify({"status": "success", "user": db["users"][name]})

@flask_app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    """Manages thread-isolated event processing loop sequences clean"""
    try:
        update_data = request.get_json(force=True)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        update = Update.de_json(update_data, telegram_app.bot)
        
        # Keep background instance running explicitly for active workers
        loop.run_until_complete(telegram_app.initialize())
        loop.run_until_complete(telegram_app.process_update(update))
        loop.close()
        
        return 'OK', 200
    except Exception as err:
        logger.error(f"Webhook tracking fallback failure notice: {err}")
        return 'Internal Error Trace', 500

@flask_app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    public_url = request.args.get('url') or f"https://{request.host}/telegram-webhook"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_app.initialize())
        success = loop.run_until_complete(telegram_app.bot.set_webhook(url=public_url))
        loop.close()
        if success:
            return jsonify({"status": "success", "message": f"Webhook linked cleanly to {public_url}"})
        return jsonify({"status": "failed"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False)
