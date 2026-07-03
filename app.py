import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  # Fixed missing import bug
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Credentials & Configurations
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8882818453:AAGHmZ6ryquopL-IKgh3kCdna70SoxDjmWc")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "998942116")
DB_FILE = "umc_database.json"

# Initialize Flask App & Enable CORS
flask_app = Flask(__name__, static_folder=".")
CORS(flask_app)

# Initialize Telegram Application globally (without starting polling)
# We handle the event updates manually via webhook route
telegram_app = Application.builder().token(BOT_TOKEN).build()

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- Telegram Bot Handler Logic ---

async def start(update: Update, context) -> None:
    mini_app_url = "https://maranatha-choir.onrender.com" 
    keyboard = [
        [InlineKeyboardButton("🎵 Open UMC Wallet", web_app=WebAppInfo(url=mini_app_url))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Welcome {update.effective_user.first_name} to the Union of Maranatha Choir Portal!\n\n"
        "Click below to login/register, select multiple donation rails, "
        "and complete secure online transactions instantly via CBE Birr.",
        reply_markup=reply_markup
    )

async def process_incoming_mini_app_payment(update: Update, context) -> None:
    try:
        raw_json = update.message.web_app_data.data
        payload = json.loads(raw_json)
        
        member_name = payload.get("member_name")
        member_phone = payload.get("member_phone")
        member_avatar = payload.get("member_avatar")
        selected_items = payload.get("selected_items")
        total_amount = payload.get("total_amount")
        status = payload.get("payment_status")
        
        user_receipt = (
            "🎉 **CBE Birr Payment Successful!** 🎉\n\n"
            f"Dear {member_name}, your transaction has been completed successfully.\n\n"
            f"🛒 **Selected:** {selected_items}\n"
            f"💰 **Total Contributed:** {total_amount} ETB\n"
            f"🏦 **Transferred To:** Account 10005246*****\n"
            f"📈 **Status:** Verified Online ({status})\n\n"
            "Thank you for your active subscription support to the UMC Ministry! 🙏"
        )
        await update.message.reply_text(user_receipt, parse_mode="Markdown")
        
        admin_notification = (
            "🚨 **New Confirmed UMC Transaction Alert** 🚨\n\n"
            f"👤 **Member Name:** {member_name}\n"
            f"📞 **Phone Number:** {member_phone}\n"
            f"🖼️ **Profile Photo Link:** {member_avatar}\n"
            f"📋 **Selected Items:** {selected_items}\n"
            f"💵 **Deposited Cash:** {total_amount} ETB\n"
            f"💳 **Merchant Vault:** 10005246*****\n"
            f"📣 **Status Message:** SUCCESSFUL PAYMENT COMPLETED"
        )
        await telegram_app.bot.send_message(chat_id=OWNER_CHAT_ID, text=admin_notification)
        
    except Exception as e:
        logger.error(f"Error parsing checkout payload: {str(e)}")
        await update.message.reply_text("Payment tracking confirmation error.")

# Register Bot Handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, process_incoming_mini_app_payment))


# --- Flask Web Routes ---

@flask_app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@flask_app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@flask_app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.json or {}
    db = load_db()
    name = data.get("name", "").strip()
    
    if not name:
        return jsonify({"status": "error", "message": "Name field cannot be empty!"})
        
    if name in db["users"]:
        return jsonify({"status": "error", "message": "Account name already exists!"})
    
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

# --- WEBHOOK ENDPOINT FOR TELEGRAM ---
@flask_app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    """Receives system update requests safely sent from Telegram servers."""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json.loads(json_string), telegram_app.bot)
        
        # Run the update parser via asyncio loop context securely
        asyncio.run(telegram_app.initialize())
        asyncio.run(telegram_app.process_update(update))
        return 'OK', 200
    return 'Forbidden', 403


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False)
