import os
import json
import logging
import asyncio
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 1. Setup Logging & Debug Output
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Configuration Settings (Falls back to defaults if environment variables aren't set)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8820217071:AAGltetsRpmnq4OG_osBdHH5pcvL0EJNdG4")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 998942116))
DB_FILE = "umc_database.json"
WEBAPP_URL = "https://davidalmitshoe-code.github.io/herry-smart/"

# 3. Initialize Flask and Enable CORS
flask_app = Flask(__name__)
CORS(flask_app)

# 4. Initialize Telegram Application
telegram_app = Application.builder().token(BOT_TOKEN).build()

# 5. Create a dedicated event loop to process Telegram tasks in the background
bot_loop = asyncio.new_event_loop()

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Start the background thread immediately
threading.Thread(target=start_background_loop, args=(bot_loop,), daemon=True).start()

# 6. Database Helper Functions
def load_db():
    if not os.path.exists(DB_FILE): 
        return {"users": {}}
    try:
        with open(DB_FILE, "r") as f: 
            return json.load(f)
    except Exception: 
        return {"users": {}}

def save_db(data):
    try:
        with open(DB_FILE, "w") as f: 
            json.dump(data, f, indent=4)
    except Exception as e: 
        logger.error(f"Error saving database: {e}")

# --- Core Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Start command triggered by user: {update.effective_user.id}")
    keyboard = [[KeyboardButton(text="🎵 Open UMC Wallet", web_app=WebAppInfo(url=WEBAPP_URL))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        f"Welcome {update.effective_user.first_name} to the Union of Maranatha Choir Portal!\n\n"
        "Click the large 🎵 **Open UMC Wallet** button below to open your account profile and complete payments.",
        reply_markup=reply_markup
    )

async def process_incoming_mini_app_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        raw_json = None
        if update.message and update.message.web_app_data:
            raw_json = update.message.web_app_data.data
        elif update.effective_message and update.effective_message.web_app_data:
            raw_json = update.effective_message.web_app_data.data

        if not raw_json:
            return

        payload = json.loads(raw_json)
        tg_username = f"@{update.effective_user.username}" if update.effective_user.username else "No Username"

        name = payload.get('member_name', '').strip()
        is_new = payload.get('is_new_user', False)

        # Handle registration saving
        if is_new and name:
            db = load_db()
            db["users"][name] = {
                "name": name,
                "phone": payload.get('member_phone'),
                "choir": payload.get('member_choir'),
                "password": payload.get('member_password'),
                "avatar": payload.get('member_avatar')
            }
            save_db(db)
            logger.info(f"Successfully registered user: {name}")

        # Construct admin log alert
        admin_alert_message = (
            "🚨 **NEW SYSTEM ACTION SUBMISSION** 🚨\n\n"
            "👤 **MEMBER PROFILE:**\n"
            f"▪️ Name: {name}\n"
            f"▪️ Phone Number: {payload.get('member_phone')}\n"
            f"▪️ Choir Dept: {payload.get('member_choir')}\n"
            f"▪️ Account Action: {'New Registration + Payment' if is_new else 'Sign In Checkout'}\n"
            f"▪️ Telegram Handle: {tg_username}\n\n"
            "📋 **TRANSACTION ALLOCATIONS:**\n"
            f"  {payload.get('selected_items')}\n\n"
            f"💵 **Total Amount:** {payload.get('total_amount')} ETB\n"
            f"🏦 **Paid To Account:** {payload.get('target_account')}\n"
            f"🆔 **CBE Transaction Reference ID:** {payload.get('txn_id')}\n"
        )

        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=admin_alert_message, parse_mode="Markdown")
        
        # Send receipt back to user
        user_confirmation = (
            "✅ **UMC Wallet Submission Successful!**\n\n"
            f"Thank you, **{name}**!\n"
            f"Your submission totaling **{payload.get('total_amount')} ETB** (Ref: `{payload.get('txn_id')}`) "
            "has been recorded successfully. Our admin team will verify it shortly. 🙏"
        )
        if update.message:
            await update.message.reply_text(text=user_confirmation, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing Mini App dataset payload: {e}")

# Register Telegram command and status listeners
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, process_incoming_mini_app_payment))

# Initialize application settings inside our persistent thread loop structure
asyncio.run_coroutine_threadsafe(telegram_app.initialize(), bot_loop).result()


# --- Flask Server Architecture Routing ---

@flask_app.route('/')
def serve_index(): 
    return "UMC Engine Online & Operational 🚀", 200

@flask_app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, telegram_app.bot)
        
        # Hands off the update processing to the background loop.
        # Flask returns 'OK' to Telegram within milliseconds, completely avoiding the timeout!
        asyncio.run_coroutine_threadsafe(telegram_app.process_update(update), bot_loop)
        
        return 'OK', 200
    except Exception as err:
        logger.error(f"Webhook structural extraction fault: {err}")
        return 'Internal Error', 500

# Handles multiple URL formats to completely avoid 404 Not Found errors
@flask_app.route('/set_webhook', methods=['GET', 'POST'])
@flask_app.route('/setwebhook', methods=['GET', 'POST'])
def set_webhook():
    public_url = f"https://{request.host}/telegram-webhook"
    try:
        future = asyncio.run_coroutine_threadsafe(telegram_app.bot.set_webhook(url=public_url), bot_loop)
        success = future.result()
        if success:
            return jsonify({
                "status": "success", 
                "message": f"Webhook linked successfully to {public_url}"
            }), 200
        return jsonify({"status": "failed", "reason": "Telegram engine rejected webhook configuration parameters."}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False)
