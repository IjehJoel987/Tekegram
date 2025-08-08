#!/usr/bin/env python3
"""
Computer Support Telegram Bot
Easy to customize and update

Install: pip install python-telegram-bot
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import threading
import http.server
import socketserver


# Enable basic logging (errors only)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR)
logger = logging.getLogger(__name__)

# ===============================
# EASY CONFIGURATION SECTION
# ===============================

# Your bot token from BotFather
BOT_TOKEN = "8255024786:AAE7PjFuaqEcP156rLV02K028mzPQ1xAe1E"

# Your friend's chat ID (he needs to message the bot first, then check logs for his chat_id)
ADMIN_CHAT_ID = "6340039582"  # Will be a number like: 123456789

# Business Information
BUSINESS_NAME = "Orbem Tech Solutions"
BUSINESS_HOURS = "9:00 AM - 6:00 PM (Mon-Sat)"

# Customize Questions and Options
QUESTIONS = {
    "problem_categories": [
        "💻 Computer won't turn on",
        "🐌 Computer running slow",
        "🦠 Virus/Malware issues", 
        "🖥️ Screen problems",
        "🔊 Audio issues",
        "📶 Internet/WiFi problems",
        "💾 Software installation",
        "🔧 Hardware repair",
        "📱 Other issues"
    ],
    "computer_types": [
        "💻 Laptop",
        "Tablet",
        "Ipod",
        "Other peripherals",
        "🖱️ Not sure"

    ],
    
    "urgency_levels": [
        "🔴 Very Urgent (Can't work at all)",
        "🟡 Moderate (Can wait a day or two)", 
        "🟢 Not urgent (When convenient)"
    ]
}

# Welcome message
WELCOME_MESSAGE = f"""
👋 Welcome to {BUSINESS_NAME}!

I'm here to help you get your computer issues resolved quickly. I'll ask you a few questions to understand your problem better.

Our technician will get back to you as soon as possible.

Business Hours: {BUSINESS_HOURS}

Let's get started! 🚀
"""

# ===============================
# CONVERSATION STATES
# ===============================
(ASKING_NAME, ASKING_PHONE, ASKING_ROOM_HALL, ASKING_COMPUTER_TYPE, 
 ASKING_PROBLEM_TYPE, ASKING_DESCRIPTION, ASKING_URGENCY, 
 CONFIRMING) = range(8)

# Store user data temporarily
user_data = {}

# ===============================
# HELPER FUNCTIONS
# ===============================

def create_keyboard(options):
    """Create a custom keyboard from list of options"""
    keyboard = [[option] for option in options]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def format_complaint(chat_id, data):
    """Format the collected data into a nice complaint summary"""
    return f"""
🎯 NEW CUSTOMER REQUEST

👤 Customer: {data.get('name', 'Not provided')}
📱 Phone: {data.get('phone', 'Not provided')}
🏠 Room/Hall: {data.get('room_hall', 'Not provided')}
👨‍💻 Username: @{data.get('username', 'Not provided')}
💻 Device: {data.get('computer_type', 'Not specified')}
⚠️ Problem: {data.get('problem_type', 'Not specified')}
📝 Description: {data.get('description', 'No details provided')}
🚨 Urgency: {data.get('urgency', 'Not specified')}

---
Time: {data.get('timestamp', 'Unknown')}
"""

# ===============================
# BOT CONVERSATION HANDLERS
# ===============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation"""
    chat_id = update.effective_chat.id
    username = update.effective_user.username or "no_username"
    user_data[chat_id] = {
        'timestamp': update.message.date.strftime("%Y-%m-%d %H:%M:%S"),
        'username': username
    }
    
    await update.message.reply_text(
        WELCOME_MESSAGE,
        reply_markup=ReplyKeyboardRemove()
    )
    
    await update.message.reply_text(
        "Let's start with your name. What should I call you? 😊"
    )
    
    return ASKING_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get customer name"""
    chat_id = update.effective_chat.id
    user_data[chat_id]['name'] = update.message.text
    
    await update.message.reply_text(
        f"Nice to meet you, {update.message.text}! 👋\n\n"
        "Now, could you please share your phone number so we can reach you?"
    )
    
    return ASKING_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get customer phone"""
    chat_id = update.effective_chat.id
    user_data[chat_id]['phone'] = update.message.text
    
    await update.message.reply_text(
        "Got it! 📞\n\n"
        "What's your room number or hall name? (Example: Room 205, Block A Hall, etc.)"
    )
    
    return ASKING_ROOM_HALL

async def get_room_hall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get room/hall information"""
    chat_id = update.effective_chat.id
    user_data[chat_id]['room_hall'] = update.message.text
    
    await update.message.reply_text(
        "Perfect! 🏠\n\n"
        "What type of computer are you having issues with?",
        reply_markup=create_keyboard(QUESTIONS['computer_types'])
    )
    
    return ASKING_COMPUTER_TYPE

async def get_computer_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get computer type"""
    chat_id = update.effective_chat.id
    user_data[chat_id]['computer_type'] = update.message.text
    
    await update.message.reply_text(
        "Thanks! 💻\n\nNow, what kind of problem are you experiencing?",
        reply_markup=create_keyboard(QUESTIONS['problem_categories'])
    )
    
    return ASKING_PROBLEM_TYPE

async def get_problem_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get problem category"""
    chat_id = update.effective_chat.id
    user_data[chat_id]['problem_type'] = update.message.text
    
    await update.message.reply_text(
        "I understand. Could you describe the problem in more detail? 📝\n\n"
        "For example:\n"
        "- When did it start?\n"
        "- What exactly happens?\n"
        "- Any error messages?\n\n"
        "The more details, the better we can help!",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ASKING_DESCRIPTION

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get detailed description"""
    chat_id = update.effective_chat.id
    user_data[chat_id]['description'] = update.message.text
    
    await update.message.reply_text(
        "Perfect! Last question - how urgent is this issue?",
        reply_markup=create_keyboard(QUESTIONS['urgency_levels'])
    )
    
    return ASKING_URGENCY

async def get_urgency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get urgency level and show summary"""
    chat_id = update.effective_chat.id
    user_data[chat_id]['urgency'] = update.message.text
    
    # Show summary for confirmation
    data = user_data[chat_id]
    summary = f"""
📋 SUMMARY OF YOUR REQUEST:

👤 Name: {data['name']}
📱 Phone: {data['phone']}
🏠 Room/Hall: {data['room_hall']}
👨‍💻 Username: @{data['username']}
💻 Device: {data['computer_type']}
⚠️ Problem: {data['problem_type']}
📝 Details: {data['description']}
🚨 Urgency: {data['urgency']}

Is this information correct?
"""
    
    keyboard = [['✅ Yes, send it!', '❌ Let me start over']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(summary, reply_markup=reply_markup)
    
    return CONFIRMING

async def confirm_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and send to admin"""
    chat_id = update.effective_chat.id
    
    if update.message.text == '✅ Yes, send it!':
        # Send to admin
        complaint = format_complaint(chat_id, user_data[chat_id])
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=complaint
            )
            
            await update.message.reply_text(
                "✅ Perfect! Your request has been sent successfully!\n\n"
                f"Our technician will contact you soon at {user_data[chat_id]['phone']}\n\n"
                f"Expected response time based on urgency: {user_data[chat_id]['urgency']}\n\n"
                "Thank you for choosing our service! 🙏",
                reply_markup=ReplyKeyboardRemove()
            )
            
        except Exception as e:
            logger.error(f"Failed to send message to admin: {e}")
            await update.message.reply_text(
                "✅ Your request has been recorded!\n\n"
                "We'll get back to you as soon as possible. Thank you! 🙏",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Clear user data
        if chat_id in user_data:
            del user_data[chat_id]
            
    else:
        # Start over
        if chat_id in user_data:
            del user_data[chat_id]
        await update.message.reply_text(
            "No problem! Let's start fresh. 🔄",
            reply_markup=ReplyKeyboardRemove()
        )
        return await start(update, context)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    chat_id = update.effective_chat.id
    if chat_id in user_data:
        del user_data[chat_id]
    
    await update.message.reply_text(
        "No problem! Feel free to start again anytime with /start 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationHandler.END

# Admin commands
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin commands"""
    if str(update.effective_chat.id) == ADMIN_CHAT_ID:
        help_text = """
🔧 ADMIN COMMANDS:
/adminstats - Show bot statistics
/adminbroadcast <message> - Send message to all users (future feature)

Bot is running and collecting customer requests! 🚀
"""
        await update.message.reply_text(help_text)

# ===============================
# MAIN FUNCTION
# ===============================

def main():
    """Run the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASKING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            ASKING_ROOM_HALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_room_hall)],
            ASKING_COMPUTER_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_computer_type)],
            ASKING_PROBLEM_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_problem_type)],
            ASKING_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            ASKING_URGENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_urgency)],
            CONFIRMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_and_send)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', admin_help))

    # Start a simple web server for Render (so it doesn't think the service crashed)
    port = 10000
    
    def start_web_server():
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"🌐 Web server running on port {port}")
            httpd.serve_forever()
    
    # Start web server in background thread
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    # Start the bot
    print("🚀 Bot is running...")
    application.run_polling()

if __name__ == '__main__':

    main()

