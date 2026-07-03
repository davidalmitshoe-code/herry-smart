import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIGURATION DEFINITIONS
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8820217071:AAGltetsRpmnq4OG_osBdHH5pcvL0EJNdG4")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 998942116))
DB_FILE = "umc_database.json"
WEBAPP_URL = "https://davidalmitshoe-code.github.io/herry-smart01/"

flask_app = Flask(__name__, static_folder=".")
CORS(flask_app, resources={r"/api/*": {"origins": "*"}})

telegram_app = Application.builder().token(BOT_TOKEN).build()
bot_loop = asyncio.new_event_loop()

# --- Database Storage Engines ---
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
        logger.error(f"Error writing to local profile storage: {str(e)}")

# --- Bot Command Flow Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("🎵 Open UMC Wallet", web_app=WebAppInfo(url=WEBAPP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Welcome {update.effective_user.first_name} to the Union of Maranatha Choir Portal!\n\n"
        "Click the button below to register/sign-in directly inside the app, manage accounts, and post financial validations.",
        reply_markup=reply_markup
    )

# 1. Capture payload strings pushed out from user click inside verifyCBEPaymentOnline()
async def process_incoming_mini_app_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        raw_json = update.message.web_app_data.data
        payload = json.loads(raw_json)
        
        tg_username = f"@{update.effective_user.username}" if update.effective_user.username else "No Username Provided"

        # 2. Build explicit visual template layout alert text block for Admin review channels
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
            f"🏦 **Paid To Account:** {payload.get('target_account')}\n"
            f"🆔 **CBE Transaction Reference ID:** {payload.get('txn_id')}\n"
        )

        # 3. Deliver text package cleanly to your ADMIN_ID chat inbox
        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=admin_alert_message, parse_mode="Markdown")
        
        # 4. Notify member in private context chat of transaction routing state
        await update.message.reply_text(
            "🎉 **Submission Confirmed!** Your member metrics and payment transaction details have been forwarded to the admin registry dashboard for review. Thank you!"
        )

    except Exception as e:
        logger.error(f"Error parsing webapp payload strings: {str(e)}")
        await update.message.reply_text("Error parsing incoming app data payload values.")

# Wire structural app framework updates
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, process_incoming_mini_app_payment))

bot_loop.run_until_complete(telegram_app.initialize())

# --- Flask Web Server API Endpoints ---

@flask_app.route('/')
def serve_index(): 
    return "UMC Core Engine Running Stable with API Registry Services Operational. 🚀", 200

@flask_app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.json or {}
    db = load_db()
    name = data.get("name", "").strip()
    
    if not name: 
        return jsonify({"status": "error", "message": "Full Name field cannot be left blank!"})
    if name in db["users"]: 
        return jsonify({"status": "error", "message": "This account name is already registered in our database!"})
    
    user_record = {
        "name": name, 
        "phone": data.get("phone"), 
        "choir": data.get("choir"),
        "password": data.get("password"), 
        "avatar": data.get("avatar")
    }
    
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
        return jsonify({"status": "error", "message": "Invalid Name or Password matching credentials!"})
        
    return jsonify({"status": "success", "user": db["users"][name]})

@flask_app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json.loads(json_string), telegram_app.bot)
        
        try:
            bot_loop.run_until_complete(telegram_app.process_update(update))
            return 'OK', 200
        except Exception as err:
            logger.error(f"Webhook process runtime error tracking: {str(err)}")
            return 'Internal Webhook Error', 500
            
    return 'Forbidden', 403

@flask_app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    public_url = request.args.get('url') or f"https://{request.host}/telegram-webhook"
    try:
        success = bot_loop.run_until_complete(telegram_app.bot.set_webhook(url=public_url))
        if success:
            return jsonify({"status": "success", "message": f"Webhook linked securely to {public_url}"})
        return jsonify({"status": "failed"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False)
