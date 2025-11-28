#!/usr/bin/env python3
"""
ZIVPN Telegram Bot - Unlimited Users Version
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

# Admin configuration - ONLY YOUR ID CAN SEE ADMIN COMMANDS
ADMIN_IDS = [7576434717, 7240495054]  # Telegram ID

# --- NEW: Monitoring Configuration ---
BANDWIDTH_ALERTS_ENABLED = True
MULTI_DEVICE_ALERTS_ENABLED = True
ALERT_CHECK_INTERVAL = 300  # 5 minutes

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
        # Get all active users' passwords
        active_users = db.execute('''
            SELECT password FROM users 
            WHERE status = "active" AND password IS NOT NULL AND password != "" 
                  AND (expires IS NULL OR expires >= CURRENT_DATE)
        ''').fetchall()
        
        # Extract unique passwords
        users_pw = sorted({str(u["password"]) for u in active_users})
        
        # Update config file
        cfg = read_json(CONFIG_FILE, {})
        if not isinstance(cfg.get("auth"), dict): 
            cfg["auth"] = {}
        
        cfg["auth"]["mode"] = "passwords"
        cfg["auth"]["config"] = users_pw
        
        write_json_atomic(CONFIG_FILE, cfg)
        
        # Restart ZIVPN service to apply changes
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

# --- NEW: Bandwidth Monitoring Functions ---
def get_bandwidth_alerts():
    """Get users who are near or over bandwidth limits"""
    db = get_db()
    try:
        alerts = db.execute('''
            SELECT username, bandwidth_used, bandwidth_limit,
                   (bandwidth_used * 100.0 / (bandwidth_limit * 1024 * 1024 * 1024)) as usage_percentage
            FROM users 
            WHERE bandwidth_limit > 0 AND status = 'active'
            AND bandwidth_used >= (bandwidth_limit * 1024 * 1024 * 1024) * 0.8  # 80% or more usage
            ORDER BY usage_percentage DESC
        ''').fetchall()
        return [dict(alert) for alert in alerts]
    except Exception as e:
        logger.error(f"Error getting bandwidth alerts: {e}")
        return []
    finally:
        db.close()

def get_multi_device_violations():
    """Get recent multi-device violations"""
    db = get_db()
    try:
        violations = db.execute('''
            SELECT target_user as username, details, created_at
            FROM audit_logs 
            WHERE action LIKE '%multi_device%'
            AND created_at > datetime('now', '-1 hour')
            ORDER BY created_at DESC
            LIMIT 10
        ''').fetchall()
        return [dict(violation) for violation in violations]
    except Exception as e:
        logger.error(f"Error getting device violations: {e}")
        return []
    finally:
        db.close()

def get_users_near_bandwidth_limit():
    """Get users who are near their bandwidth limit (80% or more)"""
    db = get_db()
    try:
        users = db.execute('''
            SELECT username, bandwidth_used, bandwidth_limit,
                   (bandwidth_used * 100.0 / (bandwidth_limit * 1024 * 1024 * 1024)) as usage_percentage
            FROM users 
            WHERE bandwidth_limit > 0 AND status = 'active'
            AND bandwidth_used >= (bandwidth_limit * 1024 * 1024 * 1024) * 0.8
            AND bandwidth_used < (bandwidth_limit * 1024 * 1024 * 1024)  # Under 100%
            ORDER BY usage_percentage DESC
        ''').fetchall()
        return [dict(user) for user in users]
    except Exception as e:
        logger.error(f"Error getting users near bandwidth limit: {e}")
        return []
    finally:
        db.close()

def get_users_over_bandwidth_limit():
    """Get users who are over their bandwidth limit"""
    db = get_db()
    try:
        users = db.execute('''
            SELECT username, bandwidth_used, bandwidth_limit,
                   (bandwidth_used * 100.0 / (bandwidth_limit * 1024 * 1024 * 1024)) as usage_percentage
            FROM users 
            WHERE bandwidth_limit > 0 AND status = 'active'
            AND bandwidth_used >= (bandwidth_limit * 1024 * 1024 * 1024)  # 100% or more
            ORDER BY usage_percentage DESC
        ''').fetchall()
        return [dict(user) for user in users]
    except Exception as e:
        logger.error(f"Error getting users over bandwidth limit: {e}")
        return []
    finally:
        db.close()

def send_alert_to_admins(bot, message):
    """Send alert message to all admin users"""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Alert sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to send alert to admin {admin_id}: {e}")

def monitor_alerts(bot):
    """Monitor and send alerts for bandwidth and multi-device violations"""
    while True:
        try:
            # Check bandwidth alerts
            if BANDWIDTH_ALERTS_ENABLED:
                users_near_limit = get_users_near_bandwidth_limit()
                users_over_limit = get_users_over_bandwidth_limit()
                
                # Send alerts for users over limit
                for user in users_over_limit:
                    alert_message = f"""
🚨 *BANDWIDTH LIMIT EXCEEDED*

👤 User: `{user['username']}`
📊 Usage: *{user['usage_percentage']:.1f}%*
📦 Used: {format_bytes(user['bandwidth_used'])}
🎯 Limit: {format_bytes(user['bandwidth_limit'] * 1024 * 1024 * 1024)}

⚠️ User has exceeded bandwidth limit!
🔧 Action: Consider suspending or increasing limit.
"""
                    send_alert_to_admins(bot, alert_message)
                
                # Send warnings for users near limit
                for user in users_near_limit:
                    if user['usage_percentage'] >= 95:  # Only alert for 95%+ usage
                        warning_message = f"""
⚠️ *BANDWIDTH LIMIT WARNING*

👤 User: `{user['username']}`
📊 Usage: *{user['usage_percentage']:.1f}%*
📦 Used: {format_bytes(user['bandwidth_used'])}
🎯 Limit: {format_bytes(user['bandwidth_limit'] * 1024 * 1024 * 1024)}

💡 User is near bandwidth limit!
"""
                        send_alert_to_admins(bot, warning_message)
            
            # Check multi-device violations
            if MULTI_DEVICE_ALERTS_ENABLED:
                violations = get_multi_device_violations()
                for violation in violations:
                    # Only send alert if violation is recent (last 5 minutes)
                    violation_time = datetime.strptime(violation['created_at'], '%Y-%m-%d %H:%M:%S')
                    if (datetime.now() - violation_time).total_seconds() <= 300:
                        alert_message = f"""
🔍 *MULTI-DEVICE VIOLATION DETECTED*

👤 User: `{violation['username']}`
📝 Details: {violation['details']}
⏰ Time: {violation['created_at']}

🚨 User may be sharing account!
"""
                        send_alert_to_admins(bot, alert_message)
            
            # Sleep for the defined interval
            time.sleep(ALERT_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in alert monitoring: {e}")
            time.sleep(60)  # Wait 1 minute if error occurs

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
/bandwidth - Bandwidth usage report
/alerts - System alerts status
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
/bandwidth - Bandwidth usage report
/alerts - System alerts status
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
    
    # Get total user count
    db = get_db()
    total_users = db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    active_users = db.execute('SELECT COUNT(*) as count FROM users WHERE status = "active"').fetchone()['count']
    
    # --- NEW: Get monitoring stats ---
    bandwidth_alerts = len(get_bandwidth_alerts())
    device_violations = len(get_multi_device_violations())
    users_near_limit = len(get_users_near_bandwidth_limit())
    users_over_limit = len(get_users_over_bandwidth_limit())
    
    db.close()
    
    admin_text = f"""
🛠️ *Admin Panel*
🌐 Server IP: `{get_server_ip()}`
📊 Total Users: *{total_users}* (Active: *{active_users}*)

*📈 Monitoring Status:*
⚠️ Bandwidth Alerts: *{bandwidth_alerts}*
🔍 Device Violations: *{device_violations}*
📶 Near Limit Users: *{users_near_limit}*
🚨 Over Limit Users: *{users_over_limit}*

*User Management:*
• /adduser <user> <pass> [days] - Add new user
• /changepass <user> <newpass> - Change password
• /deluser <username> - Delete user
• /suspend <username> - Suspend user  
• /activate <username> - Activate user
• /ban <username> - Ban user
• /unban <username> - Unban user
• /renew <username> <days> - Renew user (extend from current)
• /reset <username> <days> - Reset expiry (from today)

*Information & Monitoring:*
• /users - List all users with passwords
• /myinfo <username> - User details with password
• /stats - Server statistics
• /bandwidth - Bandwidth usage report
• /alerts - System alerts status

*Usage Examples:*
/adduser john pass123 30
/changepass john newpass456
/users - See all users with passwords
"""
    update.message.reply_text(admin_text, parse_mode='Markdown')

# --- NEW: Bandwidth Monitoring Commands ---
def bandwidth_command(update, context):
    """Show bandwidth usage report - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    db = get_db()
    try:
        # Get bandwidth usage summary
        summary = db.execute('''
            SELECT 
                COUNT(*) as total_users,
                SUM(bandwidth_used) as total_bandwidth,
                SUM(CASE WHEN bandwidth_limit > 0 THEN 1 ELSE 0 END) as limited_users,
                SUM(CASE WHEN bandwidth_used >= (bandwidth_limit * 1024 * 1024 * 1024) AND bandwidth_limit > 0 THEN 1 ELSE 0 END) as over_limit_users,
                SUM(CASE WHEN bandwidth_used >= (bandwidth_limit * 1024 * 1024 * 1024) * 0.8 AND bandwidth_used < (bandwidth_limit * 1024 * 1024 * 1024) AND bandwidth_limit > 0 THEN 1 ELSE 0 END) as near_limit_users
            FROM users WHERE status = 'active'
        ''').fetchone()
        
        # Get top bandwidth users
        top_users = db.execute('''
            SELECT username, bandwidth_used, bandwidth_limit,
                   (bandwidth_used * 100.0 / (bandwidth_limit * 1024 * 1024 * 1024)) as usage_percentage
            FROM users 
            WHERE status = 'active' AND bandwidth_limit > 0
            ORDER BY bandwidth_used DESC 
            LIMIT 10
        ''').fetchall()
        
        bandwidth_text = f"""
📊 *Bandwidth Usage Report*

*Summary:*
👥 Total Users: *{summary['total_users']}*
📦 Total Bandwidth Used: *{format_bytes(summary['total_bandwidth'] or 0)}*
🎯 Limited Users: *{summary['limited_users']}*
⚠️ Near Limit: *{summary['near_limit_users']}*
🚨 Over Limit: *{summary['over_limit_users']}*

*Top Bandwidth Users:*
"""
        
        for i, user in enumerate(top_users, 1):
            usage_percentage = user['usage_percentage'] or 0
            status_icon = "🚨" if usage_percentage >= 100 else "⚠️" if usage_percentage >= 80 else "📊"
            
            bandwidth_text += f"""
{status_icon} *{user['username']}*
📦 Used: {format_bytes(user['bandwidth_used'])}
🎯 Limit: {format_bytes(user['bandwidth_limit'] * 1024 * 1024 * 1024)}
📊 Usage: *{usage_percentage:.1f}%*
"""
        
        update.message.reply_text(bandwidth_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error generating bandwidth report: {e}")
        update.message.reply_text("❌ Error generating bandwidth report")
    finally:
        db.close()

def alerts_command(update, context):
    """Show system alerts status - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    try:
        bandwidth_alerts = get_bandwidth_alerts()
        device_violations = get_multi_device_violations()
        users_near_limit = get_users_near_bandwidth_limit()
        users_over_limit = get_users_over_bandwidth_limit()
        
        alerts_text = f"""
🚨 *System Alerts Status*

*Bandwidth Monitoring:*
⚠️ Users Near Limit (80%+): *{len(users_near_limit)}*
🚨 Users Over Limit: *{len(users_over_limit)}*
📊 Total Bandwidth Alerts: *{len(bandwidth_alerts)}*

*Device Monitoring:*
🔍 Recent Device Violations: *{len(device_violations)}*
"""
        
        # Show users over limit
        if users_over_limit:
            alerts_text += "\n*🚨 USERS OVER BANDWIDTH LIMIT:*\n"
            for user in users_over_limit[:5]:  # Show first 5
                alerts_text += f"• `{user['username']}` - {user['usage_percentage']:.1f}%\n"
        
        # Show users near limit
        if users_near_limit and len(users_over_limit) < 5:
            alerts_text += "\n*⚠️ USERS NEAR BANDWIDTH LIMIT:*\n"
            for user in users_near_limit[:5]:  # Show first 5
                alerts_text += f"• `{user['username']}` - {user['usage_percentage']:.1f}%\n"
        
        # Show recent device violations
        if device_violations:
            alerts_text += "\n*🔍 RECENT DEVICE VIOLATIONS:*\n"
            for violation in device_violations[:3]:  # Show first 3
                alerts_text += f"• `{violation['username']}` - {violation['created_at'][11:16]}\n"
        
        if not bandwidth_alerts and not device_violations:
            alerts_text += "\n✅ *No active alerts* - System is running smoothly!"
        
        update.message.reply_text(alerts_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        update.message.reply_text("❌ Error retrieving alerts")

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
        
        # --- NEW: Get monitoring stats ---
        bandwidth_alerts = len(get_bandwidth_alerts())
        device_violations = len(get_multi_device_violations())
        
        total_users = stats['total_users'] or 0
        active_users = stats['active_users'] or 0
        total_bandwidth = stats['total_bandwidth'] or 0
        today_new_users = today_users['today_users'] or 0
        
        stats_text = f"""
📊 *Server Statistics*
👥 Total Users: *{total_users}*
🟢 Active Users: *{active_users}*
🔴 Inactive Users: *{total_users - active_users}*
🆕 Today's New Users: *{today_new_users}*
📦 Total Bandwidth Used: *{format_bytes(total_bandwidth)}*

*Monitoring:*
⚠️ Bandwidth Alerts: *{bandwidth_alerts}*
🔍 Device Violations: *{device_violations}*
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
            SELECT username, password, status, expires, bandwidth_used, bandwidth_limit, concurrent_conn
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
                
                # --- NEW: Calculate usage percentage ---
                usage_percentage = 0
                if user['bandwidth_limit'] and user['bandwidth_limit'] > 0:
                    usage_percentage = (user['bandwidth_used'] or 0) / (user['bandwidth_limit'] * 1024 * 1024 * 1024) * 100
                
                usage_indicator = ""
                if usage_percentage >= 100:
                    usage_indicator = " 🚨"
                elif usage_percentage >= 80:
                    usage_indicator = " ⚠️"
                
                users_text += f"{status_icon} *{user['username']}*{usage_indicator}\n"
                users_text += f"🔐 Password: `{user['password']}`\n"
                users_text += f"📊 Status: {user['status']}\n"
                users_text += f"📦 Bandwidth: {bandwidth}\n"
                if user['bandwidth_limit'] and user['bandwidth_limit'] > 0:
                    users_text += f"📊 Usage: {usage_percentage:.1f}%\n"
                if user['expires']:
                    users_text += f"⏰ Expires: {user['expires']}\n"
                users_text += "\n"
            
            users_text += f"📋 *Showing 50 out of {total_users} users*\n"
            users_text += "💡 Use /myinfo <username> for specific user details"
        else:
            # Show all users
            for user in users:
                status_icon = "🟢" if user['status'] == 'active' else "🔴"
                bandwidth = format_bytes(user['bandwidth_used'] or 0)
                
                # --- NEW: Calculate usage percentage ---
                usage_percentage = 0
                if user['bandwidth_limit'] and user['bandwidth_limit'] > 0:
                    usage_percentage = (user['bandwidth_used'] or 0) / (user['bandwidth_limit'] * 1024 * 1024 * 1024) * 100
                
                usage_indicator = ""
                if usage_percentage >= 100:
                    usage_indicator = " 🚨"
                elif usage_percentage >= 80:
                    usage_indicator = " ⚠️"
                
                users_text += f"{status_icon} *{user['username']}*{usage_indicator}\n"
                users_text += f"🔐 Password: `{user['password']}`\n"
                users_text += f"📊 Status: {user['status']}\n"
                users_text += f"📦 Bandwidth: {bandwidth}\n"
                if user['bandwidth_limit'] and user['bandwidth_limit'] > 0:
                    users_text += f"📊 Usage: {usage_percentage:.1f}%\n"
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

def myinfo_command(update, context):
    """Get user information with password - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
        
    if not context.args:
        update.message.reply_text("Usage: /myinfo <username>\nExample: /myinfo john")
        return
        
    username = context.args[0]
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
            
        # Calculate days remaining if expiration date exists
        days_remaining = ""
        if user['expires']:
            try:
                exp_date = datetime.strptime(user['expires'], '%Y-%m-%d')
                today = datetime.now()
                days_left = (exp_date - today).days
                days_remaining = f" ({days_left} days remaining)" if days_left >= 0 else f" (Expired {-days_left} days ago)"
            except:
                days_remaining = ""
        
        # --- NEW: Calculate bandwidth usage percentage ---
        usage_percentage = 0
        if user['bandwidth_limit'] and user['bandwidth_limit'] > 0:
            usage_percentage = (user['bandwidth_used'] or 0) / (user['bandwidth_limit'] * 1024 * 1024 * 1024) * 100
        
        usage_status = ""
        if usage_percentage >= 100:
            usage_status = " 🚨 *OVER LIMIT*"
        elif usage_percentage >= 80:
            usage_status = " ⚠️ *NEAR LIMIT*"
                
        user_text = f"""
🔍 *User Information: {user['username']}*
🔐 Password: `{user['password']}`
📊 Status: *{user['status'].upper()}*
⏰ Expires: *{user['expires'] or 'Never'}{days_remaining}*
📦 Bandwidth Used: *{format_bytes(user['bandwidth_used'] or 0)}*
🎯 Bandwidth Limit: *{format_bytes(user['bandwidth_limit'] or 0) if user['bandwidth_limit'] else 'Unlimited'}*
📊 Usage Percentage: *{usage_percentage:.1f}%*{usage_status}
⚡ Speed Limit: *{user['speed_limit_up'] or 0} MB/s*
🔗 Max Connections: *{user['concurrent_conn']}*
📅 Created: *{user['created_at'][:10] if user['created_at'] else 'N/A'}*
        """
        update.message.reply_text(user_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        update.message.reply_text("❌ Error retrieving user information")
    finally:
        db.close()

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
        
        # --- NEW: Monitoring Commands ---
        dp.add_handler(CommandHandler("bandwidth", bandwidth_command))
        dp.add_handler(CommandHandler("alerts", alerts_command))

        dp.add_error_handler(error_handler)

        logger.info("🤖 ZIVPN Telegram Bot Started Successfully")
        
        # --- NEW: Start alert monitoring in background ---
        bot = updater.bot
        alert_thread = threading.Thread(target=monitor_alerts, args=(bot,), daemon=True)
        alert_thread.start()
        logger.info("🚨 Alert monitoring system started")
        
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
    
