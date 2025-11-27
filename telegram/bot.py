#!/usr/bin/env python3
"""
ZIVPN Telegram Bot - Enhanced Version with Connection Management
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
import requests

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")
BOT_TOKEN = "8514909413:AAETX4LGVYd3HR-O2Yr38OJdQmW3hGrEBF0"
CONFIG_FILE = "/etc/zivpn/config.json"
WEB_PANEL_URL = "http://localhost:19432"

# Admin configuration
ADMIN_IDS = [7576434717, 7240495054]  # Telegram ID

# ===== Enhanced Functions =====

def get_connection_dashboard():
    """Get connection dashboard data from web panel"""
    try:
        response = requests.get(f"{WEB_PANEL_URL}/connections", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
    return None

def get_user_devices(username):
    """Get user's registered devices"""
    try:
        response = requests.get(f"{WEB_PANEL_URL}/user/{username}/devices", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
    return []

def set_user_schedule(username, schedule_data):
    """Set user connection schedule"""
    try:
        response = requests.post(
            f"{WEB_PANEL_URL}/user/{username}/schedule",
            json=schedule_data,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error setting schedule: {e}")
    return False

# ===== Existing Functions (keep all existing ones) =====

def sync_config_passwords():
    """Sync passwords from database to ZIVPN config"""
    # ... keep existing implementation ...

def get_server_ip():
    """Get server IP address"""
    # ... keep existing implementation ...

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def format_bytes(size):
    """Format bytes to human readable format"""
    # ... keep existing implementation ...

def start(update, context):
    """Send welcome message - PUBLIC"""
    user_id = update.effective_user.id
    is_user_admin = is_admin(user_id)
    
    welcome_text = f"""
🤖 *ZIVPN Management Bot*
🌐 Server: `{get_server_ip()}`

*Available Commands:*
/start - Show this welcome message  
/stats - Show server statistics
/help - Show help message
"""
    
    # Only show admin commands to admin users
    if is_user_admin:
        welcome_text += """
*🛠️ Admin Commands:*
/admin - Admin panel
/adduser <user> <pass> [days] - Add user
/changepass <user> <newpass> - Change password
/deluser <username> - Delete user
/suspend <username> - Suspend user
/activate <username> - Activate user
/ban <username> - Ban user
/unban <username> - Unban user
/renew <username> <days> - Renew user
/reset <username> <days> - Reset expiry
/users - List all users with passwords
/myinfo <username> - User details with password
/connections - Connection dashboard
/devices <username> - Show user devices
/schedule <username> <start> <end> <days> - Set schedule
"""
    
    welcome_text += """

*ဖွင့်သောအမိန့်များ:*
/start - ကြိုဆိုစာကိုပြပါ
/stats - ဆာဗာစာရင်းဇယား
/help - အကူအညီစာကိုပြပါ
"""
    
    update.message.reply_text(welcome_text, parse_mode='Markdown')

# ===== Enhanced Admin Commands =====

def connections_command(update, context):
    """Show connection dashboard - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    dashboard_data = get_connection_dashboard()
    if not dashboard_data:
        update.message.reply_text("❌ Error getting connection data")
        return
    
    connections_text = f"""
📊 *Real-time Connection Dashboard*

🟢 Total Active Connections: *{dashboard_data.get('total_active_connections', 0)}*
👥 Total Registered Users: *{dashboard_data.get('total_registered_users', 0)}*
🕐 Last Updated: {dashboard_data.get('timestamp', 'N/A')}

*Connection Summary:*
"""
    
    # Add connections by port
    connections_by_port = dashboard_data.get('connections_by_port', {})
    for port, connections in list(connections_by_port.items())[:10]:  # Show first 10 ports
        connections_text += f"Port {port}: *{len(connections)}* connections\n"
    
    # Add user statistics
    user_stats = dashboard_data.get('user_statistics', [])
    online_users = sum(1 for user in user_stats if user.get('status') == 'active')
    
    connections_text += f"\n👤 Online Users: *{online_users}*"
    connections_text += f"\n💻 Total Devices: *{sum(user.get('registered_devices', 0) for user in user_stats)}*"
    
    update.message.reply_text(connections_text, parse_mode='Markdown')

def devices_command(update, context):
    """Show user devices - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /devices <username>")
        return
    
    username = context.args[0]
    devices = get_user_devices(username)
    
    if not devices:
        update.message.reply_text(f"❌ No devices found for user `{username}`")
        return
    
    devices_text = f"""
📱 *Registered Devices for {username}*

"""
    
    for i, device in enumerate(devices, 1):
        devices_text += f"{i}. *Device Hash:* `{device.get('device_hash', 'N/A')}`\n"
        devices_text += f"   *MAC:* {device.get('mac_address', 'N/A')}\n"
        devices_text += f"   *IP:* {device.get('client_ip', 'N/A')}\n"
        devices_text += f"   *Last Seen:* {device.get('last_seen', 'N/A')}\n\n"
    
    update.message.reply_text(devices_text, parse_mode='Markdown')

def schedule_command(update, context):
    """Set user connection schedule - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 4:
        update.message.reply_text("Usage: /schedule <username> <start_hour> <end_hour> <days>\nExample: /schedule john 08:00 23:00 mon,tue,wed,thu,fri,sat,sun")
        return
    
    username = context.args[0]
    start_time = context.args[1]
    end_time = context.args[2]
    days = context.args[3].split(',')
    
    # Validate time format
    try:
        datetime.strptime(start_time, "%H:%M")
        datetime.strptime(end_time, "%H:%M")
    except ValueError:
        update.message.reply_text("❌ Invalid time format. Use HH:MM (24-hour format)")
        return
    
    # Validate days
    valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    days_lower = [day.lower() for day in days]
    
    for day in days_lower:
        if day not in [d[:3] for d in valid_days] and day not in valid_days:
            update.message.reply_text(f"❌ Invalid day: {day}. Use: mon,tue,wed,thu,fri,sat,sun or full names")
            return
    
    # Convert short day names to full names
    day_mapping = {
        'mon': 'monday', 'tue': 'tuesday', 'wed': 'wednesday',
        'thu': 'thursday', 'fri': 'friday', 'sat': 'saturday', 'sun': 'sunday'
    }
    
    full_days = [day_mapping.get(day, day) for day in days_lower]
    
    schedule_data = {
        "allowed_hours": {
            "start": start_time,
            "end": end_time
        },
        "allowed_days": full_days
    }
    
    if set_user_schedule(username, schedule_data):
        schedule_text = f"""
✅ *Connection Schedule Set for {username}*

⏰ Allowed Hours: *{start_time} - {end_time}*
📅 Allowed Days: *{', '.join(full_days)}*

User can only connect during these specified times.
"""
        update.message.reply_text(schedule_text, parse_mode='Markdown')
    else:
        update.message.reply_text("❌ Error setting schedule")

# ===== Keep ALL existing command functions =====
# (adduser_command, changepass_command, deluser_command, suspend_command, 
# activate_command, ban_user, unban_user, renew_command, reset_command, 
# stats_command, users_command, myinfo_command, help_command, admin_command)

def adduser_command(update, context):
    # ... keep existing implementation exactly as is ...

def changepass_command(update, context):
    # ... keep existing implementation exactly as is ...

def deluser_command(update, context):
    # ... keep existing implementation exactly as is ...

def suspend_command(update, context):
    # ... keep existing implementation exactly as is ...

def activate_command(update, context):
    # ... keep existing implementation exactly as is ...

def ban_user(update, context):
    # ... keep existing implementation exactly as is ...

def unban_user(update, context):
    # ... keep existing implementation exactly as is ...

def renew_command(update, context):
    # ... keep existing implementation exactly as is ...

def reset_command(update, context):
    # ... keep existing implementation exactly as is ...

def stats_command(update, context):
    # ... keep existing implementation exactly as is ...

def users_command(update, context):
    # ... keep existing implementation exactly as is ...

def myinfo_command(update, context):
    # ... keep existing implementation exactly as is ...

def help_command(update, context):
    # ... keep existing implementation exactly as is ...

def admin_command(update, context):
    """Enhanced Admin panel with new features"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    # Get total user count
    db = get_db()
    total_users = db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    active_users = db.execute('SELECT COUNT(*) as count FROM users WHERE status = "active"').fetchone()['count']
    db.close()
    
    admin_text = f"""
🛠️ *Enhanced Admin Panel*
🌐 Server IP: `{get_server_ip()}`
📊 Total Users: *{total_users}* (Active: *{active_users}*)

*User Management:*
• /adduser <user> <pass> [days] - Add new user
• /changepass <user> <newpass> - Change password
• /deluser <username> - Delete user
• /suspend <username> - Suspend user  
• /activate <username> - Activate user
• /ban <username> - Ban user
• /unban <username> - Unban user
• /renew <username> <days> - Renew user
• /reset <username> <days> - Reset expiry

*Connection Management:*
• /connections - Real-time dashboard
• /devices <username> - Show user devices  
• /schedule <username> <start> <end> <days> - Set connection schedule

*Information:*
• /users - List all users with passwords
• /myinfo <username> - User details with password
• /stats - Server statistics

*Usage Examples:*
/connections - View live connections
/devices john - See John's devices  
/schedule john 08:00 23:00 mon,tue,wed,thu,fri - Set business hours
"""
    update.message.reply_text(admin_text, parse_mode='Markdown')

def error_handler(update, context):
    """Log errors"""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in environment variables")
        return
        
    try:
        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher

        # Public commands (everyone can see and use)
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", help_command))
        dp.add_handler(CommandHandler("stats", stats_command))
        
        # Admin commands (only admin can see and use)
        dp.add_handler(CommandHandler("admin", admin_command))
        dp.add_handler(CommandHandler("adduser", adduser_command))
        dp.add_handler(CommandHandler("changepass", changepass_command))
        dp.add_handler(CommandHandler("deluser", deluser_command))
        dp.add_handler(CommandHandler("suspend", suspend_command))
        dp.add_handler(CommandHandler("activate", activate_command))
        dp.add_handler(CommandHandler("ban", ban_user))
        dp.add_handler(CommandHandler("unban", unban_user))
        dp.add_handler(CommandHandler("renew", renew_command))
        dp.add_handler(CommandHandler("reset", reset_command))
        dp.add_handler(CommandHandler("users", users_command))
        dp.add_handler(CommandHandler("myinfo", myinfo_command))
        
        # Enhanced connection management commands
        dp.add_handler(CommandHandler("connections", connections_command))
        dp.add_handler(CommandHandler("devices", devices_command))
        dp.add_handler(CommandHandler("schedule", schedule_command))

        dp.add_error_handler(error_handler)

        logger.info("🤖 ZIVPN Enhanced Telegram Bot Started Successfully")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
