#!/usr/bin/env python3
"""
ZIVPN Telegram Bot - Unlimited Users Version
MODIFIED: Added support for `is_enabled` and `data_limit_gb` columns from Web Panel changes.
"""
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, filters
import sqlite3
import logging
import os
from datetime import datetime, timedelta
import socket
import json
import tempfile
import subprocess
import uuid # ⬅️ ADDED: For UUID generation in adduser

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8514909413:AAETX4LGVYd3HR-O2Yr38OJdQmW3hGrEBF0") # Use env var if available
CONFIG_FILE = "/etc/zivpn/config.json"

# Admin configuration - ONLY YOUR ID CAN SEE ADMIN COMMANDS
# NOTE: The Admin IDs below are placeholder/example values. Replace with real Admin IDs.
ADMIN_IDS = [7576434717, 7240495054]  # Telegram ID
# Convert to integer set for quick lookup
ADMIN_IDS = set([int(uid) for uid in ADMIN_IDS])

# --- Utility Functions ---

def read_json(path, default):
    try:
        with open(path,"r") as f: return json.load(f)
    except Exception:
        return default

def write_json_atomic(path, data):
    d=json.dumps(data, ensure_ascii=False, indent=2)
    dirn=os.path.dirname(path); fd,tmp=tempfile.mkstemp(prefix=".tmp-", dir=dirn)
    try:
        with os.fdopen(fd, 'w') as f: f.write(d)
        os.replace(tmp, path)
        return True
    except Exception as e:
        logger.error(f"Error writing to {path}: {e}")
        os.unlink(tmp)
        return False

def sync_config_passwords():
    """Reads all ENABLED user passwords from the DB and syncs them to the users.json file."""
    USERS_FILE = "/etc/zivpn/users.json"
    try:
        db = get_db()
        # ⬅️ MODIFIED: Select only enabled users (is_enabled=1)
        users_data = db.execute('SELECT username, password FROM users WHERE is_enabled = 1').fetchall()
        db.close()
        
        sync_data = {}
        for row in users_data:
            user = dict(row)
            sync_data[user['username']] = user['password']
                
        return write_json_atomic(USERS_FILE, sync_data)
    except Exception as e:
        logger.error(f"Error syncing user config: {e}")
        return False

def get_db():
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row 
    return db

def bytesToGB(bytes_val):
    if bytes_val is None: return "N/A"
    if bytes_val == 0: return "0 B"
    gb = bytes_val / (1024 ** 3)
    return f"{gb:.2f} GB"

def is_admin(update):
    return update.effective_user.id in ADMIN_IDS

def restricted(func):
    """Decorator to restrict access to admin commands."""
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            logger.warning(f"Unauthorized access denied for {user_id} trying to use {func.__name__}")
            update.message.reply_text("⛔ Access Denied. You are not an administrator.")
            return
        return func(update, context, *args, **kwargs)
    return wrapped

# --- Telegram Command Handlers ---

def start(update, context):
    """Sends a welcome message."""
    user = update.effective_user
    welcome_msg = f"👋 Hello {user.first_name}!\n\nThis is the ZIVPN Enterprise Management Bot.\n"
    
    if is_admin(update):
        welcome_msg += "✅ You are an Admin. Use /admin for management commands.\n"
    else:
        welcome_msg += "To check your account info, use /myinfo.\n"
        
    update.message.reply_markdown_v2(welcome_msg)

def help_command(update, context):
    """Sends help message."""
    help_text = "📚 *Available Commands:*\n"
    help_text += "/stats \- Show server connection summary\n"
    help_text += "/myinfo \- Show your account details\n"
    
    if is_admin(update):
        help_text += "\n👑 *Admin Commands:*\n"
        help_text += "/admin \- Show all admin commands\n"
        help_text += "/adduser `<user> <expiry> [limit_gb]` \- Add user\n"
        help_text += "/deluser `<user>` \- Delete user\n"
        help_text += "/renew `<user> <YYYY-MM-DD>` \- Renew expiry\n"
        help_text += "/suspend `<user>` \- Temporarily disable user\n"
        help_text += "/activate `<user>` \- Re-enable suspended user\n"
        help_text += "/changepass `<user> <new_pass>` \- Change password\n"
        help_text += "/users \- List all users\n"
        
    update.message.reply_markdown_v2(help_text)

@restricted
def admin_command(update, context):
    """Shows all admin commands."""
    help_command(update, context)

@restricted
def adduser_command(update, context):
    """
    Handles /adduser <username> <expiry> [limit_gb]
    If limit_gb is omitted or 0, it's unlimited.
    """
    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text("Usage: /adduser <username> <YYYY-MM-DD> [limit_gb (0=unlimited)]")
            return

        username = args[0]
        expiry_date_str = args[1]
        
        # ⬅️ MODIFIED: Get data limit argument
        data_limit_gb = float(args[2]) if len(args) > 2 else 0.0
        
        # Generate UUID as password
        password = str(uuid.uuid4())
        
        try:
            # Validate date format
            datetime.strptime(expiry_date_str, '%Y-%m-%d')
        except ValueError:
            update.message.reply_text("❌ Invalid expiry date format. Use YYYY-MM-DD.")
            return

        db = get_db()
        try:
            # Check if user exists
            if db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
                update.message.reply_text(f"❌ User '{username}' already exists.")
                return

            # ⬅️ MODIFIED: Insert with UUID password, is_enabled=1, and data_limit_gb
            db.execute('''
                INSERT INTO users (username, password, expiry_date, created_at, is_enabled, data_limit_gb)
                VALUES (?, ?, ?, ?, 1, ?)
            ''', (username, password, expiry_date_str, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data_limit_gb))
            db.commit()
            
            sync_config_passwords()
            
            limit_info = f"{data_limit_gb} GB" if data_limit_gb > 0 else "Unlimited"
            
            update.message.reply_text(
                f"✅ User '{username}' added successfully!\n"
                f"Password (UUID): `{password}`\n"
                f"Expiry: {expiry_date_str}\n"
                f"Data Limit: {limit_info}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"DB Error in adduser: {e}")
            update.message.reply_text(f"❌ An error occurred while adding user: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in adduser_command: {e}")
        update.message.reply_text("❌ An unexpected error occurred. Check logs.")


@restricted
def deluser_command(update, context):
    """Handles /deluser <username>"""
    if not context.args:
        update.message.reply_text("Usage: /deluser <username>")
        return

    username = context.args[0]
    db = get_db()
    try:
        cursor = db.execute('DELETE FROM users WHERE username = ?', (username,))
        db.commit()
        if cursor.rowcount > 0:
            sync_config_passwords()
            update.message.reply_text(f"✅ User '{username}' deleted successfully.")
        else:
            update.message.reply_text(f"❌ User '{username}' not found.")
    except Exception as e:
        logger.error(f"DB Error in deluser: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()

@restricted
def renew_command(update, context):
    """Handles /renew <username> <YYYY-MM-DD>"""
    if len(context.args) != 2:
        update.message.reply_text("Usage: /renew <username> <YYYY-MM-DD>")
        return

    username = context.args[0]
    new_expiry_date = context.args[1]

    try:
        datetime.strptime(new_expiry_date, '%Y-%m-%d')
    except ValueError:
        update.message.reply_text("❌ Invalid expiry date format. Use YYYY-MM-DD.")
        return

    db = get_db()
    try:
        cursor = db.execute('UPDATE users SET expiry_date = ? WHERE username = ?', (new_expiry_date, username))
        db.commit()
        if cursor.rowcount > 0:
            update.message.reply_text(f"✅ User '{username}' expiry updated to {new_expiry_date}.")
        else:
            update.message.reply_text(f"❌ User '{username}' not found.")
    except Exception as e:
        logger.error(f"DB Error in renew: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()

@restricted
def changepass_command(update, context):
    """Handles /changepass <username> <new_password>"""
    if len(context.args) != 2:
        update.message.reply_text("Usage: /changepass <username> <new_password>")
        return

    username = context.args[0]
    new_password = context.args[1]

    db = get_db()
    try:
        cursor = db.execute('UPDATE users SET password = ? WHERE username = ?', (new_password, username))
        db.commit()
        if cursor.rowcount > 0:
            sync_config_passwords()
            update.message.reply_text(f"✅ User '{username}' password changed to `{new_password}`.", parse_mode='Markdown')
        else:
            update.message.reply_text(f"❌ User '{username}' not found.")
    except Exception as e:
        logger.error(f"DB Error in changepass: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()

@restricted
def suspend_command(update, context):
    """
    ⬅️ MODIFIED: Suspend user by setting is_enabled = 0
    Handles /suspend <username>
    """
    if not context.args:
        update.message.reply_text("Usage: /suspend <username>")
        return

    username = context.args[0]
    db = get_db()
    try:
        # Set is_enabled = 0 (Disabled)
        cursor = db.execute('UPDATE users SET is_enabled = 0 WHERE username = ?', (username,))
        db.commit()
        if cursor.rowcount > 0:
            sync_config_passwords()
            update.message.reply_text(f"⏸️ User '{username}' has been temporarily suspended (Disabled).")
        else:
            update.message.reply_text(f"❌ User '{username}' not found.")
    except Exception as e:
        logger.error(f"DB Error in suspend: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()

@restricted
def activate_command(update, context):
    """
    ⬅️ MODIFIED: Activate user by setting is_enabled = 1
    Handles /activate <username>
    """
    if not context.args:
        update.message.reply_text("Usage: /activate <username>")
        return

    username = context.args[0]
    db = get_db()
    try:
        # Set is_enabled = 1 (Enabled)
        cursor = db.execute('UPDATE users SET is_enabled = 1 WHERE username = ?', (username,))
        db.commit()
        if cursor.rowcount > 0:
            sync_config_passwords()
            update.message.reply_text(f"▶️ User '{username}' has been re-activated (Enabled).")
        else:
            update.message.reply_text(f"❌ User '{username}' not found.")
    except Exception as e:
        logger.error(f"DB Error in activate: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()
        
# Ban/Unban commands are kept as they manage the `is_banned` flag, which is
# likely independent of the new `is_enabled` (Suspend/Activate) feature.
@restricted
def ban_user(update, context):
    """Handles /ban <username>"""
    if not context.args:
        update.message.reply_text("Usage: /ban <username>")
        return

    username = context.args[0]
    db = get_db()
    try:
        # Assuming a separate 'is_banned' column exists or suspending serves as banning
        # For ZIVPN's logic, let's assume it manages a `is_banned` column or similar logic
        # For simplicity based on common patterns, let's just use SUSPEND/ACTIVATE for now.
        # If the ZIVPN core requires a separate 'banned' state, we need that column.
        
        # If your ZIVPN uses `is_enabled=0` for banning, use /suspend.
        # If it uses a separate column (e.g., `is_banned`), the query below needs adjustment.
        
        # For now, we will map 'ban' to `is_enabled=0` for simplicity
        cursor = db.execute('UPDATE users SET is_enabled = 0 WHERE username = ?', (username,))
        db.commit()
        if cursor.rowcount > 0:
            sync_config_passwords()
            update.message.reply_text(f"🚫 User '{username}' has been banned (Set to Disabled).")
        else:
            update.message.reply_text(f"❌ User '{username}' not found.")
    except Exception as e:
        logger.error(f"DB Error in ban: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()

@restricted
def unban_user(update, context):
    """Handles /unban <username>"""
    if not context.args:
        update.message.reply_text("Usage: /unban <username>")
        return

    username = context.args[0]
    db = get_db()
    try:
        # For now, we will map 'unban' to `is_enabled=1` for simplicity
        cursor = db.execute('UPDATE users SET is_enabled = 1 WHERE username = ?', (username,))
        db.commit()
        if cursor.rowcount > 0:
            sync_config_passwords()
            update.message.reply_text(f"✅ User '{username}' has been unbanned (Set to Enabled).")
        else:
            update.message.reply_text(f"❌ User '{username}' not found.")
    except Exception as e:
        logger.error(f"DB Error in unban: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()
        

@restricted
def reset_command(update, context):
    """Handles /reset <username> (Reset bandwidth usage)"""
    if not context.args:
        update.message.reply_text("Usage: /reset <username>")
        return

    username = context.args[0]
    db = get_db()
    try:
        # Assuming `bytes_used` column exists for usage tracking
        cursor = db.execute('UPDATE users SET bytes_used = 0 WHERE username = ?', (username,))
        db.commit()
        if cursor.rowcount > 0:
            update.message.reply_text(f"♻️ User '{username}' bandwidth usage has been reset to 0.")
        else:
            update.message.reply_text(f"❌ User '{username}' not found.")
    except Exception as e:
        logger.error(f"DB Error in reset: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()


@restricted
def users_command(update, context):
    """Lists all users with their status and usage."""
    db = get_db()
    try:
        # ⬅️ MODIFIED: Include is_enabled and data_limit_gb
        users = db.execute('''
            SELECT username, expiry_date, bytes_used, is_enabled, data_limit_gb 
            FROM users 
            ORDER BY username ASC
        ''').fetchall()
        
        if not users:
            update.message.reply_text("No users found in the system.")
            return

        message = "👥 *User List:*\n"
        for user in users:
            expiry = user['expiry_date']
            usage = bytesToGB(user['bytes_used'])
            
            # ⬅️ ADDED: Status and Data Limit Info
            status = "✅ Enabled" if user['is_enabled'] == 1 else "❌ Disabled"
            limit_info = f"Limit: {user['data_limit_gb']} GB" if user['data_limit_gb'] > 0 else "Limit: Unlimited"
            
            message += f"• `{user['username']}` \- {status}, {limit_info}\n"
            message += f"  Usage: {usage} \| Expiry: {expiry}\n"
            
        # Send in multiple messages if too long
        max_len = 4096
        if len(message) > max_len:
            messages = [message[i:i + max_len] for i in range(0, len(message), max_len)]
            for msg in messages:
                update.message.reply_markdown_v2(msg)
        else:
            update.message.reply_markdown_v2(message)
            
    except Exception as e:
        logger.error(f"DB Error in users_command: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()

def myinfo_command(update, context):
    """Shows current user's account information."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username or str(chat_id) # Fallback to chat_id if no username

    db = get_db()
    try:
        # ⬅️ MODIFIED: Select new columns
        user_info = db.execute('''
            SELECT username, expiry_date, bytes_used, created_at, is_enabled, data_limit_gb 
            FROM users 
            WHERE username = ? OR telegram_id = ?
        ''', (username, chat_id)).fetchone()
        
        if not user_info:
            update.message.reply_text("❌ Account not found. Contact administrator.")
            return

        expiry = user_info['expiry_date']
        usage = bytesToGB(user_info['bytes_used'])
        created_at = user_info['created_at'].split(' ')[0]
        
        # ⬅️ ADDED: Status and Data Limit Info
        status = "✅ Enabled" if user_info['is_enabled'] == 1 else "❌ Disabled"
        limit_gb = user_info['data_limit_gb']
        limit_info = f"{limit_gb:.2f} GB" if limit_gb > 0 else "Unlimited"

        message = f"👤 *Your Account Info:*\n"
        message += f"• *Username:* `{user_info['username']}`\n"
        message += f"• *Status:* {status}\n" # ⬅️ ADDED
        message += f"• *Data Used:* {usage}\n"
        message += f"• *Data Limit:* {limit_info}\n" # ⬅️ ADDED
        message += f"• *Expiry Date:* {expiry}\n"
        message += f"• *Created:* {created_at}"

        update.message.reply_markdown_v2(message)
            
    except Exception as e:
        logger.error(f"DB Error in myinfo_command: {e}")
        update.message.reply_text(f"❌ An error occurred: {e}")
    finally:
        db.close()


def stats_command(update, context):
    """Shows server stats (placeholder for core ZIVPN stats)."""
    db = get_db()
    try:
        # ⬅️ MODIFIED: Total Users and Enabled Users (for dashboard consistency)
        summary = db.execute("""
            SELECT 
                COUNT(username) AS total_users,
                SUM(CASE WHEN is_enabled = 1 THEN 1 ELSE 0 END) AS enabled_users,
                SUM(bytes_used) AS total_bytes_used
            FROM users
        """).fetchone()

        total_users = summary['total_users']
        enabled_users = summary['enabled_users']
        total_usage = bytesToGB(summary['total_bytes_used'])
        
        # This part depends on ZIVPN core's real-time connection tracking
        online_count = 0
        try:
             # Placeholder for getting real-time online count
             # You might need to query a separate connections table or a ZIVPN API
             # For now, we'll set it to 0 or try a simple approximation
             # Assuming last_seen column is frequently updated by the core
            time_threshold = (datetime.now() - timedelta(seconds=120)).strftime('%Y-%m-%d %H:%M:%S')
            online_count = db.execute("""
                SELECT COUNT(username) FROM users 
                WHERE last_seen > ? AND is_enabled = 1
            """, (time_threshold,)).fetchone()[0]

        except Exception as e:
             logger.warning(f"Could not fetch online count: {e}")
             online_count = "N/A" # Fallback

        message = "📊 *Server Statistics:*\n"
        message += f"• *Total Users:* {total_users}\n"
        message += f"• *Enabled Users:* {enabled_users}\n"
        message += f"• *Online Users:* {online_count}\n"
        message += f"• *Total Bandwidth Used:* {total_usage}"
        
        update.message.reply_markdown_v2(message)

    except Exception as e:
        logger.error(f"DB Error in stats_command: {e}")
        update.message.reply_text(f"❌ An error occurred while fetching stats: {e}")
    finally:
        db.close()


def error_handler(update, context):
    """Log Errors caused by Updates."""
    logger.warning(f'Update "{update}" caused error "{context.error}"')

# --- Main Bot Execution ---

def main():
    """Start the bot."""
    if not BOT_TOKEN or not all(ADMIN_IDS):
        logger.error("❌ ERROR: BOT_TOKEN or ADMIN_IDS are not set. Check environment variables")
        return
        
    try:
        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher

        # Public commands
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", help_command))
        dp.add_handler(CommandHandler("stats", stats_command))
        dp.add_handler(CommandHandler("myinfo", myinfo_command)) # Available to all users

        # Admin commands
        dp.add_handler(CommandHandler("admin", admin_command))
        dp.add_handler(CommandHandler("adduser", adduser_command))
        dp.add_handler(CommandHandler("changepass", changepass_command))
        dp.add_handler(CommandHandler("deluser", deluser_command))
        dp.add_handler(CommandHandler("suspend", suspend_command)) # ⬅️ MODIFIED to use is_enabled=0
        dp.add_handler(CommandHandler("activate", activate_command)) # ⬅️ MODIFIED to use is_enabled=1
        dp.add_handler(CommandHandler("ban", ban_user)) # Mapped to is_enabled=0
        dp.add_handler(CommandHandler("unban", unban_user)) # Mapped to is_enabled=1
        dp.add_handler(CommandHandler("renew", renew_command))
        dp.add_handler(CommandHandler("reset", reset_command))
        dp.add_handler(CommandHandler("users", users_command))
        
        dp.add_error_handler(error_handler)

        logger.info("🤖 ZIVPN Telegram Bot Started Successfully")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    # Ensure the user config is synced on bot startup
    sync_config_passwords()
    main()
