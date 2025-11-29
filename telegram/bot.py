#!/usr/bin/env python3
"""
ZIVPN Telegram Bot - UUID Version
Enhanced with UUID authentication and modern features
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
import uuid

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

def generate_uuid():
    """Generate UUID for user authentication"""
    return str(uuid.uuid4())

def update_database_schema():
    """Add email_remark column to users table if not exists"""
    db = get_db()
    try:
        # Check if email_remark column exists
        columns = db.execute("PRAGMA table_info(users)").fetchall()
        column_names = [col[1] for col in columns]
        
        if 'email_remark' not in column_names:
            db.execute('ALTER TABLE users ADD COLUMN email_remark TEXT')
            db.commit()
            logger.info("Added email_remark column to users table")
    except Exception as e:
        logger.error(f"Database schema update error: {e}")
    finally:
        db.close()

# Update schema on startup
update_database_schema()

def sync_config_passwords():
    """Sync passwords from database to ZIVPN config"""
    db = get_db()
    try:
        # Get all active users' passwords (UUIDs)
        active_users = db.execute('''
            SELECT password FROM users 
            WHERE status = "active" AND password IS NOT NULL AND password != "" 
                  AND (expires IS NULL OR expires >= CURRENT_DATE)
        ''').fetchall()
        
        # Extract unique passwords (UUIDs)
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

def create_user_with_uuid(user_data):
    """Create user with auto-generated UUID"""
    db = get_db()
    try:
        user_uuid = generate_uuid()
        username = f"user_{int(datetime.now().timestamp())}_{user_uuid[:8]}"
        
        db.execute('''
            INSERT INTO users 
            (username, password, email_remark, expires, port, status, 
             bandwidth_limit, speed_limit_up, concurrent_conn, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username,
            user_uuid,  # Use UUID as password
            user_data.get('email_remark', ''),
            user_data.get('expires'),
            user_data.get('port'),
            'active',
            user_data.get('bandwidth_limit', 0),
            user_data.get('speed_limit', 0),
            user_data.get('concurrent_conn', 1),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        db.commit()
        return username, user_uuid
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def start(update, context):
    """Send welcome message - PUBLIC"""
    user_id = update.effective_user.id
    is_user_admin = is_admin(user_id)
    
    welcome_text = f"""
🤖 *ZIVPN Management Bot - UUID Edition*
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
/adduser <remark> <days> [data_limit] - Add user with UUID
/changepass <user> - Generate new UUID
/deluser <username> - Delete user
/suspend <username> - Suspend user
/activate <username> - Activate user
/ban <username> - Ban user
/unban <username> - Unban user
/renew <username> <days> - Renew user
/reset <username> <days> - Reset expiry
/users - List all users with UUIDs
/myinfo <username> - User details with UUID
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
/adduser <remark> <days> [data_limit] - Add user with UUID
/changepass <user> - Generate new UUID
/deluser <username> - Delete user
/suspend <username> - Suspend user
/activate <username> - Activate user
/ban <username> - Ban user
/unban <username> - Unban user
/renew <username> <days> - Renew user
/reset <username> <days> - Reset expiry
/users - List all users with UUIDs
/myinfo <username> - User details with UUID
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
    db.close()
    
    admin_text = f"""
🛠️ *Admin Panel - UUID Edition*
🌐 Server IP: `{get_server_ip()}`
📊 Total Users: *{total_users}* (Active: *{active_users}*)

*User Management:*
• /adduser <remark> <days> [data_limit] - Add new user with UUID
• /changepass <user> - Generate new UUID for user
• /deluser <username> - Delete user
• /suspend <username> - Suspend user  
• /activate <username> - Activate user
• /ban <username> - Ban user
• /unban <username> - Unban user
• /renew <username> <days> - Renew user (extend from current)
• /reset <username> <days> - Reset expiry (from today)

*Information (With UUIDs):*
• /users - List all users with UUIDs
• /myinfo <username> - User details with UUID
• /stats - Server statistics

*Usage Examples:*
/adduser "Customer Name" 30 100
/changepass user_12345678_abc12345
/users - See all users with UUIDs
"""
    update.message.reply_text(admin_text, parse_mode='Markdown')

def adduser_command(update, context):
    """Add new user with UUID - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Usage: /adduser <remark> <days> [data_limit]\nExample: /adduser \"John Doe\" 30 100")
        return
    
    email_remark = context.args[0]
    try:
        days = int(context.args[1])
    except:
        update.message.reply_text("❌ Invalid days format")
        return
    
    data_limit = 0  # default unlimited
    if len(context.args) > 2:
        try:
            data_limit = int(context.args[2])
        except:
            update.message.reply_text("❌ Invalid data_limit format")
            return
    
    expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    server_ip = get_server_ip()
    
    try:
        user_data = {
            'email_remark': email_remark,
            'expires': expiry_date,
            'bandwidth_limit': data_limit * 1024 * 1024 * 1024,  # Convert to bytes
            'concurrent_conn': 1
        }
        
        username, user_uuid = create_user_with_uuid(user_data)
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        if sync_config_passwords():
            success_text = f"""
✅ *User Added Successfully*

🌐 Server: `{server_ip}`
📧 Remark: `{email_remark}`
👤 Username: `{username}`
🔐 UUID: `{user_uuid}`
📊 Status: Active
⏰ Expires: {expiry_date}
💾 Data Limit: {'Unlimited' if data_limit == 0 else f'{data_limit} GB'}
🔗 Connections: 1

*User can now connect to VPN immediately using the UUID*
"""
        else:
            success_text = f"""
⚠️ *User Added But Sync Warning*

📧 Remark: `{email_remark}`
👤 Username: `{username}`
🔐 UUID: `{user_uuid}`
⏰ Expires: {expiry_date}

💡 User added to database but ZIVPN sync had issues.
   User may need to wait a moment to connect.
"""
        
        update.message.reply_text(success_text, parse_mode='Markdown')
        logger.info(f"User {username} added by admin {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        update.message.reply_text("❌ Error adding user")

def changepass_command(update, context):
    """Generate new UUID for user - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 1:
        update.message.reply_text("Usage: /changepass <username>\nExample: /changepass user_12345678_abc12345")
        return
    
    username = context.args[0]
    new_uuid = generate_uuid()
    
    db = get_db()
    try:
        # Check if user exists
        user = db.execute('SELECT username, email_remark FROM users WHERE username = ?', (username,)).fetchone()
        if not user:
            update.message.reply_text(f"❌ User `{username}` not found")
            return
        
        # Update UUID
        db.execute('UPDATE users SET password = ? WHERE username = ?', (new_uuid, username))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(
            f"✅ New UUID generated for *{user['email_remark'] or username}*\n"
            f"👤 Username: `{username}`\n"
            f"🔐 New UUID: `{new_uuid}`", 
            parse_mode='Markdown'
        )
        logger.info(f"User {username} UUID changed by admin {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error changing UUID: {e}")
        update.message.reply_text("❌ Error changing UUID")
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
        existing = db.execute('SELECT username, email_remark FROM users WHERE username = ?', (username,)).fetchone()
        if not existing:
            update.message.reply_text(f"❌ User `{username}` not found")
            return
        
        # Delete user
        db.execute('DELETE FROM users WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User `{existing['email_remark'] or username}` deleted")
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
        user = db.execute('SELECT email_remark FROM users WHERE username = ?', (username,)).fetchone()
        db.execute('UPDATE users SET status = "suspended" WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User *{user['email_remark'] or username}* suspended\n\n🔓 Unsuspend: /activate {username}")
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
        user = db.execute('SELECT email_remark FROM users WHERE username = ?', (username,)).fetchone()
        db.execute('UPDATE users SET status = "active" WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User *{user['email_remark'] or username}* activated")
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
        user = db.execute('SELECT email_remark FROM users WHERE username = ?', (username,)).fetchone()
        db.execute('UPDATE users SET status = "banned" WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User *{user['email_remark'] or username}* banned\n\n🔓 Unban: /unban {username}")
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
        user = db.execute('SELECT email_remark FROM users WHERE username = ?', (username,)).fetchone()
        db.execute('UPDATE users SET status = "active" WHERE username = ?', (username,))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        update.message.reply_text(f"✅ User *{user['email_remark'] or username}* unbanned")
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
        update.message.reply_text("Usage: /renew <username> <days>\nExample: /renew user_12345678_abc12345 30")
        return
    
    username = context.args[0]
    try:
        days = int(context.args[1])
    except:
        update.message.reply_text("❌ Invalid days format")
        return
    
    db = get_db()
    try:
        user = db.execute('SELECT username, email_remark, expires FROM users WHERE username = ?', (username,)).fetchone()
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

📧 Remark: *{user['email_remark'] or username}*
👤 Username: `{username}`
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
        update.message.reply_text("Usage: /reset <username> <days>\nExample: /reset user_12345678_abc12345 30")
        return
    
    username = context.args[0]
    try:
        days = int(context.args[1])
    except:
        update.message.reply_text("❌ Invalid days format")
        return
    
    db = get_db()
    try:
        user = db.execute('SELECT username, email_remark, expires FROM users WHERE username = ?', (username,)).fetchone()
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

📧 Remark: *{user['email_remark'] or username}*
👤 Username: `{username}`
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
        
        total_users = stats['total_users'] or 0
        active_users = stats['active_users'] or 0
        total_bandwidth = stats['total_bandwidth'] or 0
        today_new_users = today_users['today_users'] or 0
        
        stats_text = f"""
📊 *Server Statistics - UUID Edition*
👥 Total Users: *{total_users}*
🟢 Active Users: *{active_users}*
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
    """List all users with UUIDs - ADMIN ONLY (NO LIMIT)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
        
    db = get_db()
    try:
        # NO LIMIT - show ALL users
        users = db.execute('''
            SELECT username, password, email_remark, status, expires, bandwidth_used, bandwidth_limit, concurrent_conn
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
                data_limit = "Unlimited" if not user['bandwidth_limit'] or user['bandwidth_limit'] == 0 else f"{user['bandwidth_limit'] / 1024 / 1024 / 1024:.0f} GB"
                
                users_text += f"{status_icon} *{user['email_remark'] or user['username']}*\n"
                users_text += f"🔐 UUID: `{user['password']}`\n"
                users_text += f"👤 Username: `{user['username']}`\n"
                users_text += f"📊 Status: {user['status']}\n"
                users_text += f"💾 Data Limit: {data_limit}\n"
                users_text += f"📦 Used: {bandwidth}\n"
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
                data_limit = "Unlimited" if not user['bandwidth_limit'] or user['bandwidth_limit'] == 0 else f"{user['bandwidth_limit'] / 1024 / 1024 / 1024:.0f} GB"
                
                users_text += f"{status_icon} *{user['email_remark'] or user['username']}*\n"
                users_text += f"🔐 UUID: `{user['password']}`\n"
                users_text += f"👤 Username: `{user['username']}`\n"
                users_text += f"📊 Status: {user['status']}\n"
                users_text += f"💾 Data Limit: {data_limit}\n"
                users_text += f"📦 Used: {bandwidth}\n"
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
    """Get user information with UUID - ADMIN ONLY"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
        
    if not context.args:
        update.message.reply_text("Usage: /myinfo <username>\nExample: /myinfo user_12345678_abc12345")
        return
        
    username = context.args[0]
    db = get_db()
    try:
        user = db.execute('''
            SELECT username, password, email_remark, status, expires, bandwidth_used, bandwidth_limit,
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
        
        data_limit = "Unlimited" if not user['bandwidth_limit'] or user['bandwidth_limit'] == 0 else f"{user['bandwidth_limit'] / 1024 / 1024 / 1024:.0f} GB"
        bandwidth_used = format_bytes(user['bandwidth_used'] or 0)
                
        user_text = f"""
🔍 *User Information: {user['email_remark'] or user['username']}*
📧 Remark: {user['email_remark'] or 'N/A'}
👤 Username: `{user['username']}`
🔐 UUID: `{user['password']}`
📊 Status: *{user['status'].upper()}*
⏰ Expires: *{user['expires'] or 'Never'}{days_remaining}*
💾 Data Limit: *{data_limit}*
📦 Bandwidth Used: *{bandwidth_used}*
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

        dp.add_error_handler(error_handler)

        logger.info("🤖 ZIVPN Telegram Bot - UUID Edition Started Successfully")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
    
