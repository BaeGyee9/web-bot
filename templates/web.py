#!/usr/bin/env python3
"""
ZIVPN Enterprise Web Panel - Enhanced Version
With Connection Dashboard, Scheduling, and Device Management
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

# Import Enhanced Connection Manager
import sys
sys.path.append('/etc/zivpn')
from connection_manager import connection_manager, connection_api

# --- Localization Data ---
TRANSLATIONS = {
    'en': {
        # ... existing translations ...
        'connection_dashboard': 'Connection Dashboard',
        'active_connections': 'Active Connections',
        'device_management': 'Device Management',
        'connection_schedule': 'Connection Schedule',
        'registered_devices': 'Registered Devices',
        'schedule_settings': 'Schedule Settings',
        'allowed_hours': 'Allowed Hours',
        'allowed_days': 'Allowed Days',
        'device_fingerprint': 'Device Fingerprint',
        'mac_address': 'MAC Address',
        'connection_policies': 'Connection Policies'
    },
    'my': {
        # ... existing translations ...
        'connection_dashboard': 'ချိတ်ဆက်မှု ပင်မစာမျက်နှာ',
        'active_connections': 'တက်ကြွ ချိတ်ဆက်မှုများ',
        'device_management': 'ကိရိယာ စီမံခန့်ခွဲမှု',
        'connection_schedule': 'ချိတ်ဆက်မှု အချိန်ဇယား',
        'registered_devices': 'မှတ်ပုံတင်ထားသော ကိရိယာများ',
        'schedule_settings': 'အချိန်ဇယား ချိန်ညှိချက်များ',
        'allowed_hours': 'ခွင့်ပြုချိန်များ',
        'allowed_days': 'ခွင့်ပြုရက်များ',
        'device_fingerprint': 'ကိရိယာ လက်ဗွေ',
        'mac_address': 'MAC လိပ်စာ',
        'connection_policies': 'ချိတ်ဆက်မှု မူဝါဒများ'
    }
}

def load_html_template():
    """Load HTML template from GitHub or fallback to local template"""
    try:
        response = requests.get(HTML_TEMPLATE_URL, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"HTTP {response.status_code}")
    except Exception as e:
        print(f"Failed to load template from GitHub: {e}")
        return FALLBACK_HTML

# Fallback HTML template
FALLBACK_HTML = """
<!DOCTYPE html>
<html lang="{{lang}}">
<head>
    <meta charset="utf-8">
    <title>{{t.title}} - Channel 404</title>
    <!-- ... existing head content ... -->
</head>
<body data-theme="{{theme}}">
<!-- ... existing body content ... -->
</body>
</html>
"""

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET","dev-secret-change-me")
ADMIN_USER = os.environ.get("WEB_ADMIN_USER","").strip()
ADMIN_PASS = os.environ.get("WEB_ADMIN_PASSWORD","").strip()
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")

# Register connection API blueprint
app.register_blueprint(connection_api)

# --- Database Schema Update ---
def update_database_schema():
    """Update database with new tables for enhanced features"""
    db = sqlite3.connect(DATABASE_PATH)
    try:
        # Device fingerprints table
        db.execute('''
            CREATE TABLE IF NOT EXISTS device_fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                device_hash TEXT UNIQUE NOT NULL,
                mac_address TEXT,
                client_ip TEXT,
                user_agent TEXT,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User schedules table
        db.execute('''
            CREATE TABLE IF NOT EXISTS user_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                schedule_data TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # IP assignments table (for IP-username mapping)
        db.execute('''
            CREATE TABLE IF NOT EXISTS ip_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip_address TEXT UNIQUE NOT NULL,
                assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        db.commit()
        print("Database schema updated successfully")
    except Exception as e:
        print(f"Error updating database schema: {e}")
    finally:
        db.close()

# --- Enhanced Utility Functions ---

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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

def load_users():
    db = get_db()
    users = db.execute('''
        SELECT username as user, password, expires, port, status, 
               bandwidth_limit, bandwidth_used, speed_limit_up as speed_limit,
               concurrent_conn
        FROM users
    ''').fetchall()
    db.close()
    return [dict(u) for u in users]

def get_enhanced_user_stats():
    """Get enhanced user statistics with connection data"""
    db = get_db()
    try:
        users = db.execute('''
            SELECT u.username, u.status, u.concurrent_conn,
                   COUNT(DISTINCT df.device_hash) as device_count,
                   (SELECT schedule_data FROM user_schedules WHERE username = u.username) as schedule_data
            FROM users u
            LEFT JOIN device_fingerprints df ON u.username = df.username
            GROUP BY u.username
        ''').fetchall()
        
        enhanced_stats = []
        for user in users:
            user_dict = dict(user)
            if user_dict['schedule_data']:
                user_dict['has_schedule'] = True
            else:
                user_dict['has_schedule'] = False
            enhanced_stats.append(user_dict)
            
        return enhanced_stats
    finally:
        db.close()

def save_user(user_data):
    db = get_db()
    try:
        db.execute('''
            INSERT OR REPLACE INTO users 
            (username, password, expires, port, status, bandwidth_limit, speed_limit_up, concurrent_conn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_data['user'], user_data['password'], user_data.get('expires'),
            user_data.get('port'), 'active', user_data.get('bandwidth_limit', 0),
            user_data.get('speed_limit', 0), user_data.get('concurrent_conn', 1)
        ))
        db.commit()
        
        # Set default schedule if provided
        if user_data.get('schedule_type'):
            schedule_data = {}
            if user_data['schedule_type'] == 'business':
                schedule_data = {'allowed_hours': {'start': '00:00', 'end': '23:59'}, 'allowed_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']}
            elif user_data['schedule_type'] == 'night_only':
                schedule_data = {'allowed_hours': {'start': '18:00', 'end': '06:00'}, 'allowed_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']}
            
            if schedule_data:
                db.execute('''
                    INSERT OR REPLACE INTO user_schedules 
                    (username, schedule_data, updated_at)
                    VALUES (?, ?, ?)
                ''', (user_data['user'], json.dumps(schedule_data), datetime.now()))
                db.commit()
            
    finally:
        db.close()

def delete_user(username):
    db = get_db()
    try:
        db.execute('DELETE FROM users WHERE username = ?', (username,))
        db.execute('DELETE FROM billing WHERE username = ?', (username,))
        db.execute('DELETE FROM bandwidth_logs WHERE username = ?', (username,))
        db.execute('DELETE FROM device_fingerprints WHERE username = ?', (username,))
        db.execute('DELETE FROM user_schedules WHERE username = ?', (username,))
        db.commit()
    finally:
        db.close()

def get_server_stats():
    db = get_db()
    try:
        total_users = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        active_users_db = db.execute('SELECT COUNT(*) FROM users WHERE status = "active" AND (expires IS NULL OR expires >= CURRENT_DATE)').fetchone()[0]
        total_bandwidth = db.execute('SELECT SUM(bandwidth_used) FROM users').fetchone()[0] or 0
        
        # Get active connections from connection manager
        dashboard_data = connection_manager.get_connection_dashboard()
        active_connections = dashboard_data.get('total_active_connections', 0)
        
        server_load = min(100, (active_users_db * 5) + 10)
        
        return {
            'total_users': total_users,
            'active_users': active_users_db,
            'total_bandwidth': f"{total_bandwidth / 1024 / 1024 / 1024:.2f} GB",
            'server_load': server_load,
            'active_connections': active_connections
        }
    finally:
        db.close()

# ... (keep existing functions like get_listen_port_from_config, has_recent_udp_activity, etc.)

def build_enhanced_view(msg="", err=""):
    t = g.t
    if not require_login():
        html_template = load_html_template()
        return render_template_string(html_template, authed=False, logo=LOGO_URL, err=session.pop("login_err", None), 
                                      t=t, lang=g.lang, theme=session.get('theme', 'dark'))
    
    users=load_users()
    listen_port=get_listen_port_from_config()
    stats = get_server_stats()
    
    # Get enhanced connection data
    dashboard_data = connection_manager.get_connection_dashboard()
    enhanced_users = get_enhanced_user_stats()
    
    view=[]
    today_date=datetime.now().date()
    
    for u in users:
        status = status_for_user(u, listen_port)
        expires_str=u.get("expires","")
        
        # Find enhanced data for this user
        enhanced_data = next((eu for eu in enhanced_users if eu['username'] == u['user']), {})
        
        view.append(type("U",(),{
            "user":u.get("user",""),
            "password":u.get("password",""),
            "expires":expires_str,
            "port":u.get("port",""),
            "status":status,
            "bandwidth_limit": u.get('bandwidth_limit', 0),
            "bandwidth_used": f"{u.get('bandwidth_used', 0) / 1024 / 1024 / 1024:.2f}",
            "speed_limit": u.get('speed_limit', 0),
            "concurrent_conn": u.get('concurrent_conn', 1),
            "device_count": enhanced_data.get('device_count', 0),
            "has_schedule": enhanced_data.get('has_schedule', False)
        }))
    
    view.sort(key=lambda x:(x.user or "").lower())
    today=today_date.strftime("%Y-%m-%d")
    
    theme = session.get('theme', 'dark')
    html_template = load_html_template()
    return render_template_string(html_template, authed=True, logo=LOGO_URL, 
                                 users=view, msg=msg, err=err, today=today, stats=stats, 
                                 dashboard_data=dashboard_data, enhanced_users=enhanced_users,
                                 t=t, lang=g.lang, theme=theme)

# --- Enhanced Routes ---

@app.route("/connections", methods=["GET"])
def connection_dashboard():
    """Enhanced connection dashboard"""
    if not require_login(): return redirect(url_for('login'))
    
    dashboard_data = connection_manager.get_connection_dashboard()
    return jsonify(dashboard_data)

@app.route("/user/<username>/devices", methods=["GET"])
def get_user_devices(username):
    """Get registered devices for a user"""
    if not require_login(): return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    try:
        devices = db.execute('''
            SELECT device_hash, mac_address, client_ip, user_agent, registered_at, last_seen
            FROM device_fingerprints 
            WHERE username = ?
            ORDER BY last_seen DESC
        ''', (username,)).fetchall()
        
        return jsonify([dict(device) for device in devices])
    finally:
        db.close()

@app.route("/user/<username>/schedule", methods=["GET", "POST"])
def manage_user_schedule(username):
    """Manage connection schedule for user"""
    if not require_login(): return jsonify({"error": "Unauthorized"}), 401
    
    if request.method == "POST":
        schedule_data = request.get_json()
        db = get_db()
        try:
            db.execute('''
                INSERT OR REPLACE INTO user_schedules 
                (username, schedule_data, updated_at)
                VALUES (?, ?, ?)
            ''', (username, json.dumps(schedule_data), datetime.now()))
            db.commit()
            
            # Update cache
            connection_manager.schedule_cache[username] = schedule_data
            
            return jsonify({"status": "success"})
        finally:
            db.close()
    else:
        # GET request - return current schedule
        schedule = connection_manager.get_user_schedule(username)
        return jsonify(schedule or {})

# ... (keep existing routes like /, /add, /delete, etc.)

# --- Application Startup ---

@app.before_first_request
def initialize_enhanced_features():
    """Initialize enhanced features on first request"""
    update_database_schema()
    connection_manager.load_device_registry()
    connection_manager.start_monitoring()

if __name__ == "__main__":
    web_port = int(os.environ.get("WEB_PORT", "19432"))
    app.run(host="0.0.0.0", port=web_port)
