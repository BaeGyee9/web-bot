#!/usr/bin/env python3
"""
ZIVPN Enterprise Web Panel - External HTML Template
Downloaded from: https://raw.githubusercontent.com/BaeGyee9/web-bot/main/templates/web.py
"""

from flask import Flask, jsonify, render_template_string, request, redirect, url_for, session, make_response, g
import json, re, subprocess, os, tempfile, hmac, sqlite3, datetime, uuid # uuid ထည့်သွင်းထားသည်
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

# --- Helper Functions (Added for completeness, assumed to be in the original script) ---
def read_json(path, default):
    try:
        with open(path,"r") as f: return json.load(f)
    except Exception:
        return default

def write_json_atomic(path, data):
    # Atomically write JSON data to path
    d=json.dumps(data, ensure_ascii=False, indent=2)
    dirn=os.path.dirname(path); fd,tmp=tempfile.mkstemp(prefix=".tmp-", dir=dirn)
    try:
        with os.fdopen(fd, 'w') as f: f.write(d)
        os.replace(tmp, path)
    except Exception:
        os.remove(tmp)
        raise

# --- Localization Data ---
TRANSLATIONS = {
    'en': {
        'title': 'ZIVPN Enterprise Panel', 'login_title': 'ZIVPN Panel Login',
        'login_err': 'Invalid Username or Password', 'username': 'Username/Email',
        'password': 'Password', 'login': 'Login', 'logout': 'Logout',
        'contact': 'Contact', 'total_users': 'Total Users',
        'active_users': 'Online Users', 'bandwidth_used': 'Total Bandwidth Used',
        'add_user': 'Add User', 'del_user': 'Delete User', 'update_user': 'Update User',
        'user_added': 'User added successfully', 'user_deleted': 'User deleted successfully',
        'user_updated': 'User updated successfully', 'user_exists': 'User already exists',
        'user_not_found': 'User not found', 'username_required': 'Username is required',
        'password_required': 'Password is required', 'last_online': 'Last Online',
        'last_30_days': 'Last 30 Days', 'monthly_traffic': 'Monthly Traffic Report',
        'revenue_report': 'Revenue Report', 'report_range': 'Please select a date range',
        'invalid_date': 'Invalid date format (must be YYYY-MM-DD)',
        # New Translations for X-UI features
        'data_limit': 'Data Limit (MB)', 
        'expire_date': 'Expiration Date', 
        'unlimited': 'Unlimited',
        'status': 'Status',
        'toggle_user_status': 'Toggle Status',
        'user_suspended': 'User Suspended successfully',
        'user_activated': 'User Activated successfully',
        'current_status': 'Current Status'
    },
    'my': {
        'title': 'ZIVPN Enterprise Panel', 'login_title': 'ZIVPN Panel ဝင်ရန်',
        'login_err': 'အသုံးပြုသူအမည် သို့မဟုတ် လျှို့ဝှက်နံပါတ် မမှန်ပါ', 'username': 'အသုံးပြုသူအမည်/အီးမေးလ်',
        'password': 'လျှို့ဝှက်နံပါတ်', 'login': 'ဝင်ရောက်ပါ', 'logout': 'ထွက်ခွာပါ',
        'contact': 'ဆက်သွယ်ရန်', 'total_users': 'အသုံးပြုသူ စုစုပေါင်း',
        'active_users': 'အွန်လိုင်း အသုံးပြုသူ', 'bandwidth_used': 'ဒေတာ အသုံးပြုမှု စုစုပေါင်း',
        'add_user': 'အသုံးပြုသူ အသစ်ထည့်ရန်', 'del_user': 'အသုံးပြုသူ ဖျက်ရန်', 'update_user': 'အသုံးပြုသူ ပြင်ရန်',
        'user_added': 'အသုံးပြုသူကို အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ', 'user_deleted': 'အသုံးပြုသူကို အောင်မြင်စွာ ဖျက်ပစ်ပြီးပါပြီ',
        'user_updated': 'အသုံးပြုသူကို အောင်မြင်စွာ ပြင်ဆင်ပြီးပါပြီ', 'user_exists': 'အသုံးပြုသူ ရှိပြီးသားဖြစ်နေသည်',
        'user_not_found': 'အသုံးပြုသူ မတွေ့ရှိပါ', 'username_required': 'အသုံးပြုသူအမည် လိုအပ်ပါသည်',
        'password_required': 'လျှို့ဝှက်နံပါတ် လိုအပ်ပါသည်', 'last_online': 'နောက်ဆုံး အွန်လိုင်းဝင်ခဲ့သည်',
        'last_30_days': 'နောက်ဆုံး ရက် ၃၀', 'monthly_traffic': 'လစဉ် ဒေတာ အသုံးပြုမှု မှတ်တမ်း',
        'revenue_report': 'ဝင်ငွေ မှတ်တမ်း', 'report_range': 'ကျေးဇူးပြု၍ ရက်စွဲ အကွာအဝေး ရွေးချယ်ပါ',
        'invalid_date': 'ရက်စွဲ ပုံစံ မမှန်ပါ (YYYY-MM-DD ဖြစ်ရပါမည်)',
        # New Translations for X-UI features (မြန်မာဘာသာဖြင့် ထပ်တိုး)
        'data_limit': 'ဒေတာ ကန့်သတ်ချက် (MB)', 
        'expire_date': 'သက်တမ်းကုန်ဆုံးရက်', 
        'unlimited': 'ကန့်သတ်မဲ့',
        'status': 'အခြေအနေ',
        'toggle_user_status': 'အခြေအနေ ပြောင်းလဲ',
        'user_suspended': 'အသုံးပြုသူကို အောင်မြင်စွာ ပိတ်လိုက်ပါပြီ',
        'user_activated': 'အသုံးပြုသူကို အောင်မြင်စွာ ဖွင့်လိုက်ပါပြီ',
        'current_status': 'လက်ရှိ အခြေအနေ'
    }
}

app = Flask(__name__)
app.secret_key = os.urandom(24) # ယာယီ Secret Key

# --- Database setup functions ---

def get_db():
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    
    # 1. Create tables if they don't exist
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            telegram_id INTEGER,
            role TEXT DEFAULT 'user',
            used_traffic INTEGER DEFAULT 0,
            upload_traffic INTEGER DEFAULT 0,
            download_traffic INTEGER DEFAULT 0,
            last_online DATETIME,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS billing (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            plan_type TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Add new columns if missing (Data Limit and Expiration Date)
    try:
        db.execute('ALTER TABLE users ADD COLUMN data_limit INTEGER DEFAULT 0') # 0 = Unlimited MB
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        db.execute('ALTER TABLE users ADD COLUMN expires_at DATETIME') # NULL means no expiration
    except sqlite3.OperationalError:
        pass # Column already exists
    
    # Check for default admin user
    try:
        if db.execute('SELECT COUNT(*) FROM admins').fetchone()[0] == 0:
            db.execute('INSERT INTO admins (username, password) VALUES (?, ?)', ('admin', 'admin123'))
            print("Default admin user 'admin' created with password 'admin123'")
    except sqlite3.OperationalError:
        # Table might not exist yet, handled by CREATE TABLE
        pass

    db.commit()
    db.close()

# Initialize DB on start
init_db()

# --- Core Logic Functions ---

def sync_config_passwords():
    """
    Updates the USERS_FILE (used by the core VPN service) with credentials 
    of ONLY 'active' users.
    """
    db = get_db()
    try:
        # active status ရှိသော user များသာ ရွေးထုတ်သည်
        active_users = db.execute('SELECT username, password FROM users WHERE status = "active"').fetchall()
        
        users_data = {}
        for user in active_users:
            # username: password ပုံစံဖြင့် သိမ်းဆည်းသည်
            users_data[user['username']] = user['password']
            
        write_json_atomic(USERS_FILE, users_data)
        
        # Trigger config update in core service (e.g., restart zivpn service)
        subprocess.call(['sudo', 'systemctl', 'restart', 'zivpn.service']) 
    except Exception as e:
        print(f"Error syncing config: {e}")
    finally:
        db.close()

def require_login():
    """Checks if the user is logged in."""
    return session.get('logged_in')

# --- Before/After Request Hooks ---

@app.before_request
def before_request():
    """Sets up translation context and language for the request."""
    lang = request.cookies.get('lang', 'my')
    g.t = TRANSLATIONS.get(lang, TRANSLATIONS['my'])
    g.lang = lang

# --- Routing and API Endpoints ---

@app.route("/")
def index():
    if not require_login():
        return redirect(url_for('login'))
        
    # Attempt to load HTML template from GitHub, fallback to local file
    template = ""
    try:
        r = requests.get(HTML_TEMPLATE_URL, timeout=5)
        if r.status_code == 200:
            template = r.text
        else:
            raise Exception("Failed to fetch template")
    except Exception as e:
        print(f"Warning: Could not fetch template from GitHub. {e}")
        try:
            with open("index.html", "r") as f:
                template = f.read()
        except FileNotFoundError:
            template = "<h1>Error: index.html not found and external template failed.</h1>"

    # Pass the translation context and other variables to the template
    return render_template_string(template, t=g.t, lang=g.lang, logo_url=LOGO_URL)

# --- Authentication Routes ---

@app.route("/login", methods=["GET", "POST"])
def login():
    t = g.t
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db()
        admin = db.execute('SELECT * FROM admins WHERE username = ? AND password = ?', (username, password)).fetchone()
        db.close()
        
        if admin:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template_string(
                f"""
                <script src="https://cdn.tailwindcss.com"></script>
                <div class="min-h-screen flex items-center justify-center bg-gray-100">
                    <div class="bg-white p-8 rounded-lg shadow-xl w-full max-w-md">
                        <h2 class="text-2xl font-bold mb-6 text-center text-red-600">{t['login_err']}</h2>
                        <a href="{url_for('login')}" class="block text-center text-blue-500 hover:underline">Try Again</a>
                    </div>
                </div>
                """
            )

    # Simple login page template (for GET request)
    return render_template_string(f"""
        <script src="https://cdn.tailwindcss.com"></script>
        <div class="min-h-screen flex items-center justify-center bg-gray-100">
            <div class="bg-white p-8 rounded-lg shadow-xl w-full max-w-md">
                <h2 class="text-2xl font-bold mb-6 text-center text-gray-800">{t['login_title']}</h2>
                <form method="POST" action="{url_for('login')}">
                    <div class="mb-4">
                        <label for="username" class="block text-sm font-medium text-gray-700">{t['username']}</label>
                        <input type="text" id="username" name="username" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                    </div>
                    <div class="mb-6">
                        <label for="password" class="block text-sm font-medium text-gray-700">{t['password']}</label>
                        <input type="password" id="password" name="password" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                    </div>
                    <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                        {t['login']}
                    </button>
                </form>
            </div>
        </div>
    """)

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route("/set_lang/<lang>")
def set_lang(lang):
    resp = make_response(redirect(url_for('index')))
    if lang in TRANSLATIONS:
        resp.set_cookie('lang', lang)
    return resp

# --- User Management API Endpoints ---

@app.route("/api/users")
def get_users():
    if not require_login(): return jsonify({"ok": False, "err": g.t['login_err']}), 401
    
    db = get_db()
    
    # 7. Modify SELECT to include data_limit, expires_at, and status
    users = db.execute('''
        SELECT username, password, created_at, telegram_id, role, 
               used_traffic, upload_traffic, download_traffic, 
               last_online, status, data_limit, expires_at 
        FROM users
    ''').fetchall()
    
    # Fetch connection data from the service file (assuming it's written by the core script)
    online_data = read_json("/etc/zivpn/online.json", {})
    
    # Process the data
    user_list = []
    for u in users:
        user = dict(u)
        user['online_count'] = online_data.get(user['username'], 0)
        user['total_traffic'] = user['upload_traffic'] + user['download_traffic']
        
        # Format dates nicely
        user['created_at'] = datetime.strptime(user['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d') if user['created_at'] else 'N/A'
        user['last_online_str'] = 'N/A'
        if user['last_online']:
            dt = datetime.strptime(user['last_online'], '%Y-%m-%d %H:%M:%S')
            user['last_online_str'] = dt.strftime('%Y-%m-%d %H:%M:%S')

        # Check for expiration
        if user['expires_at']:
            expire_dt = datetime.strptime(user['expires_at'].split()[0], '%Y-%m-%d').date()
            if expire_dt < datetime.now().date():
                user['is_expired'] = True
            else:
                user['is_expired'] = False
        else:
            user['is_expired'] = False # No expiration date is not expired
            
        user_list.append(user)

    db.close()
    return jsonify(user_list)

@app.route("/api/user/add", methods=["POST"])
def add_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401

    data = request.get_json() or {}
    username = data.get('username') # ဝယ်သူရဲ့ custom name/email အဖြစ် သုံးရန်
    
    # New Fields
    data_limit_mb = data.get('data_limit_mb') # 0 = unlimited
    expire_date = data.get('expire_date')     # YYYY-MM-DD ပုံစံဖြင့် လာမည်

    if not username:
        return jsonify({"ok": False, "err": t['username_required']}), 400
    
    # 5. CRITICAL: Generate UUID for password and process new fields
    password = str(uuid.uuid4()) # Password ကို UUID အလိုအလျောက် ထုတ်လုပ်ခြင်း
    
    # Process Data Limit (Ensure it's an integer, 0 if not provided/invalid)
    try:
        # Convert to MB, 0 for unlimited
        data_limit_mb = int(data_limit_mb) if data_limit_mb is not None and data_limit_mb.isdigit() else 0
        if data_limit_mb < 0: data_limit_mb = 0
    except ValueError:
        data_limit_mb = 0
        
    # Process Expiration Date (Set to NULL if empty, validate format)
    expires_at = None
    if expire_date:
        try:
            # We only store the date part YYYY-MM-DD
            datetime.strptime(expire_date, '%Y-%m-%d') 
            expires_at = expire_date
        except ValueError:
            return jsonify({"ok": False, "err": t['invalid_date']}), 400

    db = get_db()
    try:
        db.execute(
            'INSERT INTO users (username, password, data_limit, expires_at) VALUES (?, ?, ?, ?)',
            (username, password, data_limit_mb, expires_at)
        )
        db.commit()
        
        # 4. Sync passwords to the core configuration file
        sync_config_passwords()
        
        return jsonify({"ok": True, "message": t['user_added'], "username": username, "password": password}), 200

    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "err": t['user_exists']}), 400
    finally:
        db.close()

@app.route("/api/user/update", methods=["POST"])
def update_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    password = data.get('password')
    data_limit_mb = data.get('data_limit_mb')
    expire_date = data.get('expire_date')
    
    # Start building the update query and parameters
    updates = []
    params = []
    
    if password:
        updates.append('password = ?')
        params.append(password)
        
    if data_limit_mb is not None:
        try:
            data_limit_mb = int(data_limit_mb) if str(data_limit_mb).isdigit() else 0
            if data_limit_mb < 0: data_limit_mb = 0
            updates.append('data_limit = ?')
            params.append(data_limit_mb)
        except ValueError:
            pass # Ignore invalid data limit
            
    if expire_date is not None:
        if not expire_date or expire_date.lower() == 'null':
            updates.append('expires_at = ?')
            params.append(None)
        else:
            try:
                datetime.strptime(expire_date, '%Y-%m-%d')
                updates.append('expires_at = ?')
                params.append(expire_date)
            except ValueError:
                return jsonify({"ok": False, "err": t['invalid_date']}), 400
    
    if updates and user:
        db = get_db()
        try:
            query = f'UPDATE users SET {", ".join(updates)} WHERE username = ?'
            params.append(user)
            
            db.execute(query, tuple(params))
            db.commit()
            
            sync_config_passwords() # Sync for potential password/status changes
            return jsonify({"ok": True, "message": t['user_updated']}), 200
        except Exception as e:
            return jsonify({"ok": False, "err": f"Database Error: {e}"}), 500
        finally:
            db.close()
    
    return jsonify({"ok": False, "message": "No changes requested or user missing"}), 400


@app.route("/api/user/toggle_status", methods=["POST"])
def toggle_user_status():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    username = data.get('username')
    
    if not username:
        return jsonify({"ok": False, "err": t['username_required']}), 400
        
    db = get_db()
    try:
        # 1. Find the current status
        user_data = db.execute('SELECT status FROM users WHERE username = ?', (username,)).fetchone()
        
        if not user_data:
            return jsonify({"ok": False, "err": t['user_not_found']}), 404
            
        current_status = user_data['status']
        new_status = 'suspended' if current_status == 'active' else 'active'
        
        # 2. Update the status
        db.execute('UPDATE users SET status = ? WHERE username = ?', (new_status, username))
        db.commit()
        
        # 3. Sync config to apply the change immediately
        sync_config_passwords() 
        
        message = t['user_suspended'] if new_status == 'suspended' else t['user_activated']
        return jsonify({"ok": True, "message": message, "new_status": new_status, "username": username}), 200

    finally:
        db.close()

@app.route("/api/user/del", methods=["POST"])
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
        return jsonify({"ok": True, "message": t['user_deleted']}), 200
    
    return jsonify({"ok": False, "err": t['username_required']}), 400

@app.route("/api/stats")
def get_stats():
    if not require_login(): return jsonify({"ok": False, "err": g.t['login_err']}), 401

    db = get_db()
    try:
        # User Counts
        total_users = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        
        # Online users (from temporary file)
        online_data = read_json("/etc/zivpn/online.json", {})
        active_users = len(online_data)
        
        # Traffic used
        traffic_data = db.execute('SELECT SUM(upload_traffic + download_traffic) FROM users').fetchone()[0]
        total_traffic_used = traffic_data if traffic_data is not None else 0
        
        # Recently Created Users (in the last 24 hours)
        yesterday = datetime.now() - timedelta(hours=24)
        recent_users = db.execute('SELECT COUNT(*) FROM users WHERE created_at >= ?', (yesterday.strftime('%Y-%m-%d %H:%M:%S'),)).fetchone()[0]

        # Active Users based on status (New)
        active_status_users = db.execute('SELECT COUNT(*) FROM users WHERE status = "active"').fetchone()[0]
        
        # Expired Users (New)
        today = datetime.now().strftime('%Y-%m-%d')
        expired_users = db.execute('SELECT COUNT(*) FROM users WHERE expires_at < ?', (today,)).fetchone()[0]

        # Data for bandwidth graph (last 30 days)
        data = db.execute('''
            SELECT date(created_at) as date, COUNT(*) as count 
            FROM users 
            WHERE date(created_at) >= date('now', '-30 days') 
            GROUP BY date 
            ORDER BY date
        ''').fetchall()
        
        daily_users = [dict(d) for d in data]

        return jsonify({
            "total_users": total_users,
            "active_users": active_users, # Online
            "active_status_users": active_status_users, # Based on 'status' column
            "expired_users": expired_users,
            "total_traffic_used": total_traffic_used,
            "recent_users": recent_users,
            "daily_users": daily_users
        })
    finally:
        db.close()

@app.route("/api/reports")
def get_reports():
    if not require_login(): return jsonify({"message": g.t['login_err']}), 401
    
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    report_type = request.args.get('type')
    
    db = get_db()
    try:
        if report_type == 'monthly_traffic':
            data = db.execute('''
                SELECT date(created_at) as date, SUM(upload_traffic + download_traffic) as total_traffic
                FROM users
                WHERE created_at BETWEEN ? AND datetime(?, '+1 day')
                GROUP BY date
                ORDER BY date ASC
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()

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

@app.route("/api/admin/change_password", methods=["POST"])
def change_admin_password():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401

    data = request.get_json() or {}
    new_password = data.get('new_password')
    username = session.get('username')

    if not new_password or not username:
        return jsonify({"ok": False, "err": "Password is required"}), 400

    db = get_db()
    try:
        db.execute('UPDATE admins SET password = ? WHERE username = ?', (new_password, username))
        db.commit()
        return jsonify({"ok": True, "message": "Admin password updated successfully"}), 200
    except Exception as e:
        return jsonify({"ok": False, "err": f"Database error: {e}"}), 500
    finally:
        db.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.environ.get("LISTEN_PORT", LISTEN_FALLBACK), debug=False)

# Clean up
try:
    if os.path.exists("index.html"):
        os.remove("index.html")
except Exception:
    pass

