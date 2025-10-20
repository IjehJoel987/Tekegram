"""
Teeshoot Telegram Bot - Compact Version with Admin Price Management
"""

import os
import re
import json
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("teeshoot-bot")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

BOT_TOKEN = "8419540148:AAFecDSbpcxB2-cys1bhuCZWV2qrWxEPpRY"
CLIENT_ID = 6340039582
NIGERIA_TZ = timezone(timedelta(hours=1))
DATA_FILE = "teeshoot_data.json"
# Admin management
ADMIN_IDS = {CLIENT_ID}  # Set with the main owner, others can be added


def now_ng(): return datetime.now(NIGERIA_TZ).strftime("%Y-%m-%d %H:%M:%S")

# Dynamic pricing structure with model-specific prices
ITEM_PRICES: Dict[str, Dict[str, int]] = {
    "battery": {"HP": 12000, "Dell": 13000, "Lenovo": 11500, "Acer": 10500, "Asus": 12500},
    "ram_4gb": {"HP": 6000, "Dell": 6500, "Lenovo": 5800, "Acer": 5500, "Asus": 6200},
    "ram_8gb": {"HP": 10000, "Dell": 10500, "Lenovo": 9800, "Acer": 9500, "Asus": 10200},
    "screen": {"HP": 15000, "Dell": 16000, "Lenovo": 14500, "Acer": 13500, "Asus": 15500},
    "keyboard": {"HP": 7000, "Dell": 7500, "Lenovo": 6800, "Acer": 6200, "Asus": 7200},
    "charger": {"HP": 8000, "Dell": 8500, "Lenovo": 7800, "Acer": 7200, "Asus": 8200},
    "ssd_256": {"HP": 18000, "Dell": 19000, "Lenovo": 17500, "Acer": 16500, "Asus": 18500},
    "ssd_512": {"HP": 25000, "Dell": 26000, "Lenovo": 24500, "Acer": 23000, "Asus": 25500},
    "hdd_1tb": {"HP": 15000, "Dell": 15500, "Lenovo": 14800, "Acer": 14000, "Asus": 15200},
}

TECHNICIANS = [
    {"name": "Engineer Orbem", "contact": "08012345678", "rating": "4.8/5", "fee": "₦2,000", "area": "John E204"},
    {"name": "Tech Joel", "contact": "08087654321", "rating": "4.6/5", "fee": "₦1,500", "area": "Peter E205"},
]

# Payment details
PAYMENT_INFO = {
    "account_number": "9485585858",
    "account_name": "UUFHHFHDJD",
    "bank_name": "First Bank"  # You can change this
}

@dataclass
class UserProfile:
    name: str = ""
    phone: str = ""
    email: str = ""
    department: str = ""  # Add this
    room: str = ""        # Add this
    room_number: str = "" # Add this
    requests: int = 0
    last_order: str = "None"
    preferred_tech: str = ""
    notifications_enabled: bool = True

@dataclass
class Order:
    user_id: int
    username: Optional[str]
    name: str
    item: str
    details: Dict[str, Any] = field(default_factory=dict)
    status: str = "collecting_info"
    timestamp: str = field(default_factory=now_ng)

@dataclass
class Issue:
    user_id: int
    username: Optional[str]
    name: str
    type: str
    details: Dict[str, Any] = field(default_factory=dict)
    status: str = "reported"
    timestamp: str = field(default_factory=now_ng)

@dataclass
class CallbackReq:
    user_id: int
    username: Optional[str]
    name: str
    phone_and_issue: str
    status: str = "pending"
    timestamp: str = field(default_factory=now_ng)

@dataclass
class Inquiry:
    user_id: int
    username: Optional[str]
    name: str
    inquiry_type: str
    inquiry_text: str
    status: str = "pending_response"
    timestamp: str = field(default_factory=now_ng)

# Global storage with proper typing
user_data_store: Dict[int, UserProfile] = {}
orders: Dict[str, Order] = {}
issues: Dict[str, Issue] = {}
callbacks: Dict[str, CallbackReq] = {}
inquiries: Dict[str, Inquiry] = {}
user_states: Dict[int, Dict[str, Any]] = {}
inquiry_responses: Dict[str, str] = {}  # Store predefined responses
tips_guides: Dict[str, str] = {}  # Store custom tips and guides

# Track last data load time to ensure fresh data
_last_data_load: float = 0
_DATA_RELOAD_INTERVAL = 5  # seconds

def save_all():
    backup_file = DATA_FILE + ".bak" 
    try:
        data = {
            "user_data": {str(k): asdict(v) for k, v in user_data_store.items()},
            "orders": {k: asdict(v) for k, v in orders.items()},
            "issues": {k: asdict(v) for k, v in issues.items()},
            "callbacks": {k: asdict(v) for k, v in callbacks.items()},
            "inquiries": {k: asdict(v) for k, v in inquiries.items()},
            "user_states": user_states,
            "item_prices": ITEM_PRICES,
            "admin_ids": list(ADMIN_IDS),
            "technicians": TECHNICIANS,
            "payment_info": PAYMENT_INFO,
            "inquiry_responses": inquiry_responses,
            "tips_guides": tips_guides,
        }
        
        # Write to temporary file first
        temp_file = DATA_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk
            
        # Create backup of existing file if it exists
        if os.path.exists(DATA_FILE):
            backup_file = DATA_FILE + ".bak"
            try:
                os.replace(DATA_FILE, backup_file)
            except Exception as e:
                logger.warning("Failed to create backup: %s", e)
                
        # Atomically rename temp file to actual file
        os.replace(temp_file, DATA_FILE)
        
        # Remove old backup if everything succeeded
        if os.path.exists(backup_file):
            try:
                os.remove(backup_file)
            except Exception as e:
                logger.warning("Failed to remove backup: %s", e)
                
    except Exception as e:
        logger.exception("Failed saving data: %s", e)
        # Try to restore from backup if available
        backup_file = DATA_FILE + ".bak"
        if os.path.exists(backup_file):
            try:
                os.replace(backup_file, DATA_FILE)
                logger.info("Restored data from backup file")
            except Exception as restore_e:
                logger.exception("Failed to restore from backup: %s", restore_e)


def load_all():
    """Load all data from file with proper error handling and backup management"""
    global ITEM_PRICES, _last_data_load, orders, issues, callbacks, inquiries, user_data_store
    
    # Skip reload if data is fresh enough
    now = time.time()
    if now - _last_data_load < _DATA_RELOAD_INTERVAL:
        return
        
    # Initialize empty data structures if they don't exist
    if not hasattr(load_all, 'initialized'):
        orders = {}
        issues = {}
        callbacks = {}
        inquiries = {}
        user_data_store = {}
        load_all.initialized = True

    if not os.path.exists(DATA_FILE):
        # Check for backup file
        backup_file = DATA_FILE + ".bak"
        if os.path.exists(backup_file):
            try:
                os.replace(backup_file, DATA_FILE)
                logger.info("Restored data from backup file")
            except Exception as e:
                logger.exception("Failed to restore backup: %s", e)
                return
        else:
            # If no backup exists, this might be first run
            logger.info("No data file exists yet")
            save_all()  # Create initial empty data file
            return
            
    try:
        # Try to read the data file
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            # If main file is corrupted, try backup
            backup_file = DATA_FILE + ".bak"
            if os.path.exists(backup_file):
                with open(backup_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info("Loaded data from backup file due to corrupted main file")
            else:
                raise
        
        # Clear existing data before loading
        user_data_store.clear()
        orders.clear()
        issues.clear()
        callbacks.clear()
        inquiries.clear()
        user_states.clear()
        
        # Load each section with proper error handling
        for k, v in data.get("user_data", {}).items():
            try:
                user_data_store[int(k)] = UserProfile(**v)
            except Exception as e:
                logger.error(f"Failed to load user data for {k}: {e}")
                
        for k, v in data.get("orders", {}).items():
            try:
                orders[k] = Order(**v)
            except Exception as e:
                logger.error(f"Failed to load order {k}: {e}")
                
        for k, v in data.get("issues", {}).items():
            try:
                issues[k] = Issue(**v)
            except Exception as e:
                logger.error(f"Failed to load issue {k}: {e}")
                
        for k, v in data.get("callbacks", {}).items():
            try:
                callbacks[k] = CallbackReq(**v)
            except Exception as e:
                logger.error(f"Failed to load callback {k}: {e}")
                
        for k, v in data.get("inquiries", {}).items():
            try:
                inquiries[k] = Inquiry(**v)
            except Exception as e:
                logger.error(f"Failed to load inquiry {k}: {e}")
        
        try:
            user_states.update({int(k): v for k, v in data.get("user_states", {}).items()})
        except Exception as e:
            logger.error(f"Failed to load user states: {e}")
            
        if "item_prices" in data:
            try:
                ITEM_PRICES.update(data["item_prices"])
            except Exception as e:
                logger.error(f"Failed to load item prices: {e}")
                
        if "admin_ids" in data:
            try:
                ADMIN_IDS.update(data["admin_ids"])
                ADMIN_IDS.add(CLIENT_ID)
            except Exception as e:
                logger.error(f"Failed to load admin IDs: {e}")
                
        if "technicians" in data:
            try:
                global TECHNICIANS
                TECHNICIANS = data["technicians"]
            except Exception as e:
                logger.error(f"Failed to load technicians: {e}")
                
        if "payment_info" in data:
            try:
                global PAYMENT_INFO
                PAYMENT_INFO = data["payment_info"]
            except Exception as e:
                logger.error(f"Failed to load payment info: {e}")
                
        if "inquiry_responses" in data:
            try:
                global inquiry_responses
                inquiry_responses = data["inquiry_responses"]
            except Exception as e:
                logger.error(f"Failed to load inquiry responses: {e}")
                
        if "tips_guides" in data:
            try:
                global tips_guides
                tips_guides = data["tips_guides"]
            except Exception as e:
                logger.error(f"Failed to load tips and guides: {e}")
                
        logger.info("Data loaded successfully")
        
        # After successful load, create a backup
        backup_file = DATA_FILE + ".bak"
        try:
            import shutil
            shutil.copy2(DATA_FILE, backup_file)
        except Exception as e:
            logger.warning("Failed to create backup after load: %s", e)
            
    except Exception as e:
        logger.exception("Critical error loading data: %s", e)
        # Try to restore from backup
        backup_file = DATA_FILE + ".bak"
        if os.path.exists(backup_file):
            try:
                os.replace(backup_file, DATA_FILE)
                logger.info("Restored data from backup file after critical error")
                # Recursively try to load again
                load_all()
            except Exception as restore_e:
                logger.exception("Failed to restore from backup: %s", restore_e)

# UI and helpers
MAIN_BTNS = [
    [KeyboardButton("💳 Purchase"), KeyboardButton("❓ Inquiry")],
    [KeyboardButton("🛠 Report an Issue"), KeyboardButton("🚚 Track Request")],
    [KeyboardButton("💰 Price List"), KeyboardButton("📘 Tips & Guides")],
    [KeyboardButton("🧑‍🔧 Find a Technician"), KeyboardButton("👤 My Profile")],
]
MAIN_KB = ReplyKeyboardMarkup(MAIN_BTNS, resize_keyboard=True)

# Category navigation helpers
CATEGORY_ORDER = ["orders", "issues", "callbacks", "inquiries"]

def get_next_category(current: str) -> str:
    """Get the next category in the navigation order"""
    try:
        idx = CATEGORY_ORDER.index(current)
        return CATEGORY_ORDER[(idx + 1) % len(CATEGORY_ORDER)]
    except ValueError:
        return "orders"

def get_prev_category(current: str) -> str:
    """Get the previous category in the navigation order"""
    try:
        idx = CATEGORY_ORDER.index(current)
        return CATEGORY_ORDER[(idx - 1) % len(CATEGORY_ORDER)]
    except ValueError:
        return "orders"

def fmt_money(n: int) -> str: return f"₦{n:,}"
def is_valid_phone(s: str) -> bool: return bool(re.match(r"^(?:\+?234|0)\d{10}$", re.sub(r"[^\d+]", "", s)))
def safe_username(u: Optional[str]) -> str: return f"@{u}" if u else "No username"
def _rand4() -> int: import random; return random.randint(1000, 9999)
def is_owner(update: Update) -> bool: 
    return update.effective_user and update.effective_user.id in ADMIN_IDS


def bump_user_req(uid: int, last_id: str):
    profile = user_data_store.setdefault(uid, UserProfile())
    profile.requests += 1
    profile.last_order = last_id
    save_all()

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")
            
_last_action_ts: Dict[int, float] = {}
def too_fast(user_id: int) -> bool:
    from time import time
    t = time()
    if t - _last_action_ts.get(user_id, 0) < 1.5:
        return True
    _last_action_ts[user_id] = t
    return False

def back_menu(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=callback_data)]])

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store.setdefault(uid, UserProfile())
    welcome = (
        "👋 Welcome to PC DOCTOR — Powered by OBLAK Tech!\n\n"
        "🔧 Where Logic Meets Precision.\n\n"
        "We're here to help you troubleshoot your computer,\n"
        "• 🔍 Identify possible issues,\n"
        "• 👨‍🔧 Connect you with our trained technicians, and\n"
        "• 💰We provide detailed repair cost estimates\n"
        ". Sell PC related accessories\n"
        "> We deliver our services at your convenience, right to your doorstep — all in one place.\n\n"
        "Just tell us what's wrong, and we'll take it from there!\n\n"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KB)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = "🆘 *Help*\n\n• /start — show main menu\n• /help — this screen\n• /cancel — cancel current flow\n• /id — show your Telegram ID\n• /admin — (admin only) stats\n• /broadcast <msg> — (admin)\n• /dump — (admin) dump JSON snapshot\n• /prices — (admin) manage prices\n• /manage — (admin) manage requests\n• /addadmin <id> — (admin) add new admin\n• /removeadmin <id> — (owner only) remove admin\n• /listadmins — (admin) list all admins"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_states.pop(uid, None)
    await update.message.reply_text("❌ Bet. Process canceled. Pick something else from the menu.", reply_markup=MAIN_KB)

async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🪪 Your ID: `{update.effective_user.id}`", parse_mode=ParseMode.MARKDOWN)

# Message routing
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    
    # Check for admin status update command
    if is_owner(update) and update.message.reply_to_message:
        # Look for "status X" command
        if text.lower().startswith('status '):
            new_status = text[7:].strip()
            # Find request ID in original message
            orig_text = update.message.reply_to_message.text
            import re
            # Look for any request ID format (ORD, ISS, CB, INQ followed by numbers)
            match = re.search(r'((?:ORD|ISS|CB|INQ)\d+)', orig_text)
            if match:
                req_id = match.group(1)
                # Determine store based on prefix
                prefix = req_id[:3]
                store = None
                if prefix == 'ORD': store = orders
                elif prefix == 'ISS': store = issues
                elif prefix == 'CB': store = callbacks
                elif prefix == 'INQ': store = inquiries
                
                if store and req_id in store:
                    store[req_id].status = new_status
                    save_all()
                    await update.message.reply_text(f"✅ Status updated for {req_id} to: {new_status}")
                    # Show updated admin view
                    await admin_manage(update, context)
                    return
    
    # For admin commands, always reload data first
    if text == "/manage":
        load_all()  # Force data reload

    if too_fast(uid):
        await update.message.reply_text("⏳ Chill a sec… processing.", reply_markup=MAIN_KB)
        return

    if uid in user_states and user_states[uid]:
        await handle_user_input(update, context)
        return

    # Menu routing
    menu_map = {
        "💳 Purchase": handle_purchase,
        "❓ Inquiry": handle_inquiry,
        "🛠 Report an Issue": handle_report_issue,
        "🚚 Track Request": handle_track_request,
        "💰 Price List": handle_price_list,
        "📘 Tips & Guides": handle_tips_guides,
        "🧑‍🔧 Find a Technician": handle_find_technician,
        "👤 My Profile": handle_my_profile,
        "📞 Request Callback": handle_request_callback,
        "⚙️ Settings": handle_settings,
    }
    
    if text in menu_map:
        await menu_map[text](update, context)
        return

    if re.match(r"^(ORD|ISS|CB|INQ)\d{4}$", text.upper()):
        await handle_track_input(update, context, {})
        return

    await update.message.reply_text("🤷 I didn't get that. Tap a button below to keep it moving.", reply_markup=MAIN_KB)

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    state = user_states.get(uid, {})

    # Allow abrupt menu change -> cancel current
    menu_options = ["💳 Purchase", "❓ Inquiry", "🛠 Report an Issue", "🚚 Track Request", 
                   "💰 Price List", "📘 Tips & Guides", "🧑‍🔧 Find a Technician", 
                   "👤 My Profile", "📞 Request Callback", "⚙️ Settings"]
    
    if text in menu_options:
        user_states.pop(uid, None)
        await update.message.reply_text("❌ Process canceled. Pick from the menu again:", reply_markup=MAIN_KB)
        return

    action = state.get("action")
    if action == "purchase":
        await handle_purchase_input(update, context, state)
    elif action == "callback":
        await handle_callback_input(update, context, state)
    elif action == "issue_report":
        await handle_issue_input(update, context, state)
    elif action == "track_request":
        await handle_track_input(update, context, state)
    elif action == "inquiry_other":
        await handle_inquiry_other_input(update, context)
    elif action == "update_profile":
        await handle_update_profile_input(update, context, state)
    elif action == "payment_info":
        await handle_payment_info_input(update, context, state)
    elif action == "admin_price":
        await handle_admin_price_input(update, context, state)
    elif action == "manage_technicians":
        await handle_technician_input(update, context, state)
    elif action == "manage_inquiry":
        await handle_manage_inquiry_input(update, context, state)
    elif action == "manage_tips":
        await handle_manage_tips_input(update, context, state)
    else:
        await update.message.reply_text("🤷🏽‍♂️ Not sure what we were doing. Starting fresh.", reply_markup=MAIN_KB)
        user_states.pop(uid, None)

# Purchase flow with dynamic pricing
async def handle_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = []
    
    # Create buttons dynamically from ITEM_PRICES
    for item_key in ITEM_PRICES.keys():
        # Convert item key to display name
        display_name = item_key.replace('_', ' ').title()
        
        # Add appropriate emoji based on item type
        if 'battery' in item_key:
            emoji = "🔋"
        elif 'ram' in item_key:
            emoji = "🧠"
        elif 'screen' in item_key:
            emoji = "💡"
        elif 'keyboard' in item_key:
            emoji = "⌨️"
        elif 'charger' in item_key:
            emoji = "⚡"
        elif 'ssd' in item_key or 'hdd' in item_key:
            emoji = "💽"
        else:
            emoji = "🔧"  # Default for new items
        
        kb.append([InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f"purchase_{item_key}")])
    
    kb.append([InlineKeyboardButton("❓ Other Item", callback_data="purchase_other")])  # ADD THIS LINE
    kb.append([InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu")])
    
    await update.message.reply_text("🛒 *Purchase Components*\n\nPick a category:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))


async def handle_purchase_item(query, item: str):
    uid = query.from_user.id
    user_states[uid] = {"action": "purchase", "item": item, "step": "model"}
    
    # Show prices for different models
    if item in ITEM_PRICES:
        price_text = f"💰 *{item.replace('_', ' ').title()} Prices*\n\n"
        for model, price in ITEM_PRICES[item].items():
            price_text += f"• {model}: {fmt_money(price)}\n"
        price_text += "\n📱 Which model do you want?"
    else:
        price_text = f"💰 *{item.replace('_', ' ').title()}*\n\n📱 Which model do you want?"

    await query.edit_message_text(price_text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())

async def handle_purchase_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    
    if "order_id" not in state:
        oid = f"ORD{_rand4()}"
        orders[oid] = Order(uid, update.effective_user.username, update.effective_user.first_name, state["item"])
        state["order_id"] = oid
        save_all()

    o = orders[state["order_id"]]
    step = state.get("step", "model")

    if step == "custom_item":
        o.details["custom_item"] = text
        o.details["model"] = "Custom request"
        o.details["unit_price"] = 0  # Price will be determined by admin
        state["step"] = "quantity"
        await update.message.reply_text("📦 How many units you need? (number)")
        save_all()
        return

    if step == "model":
        o.details["model"] = text
        # Try to find price for the model
        item_key = state["item"]
        if item_key in ITEM_PRICES:
            price = None
            for model_key in ITEM_PRICES[item_key]:
                if model_key.lower() in text.lower():
                    price = ITEM_PRICES[item_key][model_key]
                    o.details["unit_price"] = price
                    break
            if not price:
                # Use first available price as default
                o.details["unit_price"] = next(iter(ITEM_PRICES[item_key].values()))
        
        state["step"] = "quantity"
        await update.message.reply_text("📦 How many units you need? (number)")
        save_all()
        return

    if step == "quantity":
        try:
            q = int(text)
            if q <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Enter a valid number like 1, 2, 3…")
            return
        o.details["quantity"] = q
        state["step"] = "address"
        await update.message.reply_text("🏠 Drop your delivery address:")
        save_all()
        return

    if step == "address":
        o.details["address"] = text
        o.status = "pending_confirmation"
        unit = o.details.get("unit_price", 0)
        qty = int(o.details.get("quantity", 1))
        total = unit * qty
        o.details["total"] = total
        save_all()
        user_profile = user_data_store.get(uid, UserProfile())
        profile_info = f"📛 Name: {user_profile.name or 'N/A'}\n📱 Phone: {user_profile.phone or 'N/A'}\n📧 Email: {user_profile.email or 'N/A'}\n🏢 Department: {user_profile.department or 'N/A'}\n🚪 Room: {user_profile.room or 'N/A'}\n🔢 Room Number: {user_profile.room_number or 'N/A'}"
        
        await notify_admin(context, f"🛒 NEW ORDER\n\nOrder ID: {state['order_id']}\nItem: {o.details.get('custom_item', state['item']).replace('_', ' ').title()}\nModel: {o.details['model']}\nQuantity: {qty}\nTotal: {fmt_money(total)}\nAddress: {o.details['address']}\n⏰ Time of Order: {o.timestamp}\n\n👤 CUSTOMER PROFILE:\n{profile_info}")

        confirm = (
            f"✅ **Order Summary**\n\n"
            f"🛒 Item: {o.details.get('custom_item', state['item']).replace('_', ' ').title()}\n"
            f"📱 Model: {o.details['model']}\n"
            f"📦 Quantity: {qty}\n"
            f"💰 Total: {fmt_money(total)}\n"
            f"🏠 Address: {o.details['address']}\n\n"
            f"📋 Order ID: `{state['order_id']}`\n\n"
            f"💳 **PAYMENT DETAILS:**\n"
            f"🏦 Bank: {PAYMENT_INFO['bank_name']}\n"
            f"🔢 Account Number: `{PAYMENT_INFO['account_number']}`\n"
            f"👤 Account Name: {PAYMENT_INFO['account_name']}\n\n"
            f"⚠️ **IMPORTANT:** After payment, send your receipt screenshot to this bot. "
            f"We'll verify and process your order immediately!\n\n"
        )
        await update.message.reply_text(confirm, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KB)

        bump_user_req(uid, state["order_id"])
        user_states.pop(uid, None)

# Other handlers (simplified)
async def handle_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_states[uid] = {"action": "callback"}
    await update.message.reply_text("📞 *Request Callback*\n\nSend your *phone number* + short issue.\nExample: `08012345678 - laptop won't turn on`", parse_mode=ParseMode.MARKDOWN)

async def handle_callback_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()

    if not re.search(r"(\+?234|0)\d{10}", text.replace(" ", "")):
        await update.message.reply_text("📵 Drop a valid phone number (e.g. 080XXXXXXXX).")
        return

    cbid = f"CB{_rand4()}"
    callbacks[cbid] = CallbackReq(uid, update.effective_user.username, update.effective_user.first_name, text)
    save_all()

    await update.message.reply_text(f"📞 *Callback Request Submitted*\n\n📋 Request ID: `{cbid}`\n⏰ We'll call you back ASAP during business hours.\n\nThanks for rocking with OBLAK! 🙏🾾\n", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KB)
    user_profile = user_data_store.get(uid, UserProfile())
    user_info = f"{callbacks[cbid].name}"
    if callbacks[cbid].username:
        user_info += f" | @{callbacks[cbid].username}"
    elif user_profile.phone:
        user_info += f" | {user_profile.phone}"
    else:
        user_info += " | No contact info"

    await notify_admin(context, f"🚨 CALLBACK REQUEST\n\nID: {cbid}\nUser: {user_info}\nDetails: {text}")
    user_states.pop(uid, None)

# Simplified handlers for other features
async def handle_report_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("⚙️ Software Issue", callback_data="report_software")], [InlineKeyboardButton("🔩 Hardware Issue", callback_data="report_hardware")], [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu")]]
    await update.message.reply_text("🛠 *Report an Issue*\n\nWhat type of issue you dealing with?", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

async def handle_issue_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    if "issue_id" not in state:
        iid = f"ISS{_rand4()}"
        issues[iid] = Issue(uid, update.effective_user.username, update.effective_user.first_name, state.get("issue_type", "hardware"))
        state["issue_id"] = iid
        save_all()

    issue = issues[state["issue_id"]]
    step = state.get("step", "")

    if update.message and update.message.text:
        text = update.message.text.strip()
        if step == "model":
            issue.details["model"] = text
            state["step"] = "description"
            await update.message.reply_text("📝 Describe the issue in detail. You can also send up to 3 photos.")
            save_all()
            return
        elif step == "description":
            issue.details["description"] = text
            issue.status = "under_review"
            save_all()
            await update.message.reply_text(f"🛠 *Issue Report Submitted*\n\n📋 Issue ID: `{state['issue_id']}`\n🔧 Type: {issue.type.title()}\n📱 Model: {issue.details.get('model','N/A')}\n📝 Description: {issue.details.get('description','N/A')}\n\n⏳ Status: Under Review\n", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KB)            # Send admin notification
            user_profile = user_data_store.get(uid, UserProfile())
            user_info = f"{issue.name}"
            if issue.username:
                user_info += f" | @{issue.username}"
            elif user_profile.phone:
                user_info += f" | {user_profile.phone}"
            else:
                user_info += " | No contact info"

            # Send admin notification with profile info
            user_profile = user_data_store.get(uid, UserProfile())
            profile_info = f"📛 Name: {user_profile.name or 'N/A'}\n📱 Phone: {user_profile.phone or 'N/A'}\n📧 Email: {user_profile.email or 'N/A'}\n🏢 Department: {user_profile.department or 'N/A'}\n🚪 Room: {user_profile.room or 'N/A'}\n🔢 Room Number: {user_profile.room_number or 'N/A'}"

            await notify_admin(context, f"🔧 NEW ISSUE REPORT\n\nIssue ID: {state['issue_id']}\nType: {issue.type.title()}\nModel: {issue.details.get('model', 'N/A')}\nDescription: {issue.details.get('description', 'N/A')}\n\n👤 CUSTOMER PROFILE:\n{profile_info}")

            # Send photos to admin if any were uploaded
            photos = issue.details.get("photos", [])
            if photos:
                for admin_id in ADMIN_IDS:
                    try:
                        for photo_id in photos:
                            await context.bot.send_photo(chat_id=admin_id, photo=photo_id, caption=f"📸 Issue {state['issue_id']} - Photo")
                    except Exception as e:
                        logger.warning(f"Failed to send photos to admin {admin_id}: {e}")
            
            user_states.pop(uid, None)
            return

    if update.message and update.message.photo and step == "description":
        photo = update.message.photo[-1]
        phlist = issue.details.get("photos", [])
        if len(phlist) < 3:
            phlist.append(photo.file_id)
            issue.details["photos"] = phlist
            save_all()
            await update.message.reply_text(f"🖼 Photo saved ({len(phlist)}/3). Send more or type more details.")

async def handle_track_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_states[uid] = {"action": "track_request"}
    await update.message.reply_text("🚚 *Track Your Request*\n\nEnter your Request ID.\n\n📝 Examples:\n• Orders: ORD1234\n• Issues: ISS5678\n• Callbacks: CB9012\n• Inquiries: INQ3456\n\n📧 For support issues, contact us at: oblaktech25@gmail.com", parse_mode=ParseMode.MARKDOWN)

async def handle_track_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    req = (update.message.text or "").strip().upper()

    stores = {"ORD": orders, "ISS": issues, "CB": callbacks, "INQ": inquiries}
    for prefix, store in stores.items():
        if req.startswith(prefix) and req in store:
            item = store[req]
            if prefix == "ORD":
                msg = f"🚚 *Order Status*\n\n📋 ID: `{req}`\n🛒 Item: {item.item.replace('_',' ').title()}\n📱 Model: {item.details.get('model','N/A')}\n⏳ Status: {item.status.replace('_',' ').title()}"
            elif prefix == "ISS":
                msg = f"🛠 *Issue Status*\n\n📋 ID: `{req}`\n📧 Type: {item.type.title()}\n⏳ Status: {item.status.replace('_',' ').title()}"
            elif prefix == "CB":
                msg = f"📞 *Callback Status*\n\n📋 ID: `{req}`\n⏳ Status: {item.status.replace('_',' ').title()}"
            elif prefix == "INQ":
                msg = f"❓ *Inquiry Status*\n\n📋 ID: `{req}`\n📝 Type: {item.inquiry_type.title()}\n⏳ Status: {item.status.replace('_',' ').title()}"
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KB)
            user_states.pop(uid, None)
            return

    await update.message.reply_text(f"❌ *Request ID `{req}` not found.*\n\nCheck and try again.", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KB)
    user_states.pop(uid, None)

# Simplified other handlers
async def handle_inquiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = []
    
    # Add saved responses as buttons
    for title in inquiry_responses.keys():
        display_title = title.replace('_', ' ').title()
        kb.append([InlineKeyboardButton(f"💡 {display_title}", callback_data=f"inquiry_saved_{title}")])
    
    # Add default options
    kb.extend([
        [InlineKeyboardButton("💻 Laptop not booting", callback_data="inquiry_boot")],
        [InlineKeyboardButton("🖥 Display problem", callback_data="inquiry_display")],
        [InlineKeyboardButton("🔋 Charging issues", callback_data="inquiry_charging")],
        [InlineKeyboardButton("⚡ Performance/Speed", callback_data="inquiry_performance")],
        [InlineKeyboardButton("❓ Other", callback_data="inquiry_other")],
        [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await update.message.reply_text("❓ *Technical Inquiry*\n\nWhat's going on with your laptop?", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))


async def handle_inquiry_other_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    inquiry_id = f"INQ{_rand4()}"
    inquiries[inquiry_id] = Inquiry(uid, update.effective_user.username, update.effective_user.first_name or "User", "other", text)
    save_all()
    await update.message.reply_text(f"✅ *Inquiry Submitted*\n\n📋 Inquiry ID: `{inquiry_id}`\n📝 Your Question:\n{text}\n\n🧑‍🔧 We'll hit you back with a detailed answer.\n", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KB)
    user_profile = user_data_store.get(uid, UserProfile())
    user_info = f"{inquiries[inquiry_id].name}"
    if inquiries[inquiry_id].username:
        user_info += f" | @{inquiries[inquiry_id].username}"
    elif user_profile.phone:
        user_info += f" | {user_profile.phone}"
    else:
        user_info += " | No contact info"

    # Send admin notification with profile info
    user_profile = user_data_store.get(uid, UserProfile())
    profile_info = f"📛 Name: {user_profile.name or 'N/A'}\n📱 Phone: {user_profile.phone or 'N/A'}\n📧 Email: {user_profile.email or 'N/A'}\n🏢 Department: {user_profile.department or 'N/A'}\n🚪 Room: {user_profile.room or 'N/A'}\n🔢 Room Number: {user_profile.room_number or 'N/A'}"

    await notify_admin(context, f"📝 NEW INQUIRY\n\nInquiry ID: {inquiry_id}\nQuestion: {text}\n\n👤 CUSTOMER PROFILE:\n{profile_info}")

    bump_user_req(uid, inquiry_id)
    user_states.pop(uid, None)

# Profile management (simplified)
async def handle_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = user_data_store.setdefault(uid, UserProfile())
    if not p.name and not p.phone and not p.email:
        txt = "👤 *My Profile*\n\n🆕 Looks like this is your first visit!\n\nSetting up your profile helps us provide better support. Takes 1 minute! 🚀"
        kb = [[InlineKeyboardButton("✅ Set Up Profile", callback_data="setup_profile")], [InlineKeyboardButton("⭐ Maybe Later", callback_data="main_menu")]]
    else:
        txt = f"👤 *My Profile*\n\n📛 Name: {p.name or '❌ Not set'}\n📞 Phone: {p.phone or '❌ Not set'}\n📧 Email: {p.email or '❌ Not set'}\n🏢 Department: {p.department or '❌ Not set'}\n🚪 Room: {p.room or '❌ Not set'}\n🔢 Room Number: {p.room_number or '❌ Not set'}\n📊 Total Requests: {p.requests}\n📦 Last Request: {p.last_order}"
        kb = [[InlineKeyboardButton("✏️ Update Profile", callback_data="setup_profile")], [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu")]]
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

async def handle_update_profile_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    profile = user_data_store.setdefault(uid, UserProfile())
    step = state.get("step")

    if step == "name":
        if text.lower() != "skip": profile.name = text
        state["step"] = "phone"
        save_all()
        await update.message.reply_text("📱 Enter your phone number (or type `skip`):")
    elif step == "phone":
        if text.lower() != "skip":
            if not is_valid_phone(text):
                await update.message.reply_text("❌ Invalid phone format. Try again or type `skip`.")
                return
            profile.phone = text
        state["step"] = "email"
        save_all()
        await update.message.reply_text("📧 Enter your email (or type `skip`):")
    elif step == "email":
        if text.lower() != "skip":
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text):
                await update.message.reply_text("❌ Invalid email format. Try again or type `skip`.")
                return
            profile.email = text
        state["step"] = "department"
        save_all()
        await update.message.reply_text("🏢 Enter your department (or type `skip`):")
    elif step == "department":
        if text.lower() != "skip": profile.department = text
        state["step"] = "room"
        save_all()
        await update.message.reply_text("🚪 Enter your room/block (or type `skip`):")
    elif step == "room":
        if text.lower() != "skip": profile.room = text
        state["step"] = "room_number"
        save_all()
        await update.message.reply_text("🔢 Enter your room number (or type `skip`):")
    elif step == "room_number":
        if text.lower() != "skip": profile.room_number = text
        user_states.pop(uid, None)
        save_all()
        await update.message.reply_text(f"✅ *Profile Updated!*\n\n📛 Name: {profile.name or 'Not set'}\n📱 Phone: {profile.phone or 'Not set'}\n📧 Email: {profile.email or 'Not set'}\n🏢 Department: {profile.department or 'Not set'}\n🚪 Room: {profile.room or 'Not set'}\n🔢 Room Number: {profile.room_number or 'Not set'}", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KB)

async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = user_data_store.setdefault(uid, UserProfile())
    txt = f"⚙️ *Settings*\n\n📢 Notifications: {'✅ On' if p.notifications_enabled else '❌ Off'}\n🧑‍🔧 Preferred Tech: {p.preferred_tech or '❌ Not set'}"
    kb = [[InlineKeyboardButton("📢 Toggle Notifications", callback_data="toggle_notifications")], [InlineKeyboardButton("🧑‍🔧 Set Preferred Tech", callback_data="set_preferred_tech")], [InlineKeyboardButton("📝 Update Contact Info", callback_data="setup_profile")], [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu")]]
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

# Simplified remaining handlers

async def handle_price_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ITEM_PRICES:
        await update.message.reply_text("💰 *No prices available*\n\nContact admin to set prices.", parse_mode=ParseMode.MARKDOWN)
        return
    
    txt = "💰 *Current Prices*\n\n"
    
    # Group similar items together
    item_groups = {}
    for item, models in ITEM_PRICES.items():
        # Group items by base type
        if 'ram' in item:
            group = 'Memory (RAM)'
        elif 'ssd' in item or 'hdd' in item:
            group = 'Storage'
        elif 'battery' in item:
            group = 'Power'
        elif 'screen' in item:
            group = 'Display'
        elif 'keyboard' in item:
            group = 'Input'
        elif 'charger' in item:
            group = 'Power'
        else:
            group = 'Other Components'
        
        if group not in item_groups:
            item_groups[group] = {}
        item_groups[group][item] = models
    
    for group_name, items in item_groups.items():
        txt += f"🔧 *{group_name}:*\n"
        for item, models in items.items():
            txt += f"📦 *{item.replace('_', ' ').title()}:*\n"
            for model, price in models.items():
                txt += f"• {model}: {fmt_money(price)}\n"
        txt += "\n"
    
    txt += "⚠️ *Note:* PRICES MAY VARY DUE TO COMPLEXITY, THIS IS JUST AN OVERVIEW.\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def handle_tips_guides(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = []
    
    # Add custom tips first
    for title in tips_guides.keys():
        display_title = title.replace('_', ' ').title()
        kb.append([InlineKeyboardButton(f"💡 {display_title}", callback_data=f"tip_saved_{title}")])
    
    # Add default tips
    kb.extend([
        [InlineKeyboardButton("🔋 Maintain battery", callback_data="tip_battery")],
        [InlineKeyboardButton("⚠️ Hardware failure signs", callback_data="tip_hardware")],
        [InlineKeyboardButton("🧽 Clean your laptop", callback_data="tip_cleaning")],
        [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await update.message.reply_text("📘 *Tips & Maintenance Guides*\n\nPick a topic:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))


async def handle_find_technician(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🧑‍🔧 *Available Technicians*\n\n"
    for i, t in enumerate(TECHNICIANS, 1):
        text += f"*{i}. {t['name']}*\n📞 {t['contact']} | ⭐ {t['rating']} | 💰 {t['fee']}\n📍 {t['area']}\n\n"
    text += "💡 Book directly or use *Request Callback*."
    kb = [[InlineKeyboardButton("📞 Request Callback", callback_data="callback")], [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu")]]
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

# Admin price management
async def manage_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    
    kb = []
    for item in ITEM_PRICES.keys():
        kb.append([InlineKeyboardButton(f"💰 {item.replace('_', ' ').title()}", callback_data=f"price_item_{item}")])
    kb.append([InlineKeyboardButton("➕ Add New Item", callback_data="add_new_item")])
    kb.append([InlineKeyboardButton("🗑️ Remove Item", callback_data="remove_item")])  # ADD THIS LINE
    kb.append([InlineKeyboardButton("🏠 Back", callback_data="main_menu")])
    
    await update.message.reply_text("💰 *Price Management*\n\nSelect item to update prices:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

async def handle_admin_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    
    if state.get("step") == "new_item":
        # Adding new item
        state["new_item"] = text.lower().replace(" ", "_")
        state["step"] = "new_models"
        ITEM_PRICES[state["new_item"]] = {}
        await update.message.reply_text("💡 Now enter model prices in format:\nModel:Price\n\nExample:\nHP:12000\nDell:13000\n\nType 'done' when finished.")
        return

    elif state.get("step") == "new_models":
        if text.lower() == "done":
            save_all()
            await update.message.reply_text(f"✅ New item '{state['new_item']}' added successfully!", reply_markup=MAIN_KB)
            user_states.pop(uid, None)
            return
        
        try:
            model, price = text.split(":")
            ITEM_PRICES[state["new_item"]][model.strip()] = int(price.strip())
            save_all()
            await update.message.reply_text(f"✅ Added {model.strip()}: ₦{int(price.strip()):,}\n\nAdd more or type 'done':")
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Use Model:Price (e.g. HP:12000)")
        return
    
    elif state.get("step") == "update_prices":
        # Updating existing item prices
        item = state["item"]
        if text.lower() == "done":
            save_all()
            await update.message.reply_text(f"✅ Prices updated for {item}!", reply_markup=MAIN_KB)
            user_states.pop(uid, None)
            return
        
        # Check if it's a delete command (model: with no price)
        if ":" in text and text.endswith(":"):
            model_to_delete = text.replace(":", "").strip()
            if model_to_delete in ITEM_PRICES[item]:
                del ITEM_PRICES[item][model_to_delete]
                save_all()
                await update.message.reply_text(f"🗑️ Deleted {model_to_delete} from {item}\n\nUpdate more, delete more (Model:), or type 'done':")
            else:
                await update.message.reply_text(f"❌ {model_to_delete} not found in {item}")
            return
        
        try:
            model, price = text.split(":")
            if price.strip():  # Only update if price is provided
                ITEM_PRICES[item][model.strip()] = int(price.strip())
                save_all()
                await update.message.reply_text(f"✅ Updated {model.strip()}: ₦{int(price.strip()):,}\n\nUpdate more, delete (Model:), or type 'done':")
            else:
                await update.message.reply_text("❌ Empty price. To delete, use format: Model:")
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Use Model:Price (e.g. HP:12000) or Model: to delete")

# Photo handler
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = user_states.get(uid)
    
    if st and st.get("action") == "issue_report":
        await handle_issue_input(update, context, st)
        return
    
    # Check if user has any pending orders
    user_orders = [oid for oid, order in orders.items() if order.user_id == uid and order.status in ["pending_confirmation", "confirmed"]]
    
    if user_orders:
        # This is likely a payment receipt
        latest_order = max(user_orders)  # Get the most recent order
        
        # Update order status
        orders[latest_order].status = "payment_submitted"
        save_all()
        
        await update.message.reply_text(
            f"📸 *Payment Receipt Received!*\n\n"
            f"📋 Order: `{latest_order}`\n"
            f"✅ Your receipt has been forwarded to our team for verification.\n"
            f"⏰ We'll update your order status once payment is confirmed.\n\n"
            f"Track your order anytime with: `{latest_order}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_KB
        )
        
        # Notify all admins with the receipt
        for admin_id in ADMIN_IDS:
            try:
                order = orders[latest_order]
                user_profile = user_data_store.get(order.user_id, UserProfile())
                user_info = f"{order.name}"
                if order.username:
                    user_info += f" | @{order.username}"
                elif user_profile.phone:
                    user_info += f" | {user_profile.phone}"
                else:
                    user_info += " | No contact info"

                caption = (
                    f"💳 PAYMENT RECEIPT\n\n"
                    f"📋 Order: {latest_order}\n"
                    f"👤 Customer: {user_info}\n"
                    f"🛒 Item: {order.item.replace('_', ' ').title()}\n"
                    f"💰 Amount: {fmt_money(order.details.get('total', 0))}\n"
                    f"📱 Model: {order.details.get('model', 'N/A')}\n\n"
                    f"📄 Status: Payment Submitted\n"
                    f"⏰ Use /manage to update order status"
                )
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=update.message.photo[-1].file_id,
                    caption=caption
                )
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin_id}: {e}")
        
        return
    
    await update.message.reply_text("🖼 Photo received. If it's for an issue report, use *Report an Issue* first.", reply_markup=MAIN_KB)

# Callback query handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "main_menu":
        user_states.pop(uid, None)  # Clear any ongoing state
        await query.edit_message_text("🏠 *Main Menu*\n\nPick an option:", parse_mode=ParseMode.MARKDOWN)
        await query.message.reply_text("Choose an option:", reply_markup=MAIN_KB)
        return

    if data.startswith("purchase_"):
        item = data.replace("purchase_", "")
        if item == "other":
            user_states[uid] = {"action": "purchase", "item": "other", "step": "custom_item"}
            await query.edit_message_text("❓ *Custom Item Request*\n\n📝 What item are you looking for?\nExample: `Webcam`, `Mouse`, `Speaker`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())
        elif item in ITEM_PRICES:
            await handle_purchase_item(query, item)
        else:
            await query.answer("Item not found!", show_alert=True)
        return
    
    if data == "purchase_other":
        user_states[uid] = {"action": "purchase", "item": "other", "step": "custom_item"}
        await query.edit_message_text("❓ *Custom Item Request*\n\n📝 What item are you looking for?\nExample: `Webcam`, `Mouse`, `Speaker`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())
        return

    if data.startswith("inquiry_"):
        typ = data.replace("inquiry_", "")
        
        # Check for saved responses first
        if typ.startswith("saved_"):
            saved_title = typ.replace("saved_", "")
            if saved_title in inquiry_responses:
                response_content = inquiry_responses[saved_title]
                await query.edit_message_text(f"💡 *{saved_title.replace('_', ' ').title()}*\n\n{response_content}", parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())
                return
        
        if typ == "other":
            user_states[uid] = {"action": "inquiry_other"}
            await query.edit_message_text("❓ *Other Inquiry*\n\nTell me what's up:", parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())
        else:
            responses = {
                "boot": "💻 *Not Booting*\n\n**Try:** different adapter, remove battery, hold power 30s.",
                "display": "🖥 *Display Issues*\n\n**Check:** external monitor, brightness, physical damage.",
                "charging": "🔋 *Charging Issues*\n\n**Try:** different charger, clean port, battery calibration.",
                "performance": "⚡ *Performance*\n\n**Try:** restart, close apps, AV scan, clean temp files.",
            }
            await query.edit_message_text(responses.get(typ, "Describe it and I'll help."), parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())
        return

    if data.startswith("report_"):
        typ = data.replace("report_", "")
        user_states[uid] = {"action": "issue_report", "issue_type": typ, "step": "model"}
        await query.edit_message_text(f"🛠 **Issue Report: {typ.title()}**\n\n📱 Tell me your laptop brand & model.\nExample: `Dell Inspiron 15 3000`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())
        return

    if data.startswith("tip_"):
        tip_type = data.replace("tip_", "")
        
        # Check for saved tips first
        if tip_type.startswith("saved_"):
            saved_title = tip_type.replace("saved_", "")
            if saved_title in tips_guides:
                tip_content = tips_guides[saved_title]
                await query.edit_message_text(f"💡 *{saved_title.replace('_', ' ').title()}*\n\n{tip_content}", parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())
                return
        
        # Default tips
        tips = {
            "battery": "🔋 *Battery Tips*\n\n✅ Keep 20–80%\n✅ Use original charger\n✅ Avoid heat\n❌ Don't drain to 0%",
            "hardware": "⚠️ *Hardware Signs*\n\n• Weird noises\n• Random shutdowns\n• Overheating\n• Screen flicker",
            "cleaning": "🧽 *Cleaning*\n\nWeekly: screen + keyboard\nMonthly: vents & fans\nUse microfiber + compressed air",
        }
        await query.edit_message_text(tips.get(tip_type, "💡 Tips coming soon."), parse_mode=ParseMode.MARKDOWN, reply_markup=back_menu())
        return


    if data == "add_tip_guide":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        user_states[uid] = {"action": "manage_tips", "step": "add_title"}
        await query.edit_message_text("📝 *Add New Tip*\n\nEnter tip title/category:\nExample: `virus_protection`, `speed_optimization`", parse_mode=ParseMode.MARKDOWN)
        return

    if data == "view_tips_guides":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not tips_guides:
            await query.edit_message_text("📭 No custom tips saved yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        text = "📋 *Saved Tips:*\n\n"
        for title, content in tips_guides.items():
            text += f"**{title}:**\n{content[:100]}{'...' if len(content) > 100 else ''}\n\n"
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
        return

    if data == "edit_tip_guide":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not tips_guides:
            await query.edit_message_text("📭 No tips to edit.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        kb = []
        for title in tips_guides.keys():
            kb.append([InlineKeyboardButton(f"✏️ {title}", callback_data=f"edit_tip_{title}")])
        kb.append([InlineKeyboardButton("🏠 Back", callback_data="main_menu")])
        
        await query.edit_message_text("✏️ *Select tip to edit:*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "delete_tip_guide":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not tips_guides:
            await query.edit_message_text("📭 No tips to delete.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        kb = []
        for title in tips_guides.keys():
            kb.append([InlineKeyboardButton(f"🗑️ {title}", callback_data=f"delete_tip_{title}")])
        kb.append([InlineKeyboardButton("🏠 Back", callback_data="main_menu")])
        
        await query.edit_message_text("🗑️ *Select tip to delete:*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("edit_tip_"):
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        title = data.replace("edit_tip_", "")
        user_states[uid] = {"action": "manage_tips", "step": "edit_content", "edit_title": title}
        current_content = tips_guides.get(title, "")
        await query.edit_message_text(f"✏️ *Edit Tip: {title}*\n\nCurrent content:\n{current_content}\n\nEnter new content:", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("delete_tip_"):
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        title = data.replace("delete_tip_", "")
        if title in tips_guides:
            del tips_guides[title]
            save_all()
            await query.edit_message_text(f"✅ Deleted tip: {title}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
        return


    if data == "callback":
        user_states[uid] = {"action": "callback"}
        await query.edit_message_text("📞 *Request Callback*\n\nDrop your phone + short issue.\nExample: `08012345678 - no power on`", parse_mode=ParseMode.MARKDOWN)
        return

    if data == "setup_profile":
        user_states[uid] = {"action": "update_profile", "step": "name"}
        await query.edit_message_text("✨ *Profile Setup*\n\n📛 Enter your full name (or type `skip`):", parse_mode=ParseMode.MARKDOWN)
        return

    if data == "toggle_notifications":
        p = user_data_store.setdefault(uid, UserProfile())
        p.notifications_enabled = not p.notifications_enabled
        save_all()
        status = "enabled" if p.notifications_enabled else "disabled"
        await query.edit_message_text(f"📢 Notifications {status}!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
        return


    if data == "admin_manage":
        if not is_owner(update):  # Keep this check but use is_owner (which now checks ADMIN_IDS)
            await query.answer("Access denied", show_alert=True)
            return
        await admin_manage(update, context)
        return

    if data.startswith("admin_") and data.replace("admin_", "") in ["orders", "issues", "callbacks", "inquiries"]:
        if not is_owner(update):  # Keep this check but use is_owner (which now checks ADMIN_IDS)
            await query.answer("Access denied", show_alert=True)
            return
        request_type = data.replace("admin_", "")
        await show_admin_requests(query, request_type)
        return
    
    if data == "add_technician":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        user_states[uid] = {"action": "manage_technicians", "tech_action": "add", "step": "name"}
        await query.edit_message_text("➕ *Add New Technician*\n\n👤 Enter technician name:", parse_mode=ParseMode.MARKDOWN)
        return

    if data == "remove_technician":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not TECHNICIANS:
            await query.edit_message_text("❌ No technicians to remove.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        tech_list = "\n".join([f"{i+1}. {tech['name']}" for i, tech in enumerate(TECHNICIANS)])
        user_states[uid] = {"action": "manage_technicians", "tech_action": "remove"}
        await query.edit_message_text(f"🗑️ *Remove Technician*\n\n{tech_list}\n\nEnter number to remove:", parse_mode=ParseMode.MARKDOWN)
        return

    if data == "edit_technician":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not TECHNICIANS:
            await query.edit_message_text("❌ No technicians to edit.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        tech_list = "\n".join([f"{i+1}. {tech['name']}" for i, tech in enumerate(TECHNICIANS)])
        user_states[uid] = {"action": "manage_technicians", "tech_action": "edit", "step": "select"}
        await query.edit_message_text(f"📝 *Edit Technician*\n\n{tech_list}\n\nEnter number to edit:", parse_mode=ParseMode.MARKDOWN)
        return


    if data == "list_technicians":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not TECHNICIANS:
            text = "❌ No technicians registered."
        else:
            text = "🧑‍🔧 *Current Technicians:*\n\n"
            for i, tech in enumerate(TECHNICIANS, 1):
                text += f"*{i}. {tech['name']}*\n📞 {tech['contact']}\n⭐ {tech['rating']} | 💰 {tech['fee']}\n📍 {tech['area']}\n\n"
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
        return

#
    if data.startswith("admin_view_"):
        if not is_owner(update):  # Keep this check but use is_owner (which now checks ADMIN_IDS)
            await query.answer("Access denied", show_alert=True)
            return
        req_id = data.replace("admin_view_", "")
        try:
            await show_request_details(query, req_id)
        except Exception as e:
            logger.exception("Error in show_request_details: %s", e)
            await query.edit_message_text(f"❌ Error loading request details: {str(e)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="admin_manage")]]))
        return
    #

    if data.startswith("change_"):
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        
        field = data.replace("change_", "")
        field_names = {
            "bank": ("bank_name", "bank name"),
            "account_number": ("account_number", "account number"), 
            "account_name": ("account_name", "account name")
        }
        
        if field in field_names:
            field_key, field_display = field_names[field]
            user_states[uid] = {"action": "payment_info", "payment_field": field_key}
            await query.edit_message_text(f"💳 Enter new {field_display}:", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("status_"):
        if not is_owner(update):  # Keep this check but use is_owner (which now checks ADMIN_IDS)
            await query.answer("Access denied", show_alert=True)
            return
        parts = data.replace("status_", "").split("_", 1)
        req_id, new_status = parts[0], parts[1]
        await update_request_status(query, req_id, new_status)
        return

    if data == "set_preferred_tech":
        kb = []
        for i, tech in enumerate(TECHNICIANS):
            kb.append([InlineKeyboardButton(f"{tech['name']} ({tech['area']})", callback_data=f"select_tech_{i}")])
        await query.edit_message_text("🧑‍🔧 *Choose Preferred Technician*:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("select_tech_"):
        tech_index = int(data.replace("select_tech_", ""))
        if 0 <= tech_index < len(TECHNICIANS):
            tech = TECHNICIANS[tech_index]
            p = user_data_store.setdefault(uid, UserProfile())
            p.preferred_tech = tech['name']
            save_all()
            await query.edit_message_text(f"✅ Preferred Technician: {tech['name']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
        return

    # Admin price management callbacks
    if data.startswith("price_item_"):
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        
        item = data.replace("price_item_", "")
        current_prices = "\n".join([f"{model}: {fmt_money(price)}" for model, price in ITEM_PRICES[item].items()])
        
        user_states[uid] = {"action": "admin_price", "step": "update_prices", "item": item}
        await query.edit_message_text(
            f"💰 *Update {item.replace('_', ' ').title()} Prices*\n\n"
            f"Current prices:\n{current_prices}\n\n"
            f"📝 **Commands:**\n"
            f"• Add/Update: `Model:Price` (e.g. HP:12000)\n"
            f"• Delete: `Model:` (e.g. HP:)\n"
            f"• Finish: `done`\n\n"
            f"Enter command:",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data == "add_new_item":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        user_states[uid] = {"action": "admin_price", "step": "new_item"}
        await query.edit_message_text("➕ *Add New Item*\n\nEnter item name (e.g., 'webcam', 'speaker'):", parse_mode=ParseMode.MARKDOWN)
        return
        

    if data == "add_inquiry_response":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        user_states[uid] = {"action": "manage_inquiry", "step": "add_title"}
        await query.edit_message_text("📝 *Add Quick Response*\n\nEnter response title/category:\nExample: `boot_issues`, `performance_tips`", parse_mode=ParseMode.MARKDOWN)
        return

    if data == "view_inquiry_responses":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not inquiry_responses:
            await query.edit_message_text("📭 No responses saved yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        text = "📋 *Saved Responses:*\n\n"
        for title, content in inquiry_responses.items():
            text += f"**{title}:**\n{content[:100]}{'...' if len(content) > 100 else ''}\n\n"
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
        return


    if data == "edit_inquiry_response":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not inquiry_responses:
            await query.edit_message_text("📭 No responses to edit.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        kb = []
        for title in inquiry_responses.keys():
            kb.append([InlineKeyboardButton(f"✏️ {title}", callback_data=f"edit_response_{title}")])
        kb.append([InlineKeyboardButton("🏠 Back", callback_data="main_menu")])
        
        await query.edit_message_text("✏️ *Select response to edit:*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "remove_item":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not ITEM_PRICES:
            await query.edit_message_text("📭 No items to remove.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        kb = []
        for item in ITEM_PRICES.keys():
            kb.append([InlineKeyboardButton(f"🗑️ {item.replace('_', ' ').title()}", callback_data=f"delete_item_{item}")])
        kb.append([InlineKeyboardButton("🏠 Back", callback_data="main_menu")])
        
        await query.edit_message_text("🗑️ *Select item to remove:*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("delete_item_"):
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        item = data.replace("delete_item_", "")
        if item in ITEM_PRICES:
            del ITEM_PRICES[item]
            save_all()
            await query.edit_message_text(f"✅ Deleted item: {item.replace('_', ' ').title()}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
        return


    if data == "delete_inquiry_response":
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        if not inquiry_responses:
            await query.edit_message_text("📭 No responses to delete.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
            return
        
        kb = []
        for title in inquiry_responses.keys():
            kb.append([InlineKeyboardButton(f"🗑️ {title}", callback_data=f"delete_response_{title}")])
        kb.append([InlineKeyboardButton("🏠 Back", callback_data="main_menu")])
        
        await query.edit_message_text("🗑️ *Select response to delete:*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("edit_response_"):
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        title = data.replace("edit_response_", "")
        user_states[uid] = {"action": "manage_inquiry", "step": "edit_content", "edit_title": title}
        current_content = inquiry_responses.get(title, "")
        await query.edit_message_text(f"✏️ *Edit Response: {title}*\n\nCurrent content:\n{current_content}\n\nEnter new content:", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("delete_response_"):
        if not is_owner(update):
            await query.answer("Access denied", show_alert=True)
            return
        title = data.replace("delete_response_", "")
        if title in inquiry_responses:
            del inquiry_responses[title]
            save_all()
            await query.edit_message_text(f"✅ Deleted response: {title}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="main_menu")]]))
        return


        user_states[uid] = {"action": "admin_price", "step": "new_item"}
        await query.edit_message_text("➕ *Add New Item*\n\nEnter item name (e.g., 'webcam', 'speaker'):", parse_mode=ParseMode.MARKDOWN)
        return

# Admin commands
async def admin_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    txt = f"📊 Teeshoot Bot Data Summary\n\n📦 Orders: {len(orders)}\n🛠 Issues: {len(issues)}\n📞 Callbacks: {len(callbacks)}\n❓ Inquiries: {len(inquiries)}\n👤 Users: {len(user_data_store)}\n\n📄 Active Sessions: {len(user_states)}"
    await update.message.reply_text(txt)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(context.args)
    sent = 0
    for uid, profile in user_data_store.items():
        if profile.notifications_enabled:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📣 *Broadcast*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
                sent += 1
            except: pass
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")

async def dump_json(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    save_all()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            snippet = f.read(4000)
        await update.message.reply_text(f"🗂 Data snapshot:\n\n<pre>{snippet}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /addadmin <user_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        ADMIN_IDS.add(new_admin_id)
        save_all()
        await update.message.reply_text(f"✅ Added admin: {new_admin_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID format.")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CLIENT_ID:  # Only original owner can remove admins
        await update.message.reply_text("❌ Only the main owner can remove admins.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /removeadmin <user_id>")
        return
    
    try:
        admin_id = int(context.args[0])
        if admin_id == CLIENT_ID:
            await update.message.reply_text("❌ Cannot remove the main owner.")
            return
        if admin_id in ADMIN_IDS:
            ADMIN_IDS.remove(admin_id)
            save_all()
            await update.message.reply_text(f"✅ Removed admin: {admin_id}")
        else:
            await update.message.reply_text("❌ User is not an admin.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID format.")

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    
    admin_list = "\n".join([f"• {admin_id}" + (" (Owner)" if admin_id == CLIENT_ID else "") for admin_id in ADMIN_IDS])
    await update.message.reply_text(f"👥 **Current Admins:**\n\n{admin_list}")

async def manage_technicians(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    
    kb = [
        [InlineKeyboardButton("➕ Add Technician", callback_data="add_technician")],
        [InlineKeyboardButton("📝 Edit Technician", callback_data="edit_technician")],
        [InlineKeyboardButton("🗑️ Remove Technician", callback_data="remove_technician")],
        [InlineKeyboardButton("📋 List All", callback_data="list_technicians")],
        [InlineKeyboardButton("🏠 Back", callback_data="main_menu")],
    ]
    await update.message.reply_text("🧑‍🔧 *Technician Management*\n\nWhat would you like to do?", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

async def handle_technician_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    action = state.get("tech_action")
    step = state.get("step")
    
    if action == "add":
        if step == "name":
            state["new_tech"] = {"name": text}
            state["step"] = "contact"
            await update.message.reply_text("📱 Enter contact number:")
        elif step == "contact":
            state["new_tech"]["contact"] = text
            state["step"] = "rating"
            await update.message.reply_text("⭐ Enter rating (e.g., 4.8/5):")
        elif step == "rating":
            state["new_tech"]["rating"] = text
            state["step"] = "fee"
            await update.message.reply_text("💰 Enter service fee (e.g., ₦2,000):")
        elif step == "fee":
            state["new_tech"]["fee"] = text
            state["step"] = "area"
            await update.message.reply_text("📍 Enter service area:")
        elif step == "area":
            state["new_tech"]["area"] = text
            TECHNICIANS.append(state["new_tech"])
            save_all()
            await update.message.reply_text(f"✅ Technician '{state['new_tech']['name']}' added successfully!", reply_markup=MAIN_KB)
            user_states.pop(uid, None)
    
    elif action == "remove":
        try:
            index = int(text) - 1
            if 0 <= index < len(TECHNICIANS):
                removed = TECHNICIANS.pop(index)
                save_all()
                await update.message.reply_text(f"✅ Removed technician: {removed['name']}", reply_markup=MAIN_KB)
            else:
                await update.message.reply_text("❌ Invalid number. Try again:")
                return
        except ValueError:
            await update.message.reply_text("❌ Enter a valid number:")
            return
        user_states.pop(uid, None)
    
    elif action == "edit":
        if step == "select":
            try:
                index = int(text) - 1
                if 0 <= index < len(TECHNICIANS):
                    state["edit_index"] = index
                    state["step"] = "field"
                    await update.message.reply_text("📝 What to edit?\n1. Name\n2. Contact\n3. Rating\n4. Fee\n5. Area\n\nEnter number:")
                else:
                    await update.message.reply_text("❌ Invalid number. Try again:")
                    return
            except ValueError:
                await update.message.reply_text("❌ Enter a valid number:")
                return
        elif step == "field":
            field_map = {"1": "name", "2": "contact", "3": "rating", "4": "fee", "5": "area"}
            if text in field_map:
                state["edit_field"] = field_map[text]
                current_value = TECHNICIANS[state["edit_index"]][state["edit_field"]]
                state["step"] = "value"
                await update.message.reply_text(f"📝 Current {state['edit_field']}: {current_value}\n\nEnter new value:")
            else:
                await update.message.reply_text("❌ Invalid choice. Enter 1-5:")
                return
        elif step == "value":
            TECHNICIANS[state["edit_index"]][state["edit_field"]] = text
            save_all()
            tech_name = TECHNICIANS[state["edit_index"]]["name"]
            await update.message.reply_text(f"✅ Updated {state['edit_field']} for {tech_name}!", reply_markup=MAIN_KB)
            user_states.pop(uid, None)


async def manage_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    
    text = (
        f"💳 *Current Payment Info:*\n\n"
        f"🏦 Bank: {PAYMENT_INFO['bank_name']}\n"
        f"🔢 Account Number: {PAYMENT_INFO['account_number']}\n"
        f"👤 Account Name: {PAYMENT_INFO['account_name']}"
    )
    
    kb = [
        [InlineKeyboardButton("🏦 Change Bank", callback_data="change_bank")],
        [InlineKeyboardButton("🔢 Change Account Number", callback_data="change_account_number")],
        [InlineKeyboardButton("👤 Change Account Name", callback_data="change_account_name")],
        [InlineKeyboardButton("🏠 Back", callback_data="main_menu")],
    ]
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))


async def handle_manage_inquiry_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    step = state.get("step")
    
    if step == "add_title":
        state["new_title"] = text.lower().replace(" ", "_")
        state["step"] = "add_content"
        await update.message.reply_text("📝 Now enter the response content:")
    elif step == "add_content":
        inquiry_responses[state["new_title"]] = text
        save_all()
        await update.message.reply_text(f"✅ Added response: {state['new_title']}", reply_markup=MAIN_KB)
        user_states.pop(uid, None)
    elif step == "edit_content":
        inquiry_responses[state["edit_title"]] = text
        save_all()
        await update.message.reply_text(f"✅ Updated response: {state['edit_title']}", reply_markup=MAIN_KB)
        user_states.pop(uid, None)

async def handle_payment_info_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    field = state.get("payment_field")
    
    if field == "bank_name":
        PAYMENT_INFO["bank_name"] = text
    elif field == "account_number":
        PAYMENT_INFO["account_number"] = text
    elif field == "account_name":
        PAYMENT_INFO["account_name"] = text.upper()
    
    save_all()
    await update.message.reply_text(f"✅ Updated {field.replace('_', ' ')} successfully!", reply_markup=MAIN_KB)
    user_states.pop(uid, None)


async def manage_inquiries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    
    kb = [
        [InlineKeyboardButton("📝 Add Quick Response", callback_data="add_inquiry_response")],
        [InlineKeyboardButton("📋 View All Responses", callback_data="view_inquiry_responses")],
        [InlineKeyboardButton("✏️ Edit Response", callback_data="edit_inquiry_response")],
        [InlineKeyboardButton("🗑️ Delete Response", callback_data="delete_inquiry_response")],
        [InlineKeyboardButton("🏠 Back", callback_data="main_menu")],
    ]
    await update.message.reply_text("❓ *Inquiry Management*\n\nManage quick responses for common inquiries:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))


async def admin_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main admin management menu - Simplified Version"""
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return

    try:
        # Reload data
        load_all()
        
        # Build a simple text summary of all requests
        text = "📊 *Admin Dashboard*\n\n"
        
        # Orders Summary
        text += "📦 *ORDERS:*\n"
        if not orders:
            text += "No orders yet\n"
        else:
            for oid, order in orders.items():
                text += f"• {oid} | {order.item.replace('_',' ').title()} | {order.status}\n"
        
        text += "\n🛠 *ISSUES:*\n"
        if not issues:
            text += "No issues reported\n"
        else:
            for iid, issue in issues.items():
                text += f"• {iid} | {issue.type} | {issue.status}\n"
        
        text += "\n📞 *CALLBACKS:*\n"
        if not callbacks:
            text += "No callbacks requested\n"
        else:
            for cid, cb in callbacks.items():
                text += f"• {cid} | {cb.status}\n"
                
        text += "\n❓ *INQUIRIES:*\n"
        if not inquiries:
            text += "No inquiries yet\n"
        else:
            for qid, inq in inquiries.items():
                text += f"• {qid} | {inq.status}\n"
                
        # Add instructions
        text += "\n📝 *COMMANDS:*\n"
        text += "• Reply to any ID with 'status X' to change status\n"
        text += "• Example: `status confirmed` or `status resolved`\n"
        text += "• Use /refresh to update this view\n"
        
        # Send the message
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Error in admin_manage: {e}")
        await update.message.reply_text("⚠️ Error loading admin view. Please try again.", reply_markup=MAIN_KB)


async def handle_manage_tips_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    step = state.get("step")
    
    if step == "add_title":
        state["new_title"] = text.lower().replace(" ", "_")
        state["step"] = "add_content"
        await update.message.reply_text("📝 Now enter the tip/guide content:")
    elif step == "add_content":
        tips_guides[state["new_title"]] = text
        save_all()
        await update.message.reply_text(f"✅ Added tip: {state['new_title']}", reply_markup=MAIN_KB)
        user_states.pop(uid, None)
    elif step == "edit_content":
        tips_guides[state["edit_title"]] = text
        save_all()
        await update.message.reply_text(f"✅ Updated tip: {state['edit_title']}", reply_markup=MAIN_KB)
        user_states.pop(uid, None)


async def manage_tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Access denied.")
        return
    
    kb = [
        [InlineKeyboardButton("📝 Add New Tip", callback_data="add_tip_guide")],
        [InlineKeyboardButton("📋 View All Tips", callback_data="view_tips_guides")],
        [InlineKeyboardButton("✏️ Edit Tip", callback_data="edit_tip_guide")],
        [InlineKeyboardButton("🗑️ Delete Tip", callback_data="delete_tip_guide")],
        [InlineKeyboardButton("🏠 Back", callback_data="main_menu")],
    ]
    await update.message.reply_text("📘 *Tips & Guides Management*\n\nManage tips and maintenance guides:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

async def show_admin_requests(query, request_type: str):
    """Show list of requests by type"""
    # Always reload data before showing requests
    load_all()
    
    try:
        # Map request types to stores
        stores = {"orders": orders, "issues": issues, "callbacks": callbacks, "inquiries": inquiries}
        store = stores[request_type]
        
        # Log the current state for debugging
        logger.info(f"Showing {request_type}. Current count: {len(store)}")
        
        # Prepare the keyboard and message
        kb = []
        
        # Navigation buttons - always show these
        nav = [
            InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_{get_prev_category(request_type)}"),
            InlineKeyboardButton("🔄", callback_data=f"admin_{request_type}"),
            InlineKeyboardButton("➡️ Next", callback_data=f"admin_{get_next_category(request_type)}")
        ]
    except Exception as e:
        logger.error(f"Error preparing admin view: {e}")
        if hasattr(query, 'reply_text'):
            await query.reply_text("⚠️ Error loading management view. Try again.")
        elif hasattr(query, 'edit_message_text'):
            await query.edit_message_text("⚠️ Error loading management view. Try again.")
        return
    
    # Define the navigation order
    navigation_order = ["orders", "issues", "callbacks", "inquiries"]
    current_index = navigation_order.index(request_type)
    next_type = navigation_order[(current_index + 1) % len(navigation_order)]
    prev_type = navigation_order[(current_index - 1) % len(navigation_order)]
    
    if not store:
        message = f"📭 No {request_type} found."
        # Even with no items, show navigation buttons
        kb = [
            [
                InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_{prev_type}"),
                InlineKeyboardButton("➡️ Next", callback_data=f"admin_{next_type}")
            ],
            [InlineKeyboardButton("🔙 Menu", callback_data="admin_manage")]
        ]
        
        # Add current category counts to message
        counts = []
        for category in navigation_order:
            count = len(stores[category])
            if count > 0:
                counts.append(f"{category.title()}: {count}")
        
        if counts:
            message += "\n\n📊 Other categories:\n" + "\n".join(counts)
        
        if hasattr(query, 'edit_message_text'):
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await query.reply_text(message, reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Sort by timestamp (newest first) and filter by status
    if request_type == "orders":
        pending_statuses = ["pending_confirmation", "payment_submitted", "confirmed"]
    elif request_type == "issues":
        pending_statuses = ["reported", "under_review"]
    elif request_type == "callbacks":
        pending_statuses = ["pending"]
    else:  # inquiries
        pending_statuses = ["pending_response"]
    
    # First show pending items, then others
    pending_items = []
    other_items = []
    for req_id, item in store.items():
        if item.status in pending_statuses:
            pending_items.append((req_id, item))
        else:
            other_items.append((req_id, item))
            
    # Sort both lists by timestamp
    pending_items.sort(key=lambda x: x[1].timestamp, reverse=True)
    other_items.sort(key=lambda x: x[1].timestamp, reverse=True)
    
    # Combine lists with pending first
    sorted_items = pending_items + other_items
    
    # Calculate stats
    total_count = len(sorted_items)
    pending_count = len(pending_items)
    
    # Build keyboard with ALL requests
    kb = []
    
    # Add pending items first
    for req_id, item in sorted_items:
        # Status emoji
        if item.status in pending_statuses:
            status_emoji = "⏳"
        else:
            status_emoji = "✅"
        
        # Show more info in the button
        if request_type == "orders":
            display_name = f"{item.item.replace('_', ' ').title()[:10]} - {item.name[:10]}"
        else:
            display_name = item.name[:15]
        
        # Create button with status and timestamp
        timestamp = item.timestamp.split()[1]  # Get just the time part
        button_text = f"{status_emoji} {req_id} | {display_name} ({timestamp})"
        kb.append([InlineKeyboardButton(button_text, callback_data=f"admin_view_{req_id}")])
    
    # Add navigation and utility buttons
    nav_buttons = [
        InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_{prev_type}"),
        InlineKeyboardButton("🔄 Refresh", callback_data=f"admin_{request_type}"),
        InlineKeyboardButton("➡️ Next", callback_data=f"admin_{next_type}")
    ]
    
    kb.append(nav_buttons)
    kb.append([InlineKeyboardButton("🔙 Menu", callback_data="admin_manage")])
    
    # Add category counts to header
    other_counts = []
    for category in navigation_order:
        if category != request_type:
            count = len(stores[category])
            if count > 0:
                other_counts.append(f"{category.title()}: {count}")
    
    if other_counts:
        header += "\n\n📊 Other categories:\n" + "\n".join(other_counts)
    
    # Header message
    header = (
        f"📋 *{request_type.title()} Management*\n\n"
        f"📊 Total: {total_count} | ⏳ Pending: {pending_count}\n"
    )
    
    if hasattr(query, 'edit_message_text'):
        await query.edit_message_text(
            header,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        await query.reply_text(
            header,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb)
        )


async def show_request_details(query, req_id: str):
    """Show detailed view of a single request"""
    # Find the request
    all_stores = {"ORD": orders, "ISS": issues, "CB": callbacks, "INQ": inquiries}
    
    item = None
    prefix = req_id[:3]
    store_type = None
    
    if prefix in all_stores and req_id in all_stores[prefix]:
        item = all_stores[prefix][req_id]
        if prefix == "ORD":
            store_type = "orders"
        elif prefix == "ISS":
            store_type = "issues"
        elif prefix == "CB":
            store_type = "callbacks"
        elif prefix == "INQ":
            store_type = "inquiries"
    else:
        error_message = "❌ Request not found or has been deleted."
        if hasattr(query, 'edit_message_text'):
            await query.edit_message_text(
                error_message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_manage")]])
            )
        else:
            await query.reply_text(
                error_message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_manage")]])
            )
        return
    
    # Build details text based on type
    if prefix == "ORD":
        # Order details
        model = item.details.get('model', 'N/A')
        quantity = item.details.get('quantity', 'N/A')
        total = item.details.get('total', 0)
        address = item.details.get('address', 'N/A')
        
        # Format total safely
        try:
            total_formatted = f"₦{int(total):,}"
        except:
            total_formatted = "₦0"
        
        item_name = item.item.replace('_', ' ').title() if hasattr(item, 'item') else 'N/A'
        
        details = (
            f"📦 *Order Details*\n\n"
            f"🆔 ID: `{req_id}`\n"
            f"👤 User: {item.name}\n"
            f"🛒 Item: {item_name}\n"
            f"📱 Model: {model}\n"
            f"📦 Qty: {quantity}\n"
            f"💰 Total: {total_formatted}\n"
            f"📍 Address: {address}\n"
            f"📊 Status: *{item.status.replace('_', ' ').title()}*\n"
            f"⏰ Time: {item.timestamp}"
        )
        statuses = ["pending_confirmation", "confirmed", "payment_submitted", "payment_verified", "processing", "shipped", "delivered", "cancelled"]
        
    elif prefix == "ISS":
        # Issue details
        details = (
            f"🛠 *Issue Report*\n\n"
            f"🆔 ID: `{req_id}`\n"
            f"👤 User: {item.name}\n"
            f"🔧 Type: {item.type.title()}\n"
            f"📱 Model: {item.details.get('model', 'N/A')}\n"
            f"📝 Description:\n{item.details.get('description', 'N/A')}\n"
            f"📊 Status: *{item.status.replace('_', ' ').title()}*\n"
            f"⏰ Time: {item.timestamp}"
        )
        statuses = ["reported", "under_review", "in_progress", "resolved", "closed"]
        
    elif prefix == "CB":
        # Callback details
        details = (
            f"📞 *Callback Request*\n\n"
            f"🆔 ID: `{req_id}`\n"
            f"👤 User: {item.name}\n"
            f"📝 Details:\n{item.phone_and_issue}\n"
            f"📊 Status: *{item.status.replace('_', ' ').title()}*\n"
            f"⏰ Time: {item.timestamp}"
        )
        statuses = ["pending", "called", "completed", "no_answer"]
        
    else:  # INQ
        # Inquiry details
        details = (
            f"❓ *Inquiry*\n\n"
            f"🆔 ID: `{req_id}`\n"
            f"👤 User: {item.name}\n"
            f"📝 Type: {item.inquiry_type.title()}\n"
            f"❓ Question:\n{item.inquiry_text}\n"
            f"📊 Status: *{item.status.replace('_', ' ').title()}*\n"
            f"⏰ Time: {item.timestamp}"
        )
        statuses = ["pending_response", "responded", "resolved"]
    
    # Build status change keyboard
    kb = []
    for status in statuses:
        if status == item.status:
            emoji = "✅"
        else:
            emoji = "⚪"
        
        button_text = f"{emoji} {status.replace('_', ' ').title()}"
        kb.append([InlineKeyboardButton(button_text, callback_data=f"status_{req_id}_{status}")])
    
    # Add back button
    kb.append([InlineKeyboardButton("🔙 Back to List", callback_data=f"admin_{prefix.lower().replace('ord', 'orders').replace('iss', 'issues').replace('cb', 'callbacks').replace('inq', 'inquiries')}")])
    
    await query.edit_message_text(
        details, 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

    
async def update_request_status(query, req_id: str, new_status: str):
    """Update status of a request"""
    # Find and update
    all_stores = {"ORD": orders, "ISS": issues, "CB": callbacks, "INQ": inquiries}
    
    prefix = req_id[:3]
    
    if prefix in all_stores and req_id in all_stores[prefix]:
        store = all_stores[prefix]
        old_status = store[req_id].status
        store[req_id].status = new_status
        save_all()
        
        # Save first to ensure data is persisted
        save_all()
        
        # Notify user
        user_id = store[req_id].user_id
        if user_id in user_data_store and user_data_store[user_id].notifications_enabled:
            try:
                await query.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"📋 *Status Update*\n\n"
                        f"Request: `{req_id}`\n"
                        f"Old Status: {old_status.replace('_', ' ').title()}\n"
                        f"New Status: *{new_status.replace('_', ' ').title()}*"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.warning(f"Failed to notify user: {e}")
                # Continue even if notification fails
        
        # Show confirmation
        await query.edit_message_text(
            f"✅ *Status Updated!*\n\n"
            f"Request: `{req_id}`\n"
            f"From: {old_status.replace('_', ' ').title()}\n"
            f"To: *{new_status.replace('_', ' ').title()}*\n\n"
            f"User has been notified.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Details", callback_data=f"admin_view_{req_id}")]])
        )
    else:
        await query.edit_message_text(
            "❌ Request not found.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_manage")]])
        )

        
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Error: %s", context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Something went wrong. Try again.")
    except: pass

async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh admin view"""
    if is_owner(update):
        await admin_manage(update, context)
    else:
        await update.message.reply_text("❌ Admin only command.")

def main():
    load_all()
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("BOT_TOKEN missing.")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refresh", refresh))  # Add refresh command
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("admin", admin_data))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("dump", dump_json))
    app.add_handler(CommandHandler("prices", manage_prices))  # New admin price command
    app.add_handler(CommandHandler("manage", admin_manage))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("listadmins", list_admins))
    app.add_handler(CommandHandler("technicians", manage_technicians))
    app.add_handler(CommandHandler("payment", manage_payment_info))
    app.add_handler(CommandHandler("inquiries", manage_inquiries))
    # Messages and callbacks
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("tips", manage_tips))
    logger.info("🚀 Teeshoot bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
