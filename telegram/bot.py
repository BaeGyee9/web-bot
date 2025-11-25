#!/usr/bin/env python3
"""
ZIVPN Enhanced Telegram Bot - Real-time Monitoring & Advanced Features
Unlimited Users Version with Connection Tracking
"""

import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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

# Enhanced Configuration
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8514909413:AAETX4LGVYd3HR-O2Yr38OJdQmW3hGrEBF0")
CONFIG_FILE = "/etc/zivpn/config.json"
WEB_PANEL_URL = os.environ.get("WEB_PANEL_URL", "")

# Admin configuration
ADMIN_IDS = [7576434717, 7240495054]  # Telegram ID

# ===== Enhanced Utility Functions =====

def get_server_ip():
    """Get server IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return os.environ.get("SERVER_IP", "43.249.33.233")

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
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

def get_real_time_stats():
    """Get real-time server statistics"""
    db = get_db()
    try:
        stats = db.execute('''
            SELECT
                COUNT(*) as total_users,
                SUM(CASE WHEN status = "active" AND (expires IS NULL OR expires >= date('now')) THEN 1 ELSE 0 END) as active_users,
                SUM(bandwidth_used) as total_bandwidth,
                SUM(CASE WHEN is_online = 1 THEN 1 ELSE 0 END) as online_now
            FROM users
        ''').fetchone()
        
        # Today's activity
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_stats = db.execute('''
            SELECT 
                COUNT(DISTINCT username) as today_users,
                SUM(bytes_sent + bytes_received) as today_bandwidth
            FROM connection_logs 
            WHERE connect_time >= ?
        ''', (today_start,)).fetchone()
        
        # Online users details
        online_users = db.execute('''
            SELECT username, last_ip, last_login 
            FROM users 
            WHERE is_online = 1 
            ORDER BY last_login DESC
        ''').fetchall()
        
        return {
            'total_users': stats['total_users'] or 0,
            'active_users': stats['active_users'] or 0,
            'online_now': stats['online_now'] or 0,
            'total_bandwidth': stats['total_bandwidth'] or 0,
            'today_users': today_stats['today_users'] or 0,
            'today_bandwidth': today_stats['today_bandwidth'] or 0,
            'online_users': [dict(u) for u in online_users]
        }
    finally:
        db.close()

# ===== Enhanced Bot Commands =====

def start(update, context):
    """Enhanced start command with real-time features"""
    user_id = update.effective_user.id
    is_user_admin = is_admin(user_id)
    
    server_ip = get_server_ip()
    stats = get_real_time_stats()
    
    welcome_text = f"""
🤖 *ZIVPN Enterprise Management Bot*
🌐 Server: `{server_ip}`
📊 Online Now: *{stats['online_now']}* users

*Available Commands:*
/start - Show this welcome message  
/stats - Enhanced server statistics
/help - Show help message
"""
    
    # Only show admin commands to admin users
    if is_user_admin:
        welcome_text += """
*🛠️ Admin Commands:*
/admin - Enhanced admin panel
/adduser <user> <pass> [days] - Add user
/changepass <user> <newpass> - Change password
/deluser <username> - Delete user
/online - Show online users
/userinfo <username> - Detailed user info
/estats - Real-time statistics
/users - List all users with passwords
"""
    
    welcome_text += """

*ဖွင့်သောအမိန့်များ:*
/start - ကြိုဆိုစာကိုပြပါ
/stats - ဆာဗာစာရင်းဇယား
/help - အကူအညီစာကိုပြပါ
"""
    
    # Add inline buttons for quick actions
    keyboard = []
    if is_user_admin:
        keyboard.append([
            InlineKeyboardButton("📊 Live Stats", callback_data="live_stats"),
            InlineKeyboardButton("👥 Online Users", callback_data="online_users")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

def enhanced_stats_command(update, context):
    """Enhanced statistics with real-time data"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ Admin only command")
        return
        
    stats = get_real_time_stats()
    server_ip = get_server_ip()
    
    stats_text = f"""
📊 *Enhanced Server Statistics*
🌐 Server: `{server_ip}`
🕒 Last Updated: {datetime.now().strftime('%H:%M:%S')}

👥 Total Users: *{stats['total_users']}*
🟢 Active Users: *{stats['active_users']}*
🔴 Inactive Users: *{stats['total_users'] - stats['active_users']}*
🌐 Online Now: *{stats['online_now']}*
📦 Total Bandwidth: *{format_bytes(stats['total_bandwidth'])}*

*Today's Activity:*
👤 Active Users: *{stats['today_users']}*
📊 Bandwidth Used: *{format_bytes(stats['today_bandwidth'])}*

*Real-time Connections:*
"""
    
    if stats['online_users']:
        for user in stats['online_users'][:8]:  # Show first 8 online users
            last_seen = (datetime.now() - datetime.fromisoformat(user['last_login'])).seconds // 60 if user['last_login'] else '?'
            stats_text += f"🔹 `{user['username']}` - {user['last_ip']} ({last_seen}m)\n"
        if len(stats['online_users']) > 8:
            stats_text += f"\n... and {len(stats['online_users']) - 8} more users online"
    else:
        stats_text += "\nNo users currently online"
    
    # Add refresh button
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
        [InlineKeyboardButton("👥 Online Users", callback_data="show_online")],
        [InlineKeyboardButton("📈 Detailed Report", callback_data="detailed_report")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(stats_text, parse_mode='Markdown', reply_markup=reply_markup)

def online_users_command(update, context):
    """Show currently online users with details"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
        
    stats = get_real_time_stats()
    online_users = stats['online_users']
    
    if not online_users:
        update.message.reply_text("📭 No users currently online")
        return
        
    online_text = f"👥 *Currently Online Users ({len(online_users)})*\n\n"
    
    for user in online_users:
        # Calculate minutes since last activity
        if user['last_login']:
            last_seen = (datetime.now() - datetime.fromisoformat(user['last_login'])).seconds // 60
            time_text = f"{last_seen}m ago"
        else:
            time_text = "Unknown"
            
        online_text += f"🔹 *{user['username']}*\n"
        online_text += f"   🌐 IP: `{user['last_ip']}`\n"
        online_text += f"   ⏰ Active: {time_text}\n\n"
    
    online_text += f"🕒 Last updated: {datetime.now().strftime('%H:%M:%S')}"
    
    # Add refresh button
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_online")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(online_text, parse_mode='Markdown', reply_markup=reply_markup)

def user_info_command(update, context):
    """Get detailed information about a specific user"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
        
    if not context.args:
        update.message.reply_text("Usage: /userinfo <username>\nExample: /userinfo john")
        return
        
    username = context.args[0]
    db = get_db()
    
    try:
        user = db.execute('''
            SELECT username, password, status, expires, bandwidth_used, bandwidth_limit,
                   speed_limit_up, concurrent_conn, created_at, last_login, last_ip, 
                   is_online, total_connections
            FROM users WHERE username = ?
        ''', (username,)).fetchone()
        
        if not user:
            update.message.reply_text(f"❌ User '{username}' not found")
            return
            
        # Get connection history
        connections = db.execute('''
            SELECT client_ip, connect_time, bytes_sent + bytes_received as total_bytes
            FROM connection_logs 
            WHERE username = ? 
            ORDER BY connect_time DESC 
            LIMIT 5
        ''', (username,)).fetchall()
        
        # Calculate days remaining
        days_remaining = ""
        if user['expires']:
            try:
                exp_date = datetime.strptime(user['expires'], '%Y-%m-%d')
                today = datetime.now()
                days_left = (exp_date - today).days
                days_remaining = f" ({days_left} days remaining)" if days_left >= 0 else f" (Expired {-days_left} days ago)"
            except:
                days_remaining = ""
        
        user_text = f"""
🔍 *Detailed User Information*

👤 Username: *{user['username']}*
🔐 Password: `{user['password']}`
📊 Status: *{user['status'].upper()}*
🌐 Online: {'🟢 YES' if user['is_online'] else '🔴 NO'}

*Connection Info:*
📡 Last IP: `{user['last_ip'] or 'N/A'}`
🕒 Last Login: {user['last_login'] or 'N/A'}
🔗 Total Connections: {user['total_connections'] or 0}

*Usage & Limits:*
📦 Bandwidth Used: *{format_bytes(user['bandwidth_used'] or 0)}*
🎯 Bandwidth Limit: *{format_bytes(user['bandwidth_limit'] or 0) if user['bandwidth_limit'] else 'Unlimited'}*
⚡ Speed Limit: *{user['speed_limit_up'] or 0} MB/s*
🔗 Max Connections: *{user['concurrent_conn']}*

*Recent Connections:*
"""
        
        if connections:
            for conn in connections:
                conn_time = datetime.fromisoformat(conn['connect_time']).strftime('%m/%d %H:%M')
                user_text += f"• {conn['client_ip']} - {format_bytes(conn['total_bytes'])} - {conn_time}\n"
        else:
            user_text += "No connection history\n"
            
        user_text += f"""
⏰ Expires: *{user['expires'] or 'Never'}{days_remaining}*
📅 Created: *{user['created_at'][:10] if user['created_at'] else 'N/A'}*
"""
        update.message.reply_text(user_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        update.message.reply_text("❌ Error retrieving user information")
    finally:
        db.close()

def admin_command(update, context):
    """Enhanced admin panel with real-time features"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    stats = get_real_time_stats()
    server_ip = get_server_ip()
    
    admin_text = f"""
🛠️ *Enhanced Admin Panel*
🌐 Server IP: `{server_ip}`
📊 Online Now: *{stats['online_now']}* users

*User Management:*
• /adduser <user> <pass> [days] - Add new user
• /changepass <user> <newpass> - Change password  
• /deluser <username> - Delete user
• /suspend <username> - Suspend user
• /activate <username> - Activate user

*Monitoring & Info:*
• /estats - Enhanced statistics
• /online - Show online users
• /userinfo <username> - User details
• /users - List all users with passwords

*Quick Actions:*
"""
    
    # Add inline buttons
    keyboard = [
        [
            InlineKeyboardButton("📊 Live Stats", callback_data="live_stats"),
            InlineKeyboardButton("👥 Online Users", callback_data="online_users")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_admin"),
            InlineKeyboardButton("📋 All Users", callback_data="show_all_users")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(admin_text, parse_mode='Markdown', reply_markup=reply_markup)

# ===== Button Handlers =====

def button_handler(update, context):
    """Handle inline button callbacks"""
    query = update.callback_query
    query.answer()
    
    if query.data == "refresh_stats":
        enhanced_stats_command(update, context)
    elif query.data == "show_online":
        online_users_command(update, context)
    elif query.data == "refresh_online":
        online_users_command(update, context)
    elif query.data == "live_stats":
        enhanced_stats_command(update, context)
    elif query.data == "refresh_admin":
        admin_command(update, context)
    elif query.data == "show_all_users":
        users_command(update, context)
    elif query.data == "detailed_report":
        query.edit_message_text("📈 Generating detailed report...")
        # Implement detailed report here

# ===== Existing Commands (Keep your current functionality) =====

def help_command(update, context):
    """Show help message - PUBLIC"""
    user_id = update.effective_user.id
    is_user_admin = is_admin(user_id)
    
    help_text = """
*Bot Commands:*
📊 /stats - Enhanced server statistics
🆘 /help - Show this help message
"""
    
    if is_user_admin:
        help_text += """
🛠️ *Admin Commands:*
/admin - Enhanced admin panel
/adduser <user> <pass> [days] - Add user
/changepass <user> <newpass> - Change password
/deluser <username> - Delete user
/online - Show online users
/userinfo <username> - User details
/estats - Real-time statistics
/users - List all users with passwords
"""
    
    help_text += """

*အသုံးပြုနည်းများ:*
📊 /stats - ဆာဗာစာရင်းဇယားများကိုကြည့်ရန်
🆘 /help - အကူအညီစာကိုကြည့်ရန်
"""
    
    update.message.reply_text(help_text, parse_mode='Markdown')

# ... [Keep all your existing commands: adduser_command, changepass_command, etc.] ...
# ... [Your existing sync_config_passwords, read_json, write_json_atomic functions] ...

def main():
    """Start the enhanced bot"""
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set")
        return
        
    try:
        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher

        # Public commands
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", help_command))
        dp.add_handler(CommandHandler("stats", enhanced_stats_command))
        
        # Admin commands
        dp.add_handler(CommandHandler("admin", admin_command))
        dp.add_handler(CommandHandler("adduser", adduser_command))
        dp.add_handler(CommandHandler("changepass", changepass_command))
        dp.add_handler(CommandHandler("deluser", deluser_command))
        dp.add_handler(CommandHandler("suspend", suspend_command))
        dp.add_handler(CommandHandler("activate", activate_command))
        dp.add_handler(CommandHandler("online", online_users_command))
        dp.add_handler(CommandHandler("userinfo", user_info_command))
        dp.add_handler(CommandHandler("estats", enhanced_stats_command))
        dp.add_handler(CommandHandler("users", users_command))

        # Button handlers
        dp.add_handler(CallbackQueryHandler(button_handler))

        # Error handler
        dp.add_error_handler(error_handler)

        logger.info("🤖 ZIVPN Enhanced Telegram Bot Started Successfully")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

def error_handler(update, context):
    """Log errors"""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

# ... [Keep all your existing command functions] ...

if __name__ == "__main__":
    main()
    
