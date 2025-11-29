#!/usr/bin/env python3
"""
ZIVPN Enterprise Web Panel - External HTML Template
Downloaded from: https://raw.githubusercontent.com/BaeGyee9/web-bot/main/templates/web.py
"""

from flask import Flask, jsonify, render_template_string, request, redirect, url_for, session, make_response, g
import json, re, subprocess, os, tempfile, hmac, sqlite3, datetime
from datetime import datetime, timedelta
import statistics
import requests

# Configuration
USERS_FILE = "/etc/zivpn/users.json"
CONFIG_FILE = "/etc/zivpn/config.json"
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")
LISTEN_FALLBACK = "5667"
RECENT_SECONDS = 120
LOGO_URL = "https://raw.githubusercontent.com/BaeGyee9/khaing/main/logo.png"

# GitHub Template URL
HTML_TEMPLATE_URL = "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/templates/index.html"

# --- Localization Data ---
TRANSLATIONS = {
    'en': {
        'title': 'ZIVPN Enterprise Panel', 'login_title': 'ZIVPN Panel Login',
        'login_err': 'Invalid Username or Password', 'username': 'Username',
        'password': 'Password', 'login': 'Login', 'logout': 'Logout',
        'contact': 'Contact', 'total_users': 'Total Users',
        'active_users': 'Online Users', 'bandwidth_used': 'Total Data Used',
        'expiry_date': 'Expiry Date', 'status': 'Status', 'traffic': 'Traffic',
        'actions': 'Actions', 'add_user': 'Add User', 'renew_user': 'Renew User',
        'suspend': 'Suspend', 'activate': 'Activate', 'delete': 'Delete',
        'edit': 'Edit', 'days': 'Days', 'submit': 'Submit', 'cancel': 'Cancel',
        'confirm_delete': 'Are you sure you want to delete this user?',
        'confirm_suspend': 'Are you sure you want to suspend this user?',
        'confirm_activate': 'Are you sure you want to activate this user?',
        'confirm_renew': 'Renew user for how many days?',
        'user_added': 'User added successfully.', 'user_updated': 'User updated successfully.',
        'user_deleted': 'User deleted successfully.', 'user_suspended': 'User suspended successfully.',
        'user_activated': 'User activated successfully.', 'user_renewed': 'User renewed successfully.',
        'user_not_found': 'User not found.', 'admin_panel': 'Admin Panel',
        'total_data_limit': 'Total Data Limit', 'current_ip': 'Current IP',
        'device_limit': 'Client Limit', 'current_clients': 'Current Clients', # NEW FIELD TRANSLATION
        'unlimited': 'Unlimited', 'report_gen': 'Generate Report',
        'report_range': 'Please select a date range.', 'daily_traffic': 'Daily Traffic',
        'daily_revenue': 'Daily Revenue', 'report_type': 'Report Type',
    },
    'mm': {
        'title': 'ZIVPN စီမံခန့်ခွဲမှု Panel', 'login_title': 'ZIVPN Panel Login',
        'login_err': 'အသုံးပြုသူအမည် သို့မဟုတ် လျှို့ဝှက်နံပါတ် မမှန်ပါ', 'username': 'အသုံးပြုသူအမည်',
        'password': 'လျှို့ဝှက်နံပါတ်', 'login': 'ဝင်ရောက်မည်', 'logout': 'ထွက်ခွာမည်',
        'contact': 'ဆက်သွယ်ရန်', 'total_users': 'စုစုပေါင်း အသုံးပြုသူ',
        'active_users': 'အွန်လိုင်း အသုံးပြုသူ', 'bandwidth_used': 'အသုံးပြုပြီးသား ဒေတာပမာဏ',
        'expiry_date': 'သက်တမ်းကုန်ဆုံးရက်', 'status': 'အခြေအနေ', 'traffic': 'ဒေတာပမာဏ',
        'actions': 'လုပ်ဆောင်ချက်များ', 'add_user': 'အသုံးပြုသူ အသစ်ထည့်မည်', 'renew_user': 'သက်တမ်းတိုးမည်',
        'suspend': 'ဆိုင်းငံ့မည်', 'activate': 'ပြန်လည်ဖွင့်မည်', 'delete': 'ဖျက်ပစ်မည်',
        'edit': 'ပြင်ဆင်မည်', 'days': 'ရက်ပေါင်း', 'submit': 'အတည်ပြုမည်', 'cancel': 'ဖျက်သိမ်းမည်',
        'confirm_delete': 'ဤအသုံးပြုသူကို ဖျက်ပစ်ရန် သေချာပါသလား။',
        'confirm_suspend': 'ဤအသုံးပြုသူကို ဆိုင်းငံ့ရန် သေချာပါသလား။',
        'confirm_activate': 'ဤအသုံးပြုသူကို ပြန်လည်ဖွင့်ရန် သေချာပါသလား။',
        'confirm_renew': 'ရက်ပေါင်းမည်မျှဖြင့် သက်တမ်းတိုးမလဲ။',
        'user_added': 'အသုံးပြုသူကို အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ။', 'user_updated': 'အသုံးပြုသူ အချက်အလက်များကို ပြင်ဆင်ပြီးပါပြီ။',
        'user_deleted': 'အသုံးပြုသူကို အောင်မြင်စွာ ဖျက်ပစ်ပြီးပါပြီ။', 'user_suspended': 'အသုံးပြုသူကို အောင်မြင်စွာ ဆိုင်းငံ့ပြီးပါပြီ။',
        'user_activated': 'အသုံးပြုသူကို အောင်မြင်စွာ ပြန်လည်ဖွင့်ပြီးပါပြီ။', 'user_renewed': 'အသုံးပြုသူကို အောင်မြင်စွာ သက်တမ်းတိုးပြီးပါပြီ။',
        'user_not_found': 'အသုံးပြုသူကို ရှာမတွေ့ပါ။', 'admin_panel': 'စီမံခန့်ခွဲမှု Panel',
        'total_data_limit': 'စုစုပေါင်း ဒေတာ ကန့်သတ်ချက်', 'current_ip': 'လက်ရှိ IP လိပ်စာ',
        'device_limit': 'ကိရိယာ ကန့်သတ်ချက်', 'current_clients': 'လက်ရှိ ချိတ်ဆက်သူ', # NEW FIELD TRANSLATION
        'unlimited': 'ကန့်သတ်မဲ့', 'report_gen': 'အစီရင်ခံစာ ထုတ်ယူရန်',
        'report_range': 'ကျေးဇူးပြု၍ ရက်စွဲအပိုင်းအခြားကို ရွေးပါ။', 'daily_traffic': 'နေ့စဉ် ဒေတာအသုံးပြုမှု',
        'daily_revenue': 'နေ့စဉ် ဝင်ငွေ', 'report_type': 'အစီရင်ခံစာ အမျိုးအစား',
    },
}

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Database Functions ---
def get_db():
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    # Check and update schema for max_clients (critical for new feature)
    try:
        db.execute('SELECT max_clients FROM users LIMIT 1').fetchone()
    except sqlite3.OperationalError:
        print("Database schema updated: Adding max_clients column...")
        db.execute('ALTER TABLE users ADD COLUMN max_clients INTEGER DEFAULT 1')
        db.commit()
    # Check and update schema for active_clients (for real-time tracking)
    try:
        db.execute('SELECT active_clients FROM users LIMIT 1').fetchone()
    except sqlite3.OperationalError:
        print("Database schema updated: Adding active_clients column...")
        # active_clients should default to 0
        db.execute('ALTER TABLE users ADD COLUMN active_clients INTEGER DEFAULT 0') 
        db.commit()
    return db

def read_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading config file: {e}")
        return {}

def get_online_users():
    online_users = {}
    config = read_config()
    server_list = config.get("SERVERS", [])
    
    # Logic to gather online users from all servers or primary
    # Assuming connection status data is stored in 'online_status' table or similar for API to read.
    # For now, we'll return mock data or rely on an external API/logic not shown here.
    return online_users

def sync_config_passwords():
    """Sync passwords back to the users.json file for the core VPN service"""
    db = get_db()
    users = db.execute("SELECT username, password, status, expiry_date, data_limit_bytes, used_bytes FROM users WHERE status != 'deleted'").fetchall()
    db.close()
    
    user_data = {}
    for user in users:
        # Build the user structure expected by the VPN core system
        # The core system uses the 'status' and 'password'
        user_data[user['username']] = {
            'password': user['password'],
            'status': user['status'],
            'expiry_date': user['expiry_date'],
            'data_limit_bytes': user['data_limit_bytes'],
            'used_bytes': user['used_bytes'],
        }
        
    try:
        write_json_atomic(USERS_FILE, user_data)
        subprocess.run(["systemctl", "restart", "zivpn.service"], check=False) # Restart service to apply changes
        print("Configuration synchronized and zivpn service restarted.")
    except Exception as e:
        print(f"Error syncing configuration: {e}")

def write_json_atomic(path, data):
    """Safely write JSON data to a file."""
    d = json.dumps(data, ensure_ascii=False, indent=2)
    dirn = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=dirn)
    try:
        with os.fdopen(fd, 'w') as tmp_file:
            tmp_file.write(d)
        os.replace(tmp, path)
    except Exception as e:
        os.remove(tmp)
        raise e

# --- Auth/Global Context ---
def require_login():
    """Checks if the user is logged in as Admin"""
    if 'logged_in' not in session:
        return False
    
    # Basic session timeout logic (optional, but good practice)
    last_activity = session.get('last_activity', 0)
    if time.time() - last_activity > 3600: # 1 hour timeout
        session.pop('logged_in', None)
        return False
    session['last_activity'] = time.time()
    return session['logged_in']

@app.before_request
def before_request():
    """Set global language context and logging"""
    g.lang = request.args.get('lang', session.get('lang', 'mm'))
    g.t = TRANSLATIONS.get(g.lang, TRANSLATIONS['mm'])
    session['lang'] = g.lang
    
    if require_login():
        g.is_admin = True
    else:
        g.is_admin = False

# --- Core Routes ---
@app.route("/")
def index():
    t = g.t
    if not require_login():
        return redirect(url_for('login'))
        
    try:
        response = requests.get(HTML_TEMPLATE_URL)
        response.raise_for_status()
        template_content = response.text
    except Exception as e:
        print(f"Error loading HTML template: {e}")
        # Fallback template if fetching fails
        template_content = f"<h1>{t['title']}</h1><p>Error loading content: {e}</p>"

    db = get_db()
    
    # 1. Dashboard Stats
    total_users = db.execute("SELECT COUNT(*) FROM users WHERE status != 'deleted'").fetchone()[0]
    
    # This assumes that the core service (zivpn-api.service) updates the 'active_users' table or similar.
    # For now, we rely on the `active_clients` column which is updated by the server's connection scripts.
    active_users = db.execute("SELECT COUNT(DISTINCT username) FROM users WHERE active_clients > 0 AND status = 'active'").fetchone()[0]
    
    total_used_bytes = db.execute("SELECT SUM(used_bytes) FROM users").fetchone()[0] or 0
    total_data_limit = db.execute("SELECT SUM(data_limit_bytes) FROM users").fetchone()[0] or 0
    
    # Helper for converting bytes to readable format
    def bytes_to_readable(b):
        if b is None: return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if b < 1024.0:
                return f"{b:3.2f} {unit}"
            b /= 1024.0
        return f"{b:3.2f} PB"

    stats = {
        'total_users': total_users,
        'active_users': active_users,
        'used_total': bytes_to_readable(total_used_bytes),
        'limit_total': bytes_to_readable(total_data_limit),
    }

    # 2. Users List
    users_raw = db.execute("SELECT username, status, expiry_date, data_limit_bytes, used_bytes, max_clients, active_clients FROM users WHERE status != 'deleted' ORDER BY username ASC").fetchall()
    
    users = []
    for u in users_raw:
        user_dict = dict(u)
        user_dict['used_readable'] = bytes_to_readable(u['used_bytes'])
        user_dict['limit_readable'] = bytes_to_readable(u['data_limit_bytes'])
        
        # Calculate percentage for progress bar
        if u['data_limit_bytes'] and u['data_limit_bytes'] > 0:
            user_dict['usage_percent'] = min(100, round((u['used_bytes'] / u['data_limit_bytes']) * 100, 2))
        else:
            user_dict['usage_percent'] = 0

        # Status check
        if u['status'] == 'suspended':
            user_dict['display_status'] = t['suspend']
        elif u['expiry_date'] and datetime.strptime(u['expiry_date'], '%Y-%m-%d %H:%M:%S') < datetime.now():
            user_dict['display_status'] = t['expired']
        else:
            user_dict['display_status'] = t['activate']
            
        users.append(user_dict)
    
    db.close()
    
    return render_template_string(template_content, 
                                  t=t, 
                                  lang=g.lang, 
                                  stats=stats, 
                                  users=users, 
                                  bytes_to_readable=bytes_to_readable)


@app.route("/login", methods=["GET", "POST"])
def login():
    t = g.t
    if request.method == "POST":
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        
        # Hardcoded Admin credentials (BEST PRACTICE: use environment variables or encrypted file)
        ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
        ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin")
        
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['logged_in'] = True
            session['last_activity'] = time.time()
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "message": t['login_err']}), 401
            
    try:
        response = requests.get(HTML_TEMPLATE_URL)
        response.raise_for_status()
        template_content = response.text
    except Exception as e:
        template_content = f"<h1>{t['title']}</h1><p>Error loading content: {e}</p>"
        
    # Extract only the login section for rendering
    # This is a simplification; a cleaner way is to use proper template inheritance.
    login_html = template_content.split('<!-- START_LOGIN_BLOCK -->')[1].split('<!-- END_LOGIN_BLOCK -->')[0]

    return render_template_string(login_html, t=t, lang=g.lang)


@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


# --- API Routes for User Management ---

# --- API: Get All Users (for dynamic table update) ---
@app.route("/api/users")
def get_users_api():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    db = get_db()
    
    # IMPORTANT: Include max_clients and active_clients in the SELECT query
    users_raw = db.execute("SELECT username, password, status, expiry_date, data_limit_bytes, used_bytes, max_clients, active_clients FROM users WHERE status != 'deleted' ORDER BY username ASC").fetchall()
    db.close()
    
    # Helper for converting bytes to readable format (local scope)
    def bytes_to_readable(b):
        if b is None: return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if b < 1024.0:
                return f"{b:3.2f} {unit}"
            b /= 1024.0
        return f"{b:3.2f} PB"

    users = []
    for u in users_raw:
        user_dict = dict(u)
        user_dict['used_readable'] = bytes_to_readable(u['used_bytes'])
        user_dict['limit_readable'] = bytes_to_readable(u['data_limit_bytes'])
        
        # Usage percentage
        if u['data_limit_bytes'] and u['data_limit_bytes'] > 0:
            user_dict['usage_percent'] = min(100, round((u['used_bytes'] / u['data_limit_bytes']) * 100, 2))
        else:
            user_dict['usage_percent'] = 0

        # Status check
        if u['status'] == 'suspended':
            user_dict['display_status'] = t['suspend']
        elif u['expiry_date'] and datetime.strptime(u['expiry_date'], '%Y-%m-%d %H:%M:%S') < datetime.now():
            user_dict['display_status'] = t['expired']
        else:
            user_dict['display_status'] = t['activate']
            
        users.append(user_dict)
        
    # 3. Dashboard Stats (Re-calculate stats for API)
    total_users = db.execute("SELECT COUNT(*) FROM users WHERE status != 'deleted'").fetchone()[0]
    active_users = db.execute("SELECT COUNT(DISTINCT username) FROM users WHERE active_clients > 0 AND status = 'active'").fetchone()[0]
    total_used_bytes = db.execute("SELECT SUM(used_bytes) FROM users").fetchone()[0] or 0
    total_data_limit = db.execute("SELECT SUM(data_limit_bytes) FROM users").fetchone()[0] or 0

    stats = {
        'total_users': total_users,
        'active_users': active_users,
        'used_total': bytes_to_readable(total_used_bytes),
        'limit_total': bytes_to_readable(total_data_limit),
    }

    return jsonify({"ok": True, "users": users, "stats": stats})

# --- API: Add User ---
@app.route("/api/user/add", methods=["POST"])
def add_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    days = data.get('days')
    data_limit_gb = data.get('data_limit_gb')
    max_clients = data.get('max_clients', 1) # NEW: Get client limit, default to 1
    
    if not username or not password or not days:
        return jsonify({"ok": False, "message": "Missing required fields."}), 400
        
    try:
        days = int(days)
        data_limit_gb = int(data_limit_gb) if data_limit_gb else 0
        max_clients = int(max_clients) # Ensure max_clients is an integer
        if max_clients <= 0: max_clients = 1 # Must be at least 1
    except ValueError:
        return jsonify({"ok": False, "message": "Invalid numeric input."}), 400
        
    expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    data_limit_bytes = data_limit_gb * (1024**3)
    
    db = get_db()
    try:
        # Check if user already exists
        if db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
            return jsonify({"ok": False, "message": f"User '{username}' already exists."}), 409
            
        db.execute('''
            INSERT INTO users (username, password, status, expiry_date, data_limit_bytes, used_bytes, max_clients)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, password, 'active', expiry_date, data_limit_bytes, 0, max_clients))
        db.commit()
        sync_config_passwords()
        return jsonify({"ok": True, "message": t['user_added']})
    finally:
        db.close()

# --- API: Delete User ---
@app.route("/api/user/delete", methods=["POST"])
def delete_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    
    if not user: return jsonify({"ok": False, "message": "Missing username"}), 400
    
    db = get_db()
    try:
        db.execute('UPDATE users SET status = ? WHERE username = ?', ('deleted', user))
        db.commit()
        sync_config_passwords()
        return jsonify({"ok": True, "message": t['user_deleted']})
    finally:
        db.close()

# --- API: Suspend User ---
@app.route("/api/user/suspend", methods=["POST"])
def suspend_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    
    if not user: return jsonify({"ok": False, "message": "Missing username"}), 400
    
    db = get_db()
    try:
        db.execute('UPDATE users SET status = ? WHERE username = ?', ('suspended', user))
        db.commit()
        sync_config_passwords()
        return jsonify({"ok": True, "message": t['user_suspended']})
    finally:
        db.close()

# --- API: Activate User ---
@app.route("/api/user/activate", methods=["POST"])
def activate_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    
    if not user: return jsonify({"ok": False, "message": "Missing username"}), 400
    
    db = get_db()
    try:
        db.execute('UPDATE users SET status = ? WHERE username = ?', ('active', user))
        db.commit()
        sync_config_passwords()
        return jsonify({"ok": True, "message": t['user_activated']})
    finally:
        db.close()

# --- API: Renew User ---
@app.route("/api/user/renew", methods=["POST"])
def renew_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    days = data.get('days')
    
    if not user or not days: return jsonify({"ok": False, "message": "Missing required fields"}), 400
    
    try:
        days = int(days)
    except ValueError:
        return jsonify({"ok": False, "message": "Invalid days value"}), 400
        
    db = get_db()
    try:
        user_data = db.execute('SELECT expiry_date FROM users WHERE username = ?', (user,)).fetchone()
        if not user_data:
            return jsonify({"ok": False, "message": t['user_not_found']}), 404
            
        current_expiry = datetime.strptime(user_data['expiry_date'], '%Y-%m-%d %H:%M:%S')
        
        # If already expired, start from now. If not expired, add to current expiry.
        if current_expiry < datetime.now():
            new_expiry = datetime.now() + timedelta(days=days)
        else:
            new_expiry = current_expiry + timedelta(days=days)
            
        new_expiry_str = new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        
        db.execute('UPDATE users SET expiry_date = ?, status = ? WHERE username = ?', (new_expiry_str, 'active', user))
        db.commit()
        sync_config_passwords()
        return jsonify({"ok": True, "message": t['user_renewed']})
    finally:
        db.close()

# --- API: Reset Traffic ---
@app.route("/api/user/reset_traffic", methods=["POST"])
def reset_traffic():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    
    if not user: return jsonify({"ok": False, "message": "Missing username"}), 400
    
    db = get_db()
    try:
        db.execute('UPDATE users SET used_bytes = ? WHERE username = ?', (0, user))
        db.commit()
        sync_config_passwords() # Should trigger sync if traffic is monitored by core service
        return jsonify({"ok": True, "message": "Traffic reset successfully."})
    finally:
        db.close()

# --- API: Edit User Details (Password, Data Limit, Max Clients) ---
@app.route("/api/user/edit", methods=["POST"])
def edit_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    new_password = data.get('password')
    data_limit_gb = data.get('data_limit_gb')
    max_clients = data.get('max_clients') # NEW: Max Clients
    
    if not user:
        return jsonify({"ok": False, "message": "Missing username"}), 400
        
    db = get_db()
    try:
        updates = []
        params = []
        
        if new_password:
            updates.append("password = ?")
            params.append(new_password)
            
        if data_limit_gb is not None:
            try:
                data_limit_bytes = int(data_limit_gb) * (1024**3)
                updates.append("data_limit_bytes = ?")
                params.append(data_limit_bytes)
            except ValueError:
                return jsonify({"ok": False, "message": "Invalid data limit input."}), 400

        # NEW: Update max_clients
        if max_clients is not None:
            try:
                max_clients_int = int(max_clients)
                if max_clients_int <= 0: max_clients_int = 1 # Must be at least 1
                updates.append("max_clients = ?")
                params.append(max_clients_int)
            except ValueError:
                return jsonify({"ok": False, "message": "Invalid client limit input."}), 400

        if not updates:
            return jsonify({"ok": False, "message": "No changes provided."}), 400
            
        sql = f"UPDATE users SET {', '.join(updates)} WHERE username = ?"
        params.append(user)
        
        db.execute(sql, tuple(params))
        db.commit()
        sync_config_passwords()
        return jsonify({"ok": True, "message": t['user_updated']})
    finally:
        db.close()

# --- API: Update User Password (Legacy, kept for compatibility) ---
@app.route("/api/user/update", methods=["POST"])
def update_user_password():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    password = data.get('password')
    
    if user and password:
        db = get_db()
        db.execute('UPDATE users SET password = ? WHERE username = ?', (password, user))
        db.commit()
        db.close()
        sync_config_passwords()
        return jsonify({"ok": True, "message": "User password updated successfully."})
    else:
        return jsonify({"ok": False, "message": "Missing username or password."}), 400

# --- API: Get Reports ---
@app.route("/api/reports")
def get_reports():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401

    from_date = request.args.get('from')
    to_date = request.args.get('to')
    report_type = request.args.get('type')
    
    # Basic date validation
    try:
        if from_date: datetime.strptime(from_date, '%Y-%m-%d')
        if to_date: datetime.strptime(to_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({"message": "Invalid date format. Use YYYY-MM-DD."}), 400

    db = get_db()
    try:
        data = []
        
        # This assumes you have 'traffic_log' and 'billing' tables for reporting
        if report_type == 'traffic':
            # Example query for daily traffic (assuming traffic_log table exists)
            data = db.execute('''
                SELECT 
                    DATE(created_at) as date, 
                    SUM(bytes_used) as total_bytes_used
                FROM traffic_log
                WHERE created_at BETWEEN ? AND datetime(?, '+1 day')
                GROUP BY date
                ORDER BY date ASC
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()

        elif report_type == 'revenue':
            # Example query for revenue (assuming billing table exists)
            data = db.execute('''
                SELECT plan_type, currency, SUM(amount) as total_revenue
                FROM billing
                WHERE created_at BETWEEN ? AND datetime(?, '+1 day')
                GROUP BY plan_type, currency
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()
        
        else:
            return jsonify({"message": "Invalid report type"}), 400

        return jsonify([dict(d) for d in data])
    finally:
        db.close()


if __name__ == "__main__":
    import time
    app.run(host='0.0.0.0', port=os.environ.get("WEB_PORT", 8080), debug=True)

