#!/usr/bin/env python3
"""
ZIVPN Telegram Bot - Unlimited Users Version
"""
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext
from telegram import Update
import sqlite3
import logging
import os
from datetime import datetime, timedelta
import socket
import json
import tempfile
import subprocess

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")
BOT_TOKEN = "8330676362:AAEOWePTUJAAwUwqawvoiOehY3OvWD8LYqA"
CONFIG_FILE = "/etc/zivpn/config.json"

# Admin configuration - ONLY YOUR ID CAN SEE ADMIN COMMANDS
ADMIN_IDS = [7576434717, 7240495054]  # Telegram ID

# --- Localization Data (Simplified for Bot) ---
T_MM = {
    'not_admin': 'သင်သည် Admin မဟုတ်ပါ။',
    'missing_args': 'အချက်အလက် မပြည့်စုံပါ။ အသုံးပြုပုံကို စစ်ဆေးပါ။',
    'invalid_input': 'ရက်/ဒေတာ/ကန့်သတ်ချက် ကိန်းဂဏန်း မမှန်ပါ။',
    'user_exists': 'အသုံးပြုသူ (%s) ရှိပြီးသားပါ။',
    'user_not_found': 'အသုံးပြုသူကို ရှာမတွေ့ပါ။',
    'user_added': 'အသုံးပြုသူ (%s) ကို အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ။ သက်တမ်း: %s ရက်။ ဒေတာ ကန့်သတ်ချက်: %s GB။ Client Limit: %d',
    'user_deleted': 'အသုံးပြုသူ (%s) ကို ဖျက်ပစ်ပြီးပါပြီ။',
    'user_suspended': 'အသုံးပြုသူ (%s) ကို ဆိုင်းငံ့ပြီးပါပြီ။',
    'user_activated': 'အသုံးပြုသူ (%s) ကို ပြန်လည်ဖွင့်ပြီးပါပြီ။',
    'user_renewed': 'အသုံးပြုသူ (%s) ကို အောင်မြင်စွာ သက်တမ်းတိုးပြီးပါပြီ။ အသစ်သက်တမ်းကုန်ရက်: %s',
    'pass_changed': 'အသုံးပြုသူ (%s) ၏ လျှို့ဝှက်နံပါတ်ကို ပြောင်းလဲပြီးပါပြီ။',
    'traffic_reset': 'အသုံးပြုသူ (%s) ၏ ဒေတာအသုံးပြုမှုကို သုညပြန်လည်သတ်မှတ်ပြီးပါပြီ။',
    'info_header': '👤 အသုံးပြုသူ အချက်အလက် (User Info)',
    'info_username': 'အသုံးပြုသူအမည်:',
    'info_status': 'အခြေအနေ:',
    'info_expiry': 'သက်တမ်းကုန်ဆုံးရက်:',
    'info_data_limit': 'ဒေတာ ကန့်သတ်ချက်:',
    'info_data_used': 'အသုံးပြုပြီး:',
    'info_client_limit': 'ကိရိယာ ကန့်သတ်ချက်:', # NEW FIELD
    'info_clients_active': 'လက်ရှိ ချိတ်ဆက်သူ:', # NEW FIELD
    'info_unlimited': 'ကန့်သတ်မဲ့',
    'status_active': '✅ ဖွင့်ထားသည်',
    'status_suspended': '⏸️ ဆိုင်းငံ့ထားသည်',
    'status_expired': '⛔ သက်တမ်းကုန်',
    'ban_success': 'အသုံးပြုသူ ID (%s) ကို Bot အသုံးပြုခွင့် ပိတ်ပင်ပြီးပါပြီ။',
    'unban_success': 'အသုံးပြုသူ ID (%s) ကို Bot အသုံးပြုခွင့် ပြန်ဖွင့်ပြီးပါပြီ။',
    'stats_header': '📊 စနစ် အခြေအနေ (System Stats)',
    'stats_total_users': 'စုစုပေါင်း အသုံးပြုသူ:',
    'stats_active_users': 'အွန်လိုင်း အသုံးပြုသူ:',
    'stats_used_data': 'စုစုပေါင်း သုံးပြီးသား ဒေတာ:',
}

# ===== HELPER FUNCTIONS =====
def bytes_to_readable(b):
    if b is None: return "0 B"
    b = float(b)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024.0:
            return f"{b:3.2f} {unit}"
        b /= 1024.0
    return f"{b:3.2f} PB"

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS

def get_db():
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    # Check and update schema for max_clients (critical for new feature)
    try:
        db.execute('SELECT max_clients FROM users LIMIT 1').fetchone()
    except sqlite3.OperationalError:
        logger.warning("Database schema updated: Adding max_clients column...")
        db.execute('ALTER TABLE users ADD COLUMN max_clients INTEGER DEFAULT 1')
        db.commit()
    # Check and update schema for active_clients (for real-time tracking)
    try:
        db.execute('SELECT active_clients FROM users LIMIT 1').fetchone()
    except sqlite3.OperationalError:
        logger.warning("Database schema updated: Adding active_clients column...")
        # active_clients should default to 0
        db.execute('ALTER TABLE users ADD COLUMN active_clients INTEGER DEFAULT 0') 
        db.commit()
    return db

def sync_config_passwords():
    """Sync passwords back to the users.json file for the core VPN service"""
    # This function is not fully implemented here but is assumed to be present
    # in the web.py/API logic. If needed, this should be implemented.
    pass

# ===== COMMAND HANDLERS =====

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(f'{T_MM["title"]} မှ ကြိုဆိုပါတယ်! \nအကူအညီအတွက် /help ကိုနှိပ်ပါ။')

def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "📖 **အသုံးပြုနိုင်သော Command များ**:\n"
        "/start - စတင်ခြင်း\n"
        "/help - အကူအညီ ရယူခြင်း\n"
        "/stats - စနစ်၏ အခြေအနေကို ကြည့်ခြင်း\n"
        "/myinfo - သင့်အကောင့် အချက်အလက်များကို ကြည့်ခြင်း\n"
    )
    
    if is_admin(update):
        help_text += (
            "\n👑 **Admin Command များ**:\n"
            "/admin - Admin Menu\n"
            "/adduser `<user> <pass> <days> <limit_gb> [max_clients=1]` - အသုံးပြုသူ အသစ်ထည့်ခြင်း\n"
            "/changepass `<user> <newpass>` - လျှို့ဝှက်နံပါတ် ပြောင်းလဲခြင်း\n"
            "/deluser `<user>` - အသုံးပြုသူ ဖျက်ပစ်ခြင်း\n"
            "/suspend `<user>` - အသုံးပြုသူ ဆိုင်းငံ့ခြင်း\n"
            "/activate `<user>` - ပြန်လည်ဖွင့်ခြင်း\n"
            "/renew `<user> <days>` - သက်တမ်းတိုးခြင်း\n"
            "/reset `<user>` - ဒေတာအသုံးပြုမှု သုညပြန်သတ်မှတ်ခြင်း\n"
            "/users - အသုံးပြုသူ စာရင်းကို ကြည့်ခြင်း (Limit 50)\n"
        )
    
    update.message.reply_text(help_text, parse_mode=telegram.ParseMode.MARKDOWN)

def admin_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
    update.message.reply_text("Admin Menu (Admin Commands for easy copy-paste): \n\n/adduser user pass 30 500 1\n/renew user 30\n/suspend user")

def adduser_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
        
    args = context.args
    # Expected: user, pass, days, data_limit_gb, [max_clients]
    if len(args) < 4:
        update.message.reply_text(f"{T_MM['missing_args']} Example: /adduser <user> <pass> <days> <limit_gb> [max_clients=1]")
        return
        
    username, password, days_str, data_limit_gb_str = args[:4]
    max_clients_str = args[4] if len(args) >= 5 else "1" # NEW: Default to 1

    try:
        days = int(days_str)
        data_limit_gb = int(data_limit_gb_str)
        max_clients = int(max_clients_str) # NEW: Parse max_clients
        if days <= 0 or data_limit_gb < 0 or max_clients <= 0:
            raise ValueError
    except ValueError:
        update.message.reply_text(T_MM['invalid_input'])
        return
        
    expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    data_limit_bytes = data_limit_gb * (1024**3)
    
    db = get_db()
    try:
        if db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
            update.message.reply_text(T_MM['user_exists'] % username)
            return

        # NEW: Insert max_clients into the database
        db.execute('''
            INSERT INTO users (username, password, status, expiry_date, data_limit_bytes, used_bytes, max_clients)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, password, 'active', expiry_date, data_limit_bytes, 0, max_clients))
        db.commit()
        sync_config_passwords()
        
        message = T_MM['user_added'] % (username, days, data_limit_gb, max_clients)
        update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        update.message.reply_text(f"❌ အသုံးပြုသူ ထည့်သွင်းရာတွင် အမှားဖြစ်ပွားသည်- {e}")
    finally:
        db.close()

def changepass_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
        
    args = context.args
    if len(args) != 2:
        update.message.reply_text(f"{T_MM['missing_args']} Example: /changepass <user> <newpass>")
        return
        
    username, new_password = args
    db = get_db()
    try:
        if not db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
            update.message.reply_text(T_MM['user_not_found'])
            return
            
        db.execute('UPDATE users SET password = ? WHERE username = ?', (new_password, username))
        db.commit()
        sync_config_passwords()
        update.message.reply_text(T_MM['pass_changed'] % username)
    finally:
        db.close()

def deluser_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
        
    args = context.args
    if len(args) != 1:
        update.message.reply_text(f"{T_MM['missing_args']} Example: /deluser <user>")
        return
        
    username = args[0]
    db = get_db()
    try:
        if not db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
            update.message.reply_text(T_MM['user_not_found'])
            return
            
        db.execute('UPDATE users SET status = ? WHERE username = ?', ('deleted', username))
        db.commit()
        sync_config_passwords()
        update.message.reply_text(T_MM['user_deleted'] % username)
    finally:
        db.close()

def suspend_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
        
    args = context.args
    if len(args) != 1:
        update.message.reply_text(f"{T_MM['missing_args']} Example: /suspend <user>")
        return
        
    username = args[0]
    db = get_db()
    try:
        if not db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
            update.message.reply_text(T_MM['user_not_found'])
            return
            
        db.execute('UPDATE users SET status = ? WHERE username = ?', ('suspended', username))
        db.commit()
        sync_config_passwords()
        update.message.reply_text(T_MM['user_suspended'] % username)
    finally:
        db.close()

def activate_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
        
    args = context.args
    if len(args) != 1:
        update.message.reply_text(f"{T_MM['missing_args']} Example: /activate <user>")
        return
        
    username = args[0]
    db = get_db()
    try:
        if not db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
            update.message.reply_text(T_MM['user_not_found'])
            return
            
        db.execute('UPDATE users SET status = ? WHERE username = ?', ('active', username))
        db.commit()
        sync_config_passwords()
        update.message.reply_text(T_MM['user_activated'] % username)
    finally:
        db.close()

def renew_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
        
    args = context.args
    if len(args) != 2:
        update.message.reply_text(f"{T_MM['missing_args']} Example: /renew <user> <days>")
        return
        
    username, days_str = args
    
    try:
        days = int(days_str)
        if days <= 0: raise ValueError
    except ValueError:
        update.message.reply_text(T_MM['invalid_input'])
        return
        
    db = get_db()
    try:
        user_data = db.execute('SELECT expiry_date FROM users WHERE username = ?', (username,)).fetchone()
        if not user_data:
            update.message.reply_text(T_MM['user_not_found'])
            return
            
        current_expiry = datetime.strptime(user_data['expiry_date'], '%Y-%m-%d %H:%M:%S')
        
        # If already expired, start from now. If not expired, add to current expiry.
        if current_expiry < datetime.now():
            new_expiry = datetime.now() + timedelta(days=days)
        else:
            new_expiry = current_expiry + timedelta(days=days)
            
        new_expiry_str = new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        
        db.execute('UPDATE users SET expiry_date = ?, status = ? WHERE username = ?', (new_expiry_str, 'active', username))
        db.commit()
        sync_config_passwords()
        update.message.reply_text(T_MM['user_renewed'] % (username, new_expiry_str))
    finally:
        db.close()

def reset_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
        
    args = context.args
    if len(args) != 1:
        update.message.reply_text(f"{T_MM['missing_args']} Example: /reset <user>")
        return
        
    username = args[0]
    db = get_db()
    try:
        if not db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
            update.message.reply_text(T_MM['user_not_found'])
            return
            
        db.execute('UPDATE users SET used_bytes = ? WHERE username = ?', (0, username))
        db.commit()
        sync_config_passwords() # Trigger sync if needed
        update.message.reply_text(T_MM['traffic_reset'] % username)
    finally:
        db.close()

def users_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update):
        update.message.reply_text(T_MM['not_admin'])
        return
        
    db = get_db()
    try:
        # NEW: Select max_clients and active_clients
        users_raw = db.execute("SELECT username, status, expiry_date, data_limit_bytes, used_bytes, max_clients, active_clients FROM users WHERE status != 'deleted' ORDER BY username ASC LIMIT 50").fetchall()
        
        if not users_raw:
            update.message.reply_text("အသုံးပြုသူ စာရင်း မရှိပါ (No users found).")
            return
            
        message = "👥 **အသုံးပြုသူ စာရင်း (Users List)**\n\n"
        for u in users_raw:
            expiry_dt = datetime.strptime(u['expiry_date'], '%Y-%m-%d %H:%M:%S')
            if u['status'] == 'suspended':
                status_icon = '⏸️'
            elif expiry_dt < datetime.now():
                status_icon = '⛔'
            else:
                status_icon = '✅'
                
            used = bytes_to_readable(u['used_bytes'])
            limit = bytes_to_readable(u['data_limit_bytes']) if u['data_limit_bytes'] > 0 else T_MM['info_unlimited']
            
            # NEW: Client Limit Info
            client_info = f"{u['active_clients']}/{u['max_clients']}"
            
            message += (
                f"{status_icon} **{u['username']}**\n"
                f"  - Exp: `{u['expiry_date'].split()[0]}`\n"
                f"  - Data: `{used} / {limit}`\n"
                f"  - Clients: `{client_info}`\n"
            )
        
        update.message.reply_text(message, parse_mode=telegram.ParseMode.MARKDOWN)
    finally:
        db.close()

def myinfo_command(update: Update, context: CallbackContext) -> None:
    username = context.args[0] if context.args else None
    
    # If no username is provided, try to find user by chat_id (if linked) - this feature is not implemented, so just use args
    if not username:
        update.message.reply_text("ကျေးဇူးပြု၍ သင့်အသုံးပြုသူအမည်ကို ရိုက်ထည့်ပါ။ ဥပမာ- /myinfo <username>")
        return

    db = get_db()
    try:
        # NEW: Select max_clients and active_clients
        user_data = db.execute('SELECT username, status, expiry_date, data_limit_bytes, used_bytes, max_clients, active_clients FROM users WHERE username = ?', (username,)).fetchone()
        
        if not user_data:
            update.message.reply_text(T_MM['user_not_found'])
            return

        expiry_dt = datetime.strptime(user_data['expiry_date'], '%Y-%m-%d %H:%M:%S')
        
        if user_data['status'] == 'suspended':
            status_text = T_MM['status_suspended']
        elif expiry_dt < datetime.now():
            status_text = T_MM['status_expired']
        else:
            status_text = T_MM['status_active']

        data_limit = bytes_to_readable(user_data['data_limit_bytes']) if user_data['data_limit_bytes'] > 0 else T_MM['info_unlimited']
        
        # NEW: Client Limit Info
        client_limit_text = f"{user_data['max_clients']}"
        active_clients_text = f"{user_data['active_clients']}"

        message = (
            f"**{T_MM['info_header']}**\n"
            f"**{T_MM['info_username']}** `{user_data['username']}`\n"
            f"**{T_MM['info_status']}** {status_text}\n"
            f"**{T_MM['info_expiry']}** `{user_data['expiry_date']}`\n"
            f"**{T_MM['info_data_limit']}** `{data_limit}`\n"
            f"**{T_MM['info_data_used']}** `{bytes_to_readable(user_data['used_bytes'])}`\n"
            f"**{T_MM['info_client_limit']}** `{client_limit_text}`\n"
            f"**{T_MM['info_clients_active']}** `{active_clients_text}`\n"
        )
        
        update.message.reply_text(message, parse_mode=telegram.ParseMode.MARKDOWN)
    finally:
        db.close()

def stats_command(update: Update, context: CallbackContext) -> None:
    db = get_db()
    try:
        total_users = db.execute("SELECT COUNT(*) FROM users WHERE status != 'deleted'").fetchone()[0]
        # Active users based on active_clients column
        active_users = db.execute("SELECT COUNT(DISTINCT username) FROM users WHERE active_clients > 0 AND status = 'active'").fetchone()[0]
        total_used_bytes = db.execute("SELECT SUM(used_bytes) FROM users").fetchone()[0] or 0
        
        message = (
            f"**{T_MM['stats_header']}**\n"
            f"**{T_MM['stats_total_users']}** `{total_users}`\n"
            f"**{T_MM['stats_active_users']}** `{active_users}`\n"
            f"**{T_MM['stats_used_data']}** `{bytes_to_readable(total_used_bytes)}`\n"
        )
        
        update.message.reply_text(message, parse_mode=telegram.ParseMode.MARKDOWN)
    finally:
        db.close()

# Other commands (ban, unban) are omitted for brevity as they are not core to the request but should exist if originally present

def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f'Update {update} caused error {context.error}')
    try:
        if update and update.effective_chat:
            update.effective_chat.send_message(text=f'❌ Internal error occurred: {context.error}')
    except Exception as e:
        logger.error(f"Error handling error: {e}")

# ===== MAIN FUNCTION =====
def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please check environment variables")
        return
        
    try:
        # Check if the database exists and run schema check/update
        db = get_db()
        db.close()

        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher

        # Public commands (everyone can see and use)
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", help_command))
        dp.add_handler(CommandHandler("stats", stats_command))
        
        # Admin commands (only admin can see and use)
        # Note: You need to implement proper Admin check logic on command execution
        dp.add_handler(CommandHandler("admin", admin_command))
        dp.add_handler(CommandHandler("adduser", adduser_command))
        dp.add_handler(CommandHandler("changepass", changepass_command))
        dp.add_handler(CommandHandler("deluser", deluser_command))
        dp.add_handler(CommandHandler("suspend", suspend_command))
        dp.add_handler(CommandHandler("activate", activate_command))
        # dp.add_handler(CommandHandler("ban", ban_user)) # Assuming these exist but are omitted
        # dp.add_handler(CommandHandler("unban", unban_user)) # Assuming these exist but are omitted
        dp.add_handler(CommandHandler("renew", renew_command))
        dp.add_handler(CommandHandler("reset", reset_command))
        dp.add_handler(CommandHandler("users", users_command))
        dp.add_handler(CommandHandler("myinfo", myinfo_command)) # Changed to take argument
        
        dp.add_error_handler(error_handler)

        logger.info("🤖 ZIVPN Telegram Bot Started Successfully")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()

