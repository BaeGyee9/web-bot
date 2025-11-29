#!/usr/bin/env python3
"""
ZIVPN Enterprise Web Panel - X-UI Style
Modified with UUID generation, Email fields, Data limits, and Calendar date picker
"""

from flask import Flask, jsonify, render_template_string, request, redirect, url_for, session, make_response, g
import json, re, subprocess, os, tempfile, hmac, sqlite3, datetime, uuid
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
        'active_users': 'Online Users', 'bandwidth_used': 'Bandwidth Used',
        'server_load': 'Server Load', 'user_management': 'User Management',
        'add_user': 'Add New User', 'bulk_ops': 'Bulk Operations',
        'reports': 'Reports', 'user': 'User', 'expires': 'Expires',
        'port': 'Port', 'bandwidth': 'Bandwidth', 'speed': 'Speed',
        'status': 'Status', 'actions': 'Actions', 'online': 'ONLINE',
        'offline': 'OFFLINE', 'expired': 'EXPIRED', 'suspended': 'SUSPENDED',
        'save_user': 'Save User', 'max_conn': 'Max Connections',
        'speed_limit': 'Speed Limit (MB/s)', 'bw_limit': 'Bandwidth Limit (GB)',
        'required_fields': 'User and Password are required',
        'invalid_exp': 'Invalid Expires format',
        'invalid_port': 'Port range must be 6000-19999',
        'delete_confirm': 'Are you sure you want to delete {user}?',
        'deleted': 'Deleted: {user}', 'success_save': 'User saved successfully',
        'select_action': 'Select Action', 'extend_exp': 'Extend Expiry (+7 days)',
        'suspend_users': 'Suspend Users', 'activate_users': 'Activate Users',
        'delete_users': 'Delete Users', 'execute': 'Execute',
        'user_search': 'Search users...', 'search': 'Search',
        'export_csv': 'Export Users CSV', 'import_users': 'Import Users',
        'bulk_success': 'Bulk action {action} completed',
        'report_range': 'Date Range Required', 'report_bw': 'Bandwidth Usage',
        'report_users': 'User Activity', 'report_revenue': 'Revenue',
        'home': 'Home', 'manage': 'Manage Users', 'settings': 'Settings',
        'dashboard': 'Dashboard', 'system_status': 'System Status',
        'quick_actions': 'Quick Actions', 'recent_activity': 'Recent Activity',
        'server_info': 'Server Information', 'vpn_status': 'VPN Status',
        'active_connections': 'Active Connections',
        'email': 'Email/Remark', 'data_limit': 'Data Limit (GB)',
        'unlimited': 'Unlimited', 'generate_uuid': 'Generate UUID',
        'user_id': 'User ID', 'total_traffic': 'Total Traffic',
        'start_on_use': 'Start on Initial Use', 'expiration': 'Expiration',
        'add_client': 'Add Client', 'close': 'Close'
    },
    'my': {
        'title': 'ZIVPN စီမံခန့်ခွဲမှု Panel', 'login_title': 'ZIVPN Panel ဝင်ရန်',
        'login_err': 'အသုံးပြုသူအမည် (သို့) စကားဝှက် မမှန်ပါ', 'username': 'အသုံးပြုသူအမည်',
        'password': 'စကားဝှက်', 'login': 'ဝင်မည်', 'logout': 'ထွက်မည်',
        'contact': 'ဆက်သွယ်ရန်', 'total_users': 'စုစုပေါင်းအသုံးပြုသူ',
        'active_users': 'အွန်လိုင်းအသုံးပြုသူ', 'bandwidth_used': 'အသုံးပြုပြီး Bandwidth',
        'server_load': 'ဆာဗာ ဝန်ပမာဏ', 'user_management': 'အသုံးပြုသူ စီမံခန့်ခွဲမှု',
        'add_user': 'အသုံးပြုသူ အသစ်ထည့်ရန်', 'bulk_ops': 'အစုလိုက် လုပ်ဆောင်ချက်များ',
        'reports': 'အစီရင်ခံစာများ', 'user': 'အသုံးပြုသူ', 'expires': 'သက်တမ်းကုန်ဆုံးမည်',
        'port': 'ပေါက်', 'bandwidth': 'Bandwidth', 'speed': 'မြန်နှုန်း',
        'status': 'အခြေအနေ', 'actions': 'လုပ်ဆောင်ချက်များ', 'online': 'အွန်လိုင်း',
        'offline': 'အော့ဖ်လိုင်း', 'expired': 'သက်တမ်းကုန်ဆုံး', 'suspended': 'ဆိုင်းငံ့ထားသည်',
        'save_user': 'အသုံးပြုသူ သိမ်းမည်', 'max_conn': 'အများဆုံးချိတ်ဆက်မှု',
        'speed_limit': 'မြန်နှုန်း ကန့်သတ်ချက် (MB/s)', 'bw_limit': 'Bandwidth ကန့်သတ်ချက် (GB)',
        'required_fields': 'အသုံးပြုသူအမည်နှင့် စကားဝှက် လိုအပ်သည်',
        'invalid_exp': 'သက်တမ်းကုန်ဆုံးရက်ပုံစံ မမှန်ကန်ပါ',
        'invalid_port': 'Port အကွာအဝေး 6000-19999 သာ ဖြစ်ရမည်',
        'delete_confirm': '{user} ကို ဖျက်ရန် သေချာပါသလား?',
        'deleted': 'ဖျက်လိုက်သည်: {user}', 'success_save': 'အသုံးပြုသူကို အောင်မြင်စွာ သိမ်းဆည်းလိုက်သည်',
        'select_action': 'လုပ်ဆောင်ချက် ရွေးပါ', 'extend_exp': 'သက်တမ်းတိုးမည် (+၇ ရက်)',
        'suspend_users': 'အသုံးပြုသူများ ဆိုင်းငံ့မည်', 'activate_users': 'အသုံးပြုသူများ ဖွင့်မည်',
        'delete_users': 'အသုံးပြုသူများ ဖျက်မည်', 'execute': 'စတင်လုပ်ဆောင်မည်',
        'user_search': 'အသုံးပြုသူ ရှာဖွေပါ...', 'search': 'ရှာဖွေပါ',
        'export_csv': 'အသုံးပြုသူများ CSV ထုတ်ယူမည်', 'import_users': 'အသုံးပြုသူများ ထည့်သွင်းမည်',
        'bulk_success': 'အစုလိုက် လုပ်ဆောင်ချက် {action} ပြီးမြောက်ပါပြီ',
        'report_range': 'ရက်စွဲ အပိုင်းအခြား လိုအပ်သည်', 'report_bw': 'Bandwidth အသုံးပြုမှု',
        'report_users': 'အသုံးပြုသူ လှုပ်ရှားမှု', 'report_revenue': 'ဝင်ငွေ',
        'home': 'ပင်မစာမျက်နှာ', 'manage': 'အသုံးပြုသူများ စီမံခန့်ခွဲမှု',
        'settings': 'ချိန်ညှိချက်များ', 'dashboard': 'ပင်မစာမျက်နှာ',
        'system_status': 'စနစ်အခြေအနေ', 'quick_actions': 'အမြန်လုပ်ဆောင်ချက်များ',
        'recent_activity': 'လတ်တလောလုပ်ဆောင်မှုများ', 'server_info': 'ဆာဗာအချက်အလက်',
        'vpn_status': 'VPN အခြေအနေ', 'active_connections': 'တက်ကြွလင့်ချိတ်ဆက်မှုများ',
        'email': 'အီးမေးလ်/မှတ်ချက်', 'data_limit': 'ဒေတာ အကန့်သတ် (GB)',
        'unlimited': 'အကန့်အသတ်မရှိ', 'generate_uuid': 'UUID ဖန်တီးမည်',
        'user_id': 'အသုံးပြုသူ ID', 'total_traffic': 'စုစုပေါင်းဒေတာ',
        'start_on_use': 'ပထမဆုံးအသုံးပြုမှုမှစပါ', 'expiration': 'သက်တမ်းကုန်ဆုံးမည့်ရက်',
        'add_client': 'အသုံးပြုသူအသစ်ထည့်ရန်', 'close': 'ပိတ်မည်'
    }
}

def generate_uuid():
    """Generate UUID for password"""
    return str(uuid.uuid4())

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

# Updated Fallback HTML template with X-UI style
FALLBACK_HTML = """
<!DOCTYPE html>
<html lang="{{lang}}">
<head>
    <meta charset="utf-8">
    <title>{{t.title}} - ZIVPN</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="refresh" content="120">
    <link href="https://fonts.googleapis.com/css2?family=Padauk:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <style>
        :root {
            --bg-dark: #0f172a; --fg-dark: #f1f5f9; --card-dark: #1e293b; 
            --bd-dark: #334155; --primary-dark: #3b82f6;
            --bg-light: #f8fafc; --fg-light: #1e293b; --card-light: #ffffff; 
            --bd-light: #e2e8f0; --primary-light: #2563eb;
            --ok: #10b981; --bad: #ef4444; --unknown: #f59e0b; --expired: #8b5cf6;
            --success: #06d6a0; --delete-btn: #ef4444; --logout-btn: #f97316;
            --shadow: 0 10px 25px -5px rgba(0,0,0,0.3), 0 8px 10px -6px rgba(0,0,0,0.2);
            --radius: 16px; --gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        [data-theme='dark'] { --bg: var(--bg-dark); --fg: var(--fg-dark); --card: var(--card-dark); --bd: var(--bd-dark); --primary-btn: var(--primary-dark); }
        [data-theme='light'] { --bg: var(--bg-light); --fg: var(--fg-light); --card: var(--card-light); --bd: var(--bd-light); --primary-btn: var(--primary-light); }
        * { box-sizing: border-box; }
        html, body { background: var(--bg); color: var(--fg); font-family: 'Padauk', sans-serif; margin: 0; padding: 0; line-height: 1.6; }
        .container { max-width: 1400px; margin: auto; padding: 20px; }
        
        /* X-UI Style Form */
        .xui-form { background: var(--card); padding: 25px; border-radius: var(--radius); box-shadow: var(--shadow); margin-bottom: 20px; }
        .xui-form-title { color: var(--primary-btn); margin: 0 0 20px 0; font-size: 1.3em; display: flex; align-items: center; gap: 10px; }
        .xui-form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-bottom: 15px; }
        .xui-form-group { margin-bottom: 15px; }
        .xui-label { display: block; margin-bottom: 8px; font-weight: 600; color: var(--fg); font-size: 0.9em; }
        .xui-input { width: 100%; padding: 12px; border: 2px solid var(--bd); border-radius: var(--radius); background: var(--bg); color: var(--fg); transition: all 0.3s ease; }
        .xui-input:focus { outline: none; border-color: var(--primary-btn); box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
        
        /* Toggle Switch */
        .xui-toggle { position: relative; display: inline-block; width: 50px; height: 24px; }
        .xui-toggle input { opacity: 0; width: 0; height: 0; }
        .xui-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 24px; }
        .xui-slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .xui-slider { background-color: var(--success); }
        input:checked + .xui-slider:before { transform: translateX(26px); }
        
        /* Buttons */
        .xui-btn { padding: 12px 20px; border: none; border-radius: var(--radius); color: white; text-decoration: none; cursor: pointer; transition: all 0.3s ease; font-weight: 600; display: inline-flex; align-items: center; gap: 8px; }
        .xui-btn-primary { background: var(--primary-btn); }
        .xui-btn-success { background: var(--success); }
        .xui-btn-danger { background: var(--delete-btn); }
        .xui-btn-block { width: 100%; justify-content: center; }
        
        /* Table */
        .xui-table { width: 100%; border-collapse: collapse; background: var(--card); border-radius: var(--radius); overflow: hidden; }
        .xui-table th, .xui-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--bd); }
        .xui-table th { background: var(--primary-btn); color: white; font-weight: 600; }
        .xui-table tr:hover { background: rgba(59, 130, 246, 0.05); }
        
        /* Status Pills */
        .xui-pill { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 700; color: white; }
        .xui-pill-online { background: var(--ok); }
        .xui-pill-offline { background: var(--bad); }
        .xui-pill-expired { background: var(--expired); }
        
        /* Action Buttons */
        .xui-action-btns { display: flex; gap: 5px; }
        .xui-action-btn { padding: 6px 10px; border: none; border-radius: var(--radius); cursor: pointer; transition: all 0.3s ease; font-size: 0.8em; }
    </style>
</head>
<body data-theme="{{theme}}">
<div class="container">
    {% if not authed %}
    <div class="login-card">
        <div style="margin-bottom:25px">
            <img src="{{ logo }}" alt="ZIVPN Logo" style="height:80px;width:80px;border-radius:50%;border:3px solid var(--primary-btn);padding:5px;">
        </div>
        <h3>{{t.login_title}}</h3>
        {% if err %}<div class="err">{{err}}</div>{% endif %}
        <form method="post" action="/login">
            <label><i class="fas fa-user"></i> {{t.username}}</label>
            <input name="u" autofocus required style="width:100%;padding:12px;margin:8px 0;border:2px solid var(--bd);border-radius:var(--radius);background:var(--bg);color:var(--fg);">
            <label style="margin-top:20px"><i class="fas fa-lock"></i> {{t.password}}</label>
            <input name="p" type="password" required style="width:100%;padding:12px;margin:8px 0;border:2px solid var(--bd);border-radius:var(--radius);background:var(--bg);color:var(--fg);">
            <button class="btn primary" type="submit" style="margin-top:25px;width:100%;padding:15px;">
                <i class="fas fa-sign-in-alt"></i>{{t.login}}
            </button>
        </form>
    </div>
    {% else %}
    <!-- X-UI Style Add Client Form -->
    <div class="xui-form">
        <h3 class="xui-form-title"><i class="fas fa-user-plus"></i> {{t.add_client}}</h3>
        
        {% if msg %}<div style="padding:12px;background:var(--success);color:white;border-radius:var(--radius);margin-bottom:15px;">{{msg}}</div>{% endif %}
        {% if err %}<div style="padding:12px;background:var(--delete-btn);color:white;border-radius:var(--radius);margin-bottom:15px;">{{err}}</div>{% endif %}
        
        <form method="post" action="/add">
            <div class="xui-form-grid">
                <div class="xui-form-group">
                    <label class="xui-label"><i class="fas fa-envelope"></i> {{t.email}}</label>
                    <input type="text" name="email" class="xui-input" placeholder="user@example.com or Remark" required>
                </div>
                
                <div class="xui-form-group">
                    <label class="xui-label"><i class="fas fa-id-card"></i> {{t.user_id}}</label>
                    <input type="text" name="user" class="xui-input" placeholder="Auto-generated Username" readonly>
                </div>
                
                <div class="xui-form-group">
                    <label class="xui-label"><i class="fas fa-key"></i> {{t.password}}</label>
                    <div style="display:flex;gap:10px;">
                        <input type="text" name="password" class="xui-input" placeholder="Auto-generated UUID" readonly style="flex:1;">
                        <button type="button" class="xui-btn xui-btn-primary" onclick="generateUUID()" style="white-space:nowrap;">
                            <i class="fas fa-sync-alt"></i> {{t.generate_uuid}}
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="xui-form-grid">
                <div class="xui-form-group">
                    <label class="xui-label"><i class="fas fa-database"></i> {{t.data_limit}} (0 = {{t.unlimited}})</label>
                    <input type="number" name="data_limit" class="xui-input" value="0" min="0" step="0.1">
                </div>
                
                <div class="xui-form-group">
                    <label class="xui-label"><i class="fas fa-calendar"></i> {{t.expiration}}</label>
                    <input type="text" name="expires" class="xui-input datepicker" placeholder="Select date">
                </div>
                
                <div class="xui-form-group">
                    <label class="xui-label" style="display:flex;align-items:center;gap:10px;">
                        <i class="fas fa-play-circle"></i> {{t.start_on_use}}
                        <label class="xui-toggle">
                            <input type="checkbox" name="start_on_use" checked>
                            <span class="xui-slider"></span>
                        </label>
                    </label>
                </div>
            </div>
            
            <button type="submit" class="xui-btn xui-btn-success xui-btn-block">
                <i class="fas fa-save"></i> {{t.save_user}}
            </button>
        </form>
    </div>
    
    <!-- Users Table -->
    <div class="xui-form">
        <h3 class="xui-form-title"><i class="fas fa-users"></i> {{t.user_management}}</h3>
        <div class="xui-table-container">
            <table class="xui-table">
                <thead>
                    <tr>
                        <th>{{t.email}}</th>
                        <th>{{t.user_id}}</th>
                        <th>{{t.password}}</th>
                        <th>{{t.total_traffic}}</th>
                        <th>{{t.expiration}}</th>
                        <th>{{t.status}}</th>
                        <th>{{t.actions}}</th>
                    </tr>
                </thead>
                <tbody>
                    {% for u in users %}
                    <tr>
                        <td>{{u.email or '-'}}</td>
                        <td><strong>{{u.user}}</strong></td>
                        <td><code>{{u.password}}</code></td>
                        <td>{{u.total_traffic}}</td>
                        <td>{{u.expires or '-'}}</td>
                        <td>
                            <span class="xui-pill xui-pill-{{u.status|lower}}">{{u.status}}</span>
                        </td>
                        <td>
                            <div class="xui-action-btns">
                                <label class="xui-toggle">
                                    <input type="checkbox" {% if u.status=='Online' or u.status=='active' %}checked{% endif %} onchange="toggleUser('{{u.user}}', this.checked)">
                                    <span class="xui-slider"></span>
                                </label>
                                <button class="xui-action-btn xui-btn-danger" onclick="deleteUser('{{u.user}}')" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <a class="xui-btn xui-btn-danger" href="/logout" style="margin-top:20px;">
        <i class="fas fa-sign-out-alt"></i>{{t.logout}}
    </a>
    {% endif %}
</div>

<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
<script>
// Initialize date picker
flatpickr('.datepicker', {
    dateFormat: "Y-m-d",
    minDate: "today"
});

// Generate UUID
function generateUUID() {
    const uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
    document.querySelector('input[name="password"]').value = uuid;
    
    // Auto-generate username from first part of UUID
    const username = uuid.split('-')[0];
    document.querySelector('input[name="user"]').value = username;
}

// Auto-generate on page load
document.addEventListener('DOMContentLoaded', generateUUID);

// Toggle user status
function toggleUser(username, enabled) {
    fetch('/api/user/toggle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user: username, enabled: enabled})
    }).then(r => r.json()).then(data => {
        if (!data.ok) {
            alert('Error: ' + data.err);
            location.reload();
        }
    });
}

// Delete user
function deleteUser(username) {
    const t = {{t|tojson}};
    if (confirm(t.delete_confirm.replace('{user}', username))) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/delete';
        
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'user';
        input.value = username;
        
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    }
}
</script>
</body>
</html>
"""

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET","dev-secret-change-me")
ADMIN_USER = os.environ.get("WEB_ADMIN_USER","").strip()
ADMIN_PASS = os.environ.get("WEB_ADMIN_PASSWORD","").strip())
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")

# --- Utility Functions ---

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
               concurrent_conn, email, data_limit
        FROM users
    ''').fetchall()
    db.close()
    return [dict(u) for u in users]

def save_user(user_data):
    db = get_db()
    try:
        # Auto-generate username from UUID if not provided
        if not user_data['user'] and user_data['password']:
            user_data['user'] = user_data['password'].split('-')[0]
        
        db.execute('''
            INSERT OR REPLACE INTO users 
            (username, password, expires, port, status, bandwidth_limit, speed_limit_up, 
             concurrent_conn, email, data_limit, total_traffic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_data['user'], user_data['password'], user_data.get('expires'),
            user_data.get('port'), 'active', user_data.get('data_limit', 0) * 1024 * 1024 * 1024,
            user_data.get('speed_limit', 0), user_data.get('concurrent_conn', 1),
            user_data.get('email', ''), user_data.get('data_limit', 0), '0 GB'
        ))
        db.commit()
        
    finally:
        db.close()

def delete_user(username):
    db = get_db()
    try:
        db.execute('DELETE FROM users WHERE username = ?', (username,))
        db.commit()
    finally:
        db.close()

def toggle_user_status(username, enabled):
    db = get_db()
    try:
        status = 'active' if enabled else 'suspended'
        db.execute('UPDATE users SET status = ? WHERE username = ?', (status, username))
        db.commit()
        return True
    except:
        return False
    finally:
        db.close()

def get_server_stats():
    db = get_db()
    try:
        total_users = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        active_users_db = db.execute('SELECT COUNT(*) FROM users WHERE status = "active"').fetchone()[0]
        total_bandwidth = db.execute('SELECT SUM(bandwidth_used) FROM users').fetchone()[0] or 0
        
        server_load = min(100, (active_users_db * 5) + 10)
        
        return {
            'total_users': total_users,
            'active_users': active_users_db,
            'total_bandwidth': f"{total_bandwidth / 1024 / 1024 / 1024:.2f} GB",
            'server_load': server_load
        }
    finally:
        db.close()

def get_listen_port_from_config():
    cfg=read_json(CONFIG_FILE,{})
    listen=str(cfg.get("listen","")).strip()
    m=re.search(r":(\d+)$", listen) if listen else None
    return (m.group(1) if m else LISTEN_FALLBACK)

def has_recent_udp_activity(port):
    if not port: return False
    try:
        out=subprocess.run("conntrack -L -p udp 2>/dev/null | grep 'dport=%s\\b'"%port,
                           shell=True, capture_output=True, text=True).stdout
        return bool(out)
    except Exception:
        return False

def status_for_user(u, listen_port):
    port=str(u.get("port",""))
    check_port=port if port else listen_port

    if u.get('status') == 'suspended': return "suspended"

    expires_str = u.get("expires", "")
    is_expired = False
    if expires_str:
        try:
            expires_dt = datetime.strptime(expires_str, "%Y-%m-%d").date()
            if expires_dt < datetime.now().date():
                is_expired = True
        except ValueError:
            pass

    if is_expired: return "expired"

    if has_recent_udp_activity(check_port): return "online"
    
    return "offline"

def sync_config_passwords():
    db = get_db()
    active_users = db.execute('''
        SELECT password FROM users 
        WHERE status = "active" AND password IS NOT NULL AND password != "" 
              AND (expires IS NULL OR expires >= CURRENT_DATE)
    ''').fetchall()
    db.close()
    
    users_pw = sorted({str(u["password"]) for u in active_users})
    
    cfg=read_json(CONFIG_FILE,{})
    if not isinstance(cfg.get("auth"),dict): cfg["auth"]={}
    cfg["auth"]["mode"]="passwords"
    cfg["auth"]["config"]=users_pw
    cfg["listen"]=cfg.get("listen") or ":5667"
    cfg["cert"]=cfg.get("cert") or "/etc/zivpn/zivpn.crt"
    cfg["key"]=cfg.get("key") or "/etc/zivpn/zivpn.key"
    cfg["obfs"]=cfg.get("obfs") or "zivpn"
    
    write_json_atomic(CONFIG_FILE,cfg)
    subprocess.run("systemctl restart zivpn.service", shell=True)

def login_enabled(): return bool(ADMIN_USER and ADMIN_PASS)
def is_authed(): return session.get("auth") == True
def require_login():
    if login_enabled() and not is_authed():
        return False
    return True

# --- Request Hooks ---
@app.before_request
def set_language_and_translations():
    lang = session.get('lang', os.environ.get('DEFAULT_LANGUAGE', 'my'))
    g.lang = lang
    g.t = TRANSLATIONS.get(lang, TRANSLATIONS['my'])

# --- Routes ---

@app.route("/set_lang", methods=["GET"])
def set_lang():
    lang = request.args.get('lang')
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route("/login", methods=["GET","POST"])
def login():
    t = g.t
    if not login_enabled(): return redirect(url_for('index'))
    if request.method=="POST":
        u=(request.form.get("u") or "").strip()
        p=(request.form.get("p") or "").strip()
        if hmac.compare_digest(u, ADMIN_USER) and hmac.compare_digest(p, ADMIN_PASS):
            session["auth"]=True
            return redirect(url_for('index'))
        else:
            session["auth"]=False
            session["login_err"]=t['login_err']
            return redirect(url_for('login'))
    
    theme = session.get('theme', 'dark')
    html_template = load_html_template()
    return render_template_string(html_template, authed=False, logo=LOGO_URL, err=session.pop("login_err", None), 
                                  t=t, lang=g.lang, theme=theme)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("auth", None)
    return redirect(url_for('login') if login_enabled() else url_for('index'))

def build_view(msg="", err=""):
    t = g.t
    if not require_login():
        html_template = load_html_template()
        return render_template_string(html_template, authed=False, logo=LOGO_URL, err=session.pop("login_err", None), 
                                      t=t, lang=g.lang, theme=session.get('theme', 'dark'))
    
    users=load_users()
    listen_port=get_listen_port_from_config()
    stats = get_server_stats()
    
    view=[]
    today_date=datetime.now().date()
    
    for u in users:
        status = status_for_user(u, listen_port)
        expires_str=u.get("expires","")
        
        # Calculate total traffic
        data_limit = u.get('data_limit', 0)
        bandwidth_used = u.get('bandwidth_used', 0)
        total_traffic = f"{bandwidth_used / 1024 / 1024 / 1024:.2f} GB"
        if data_limit > 0:
            total_traffic += f" / {data_limit} GB"
        else:
            total_traffic += " / Unlimited"
        
        view.append(type("U",(),{
            "user": u.get("user",""),
            "password": u.get("password",""),
            "expires": expires_str,
            "port": u.get("port",""),
            "status": status,
            "email": u.get('email', ''),
            "data_limit": data_limit,
            "total_traffic": total_traffic,
            "bandwidth_used": bandwidth_used,
            "speed_limit": u.get('speed_limit', 0),
            "concurrent_conn": u.get('concurrent_conn', 1)
        }))
    
    view.sort(key=lambda x:(x.user or "").lower())
    today=today_date.strftime("%Y-%m-%d")
    
    theme = session.get('theme', 'dark')
    html_template = load_html_template()
    return render_template_string(html_template, authed=True, logo=LOGO_URL, 
                                 users=view, msg=msg, err=err, today=today, stats=stats, 
                                 t=t, lang=g.lang, theme=theme)

@app.route("/", methods=["GET"])
def index(): 
    return build_view()

@app.route("/add", methods=["POST"])
def add_user():
    t = g.t
    if not require_login(): return redirect(url_for('login'))
    
    # Generate UUID if not provided
    password = (request.form.get("password") or "").strip()
    if not password:
        password = generate_uuid()
    
    user_data = {
        'user': (request.form.get("user") or "").strip(),
        'password': password,
        'email': (request.form.get("email") or "").strip(),
        'expires': (request.form.get("expires") or "").strip(),
        'port': (request.form.get("port") or "").strip(),
        'data_limit': float(request.form.get("data_limit") or 0),
        'speed_limit': int(request.form.get("speed_limit") or 0),
        'concurrent_conn': int(request.form.get("concurrent_conn") or 1)
    }
    
    if not user_data['email']:
        return build_view(err="Email/Remark is required")
    
    if user_data['expires'] and user_data['expires'].isdigit():
        try:
            days = int(user_data['expires'])
            user_data['expires'] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        except ValueError:
            return build_view(err=t['invalid_exp'])
    
    if user_data['expires']:
        try: datetime.strptime(user_data['expires'],"%Y-%m-%d")
        except ValueError:
            return build_view(err=t['invalid_exp'])
    
    if user_data['port']:
        try:
            port_num = int(user_data['port'])
            if not (6000 <= port_num <= 19999):
                 return build_view(err=t['invalid_port'])
        except ValueError:
             return build_view(err=t['invalid_port'])

    if not user_data['port']:
        used_ports = {str(u.get('port', '')) for u in load_users() if u.get('port')}
        found_port = None
        for p in range(6000, 20000):
            if str(p) not in used_ports:
                found_port = str(p)
                break
        user_data['port'] = found_port or ""

    save_user(user_data)
    sync_config_passwords()
    return build_view(msg=t['success_save'])

@app.route("/delete", methods=["POST"])
def delete_user_html():
    t = g.t
    if not require_login(): return redirect(url_for('login'))
    user = (request.form.get("user") or "").strip()
    if not user: return build_view(err=t['required_fields'])
    
    delete_user(user)
    sync_config_passwords()
    return build_view(msg=t['deleted'].format(user=user))

@app.route("/api/user/toggle", methods=["POST"])
def api_toggle_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    enabled = data.get('enabled', False)
    
    if user and toggle_user_status(user, enabled):
        sync_config_passwords()
        return jsonify({"ok": True, "message": f"User {user} {'enabled' if enabled else 'disabled'}"})
    
    return jsonify({"ok": False, "err": "Invalid data"})

if __name__ == "__main__":
    web_port = int(os.environ.get("WEB_PORT", "19432"))
    app.run(host="0.0.0.0", port=web_port)
