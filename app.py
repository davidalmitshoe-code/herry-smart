import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8882818453:AAGHmZ6ryquopL-IKgh3kCdna70SoxDjmWc")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "998942116")
DB_FILE = "umc_database.json"

flask_app = Flask(__name__, static_folder=".")
CORS(flask_app, resources={r"/api/*": {"origins": "*"}})

telegram_app = Application.builder().token(BOT_TOKEN).build()

# Dictionary to catch user data data until they upload the picture screenshot
pending_receipts = {}

def load_db():
    if not os.path.exists(DB_FILE): return {"users": {}}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except Exception: return {"users": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

async def start(update: Update, context) -> None:
    mini_app_url = "https://maranatha-choir.onrender.com" 
    keyboard = [[InlineKeyboardButton("🎵 Open UMC Wallet", web_app=WebAppInfo(url=mini_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Welcome {update.effective_user.first_name} to the Union of Maranatha Choir Portal!\n\n"
        "Click below to login/register, choose donation rails, and submit your bank transaction proofs directly to admin review.",
        reply_markup=reply_markup
    )

# 1. Capture the structural text metadata submission from WebApp
async def process_incoming_mini_app_payment(update: Update, context) -> None:
    try:
        user_id = update.effective_user.id
        raw_json = update.message.web_app_data.data
        payload = json.loads(raw_json)
        
        # Save payload data temporarily awaiting screenshot photo
        pending_receipts[user_id] = payload
        
        await update.message.reply_text(
            "📝 **Data Details Recorded!**\n\n"
            "Now, please upload / send the **payment screenshot picture** as a reply to this message right here. "
            "We will bundle it up with your info and submit it straight to the admin vault.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error reading app layout data: {str(e)}")
        await update.message.reply_text("Error parsing app data payload.")

# 2. Capture the actual picture upload, construct the full receipt, and notify Admin
async def handle_screenshot_upload(update: Update, context) -> None:
    user_id = update.effective_user.id
    
    if user_id not in pending_receipts:
        await update.message.reply_text("Please open the Mini App wallet and select transaction items before uploading your proof.")
        return

    try:
        payload = pending_receipts.pop(user_id)
        photo_file = await update.message.photo[-1].get_file()
        file_id = photo_file.file_id

        # Notify User
        await update.message.reply_text(
            "🎉 **Thank You!** Your payment data details and verification screenshot have been submitted successfully. "
            "Our admin team will review it shortly. 🙏"
        )

        # Notify Admin with all account details + structural photo attachment
        admin_caption = (
            "🚨 **NEW PAYMENT SUBMISSION RECEIVED** 🚨\n\n"
            f"👤 **Member Name:** {payload.get('member_name')}\n"
            f"📞 **Phone Number:** {payload.get('member_phone')}\n"
            f"⛪ **Choir Dept:** {payload.get('member_choir')}\n\n"
            f"📋 **Selected Items:** {payload.get('selected_items')}\n"
            f"💵 **Total Cost Amount:** {payload.get('total_amount')} ETB\n"
            f"🏦 **Paid To Account:** {payload.get('target_account')}\n"
            f"🆔 **Transaction ID / Note:** {payload.get('txn_id')}\n"
        )
        await telegram_app.bot.send_photo(chat_id=OWNER_CHAT_ID, photo=file_id, caption=admin_caption)

    except Exception as e:
        logger.error(f"Error forwarding proof to admin: {str(e)}")
        await update.message.reply_text("Internal error submission parsing.")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, process_incoming_mini_app_payment))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot_upload))

# --- Flask Web Routes ---

@flask_app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')

@flask_app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

@flask_app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.json or {}
    db = load_db()
    name = data.get("name", "").strip()
    if not name: return jsonify({"status": "error", "message": "Name field empty!"})
    if name in db["users"]: return jsonify({"status": "error", "message": "Account name exists!"})
    
    user_record = {
        "name": name, "phone": data.get("phone"), "choir": data.get("choir"),
        "password": data.get("password"), "avatar": data.get("avatar")
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
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(telegram_app.initialize(), loop)
            future.result()
            future2 = asyncio.run_coroutine_threadsafe(telegram_app.process_update(update), loop)
            future2.result()
        else:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            new_loop.run_until_complete(telegram_app.initialize())
            new_loop.run_until_complete(telegram_app.process_update(update))
            new_loop.close()
        return 'OK', 200
    return 'Forbidden', 403

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False)
