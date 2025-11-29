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
import uuid # ⬅️ ADDED: For UUID generation

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
        'active_users': 'Online Users', 'bandwidth_used': 'Bandwidth Used',
        'expiry_date': 'Expiry Date', 'status': 'Status', 'action': 'Action',
        'add_user': 'Add User', 'delete_user': 'Delete User', 
        'renew_user': 'Renew User', 'suspend_user': 'Suspend User',
        'settings': 'Settings', 'report_range': 'Please select a date range for the report.',
        'user_not_found': 'User not found in database.',
        'edit_user': 'Edit User', 'update_user': 'Update User',
        'current_password': 'Current Password', 'new_password': 'New Password',
        'change_password': 'Change Password', 'password_updated': 'Password updated successfully!',
        'password_fail': 'Failed to update password.',
        'update_pass': 'Change Account Password',
        'report_title': 'Reports & Analytics',
        'select_report': 'Select Report Type',
        'from_date': 'From Date',
        'to_date': 'To Date',
        'generate_report': 'Generate Report',
        'type_all': 'All Users',
        'type_active': 'Active Users',
        'type_stats': 'Connection Stats',
        'type_revenue': 'Revenue Summary',
        # New Translations for UI/UX changes
        'user_email': 'User/Email (for notes)', # Changed to be more descriptive
        'data_limit': 'Data Limit (GB, 0 for Unlimited)', # Added for bandwidth limit
        'auto_gen_pass': 'Auto-Generate Password', # Added for UUID
        'is_enabled': 'Enabled', # New column for status
        'status_enabled': 'Enabled',
        'status_disabled': 'Disabled',
        'enable': 'Enable',
        'disable': 'Disable',
        'edit_expiry': 'Edit Expiry Date'
    },
    'my': {
        'title': 'ZIVPN စီမံခန့်ခွဲမှု', 'login_title': 'ZIVPN Panel ဝင်ရန်',
        'login_err': 'အသုံးပြုသူအမည် (သို့) လျှို့ဝှက်နံပါတ် မှားယွင်းနေပါသည်။', 'username': 'အသုံးပြုသူအမည်',
        'password': 'လျှို့ဝှက်နံပါတ်', 'login': 'ဝင်ရောက်ပါ', 'logout': 'ထွက်ခွာပါ',
        'contact': 'ဆက်သွယ်ရန်', 'total_users': 'စုစုပေါင်း အသုံးပြုသူ',
        'active_users': 'အွန်လိုင်း အသုံးပြုသူ', 'bandwidth_used': 'သုံးစွဲပြီးသော ဒေတာ',
        'expiry_date': 'သက်တမ်းကုန်ဆုံးရက်', 'status': 'အခြေအနေ', 'action': 'လုပ်ဆောင်ချက်',
        'add_user': 'အသုံးပြုသူ ထည့်ရန်', 'delete_user': 'ဖျက်ပစ်ရန်', 
        'renew_user': 'သက်တမ်းတိုးရန်', 'suspend_user': 'ဆိုင်းငံ့ရန်',
        'settings': 'ဆက်တင်များ', 'report_range': 'အစီရင်ခံစာအတွက် ရက်စွဲအပိုင်းအခြား ရွေးချယ်ပါ။',
        'user_not_found': 'အသုံးပြုသူကို ဒေတာဘေ့စ်တွင် မတွေ့ပါ။',
        'edit_user': 'အသုံးပြုသူ ပြင်ဆင်ရန်', 'update_user': 'အသုံးပြုသူ အချက်အလက်ပြင်ဆင်ရန်',
        'current_password': 'လက်ရှိ လျှို့ဝှက်နံပါတ်', 'new_password': 'လျှို့ဝှက်နံပါတ် အသစ်',
        'change_password': 'လျှို့ဝှက်နံပါတ် ပြောင်းရန်', 'password_updated': 'လျှို့ဝှက်နံပါတ် အောင်မြင်စွာ ပြောင်းလဲပြီးပါပြီ။',
        'password_fail': 'လျှို့ဝှက်နံပါတ် ပြောင်းလဲရန် မအောင်မြင်ပါ။',
        'update_pass': 'အကောင့် လျှို့ဝှက်နံပါတ် ပြောင်းရန်',
        'report_title': 'အစီရင်ခံစာများ & ခွဲခြမ်းစိတ်ဖြာချက်',
        'select_report': 'အစီရင်ခံစာ အမျိုးအစား ရွေးချယ်ပါ',
        'from_date': 'မှစ၍ ရက်စွဲ',
        'to_date': 'အထိ ရက်စွဲ',
        'generate_report': 'အစီရင်ခံစာ ထုတ်ပါ',
        'type_all': 'အသုံးပြုသူ အားလုံး',
        'type_active': 'အသုံးပြုနေသူများ',
        'type_stats': 'ချိတ်ဆက်မှု စာရင်းဇယား',
        'type_revenue': 'ဝင်ငွေ အကျဉ်းချုပ်',
        # New Translations for UI/UX changes
        'user_email': 'အသုံးပြုသူ/မှတ်စု (Email)',
        'data_limit': 'ဒေတာ ကန့်သတ်ချက် (GB, 0 ဆိုလျှင် အကန့်အသတ်မဲ့)',
        'auto_gen_pass': 'အလိုအလျောက် နံပါတ်ထုတ်ပါ',
        'is_enabled': 'ဖွင့်ထားခြင်း',
        'status_enabled': 'ဖွင့်ထားသည်',
        'status_disabled': 'ပိတ်ထားသည်',
        'enable': 'ဖွင့်ရန်',
        'disable': 'ပိတ်ရန်',
        'edit_expiry': 'သက်တမ်းပြင်ရန်'
    }
}


# --- Flask Setup ---
app = Flask(__name__)
# The secret key is essential for managing sessions (login)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# --- Database Functions ---
def get_db():
    db = sqlite3.connect(DATABASE_PATH)
    # Allows fetching results as dictionaries
    db.row_factory = sqlite3.Row 
    return db

def init_db():
    """Ensure the necessary columns and tables exist for the new features."""
    db = get_db()
    cursor = db.cursor()
    
    # 1. Check/Add `is_enabled` and `data_limit_gb` to `users` table
    try:
        # Check if the column exists by trying to access it
        cursor.execute("SELECT is_enabled, data_limit_gb FROM users LIMIT 1")
    except sqlite3.OperationalError:
        # Columns don't exist, add them
        print("Database schema updating: Adding is_enabled and data_limit_gb to users table.")
        cursor.execute("ALTER TABLE users ADD COLUMN is_enabled INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE users ADD COLUMN data_limit_gb REAL DEFAULT 0.0")
        db.commit()
    
    # 2. Ensure `billing` table exists (if not already handled by ZIVPN core)
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                plan_type TEXT,
                amount REAL,
                currency TEXT,
                created_at TEXT
            )
        """)
        db.commit()
    except Exception as e:
        print(f"Billing table creation skipped or failed: {e}")

    db.close()
    
# Run DB initialization at startup
init_db()

# --- Utility Functions ---

def sync_config_passwords():
    """Reads all user passwords from the DB and syncs them to a users.json file
       that the ZIVPN core service might use."""
    try:
        db = get_db()
        # Fetch username, password, and *new* is_enabled status
        users_data = db.execute('SELECT username, password, is_enabled FROM users').fetchall()
        db.close()
        
        # Format the data for the ZIVPN core config (if it expects a JSON file)
        # ONLY include users that are currently ENABLED (is_enabled=1)
        sync_data = {}
        for row in users_data:
            user = dict(row)
            if user.get('is_enabled') == 1:
                sync_data[user['username']] = user['password']
                
        dirn = os.path.dirname(USERS_FILE)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=dirn)
        
        with os.fdopen(fd, 'w') as f:
            json.dump(sync_data, f, indent=2)
            
        # Atomic rename to replace the old file
        os.replace(tmp, USERS_FILE)
        
        # Trigger a reload of the ZIVPN service (optional, but good practice)
        subprocess.run(['sudo', 'systemctl', 'reload-or-restart', 'zivpn.service'], check=False)
        return True
    except Exception as e:
        print(f"Error syncing user config: {e}")
        return False

def require_login():
    """Checks if the user is logged in."""
    # Also ensures the translation object 't' is available globally for the request
    lang = request.cookies.get('lang', 'my')
    g.t = TRANSLATIONS.get(lang, TRANSLATIONS['my'])
    g.lang = lang
    return session.get('logged_in')

def get_current_user():
    """Returns the current logged-in username or None."""
    return session.get('username')

# --- Before/After Request Hooks ---

@app.before_request
def before_request():
    # Setup localization and check login status
    require_login()
    
# --- Routes ---

@app.route("/")
def index():
    if not require_login():
        return redirect(url_for('login'))

    try:
        db = get_db()
        
        # 1. Summary Data (Total/Active/Bandwidth)
        summary = db.execute("""
            SELECT 
                COUNT(username) AS total_users,
                SUM(CASE WHEN is_enabled = 1 THEN 1 ELSE 0 END) AS enabled_users,
                SUM(bytes_used) AS total_bytes_used
            FROM users
        """).fetchone()

        # 2. Online Users (Last seen in RECENT_SECONDS and is_enabled=1)
        # Note: This is a placeholder for ZIVPN's specific tracking logic,
        # assuming `last_seen` column exists and tracks timestamp.
        time_threshold = (datetime.now() - timedelta(seconds=RECENT_SECONDS)).strftime('%Y-%m-%d %H:%M:%S')
        online_users_count = db.execute("""
            SELECT COUNT(username) FROM users 
            WHERE last_seen > ? AND is_enabled = 1
        """, (time_threshold,)).fetchone()[0]

        # 3. Full User List (including new columns)
        users = db.execute('''
            SELECT username, password, email, created_at, expiry_date, is_enabled,
                   bytes_used, data_limit_gb, last_seen
            FROM users
            ORDER BY username ASC
        ''').fetchall()
        
        # 4. Connections/Traffic Stats (Placeholder - depends on ZIVPN Core)
        # Fetching last 10 connections for display
        connections = db.execute('''
            SELECT username, ip_address, bytes_received, bytes_sent, connected_at
            FROM connections 
            ORDER BY connected_at DESC LIMIT 10
        ''').fetchall()
        
        # 5. Revenue Summary (Placeholder - depends on ZIVPN Core)
        revenue = db.execute('SELECT SUM(amount) FROM billing WHERE currency = "MMK"').fetchone()[0] or 0

        db.close()
        
        # Prepare context data
        context = {
            't': g.t, # Translations
            'lang': g.lang,
            'user': get_current_user(),
            'total_users': summary['total_users'],
            'enabled_users': summary['enabled_users'],
            'online_users': online_users_count,
            'total_bytes_used': summary['total_bytes_used'],
            'total_revenue': revenue,
            'users': [dict(u) for u in users],
            'connections': [dict(c) for c in connections],
            'logo_url': LOGO_URL
        }

        # Fetch the HTML template from the remote source or use a local backup
        template_content = requests.get(HTML_TEMPLATE_URL).text
        return render_template_string(template_content, **context)

    except Exception as e:
        # Handle database or other runtime errors
        print(f"An error occurred in index route: {e}")
        # Return a simple error page
        return f"<h1>Error Loading Panel</h1><p>Database or script error: {e}</p>", 500

@app.route("/login", methods=["GET", "POST"])
def login():
    t = g.t
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Basic hardcoded admin check (can be expanded to DB check)
        # This uses the current ZIVPN's admin credentials logic
        admin_data = {}
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                admin_data = config.get('admin', {})
        except Exception:
            # Fallback or initial config doesn't exist
            pass
            
        if username == admin_data.get('user') and password == admin_data.get('pass'):
            session['logged_in'] = True
            session['username'] = username
            resp = make_response(redirect(url_for('index')))
            resp.set_cookie('lang', g.lang, max_age=3600*24*30)
            return resp
        
        return render_template_string(get_login_template(), error=t['login_err'], t=t)
        
    return render_template_string(get_login_template(), error=None, t=t)

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

# --- API Endpoints ---

@app.route("/api/user/add", methods=["POST"])
def add_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    username = data.get('user')
    password = data.get('password')
    email = data.get('email', '') # Now used for notes/email field
    expiry = data.get('expiry')
    # ⬅️ ADDED: Get new data limit, default to 0.0 (Unlimited)
    data_limit_gb = float(data.get('data_limit_gb', 0.0)) 
    
    if not username or not expiry:
        return jsonify({"ok": False, "err": "Username and Expiry Date are required."}), 400

    # ⬅️ MODIFIED: If password is empty/auto_gen_pass is true, generate a UUID
    if not password or data.get('auto_gen_pass'):
        password = str(uuid.uuid4())
    
    # Simple check for date format (YYYY-MM-DD)
    try:
        datetime.strptime(expiry, '%Y-%m-%d')
    except ValueError:
        return jsonify({"ok": False, "err": "Invalid expiry date format. Use YYYY-MM-DD"}), 400

    try:
        db = get_db()
        
        # Check if user already exists
        if db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone():
            db.close()
            return jsonify({"ok": False, "err": f"User '{username}' already exists."}), 400
            
        # ⬅️ MODIFIED: Insert with new columns: is_enabled (1) and data_limit_gb
        db.execute('''
            INSERT INTO users (username, password, email, expiry_date, created_at, is_enabled, data_limit_gb)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        ''', (username, password, email, expiry, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data_limit_gb))
        
        db.commit()
        db.close()
        
        sync_config_passwords() # Sync the updated user list
        
        return jsonify({"ok": True, "message": f"User {username} added successfully.", "password": password})
    except Exception as e:
        return jsonify({"ok": False, "err": f"Database error: {e}"}), 500

@app.route("/api/user/delete", methods=["POST"])
def delete_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    
    if user:
        db = get_db()
        db.execute('DELETE FROM users WHERE username = ?', (user,))
        db.commit()
        db.close()
        
        sync_config_passwords()
        return jsonify({"ok": True, "message": f"User {user} deleted successfully."})
        
    return jsonify({"ok": False, "err": "Username is required for deletion."}), 400

@app.route("/api/user/renew", methods=["POST"])
def renew_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    new_expiry_date = data.get('expiry')
    
    if not user or not new_expiry_date:
        return jsonify({"ok": False, "err": "Username and new expiry date are required."}), 400

    try:
        # Simple check for date format (YYYY-MM-DD)
        datetime.strptime(new_expiry_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({"ok": False, "err": "Invalid expiry date format. Use YYYY-MM-DD"}), 400

    db = get_db()
    
    # ⬅️ MODIFIED: Allow updating expiry date directly
    db.execute('UPDATE users SET expiry_date = ? WHERE username = ?', (new_expiry_date, user))
    db.commit()
    db.close()
    
    # Note: Sync not strictly needed here unless expiry triggers core config changes, 
    # but safe to include if in doubt.
    # sync_config_passwords() 
    
    return jsonify({"ok": True, "message": f"User {user} expiry updated to {new_expiry_date}."})

@app.route("/api/user/status", methods=["POST"])
def update_user_status():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    # status: 1 for enabled, 0 for disabled
    status = data.get('status')
    
    if not user or status is None:
        return jsonify({"ok": False, "err": "Username and status are required."}), 400
        
    try:
        status_int = int(status)
        if status_int not in [0, 1]:
            return jsonify({"ok": False, "err": "Status must be 0 (Disabled) or 1 (Enabled)."}), 400
    except ValueError:
        return jsonify({"ok": False, "err": "Status must be a number (0 or 1)."}), 400

    db = get_db()
    # ⬅️ ADDED: Update the new `is_enabled` column
    db.execute('UPDATE users SET is_enabled = ? WHERE username = ?', (status_int, user))
    db.commit()
    db.close()
    
    sync_config_passwords() # Sync is CRITICAL here to apply the enable/disable change
    
    action = "Enabled" if status_int == 1 else "Disabled"
    return jsonify({"ok": True, "message": f"User {user} has been {action}."})


@app.route("/api/user/update", methods=["POST"])
def update_user():
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
        return jsonify({"ok": True, "message": t['password_updated']})
        
    return jsonify({"ok": False, "err": t['password_fail']}), 400

@app.route("/api/reports", methods=["GET"])
def get_reports():
    if not require_login(): return jsonify({"message": g.t['login_err']}), 401
    
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    report_type = request.args.get('type')
    
    if not report_type:
        return jsonify({"message": "Report type is required"}), 400

    db = get_db()
    try:
        db.row_factory = sqlite3.Row # Ensure rows are dicts
        
        # --- Type: all ---
        if report_type == 'all':
            # ⬅️ MODIFIED: Include new columns in the ALL report
            data = db.execute('''
                SELECT username, email, created_at, expiry_date, bytes_used, is_enabled, data_limit_gb
                FROM users
                WHERE created_at BETWEEN ? AND datetime(?, '+1 day')
                ORDER BY created_at DESC
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()
        
        # --- Type: active (Enabled Users) ---
        elif report_type == 'active':
             data = db.execute('''
                SELECT username, email, created_at, expiry_date, bytes_used, data_limit_gb
                FROM users
                WHERE is_enabled = 1 AND created_at BETWEEN ? AND datetime(?, '+1 day')
                ORDER BY created_at DESC
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()
            
        # --- Type: stats (Daily Connection Stats) ---
        elif report_type == 'stats':
            # This logic assumes a `connections_daily` table or similar exists
            data = db.execute('''
                SELECT strftime('%Y-%m-%d', connected_at) as date,
                       COUNT(DISTINCT username) as total_users,
                       SUM(bytes_received + bytes_sent) as total_traffic
                FROM connections
                WHERE connected_at BETWEEN ? AND datetime(?, '+1 day')
                GROUP BY date
                ORDER BY date ASC
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()

        # --- Type: revenue ---
        elif report_type == 'revenue':
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

# --- Login Template (Used when HTML template is not available) ---
def get_login_template():
    # Simple hardcoded login page for when index.html cannot be fetched
    return """
<!DOCTYPE html>
<html>
<head>
    <title>{{t.login_title}}</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
        body { font-family: sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 300px; text-align: center; }
        .login-card h2 { margin-bottom: 20px; color: #3b82f6; }
        .login-card input[type="text"], .login-card input[type="password"] { width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        .login-card button { width: 100%; padding: 10px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        .error { color: #ef4444; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>{{t.login_title}}</h2>
        {% if error %}
        <div class="error">{{error}}</div>
        {% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="{{t.username}}" required>
            <input type="password" name="password" placeholder="{{t.password}}" required>
            <button type="submit">{{t.login}}</button>
        </form>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    # In a production environment, use a proper WSGI server (Gunicorn/uWSGI)
    # The default port is 5000, but often overridden by ZIVPN install scripts
    port = int(os.environ.get("FLASK_RUN_PORT", 8081))
    app.run(debug=True, host='0.0.0.0', port=port)
