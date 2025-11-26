#!/usr/bin/env python3
"""
ZIVPN Telegram Bot - ENTERPRISE EDITION with Real-time Monitoring
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
import threading
import time

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

# Admin configuration
ADMIN_IDS = [7576434717, 7240495054]  # Telegram ID

class RealTimeMonitor:
    def __init__(self):
        self.live_connections = {}
        self.connection_lock = threading.Lock()
        
    def update_connection(self, username, client_ip, port, action='connect'):
        with self.connection_lock:
            connection_key = f"{username}_{client_ip}_{port}"
            
            if action == 'connect':
                self.live_connections[connection_key] = {
                    'username': username,
                    'client_ip': client_ip,
                    'port': port,
                    'connect_time': datetime.now(),
                    'last_update': datetime.now()
                }
            elif action == 'disconnect':
                if connection_key in self.live_connections:
                    del self.live_connections[connection_key]
            elif action == 'update':
                if connection_key in self.live_connections:
                    self.live_connections[connection_key]['last_update'] = datetime.now()
    
    def get_live_connections(self):
        with self.connection_lock:
            # Clean up stale connections (older than 5 minutes)
            current_time = datetime.now()
            stale_keys = []
            for key, conn in self.live_connections.items():
                if (current_time - conn['last_update']).total_seconds() > 300:  # 5 minutes
                    stale_keys.append(key)
            
            for key in stale_keys:
                del self.live_connections[key]
            
            return list(self.live_connections.values())
    
    def get_user_connections(self, username):
        live_conns = self.get_live_connections()
        return [conn for conn in live_conns if conn['username'] == username]

# Global monitor instance
monitor = RealTimeMonitor()

# ===== SYNC CONFIG FUNCTIONS =====
def read_json(path, default):
    try:
        with open(path,"r") as f: return json.load(f)
    except Exception:
        return default

def write_json_atomic(path, data):
    d=json.dumps(data, ensure_ascii=False, indent=2)
    dirn=os.path.dirname(path); fd,tmp=tempfile.mkstemp(prefix=".tmp-", dir=dirn)
    try:
        with os.fdopen(fd,"w") as f: f.write(d)
        os.replace(tmp,path)
    finally:
        try: os.remove(tmp)
        except: pass

def sync_config_passwords():
    """Sync passwords from database to ZIVPN config"""
    db = get_db()
    try:
        active_users = db.execute('''
            SELECT password FROM users 
            WHERE status = "active" AND password IS NOT NULL AND password != "" 
                  AND (expires IS NULL OR expires >= CURRENT_DATE)
        ''').fetchall()
        
        users_pw = sorted({str(u["password"]) for u in active_users})
        
        cfg = read_json(CONFIG_FILE, {})
        if not isinstance(cfg.get("auth"), dict): 
            cfg["auth"] = {}
        
        cfg["auth"]["mode"] = "passwords"
        cfg["auth"]["config"] = users_pw
        
        write_json_atomic(CONFIG_FILE, cfg)
        
        result = subprocess.run("systemctl restart zivpn.service", shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("ZIVPN service restarted successfully for config sync")
            return True
        else:
            logger.error(f"Failed to restart ZIVPN service: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error syncing passwords: {e}")
        return False
    finally:
        db.close()

def get_server_ip():
    """Get server IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "43.249.33.233"  # fallback IP

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
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def format_duration(seconds):
    """Format seconds to human readable duration"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m {int(seconds%60)}s"
    else:
        return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"

# ===== NEW REAL-TIME COMMANDS =====

def online_command(update, context):
    """Show currently online users - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    live_connections = monitor.get_live_connections()
    
    if not live_connections:
        update.message.reply_text("📭 No users currently online")
        return
    
    online_text = "🔴 *Live Connections - Real Time*\n\n"
    
    for i, conn in enumerate(live_connections, 1):
        duration = (datetime.now() - conn['connect_time']).total_seconds()
        online_text += f"{i}. *{conn['username']}*\n"
        online_text += f"   🌐 IP: `{conn['client_ip']}`\n"
        online_text += f"   🚪 Port: `{conn['port']}`\n"
        online_text += f"   ⏰ Connected: {format_duration(duration)} ago\n"
        online_text += f"   📍 Status: 🟢 LIVE\n\n"
    
    online_text += f"📊 Total Online: *{len(live_connections)}* users"
    
    update.message.reply_text(online_text, parse_mode='Markdown')

def userinfo_command(update, context):
    """Get detailed user information with live status - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
        
    if not context.args:
        update.message.reply_text("Usage: /userinfo <username>\nExample: /userinfo john")
        return
        
    username = context.args[0]
    
    # Get user details from database
    db = get_db()
    try:
        user = db.execute('''
            SELECT username, password, status, expires, bandwidth_used, bandwidth_limit,
                   speed_limit_up, concurrent_conn, created_at
            FROM users WHERE username = ?
        ''', (username,)).fetchone()
        
        if not user:
            update.message.reply_text(f"❌ User '{username}' not found")
            return
            
        # Check if user is currently online
        live_conns = monitor.get_user_connections(username)
        is_online = len(live_conns) > 0
        
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
        
        # Get connection history (last 7 days)
        conn_history = db.execute('''
            SELECT COUNT(*) as connection_count
            FROM user_sessions 
            WHERE username = ? AND start_time >= datetime('now', '-7 days')
        ''', (username,)).fetchone()
        
        user_text = f"""
🔍 *User Information - Real Time*

👤 Username: *{user['username']}*
🔐 Password: `{user['password']}`
📊 Status: *{user['status'].upper()}* {'🟢 ONLINE' if is_online else '🔴 OFFLINE'}

⏰ Expires: *{user['expires'] or 'Never'}{days_remaining}*
📦 Bandwidth Used: *{format_bytes(user['bandwidth_used'] or 0)}*
🎯 Bandwidth Limit: *{format_bytes(user['bandwidth_limit'] or 0) if user['bandwidth_limit'] else 'Unlimited'}*
⚡ Speed Limit: *{user['speed_limit_up'] or 0} MB/s*
🔗 Max Connections: *{user['concurrent_conn']}*
📅 Created: *{user['created_at'][:10] if user['created_at'] else 'N/A'}*

📈 Activity (7 days): *{conn_history['connection_count']} connections*
        """
        
        # Add live connection details if online
        if is_online:
            user_text += f"\n*🟢 Live Connections ({len(live_conns)}):*\n"
            for conn in live_conns:
                duration = (datetime.now() - conn['connect_time']).total_seconds()
                user_text += f"• IP: `{conn['client_ip']}` | Port: {conn['port']} | {format_duration(duration)}\n"
        
        update.message.reply_text(user_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        update.message.reply_text("❌ Error retrieving user information")
    finally:
        db.close()

def kick_command(update, context):
    """Kick user from VPN - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /kick <username>\nExample: /kick john")
        return
    
    username = context.args[0]
    
    # Get user's live connections
    live_conns = monitor.get_user_connections(username)
    
    if not live_conns:
        update.message.reply_text(f"❌ User *{username}* is not currently online", parse_mode='Markdown')
        return
    
    # Kick all connections for this user
    kicked_count = 0
    for conn in live_conns:
        try:
            # Use conntrack to drop connection
            result = subprocess.run(
                f"conntrack -D -p udp --dport {conn['port']} --src {conn['client_ip']}",
                shell=True, capture_output=True, text=True
            )
            if result.returncode == 0:
                monitor.update_connection(conn['username'], conn['client_ip'], conn['port'], 'disconnect')
                kicked_count += 1
        except Exception as e:
            logger.error(f"Error kicking connection: {e}")
    
    if kicked_count > 0:
        update.message.reply_text(f"✅ Kicked *{kicked_count}* connections for *{username}*", parse_mode='Markdown')
    else:
        update.message.reply_text(f"❌ Failed to kick connections for *{username}*", parse_mode='Markdown')

def notify_command(update, context):
    """Send notification to all users - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /notify <message>\nExample: /notify Server maintenance in 10 minutes")
        return
    
    message = ' '.join(context.args)
    
    # Get all active users
    db = get_db()
    try:
        active_users = db.execute('''
            SELECT username FROM users 
            WHERE status = "active" AND (expires IS NULL OR expires >= CURRENT_DATE)
        ''').fetchall()
        
        total_users = len(active_users)
        
        # In a real implementation, you would send notifications via:
        # - SMS Gateway
        # - Email
        # - Push notifications
        # - Telegram to individual users
        
        notify_text = f"""
📢 *Broadcast Notification*

💬 Message: {message}

📊 Sent to: *{total_users}* active users
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_This is a broadcast message from ZIVPN Administration_
        """
        
        update.message.reply_text(notify_text, parse_mode='Markdown')
        
        # Log the notification
        db.execute('''
            INSERT INTO notifications (username, message, type)
            VALUES (?, ?, 'broadcast')
        ''', ('SYSTEM', message))
        db.commit()
        
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        update.message.reply_text("❌ Error sending notification")
    finally:
        db.close()

def revenue_command(update, context):
    """Show revenue analytics - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    db = get_db()
    try:
        # Get revenue by plan type
        revenue_by_plan = db.execute('''
            SELECT plan_type, COUNT(*) as user_count, 
                   SUM(amount) as total_revenue
            FROM billing 
            WHERE payment_status = 'completed'
            GROUP BY plan_type
        ''').fetchall()
        
        # Get today's revenue
        today_revenue = db.execute('''
            SELECT SUM(amount) as today_total
            FROM billing 
            WHERE date(created_at) = date('now') 
            AND payment_status = 'completed'
        ''').fetchone()
        
        # Get monthly revenue
        monthly_revenue = db.execute('''
            SELECT SUM(amount) as month_total
            FROM billing 
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
            AND payment_status = 'completed'
        ''').fetchone()
        
        revenue_text = "💰 *Revenue Analytics*\n\n"
        
        revenue_text += f"📅 Today: *{today_revenue['today_total'] or 0:.2f} MMK*\n"
        revenue_text += f"📈 This Month: *{monthly_revenue['month_total'] or 0:.2f} MMK*\n\n"
        
        revenue_text += "*Revenue by Plan Type:*\n"
        total_revenue = 0
        for plan in revenue_by_plan:
            revenue_text += f"• {plan['plan_type'].title()}: {plan['user_count']} users, {plan['total_revenue'] or 0:.2f} MMK\n"
            total_revenue += plan['total_revenue'] or 0
        
        revenue_text += f"\n💰 Total Revenue: *{total_revenue:.2f} MMK*"
        
        update.message.reply_text(revenue_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting revenue: {e}")
        update.message.reply_text("❌ Error retrieving revenue analytics")
    finally:
        db.close()

# ===== EXISTING COMMANDS (UPDATED) =====

def start(update, context):
    """Send welcome message - PUBLIC"""
    user_id = update.effective_user.id
    is_user_admin = is_admin(user_id)
    
    welcome_text = f"""
🤖 *ZIVPN Management Bot - ENTERPRISE EDITION*
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
/online - Live online users
/userinfo <user> - Detailed user info
/kick <user> - Kick user from VPN
/notify <msg> - Broadcast message
/revenue - Revenue analytics

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
"""
    
    welcome_text += """

*ဖွင့်သောအမိန့်များ:*
/start - ကြိုဆိုစာကိုပြပါ
/stats - ဆာဗာစာရင်းဇယား
/help - အကူအညီစာကိုပြပါ
"""
    
    update.message.reply_text(welcome_text, parse_mode='Markdown')

def help_command(update, context):
    """Show help message - PUBLIC"""
    user_id = update.effective_user.id
    is_user_admin = is_admin(user_id)
    
    help_text = """
*Bot Commands:*
📊 /stats - Show server statistics
🆘 /help - Show this help message
"""
    
    # Only show admin help to admin users
    if is_user_admin:
        help_text += """
🛠️ *Admin Commands:*
👥 /online - Live online users
🔍 /userinfo <user> - Detailed user info
🦵 /kick <user> - Kick user from VPN
📢 /notify <msg> - Broadcast message
💰 /revenue - Revenue analytics

👤 /adduser <user> <pass> [days] - Add user
🔐 /changepass <user> <newpass> - Change password
🗑️ /deluser <username> - Delete user
⏸️ /suspend <username> - Suspend user
▶️ /activate <username> - Activate user
🚫 /ban <username> - Ban user
✅ /unban <username> - Unban user
🔄 /renew <username> <days> - Renew user
📅 /reset <username> <days> - Reset expiry
📋 /users - List all users with passwords
"""
    
    help_text += """

*အသုံးပြုနည်းများ:*
📊 /stats - ဆာဗာစာရင်းဇယားများကိုကြည့်ရန်
🆘 /help - အကူအညီစာကိုကြည့်ရန်
"""
    
    update.message.reply_text(help_text, parse_mode='Markdown')

def admin_command(update, context):
    """Admin panel - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    # Get real-time stats
    db = get_db()
    total_users = db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    active_users = db.execute('SELECT COUNT(*) as count FROM users WHERE status = "active"').fetchone()['count']
    live_connections = len(monitor.get_live_connections())
    db.close()
    
    admin_text = f"""
🛠️ *Admin Panel - Real Time*
🌐 Server IP: `{get_server_ip()}`
📊 Total Users: *{total_users}*
🟢 Active Users: *{active_users}*
🔴 Live Connections: *{live_connections}*

*Real-time Monitoring:*
👥 /online - Live online users
🔍 /userinfo <user> - Detailed user info
🦵 /kick <user> - Kick user from VPN
📢 /notify <msg> - Broadcast message
💰 /revenue - Revenue analytics

*User Management:*
👤 /adduser <user> <pass> [days] - Add new user
🔐 /changepass <user> <newpass> - Change password
🗑️ /deluser <username> - Delete user
⏸️ /suspend <username> - Suspend user  
▶️ /activate <username> - Activate user
🚫 /ban <username> - Ban user
✅ /unban <username> - Unban user
🔄 /renew <username> <days> - Renew user
📅 /reset <username> <days> - Reset expiry

*Information:*
📋 /users - List all users with passwords
📊 /stats - Server statistics

*Usage Examples:*
/adduser john pass123 30
/online - See live connections
/userinfo john - Detailed user info
"""
    update.message.reply_text(admin_text, parse_mode='Markdown')

# ===== EXISTING USER MANAGEMENT FUNCTIONS =====

def adduser_command(update, context):
    """Add new user - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Usage: /adduser <username> <password> [days]\nExample: /adduser john pass123 30")
        return
    
    username = context.args[0]
    password = context.args[1]
    days = 30  # default 30 days
    
    if len(context.args) > 2:
        try:
            days = int(context.args[2])
        except:
            update.message.reply_text("❌ Invalid days format")
            return
    
    expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    server_ip = get_server_ip()
    
    db = get_db()
    try:
        # Check if user exists
        existing = db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            update.message.reply_text(f"❌ User `{username}` already exists")
            return
        
        # Add user to database
        db.execute('''
            INSERT INTO users (username, password, status, expires, concurrent_conn, created_at)
            VALUES (?, ?, 'active', ?, 1, datetime('now'))
        ''', (username, password, expiry_date))
        db.commit()
        
        # Add to billing table
        db.execute('''
            INSERT INTO billing (username, plan_type, amount, currency, payment_status, expires_at)
            VALUES (?, 'monthly', 0, 'MMK', 'completed', ?)
        ''', (username, expiry_date))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        if sync_config_passwords():
            success_text = f"""
✅ *User Added Successfully*

🌐 Server: `{server_ip}`
👤 Username: `{username}`
🔐 Password: `{password}`
📊 Status: Active
⏰ Expires: {expiry_date}
🔗 Connections: 1

*User can now connect to VPN immediately*
"""
        else:
            success_text = f"""
⚠️ *User Added But Sync Warning*

👤 Username: `{username}`
🔐 Password: `{password}`
⏰ Expires: {expiry_date}

💡 User added to database but ZIVPN sync had issues.
   User may need to wait a moment to connect.
"""
        
        update.message.reply_text(success_text, parse_mode='Markdown')
        logger.info(f"User {username} added by admin {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        update.message.reply_text("❌ Error adding user")
    finally:
        db.close()

def changepass_command(update, context):
    """Change user password - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Usage: /changepass <username> <new_password>\nExample: /changepass john newpass123")
        return
    
    username = context.args[0]
    new_password = context.args[1]
    
    db = get_db()
    try:
        # Check if user exists
        user = db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone()
        if not user:
            update.message.reply_text(f"❌ User `{username}` not found")
            return
        
        # Update password
        db.execute('UPDATE users SET password = ? WHERE username = ?', (new_password, username))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ Password changed for *{username}*\n🔐 New Password: `{new_password}`", parse_mode='Markdown')
        logger.info(f"User {username} password changed by admin {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        update.message.reply_text("❌ Error changing password")
    finally:
        db.close()

def deluser_command(update, context):
    """Delete user - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /deluser <username>")
        return
    
    username = context.args[0]
    db = get_db()
    try:
        # Check if user exists
        existing = db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone()
        if not existing:
            update.message.reply_text(f"❌ User `{username}` not found")
            return
        
        # Delete user
        db.execute('DELETE FROM users WHERE username = ?', (username,))
        db.execute('DELETE FROM billing WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User `{username}` deleted")
        logger.info(f"User {username} deleted by admin {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        update.message.reply_text("❌ Error deleting user")
    finally:
        db.close()

def suspend_command(update, context):
    """Suspend user - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /suspend <username>")
        return
    
    username = context.args[0]
    db = get_db()
    try:
        db.execute('UPDATE users SET status = "suspended" WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User *{username}* suspended\n\n🔓 Unsuspend: /activate {username}")
        logger.info(f"User {username} suspended by admin {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error suspending user: {e}")
        update.message.reply_text("❌ Error suspending user")
    finally:
        db.close()

def activate_command(update, context):
    """Activate user - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /activate <username>")
        return
    
    username = context.args[0]
    db = get_db()
    try:
        db.execute('UPDATE users SET status = "active" WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User *{username}* activated")
        logger.info(f"User {username} activated by admin {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error activating user: {e}")
        update.message.reply_text("❌ Error activating user")
    finally:
        db.close()

def ban_user(update, context):
    """Ban user - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /ban <username>")
        return
    
    username = context.args[0]
    db = get_db()
    try:
        db.execute('UPDATE users SET status = "banned" WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User *{username}* banned\n\n🔓 Unban: /unban {username}")
        logger.info(f"User {username} banned by admin {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        update.message.reply_text("❌ Error banning user")
    finally:
        db.close()

def unban_user(update, context):
    """Unban user - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /unban <username>")
        return
    
    username = context.args[0]
    db = get_db()
    try:
        db.execute('UPDATE users SET status = "active" WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User *{username}* unbanned")
        logger.info(f"User {username} unbanned by admin {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        update.message.reply_text("❌ Error unbanning user")
    finally:
        db.close()

def renew_command(update, context):
    """Renew user - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Usage: /renew <username> <days>\nExample: /renew john 30")
        return
    
    username = context.args[0]
    try:
        days = int(context.args[1])
    except:
        update.message.reply_text("❌ Invalid days format")
        return
    
    db = get_db()
    try:
        user = db.execute('SELECT username, expires FROM users WHERE username = ?', (username,)).fetchone()
        if not user:
            update.message.reply_text(f"❌ User `{username}` not found")
            return
        
        if user['expires']:
            current_expiry = datetime.strptime(user['expires'], '%Y-%m-%d')
            new_expiry = current_expiry + timedelta(days=days)
            old_expiry_str = user['expires']
        else:
            new_expiry = datetime.now() + timedelta(days=days)
            old_expiry_str = "Never"
        
        new_expiry_str = new_expiry.strftime('%Y-%m-%d')
        
        db.execute('UPDATE users SET expires = ? WHERE username = ?', (new_expiry_str, username))
        db.commit()
        
        renew_text = f"""
✅ *User Renewed*

👤 Username: *{username}*
⏰ Old Expiry: {old_expiry_str}
🔄 Days Added: {days} days
📅 New Expiry: {new_expiry_str}
        """
        update.message.reply_text(renew_text, parse_mode='Markdown')
        logger.info(f"User {username} renewed for {days} days by admin {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error renewing user: {e}")
        update.message.reply_text("❌ Error renewing user")
    finally:
        db.close()

def reset_command(update, context):
    """Reset user expiry - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Usage: /reset <username> <days>\nExample: /reset john 30")
        return
    
    username = context.args[0]
    try:
        days = int(context.args[1])
    except:
        update.message.reply_text("❌ Invalid days format")
        return
    
    db = get_db()
    try:
        user = db.execute('SELECT username, expires FROM users WHERE username = ?', (username,)).fetchone()
        if not user:
            update.message.reply_text(f"❌ User `{username}` not found")
            return
        
        old_expiry_str = user['expires'] or "Never"
        new_expiry = datetime.now() + timedelta(days=days)
        new_expiry_str = new_expiry.strftime('%Y-%m-%d')
        
        db.execute('UPDATE users SET expires = ? WHERE username = ?', (new_expiry_str, username))
        db.commit()
        
        reset_text = f"""
🔄 *User Expiry Reset*

👤 Username: *{username}*
⏰ Old Expiry: {old_expiry_str}
📅 Reset From: Today
🔄 New Duration: {days} days
📅 New Expiry: {new_expiry_str}
        """
        update.message.reply_text(reset_text, parse_mode='Markdown')
        logger.info(f"User {username} expiry reset to {days} days by admin {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error resetting user: {e}")
        update.message.reply_text("❌ Error resetting user")
    finally:
        db.close()

def stats_command(update, context):
    """Show server statistics - PUBLIC"""
    db = get_db()
    try:
        stats = db.execute('''
            SELECT
                COUNT(*) as total_users,
                SUM(CASE WHEN status = "active" AND (expires IS NULL OR expires >= date('now')) THEN 1 ELSE 0 END) as active_users,
                SUM(bandwidth_used) as total_bandwidth
            FROM users
        ''').fetchone()
        
        today_users = db.execute('''
            SELECT COUNT(*) as today_users
            FROM users
            WHERE date(created_at) = date('now')
        ''').fetchone()
        
        # Real-time connections
        live_connections = len(monitor.get_live_connections())
        
        total_users = stats['total_users'] or 0
        active_users = stats['active_users'] or 0
        total_bandwidth = stats['total_bandwidth'] or 0
        today_new_users = today_users['today_users'] or 0
        
        stats_text = f"""
📊 *Server Statistics - Real Time*
👥 Total Users: *{total_users}*
🟢 Active Users: *{active_users}*
🔴 Live Connections: *{live_connections}*
🔴 Inactive Users: *{total_users - active_users}*
🆕 Today's New Users: *{today_new_users}*
📦 Total Bandwidth Used: *{format_bytes(total_bandwidth)}*
        """
        update.message.reply_text(stats_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        update.message.reply_text("❌ Error retrieving statistics")
    finally:
        db.close()

def users_command(update, context):
    """List all users with passwords - ADMIN ONLY (NO LIMIT)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
        
    db = get_db()
    try:
        # NO LIMIT - show ALL users
        users = db.execute('''
            SELECT username, password, status, expires, bandwidth_used, concurrent_conn
            FROM users
            ORDER BY created_at DESC
        ''').fetchall()  # NO LIMIT 20
        
        if not users:
            update.message.reply_text("📭 No users found")
            return
        
        total_users = len(users)
        users_text = f"👥 *All Users ({total_users})*\n\n"
        
        # If too many users, split into chunks
        if total_users > 50:
            # Show first 50 users with summary
            for i, user in enumerate(users[:50]):
                status_icon = "🟢" if user['status'] == 'active' else "🔴"
                bandwidth = format_bytes(user['bandwidth_used'] or 0)
                users_text += f"{status_icon} *{user['username']}*\n"
                users_text += f"🔐 Password: `{user['password']}`\n"
                users_text += f"📊 Status: {user['status']}\n"
                users_text += f"📦 Bandwidth: {bandwidth}\n"
                if user['expires']:
                    users_text += f"⏰ Expires: {user['expires']}\n"
                users_text += "\n"
            
            users_text += f"📋 *Showing 50 out of {total_users} users*\n"
            users_text += "💡 Use /userinfo <username> for specific user details"
        else:
            # Show all users
            for user in users:
                status_icon = "🟢" if user['status'] == 'active' else "🔴"
                bandwidth = format_bytes(user['bandwidth_used'] or 0)
                users_text += f"{status_icon} *{user['username']}*\n"
                users_text += f"🔐 Password: `{user['password']}`\n"
                users_text += f"📊 Status: {user['status']}\n"
                users_text += f"📦 Bandwidth: {bandwidth}\n"
                users_text += f"🔗 Connections: {user['concurrent_conn']}\n"
                if user['expires']:
                    users_text += f"⏰ Expires: {user['expires']}\n"
                users_text += "\n"
        
        update.message.reply_text(users_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        update.message.reply_text("❌ Error retrieving users list")
    finally:
        db.close()

def error_handler(update, context):
    """Log errors"""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def connection_monitor_loop():
    """Background thread to monitor connections"""
    while True:
        try:
            # Get active connections from conntrack
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null | grep -E 'dport=(5667|[6-9][0-9]{3}|[1-9][0-9]{4})' | awk '{print $7,$8}'",
                shell=True, capture_output=True, text=True
            )
            
            if result.returncode == 0:
                current_connections = {}
                for line in result.stdout.split('\n'):
                    if 'src=' in line and 'dport=' in line:
                        try:
                            parts = line.split()
                            src_ip = None
                            dport = None
                            
                            for part in parts:
                                if part.startswith('src='):
                                    src_ip = part.split('=')[1]
                                elif part.startswith('dport='):
                                    dport = part.split('=')[1]
                            
                            if src_ip and dport:
                                # Try to map port to username
                                db = get_db()
                                user = db.execute(
                                    'SELECT username FROM users WHERE port = ? OR (? = "5667" AND username IN (SELECT username FROM users WHERE port IS NULL))',
                                    (dport, dport)
                                ).fetchone()
                                db.close()
                                
                                if user:
                                    connection_key = f"{user['username']}_{src_ip}_{dport}"
                                    current_connections[connection_key] = True
                                    monitor.update_connection(user['username'], src_ip, dport, 'update')
                        except:
                            continue
                
                # Remove connections that are no longer active
                live_conns = monitor.get_live_connections()
                for conn in live_conns:
                    connection_key = f"{conn['username']}_{conn['client_ip']}_{conn['port']}"
                    if connection_key not in current_connections:
                        monitor.update_connection(conn['username'], conn['client_ip'], conn['port'], 'disconnect')
            
        except Exception as e:
            logger.error(f"Connection monitor error: {e}")
        
        time.sleep(10)  # Check every 10 seconds

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in environment variables")
        return
        
    try:
        # Start connection monitor in background thread
        monitor_thread = threading.Thread(target=connection_monitor_loop, daemon=True)
        monitor_thread.start()
        
        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher

        # Public commands (everyone can see and use)
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", help_command))
        dp.add_handler(CommandHandler("stats", stats_command))
        
        # Admin commands (only admin can see and use)
        dp.add_handler(CommandHandler("admin", admin_command))
        dp.add_handler(CommandHandler("online", online_command))
        dp.add_handler(CommandHandler("userinfo", userinfo_command))
        dp.add_handler(CommandHandler("kick", kick_command))
        dp.add_handler(CommandHandler("notify", notify_command))
        dp.add_handler(CommandHandler("revenue", revenue_command))
        
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

        dp.add_error_handler(error_handler)

        logger.info("🤖 ZIVPN Telegram Bot Started Successfully with Real-time Monitoring")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
    
