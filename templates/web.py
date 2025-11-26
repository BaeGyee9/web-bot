#!/usr/bin/env python3
"""
ZIVPN Enterprise Web Panel - Enhanced with Real-time Monitoring
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
        'live_connections': 'Live Connections', 'connection_monitor': 'Connection Monitor',
        'client_ip': 'Client IP', 'connected_time': 'Connected Time',
        'duration': 'Duration', 'data_used': 'Data Used', 'real_time_monitoring': 'Real-time Monitoring'
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
        'live_connections': 'တိုက်ရိုက်ချိတ်ဆက်မှုများ', 'connection_monitor': 'ချိတ်ဆက်မှု စောင့်ကြည့်ရေး',
        'client_ip': 'ကလိုင်းယန့် IP', 'connected_time': 'ချိတ်ဆက်သည့်အချိန်',
        'duration': 'ကြာချိန်', 'data_used': 'အသုံးပြုပြီး ဒေတာ', 'real_time_monitoring': 'တိုက်ရိုက်စောင့်ကြည့်ခြင်း'
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
        # Fallback to local template (will be enhanced)
        return FALLBACK_HTML

# Enhanced Fallback HTML template with connection monitoring
FALLBACK_HTML = """
<!DOCTYPE html>
<html lang="{{lang}}">
<head>
    <meta charset="utf-8">
    <title>{{t.title}} - ZIVPN Enterprise</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="refresh" content="120">
    <link href="https://fonts.googleapis.com/css2?family=Padauk:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
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
        html, body { background: var(--bg); color: var(--fg); font-family: 'Padauk', sans-serif; margin: 0; padding: 0; line-height: 1.6; min-height: 100vh; }
        .container { max-width: 1400px; margin: auto; padding: 20px; padding-bottom: 80px; }
        
        /* Connection Monitor Styles */
        .connections-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin: 20px 0; }
        .connection-card { background: var(--card); padding: 15px; border-radius: var(--radius); border: 1px solid var(--bd); }
        .connection-header { display: flex; justify-content: between; align-items: center; margin-bottom: 10px; }
        .connection-user { font-weight: bold; color: var(--primary-btn); }
        .connection-ip { font-family: monospace; background: var(--bg); padding: 2px 6px; border-radius: 4px; font-size: 0.8em; }
        .connection-details { font-size: 0.85em; color: var(--bd); }
        .live-badge { background: var(--ok); color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; font-weight: bold; }
        
        /* Stats enhancements */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { padding: 20px; background: var(--card); border-radius: var(--radius); text-align: center; box-shadow: var(--shadow); border: 1px solid var(--bd); }
        .stat-number { font-size: 1.8em; font-weight: 900; margin: 8px 0; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        
        /* Real-time blinking effect */
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .live-indicator { animation: blink 2s infinite; color: var(--ok); }
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
    
    <!-- Enhanced Header with Connection Stats -->
    <header class="header">
        <div class="header-content">
            <div class="logo-container">
                <img src="{{ logo }}" alt="ZIVPN" class="logo">
                <h1>ZIVPN Enterprise</h1>
            </div>
            <div class="subtitle">
                <i class="fas fa-circle live-indicator"></i> 
                {{t.real_time_monitoring}} | 
                {{t.active_connections}}: <strong>{{ live_stats.active_connections }}</strong>
            </div>
        </div>
    </header>

    <!-- Navigation -->
    <nav class="bottom-nav">
        <div class="nav-items">
            <a href="javascript:void(0)" class="nav-item active" onclick="showSection('home')">
                <i class="fas fa-home nav-icon"></i>
                <span class="nav-label">{{t.home}}</span>
            </a>
            <a href="javascript:void(0)" class="nav-item" onclick="showSection('connections')">
                <i class="fas fa-plug nav-icon"></i>
                <span class="nav-label">{{t.live_connections}}</span>
            </a>
            <a href="javascript:void(0)" class="nav-item" onclick="showSection('manage')">
                <i class="fas fa-users nav-icon"></i>
                <span class="nav-label">{{t.manage}}</span>
            </a>
            <a href="javascript:void(0)" class="nav-item" onclick="showSection('adduser')">
                <i class="fas fa-user-plus nav-icon"></i>
                <span class="nav-label">Add User</span>
            </a>
            <a href="javascript:void(0)" class="nav-item" onclick="showSection('reports')">
                <i class="fas fa-chart-bar nav-icon"></i>
                <span class="nav-label">{{t.reports}}</span>
            </a>
            <a href="javascript:void(0)" class="nav-item" onclick="openSettings()">
                <i class="fas fa-cog nav-icon"></i>
                <span class="nav-label">{{t.settings}}</span>
            </a>
        </div>
    </nav>

    <!-- Home Section -->
    <div id="home" class="content-section active">
        <!-- Enhanced Stats Overview -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon" style="color:var(--primary-btn);">
                    <i class="fas fa-users"></i>
                </div>
                <div class="stat-number">{{ stats.total_users }}</div>
                <div class="stat-label">{{t.total_users}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color:var(--ok);">
                    <i class="fas fa-signal"></i>
                </div>
                <div class="stat-number">{{ stats.active_users }}</div>
                <div class="stat-label">{{t.active_users}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color:var(--success);">
                    <i class="fas fa-plug"></i>
                </div>
                <div class="stat-number">{{ live_stats.active_connections }}</div>
                <div class="stat-label">{{t.active_connections}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color:var(--delete-btn);">
                    <i class="fas fa-database"></i>
                </div>
                <div class="stat-number">{{ stats.total_bandwidth }}</div>
                <div class="stat-label">{{t.bandwidth_used}}</div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="form-card">
            <h3 class="form-title"><i class="fas fa-bolt"></i> {{t.quick_actions}}</h3>
            <div class="quick-actions">
                <a href="javascript:void(0)" class="quick-btn" onclick="showSection('connections')">
                    <i class="fas fa-plug"></i>
                    <span>{{t.live_connections}}</span>
                </a>
                <a href="javascript:void(0)" class="quick-btn" onclick="showSection('manage')">
                    <i class="fas fa-users"></i>
                    <span>{{t.manage}}</span>
                </a>
                <a href="javascript:void(0)" class="quick-btn" onclick="showSection('adduser')">
                    <i class="fas fa-user-plus"></i>
                    <span>{{t.add_user}}</span>
                </a>
                <a href="javascript:void(0)" class="quick-btn" onclick="showSection('reports')">
                    <i class="fas fa-chart-bar"></i>
                    <span>{{t.reports}}</span>
                </a>
            </div>
        </div>

        <!-- Recent Activity with Connections -->
        <div class="form-card">
            <h3 class="form-title"><i class="fas fa-clock"></i> {{t.recent_activity}}</h3>
            <div style="max-height: 200px; overflow-y: auto;">
                {% for u in users[:5] %}
                <div style="padding: 10px; border-bottom: 1px solid var(--bd); display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{{u.user}}</strong>
                        <div style="font-size: 0.8em; color: var(--bd);">
                            Port: {{u.port or 'Default'}} | 
                            Connections: {{u.active_connections or 0}}
                        </div>
                    </div>
                    <span class="pill pill-{{u.status|lower}}">{{u.status}}</span>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <!-- Live Connections Section -->
    <div id="connections" class="content-section">
        <div class="form-card">
            <h3 class="form-title">
                <i class="fas fa-plug"></i> {{t.live_connections}}
                <span class="live-badge">{{ live_stats.active_connections }} Active</span>
            </h3>
            
            {% if live_connections %}
            <div class="connections-grid">
                {% for conn in live_connections %}
                <div class="connection-card">
                    <div class="connection-header">
                        <div class="connection-user">{{ conn.username }}</div>
                        <div class="live-badge">LIVE</div>
                    </div>
                    <div class="connection-ip">{{ conn.client_ip }}</div>
                    <div class="connection-details">
                        <div><i class="fas fa-port"></i> Port: {{ conn.server_port }}</div>
                        <div><i class="fas fa-clock"></i> Duration: {{ conn.duration|round|int }}s</div>
                        <div><i class="fas fa-database"></i> Data: {{ (conn.bytes_sent + conn.bytes_recv)|filesizeformat }}</div>
                        <div><i class="fas fa-signal"></i> Connected: {{ conn.connected_at }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div style="text-align: center; padding: 40px; color: var(--bd);">
                <i class="fas fa-plug" style="font-size: 3em; margin-bottom: 15px;"></i>
                <h3>No Active Connections</h3>
                <p>No users are currently connected to the VPN.</p>
            </div>
            {% endif %}
        </div>
    </div>

    <!-- Existing Manage Users, Add User, Reports sections -->
    <!-- ... [Previous sections remain the same] ... -->
    
    {% endif %}
</div>

<script>
// Auto-refresh connections every 10 seconds
function refreshConnections() {
    if (document.getElementById('connections').classList.contains('active')) {
        // You can implement AJAX refresh here
        console.log('Refreshing connections...');
    }
}
setInterval(refreshConnections, 10000);
</script>
</body>
</html>
"""

# ... [Rest of the web.py code remains the same with enhanced functions] ...

def get_live_connections():
    """Get live connections from connection manager"""
    try:
        response = requests.get('http://localhost:8082/api/v1/connections', timeout=2)
        if response.status_code == 200:
            return response.json().get('connections', [])
    except:
        pass
    return []

def get_live_stats():
    """Get live connection statistics"""
    try:
        response = requests.get('http://localhost:8082/api/v1/connection_stats', timeout=2)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {'total_connections': 0, 'unique_users': 0, 'total_bandwidth': 0}

# Enhanced build_view function
def build_view(msg="", err=""):
    t = g.t
    if not require_login():
        html_template = load_html_template()
        return render_template_string(html_template, authed=False, logo=LOGO_URL, err=session.pop("login_err", None), 
                                      t=t, lang=g.lang, theme=session.get('theme', 'dark'))
    
    users=load_users()
    listen_port=get_listen_port_from_config()
    stats = get_server_stats()
    live_connections = get_live_connections()
    live_stats = get_live_stats()
    
    view=[]
    today_date=datetime.now().date()
    
    for u in users:
        status = status_for_user(u, listen_port)
        expires_str=u.get("expires","")
        
        # Get active connections for this user
        user_active_conns = [conn for conn in live_connections if conn['username'] == u.get('user','')]
        
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
            "active_connections": len(user_active_conns)
        }))
    
    view.sort(key=lambda x:(x.user or "").lower())
    today=today_date.strftime("%Y-%m-%d")
    
    theme = session.get('theme', 'dark')
    html_template = load_html_template()
    return render_template_string(html_template, authed=True, logo=LOGO_URL, 
                                 users=view, msg=msg, err=err, today=today, stats=stats,
                                 live_connections=live_connections, live_stats=live_stats,
                                 t=t, lang=g.lang, theme=theme)

# ... [Rest of the existing web.py code remains unchanged] ...

if __name__ == "__main__":
    web_port = int(os.environ.get("WEB_PORT", "19432"))
    app.run(host="0.0.0.0", port=web_port)
