#!/bin/bash
# ZIVPN UDP Server + Web UI (Myanmar) - ENTERPRISE EDITION
# Author: မောင်သုည [🇲🇲]
# Features: Complete Enterprise Management System with Bandwidth Control, Billing, Multi-Server, API, etc.
set -euo pipefail

# ===== Pretty =====
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

echo -e "\n$LINE\n${G}🌟 ZIVPN UDP Server + Web UI - ENTERPRISE EDITION ${Z}\n${M}🧑‍💻 Script By မောင်သုည [🇲🇲] ${Z}\n$LINE"

# ===== Root check & apt guards =====
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${R} script root accept (sudo -i)${Z}"; exit 1
fi
export DEBIAN_FRONTEND=noninteractive

wait_for_apt() {
  echo -e "${Y}⏳ wait apt 3 min ${Z}"
  for _ in $(seq 1 60); do
    if pgrep -x apt-get >/dev/null || pgrep -x apt >/dev/null || pgrep -f 'apt.systemd.daily' >/dev/null || pgrep -x unattended-upgrade >/dev/null; then
      sleep 5
    else return 0; fi
  done
  echo -e "${Y}⚠️ apt timers ကို ယာယီရပ်နေပါတယ်${Z}"
  systemctl stop --now unattended-upgrades.service 2>/dev/null || true
  systemctl stop --now apt-daily.service apt-daily.timer 2>/dev/null || true
  systemctl stop --now apt-daily-upgrade.service apt-daily-upgrade.timer 2>/dev/null || true
}

apt_guard_start(){
  wait_for_apt
  CNF_CONF="/etc/apt/apt.conf.d/50command-not-found"
  if [ -f "$CNF_CONF" ]; then mv "$CNF_CONF" "${CNF_CONF}.disabled"; CNF_DISABLED=1; else CNF_DISABLED=0; fi
}
apt_guard_end(){
  dpkg --configure -a >/dev/null 2>&1 || true
  apt-get -f install -y >/dev/null 2>&1 || true
  if [ "${CNF_DISABLED:-0}" = "1" ] && [ -f "${CNF_CONF}.disabled" ]; then mv "${CNF_CONF}.disabled" "$CNF_CONF"; fi
}

# Stop old services
systemctl stop zivpn.service 2>/dev/null || true
systemctl stop zivpn-web.service 2>/dev/null || true
systemctl stop zivpn-api.service 2>/dev/null || true
systemctl stop zivpn-bot.service 2>/dev/null || true
systemctl stop zivpn-cleanup.timer 2>/dev/null || true
systemctl stop zivpn-backup.timer 2>/dev/null || true
systemctl stop zivpn-connection.service 2>/dev/null || true

# ===== Enhanced Packages =====
say "${Y}📦 Enhanced Packages တင်နေပါတယ်...${Z}"
apt_guard_start
apt-get update -y -o APT::Update::Post-Invoke-Success::= -o APT::Update::Post-Invoke::= >/dev/null
apt-get install -y curl ufw jq python3 python3-flask python3-pip python3-venv iproute2 conntrack ca-certificates sqlite3 >/dev/null || \
{
  apt-get install -y -o DPkg::Lock::Timeout=60 python3-apt >/dev/null || true
  apt-get install -y curl ufw jq python3 python3-flask python3-pip iproute2 conntrack ca-certificates sqlite3 >/dev/null
}

# Additional Python packages
pip3 install requests python-dateutil python-dotenv python-telegram-bot >/dev/null 2>&1 || true
apt_guard_end

# ===== Paths =====
BIN="/usr/local/bin/zivpn"
CFG="/etc/zivpn/config.json"
USERS="/etc/zivpn/users.json"
DB="/etc/zivpn/zivpn.db"
ENVF="/etc/zivpn/web.env"
BACKUP_DIR="/etc/zivpn/backups"
mkdir -p /etc/zivpn "$BACKUP_DIR"

# ===== Download ZIVPN binary =====
say "${Y}⬇️ ZIVPN binary ကို ဒေါင်းနေပါတယ်...${Z}"
PRIMARY_URL="https://github.com/zahidbd2/udp-zivpn/releases/download/udp-zivpn_1.4.9/udp-zivpn-linux-amd64"
FALLBACK_URL="https://github.com/zahidbd2/udp-zivpn/releases/latest/download/udp-zivpn-linux-amd64"
TMP_BIN="$(mktemp)"
if ! curl -fsSL -o "$TMP_BIN" "$PRIMARY_URL"; then
  echo -e "${Y}Primary URL မရ — latest ကို စမ်းပါတယ်...${Z}"
  curl -fSL -o "$TMP_BIN" "$FALLBACK_URL"
fi
install -m 0755 "$TMP_BIN" "$BIN"
rm -f "$TMP_BIN"

# ===== Enhanced Database Setup =====
say "${Y}🗃️ Enhanced Database ဖန်တီးနေပါတယ်...${Z}"
sqlite3 "$DB" <<'EOF'
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    expires DATE,
    port INTEGER,
    status TEXT DEFAULT 'active',
    bandwidth_limit INTEGER DEFAULT 0,
    bandwidth_used INTEGER DEFAULT 0,
    speed_limit_up INTEGER DEFAULT 0,
    speed_limit_down INTEGER DEFAULT 0,
    concurrent_conn INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    email TEXT DEFAULT '',
    data_limit INTEGER DEFAULT 0,
    total_traffic TEXT DEFAULT '0 GB'
);

CREATE TABLE IF NOT EXISTS billing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    plan_type TEXT DEFAULT 'monthly',
    amount REAL DEFAULT 0,
    currency TEXT DEFAULT 'MMK',
    payment_method TEXT,
    payment_status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS bandwidth_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    bytes_used INTEGER DEFAULT 0,
    log_date DATE DEFAULT CURRENT_DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS server_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    total_bandwidth INTEGER DEFAULT 0,
    server_load REAL DEFAULT 0,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user TEXT NOT NULL,
    action TEXT NOT NULL,
    target_user TEXT,
    details TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    read_status INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Add new columns if they don't exist
PRAGMA foreign_keys=off;
BEGIN TRANSACTION;

-- Check if columns exist and add them if not
CREATE TABLE IF NOT EXISTS users_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    expires DATE,
    port INTEGER,
    status TEXT DEFAULT 'active',
    bandwidth_limit INTEGER DEFAULT 0,
    bandwidth_used INTEGER DEFAULT 0,
    speed_limit_up INTEGER DEFAULT 0,
    speed_limit_down INTEGER DEFAULT 0,
    concurrent_conn INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    email TEXT DEFAULT '',
    data_limit INTEGER DEFAULT 0,
    total_traffic TEXT DEFAULT '0 GB'
);

-- Copy data from old table to new table
INSERT OR IGNORE INTO users_new (
    id, username, password, expires, port, status, bandwidth_limit, bandwidth_used,
    speed_limit_up, speed_limit_down, concurrent_conn, created_at, updated_at,
    email, data_limit, total_traffic
)
SELECT 
    id, username, password, expires, port, status, bandwidth_limit, bandwidth_used,
    speed_limit_up, speed_limit_down, concurrent_conn, created_at, updated_at,
    COALESCE(email, ''), COALESCE(data_limit, 0), COALESCE(total_traffic, '0 GB')
FROM users;

DROP TABLE IF EXISTS users;
ALTER TABLE users_new RENAME TO users;

COMMIT;
PRAGMA foreign_keys=on;
EOF

# ===== Base config & Certs =====
if [ ! -f "$CFG" ]; then
  say "${Y}🧩 config.json ဖန်တီးနေပါတယ်...${Z}"
  curl -fsSL -o "$CFG" "https://raw.githubusercontent.com/zahidbd2/udp-zivpn/main/config.json" || echo '{}' > "$CFG"
fi

if [ ! -f /etc/zivpn/zivpn.crt ] || [ ! -f /etc/zivpn/zivpn.key ]; then
  say "${Y}🔐 SSL စိတျဖိုင်တွေ ဖန်တီးနေပါတယ်...${Z}"
  openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 \
    -subj "/C=MM/ST=Yangon/L=Yangon/O=KHAINGUDP/OU=Net/CN=khaingudp" \
    -keyout "/etc/zivpn/zivpn.key" -out "/etc/zivpn/zivpn.crt" >/dev/null 2>&1
fi

# ===== Web Admin & ENV Setup =====
say "${Y}🔒 Web Admin Login UI ${Z}"
read -r -p "Web Admin Username (Enter=admin): " WEB_USER
WEB_USER="${WEB_USER:-admin}"
read -r -s -p "Web Admin Password: " WEB_PASS; echo

# Generate strong secret
if command -v openssl >/dev/null 2>&1; then
  WEB_SECRET="$(openssl rand -hex 32)"
else
  WEB_SECRET="$(python3 - <<'PY'
import secrets;print(secrets.token_hex(32))
PY
)"
fi

# Get Telegram Bot Token (optional)
read -r -p "Telegram Bot Token (Optional, Enter=Skip): " BOT_TOKEN
BOT_TOKEN="${BOT_TOKEN:-8079105459:AAFNww6keJvnGJi4DpAHZGESBcL9ytFxqA4}"

{
  echo "WEB_ADMIN_USER=${WEB_USER}"
  echo "WEB_ADMIN_PASSWORD=${WEB_PASS}"
  echo "WEB_SECRET=${WEB_SECRET}"
  echo "DATABASE_PATH=${DB}"
  echo "TELEGRAM_BOT_TOKEN=${BOT_TOKEN}"
  echo "DEFAULT_LANGUAGE=my"
} > "$ENVF"
chmod 600 "$ENVF"

# ===== Ask initial VPN passwords =====
say "${G}🔏 VPN Password List (eg: channel404,alice,pass1)${Z}"
read -r -p "Passwords (Enter=zi): " input_pw
if [ -z "${input_pw:-}" ]; then
  PW_LIST='["zi"]'
else
  PW_LIST=$(echo "$input_pw" | awk -F',' '{
    printf("["); for(i=1;i<=NF;i++){gsub(/^ *| *$/,"",$i); printf("%s\"%s\"", (i>1?",":""), $i)}; printf("]")
  }')
fi

# Get Server IP
SERVER_IP=$(hostname -I | awk '{print $1}')
if [ -z "${SERVER_IP:-}" ]; then
  SERVER_IP=$(curl -s icanhazip.com || echo "127.0.0.1")
fi

# ===== Update config.json =====
if jq . >/dev/null 2>&1 <<<'{}'; then
  TMP=$(mktemp)
  jq --argjson pw "$PW_LIST" --arg ip "$SERVER_IP" '
    .auth.mode = "passwords" |
    .auth.config = $pw |
    .listen = (."listen" // ":5667") |
    .cert = "/etc/zivpn/zivpn.crt" |
    .key  = "/etc/zivpn/zivpn.key" |
    .obfs = (."obfs" // "zivpn") |
    .server = $ip
  ' "$CFG" > "$TMP" && mv "$TMP" "$CFG"
fi
[ -f "$USERS" ] || echo "[]" > "$USERS"
chmod 644 "$CFG" "$USERS"

# ===== Download Updated Web Panel =====
say "${Y}🌐 Updated Web Panel ထည့်သွင်းနေပါတယ်...${Z}"
cat > /etc/zivpn/web.py << 'EOF'
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
        'add_client': 'Add Client', 'close': 'Close',
        'enabled': 'Enabled', 'disabled': 'Disabled'
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
        'add_client': 'အသုံးပြုသူအသစ်ထည့်ရန်', 'close': 'ပိတ်မည်',
        'enabled': 'ဖွင့်ထား', 'disabled': 'ပိတ်ထား'
    }
}

def generate_uuid():
    """Generate UUID for password"""
    return str(uuid.uuid4())

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
        .xui-table-container { overflow-x: auto; border-radius: var(--radius); background: var(--card); border: 1px solid var(--bd); margin: 20px 0; }
        .xui-table { width: 100%; border-collapse: collapse; background: var(--card); }
        .xui-table th, .xui-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--bd); }
        .xui-table th { background: var(--primary-btn); color: white; font-weight: 600; }
        .xui-table tr:hover { background: rgba(59, 130, 246, 0.05); }
        
        /* Status Pills */
        .xui-pill { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 700; color: white; }
        .xui-pill-online { background: var(--ok); }
        .xui-pill-offline { background: var(--bad); }
        .xui-pill-expired { background: var(--expired); }
        .xui-pill-suspended { background: var(--unknown); }
        
        /* Action Buttons */
        .xui-action-btns { display: flex; gap: 5px; align-items: center; }
        .xui-action-btn { padding: 6px 10px; border: none; border-radius: var(--radius); cursor: pointer; transition: all 0.3s ease; font-size: 0.8em; }
        
        /* Login Styles */
        .login-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--gradient); padding: 20px; }
        .login-card { background: var(--card); padding: 30px; border-radius: var(--radius); box-shadow: var(--shadow); width: 100%; max-width: 400px; text-align: center; }
        .login-logo { height: 80px; width: 80px; border-radius: 50%; border: 3px solid var(--primary-btn); margin: 0 auto 20px; padding: 5px; background: white; }
        .login-title { margin: 0 0 20px 0; color: var(--fg); font-size: 1.5em; font-weight: 700; }
        .alert { padding: 12px 15px; border-radius: var(--radius); margin: 15px 0; font-weight: 600; }
        .alert-success { background: var(--success); color: white; }
        .alert-error { background: var(--delete-btn); color: white; }
    </style>
</head>
<body data-theme="{{theme}}">

{% if not authed %}
<div class="login-container">
    <div class="login-card">
        <img src="{{ logo }}" alt="ZIVPN" class="login-logo">
        <h2 class="login-title">{{t.login_title}}</h2>
        {% if err %}<div class="alert alert-error">{{err}}</div>{% endif %}
        <form method="post" action="/login">
            <div class="xui-form-group">
                <label class="xui-label"><i class="fas fa-user"></i> {{t.username}}</label>
                <input name="u" class="xui-input" autofocus required>
            </div>
            <div class="xui-form-group">
                <label class="xui-label"><i class="fas fa-lock"></i> {{t.password}}</label>
                <input name="p" type="password" class="xui-input" required>
            </div>
            <button type="submit" class="xui-btn xui-btn-primary xui-btn-block">
                <i class="fas fa-sign-in-alt"></i> {{t.login}}
            </button>
        </form>
    </div>
</div>
{% else %}

<div class="container">
    <!-- X-UI Style Add Client Form -->
    <div class="xui-form">
        <h3 class="xui-form-title"><i class="fas fa-user-plus"></i> {{t.add_client}}</h3>
        
        {% if msg %}<div class="alert alert-success">{{msg}}</div>{% endif %}
        {% if err %}<div class="alert alert-error">{{err}}</div>{% endif %}
        
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
                        <td><code style="background:var(--bg);padding:2px 5px;border-radius:4px;">{{u.password}}</code></td>
                        <td>{{u.total_traffic}}</td>
                        <td>{{u.expires or '-'}}</td>
                        <td>
                            <span class="xui-pill xui-pill-{{u.status|lower}}">{{u.status}}</span>
                        </td>
                        <td>
                            <div class="xui-action-btns">
                                <label class="xui-toggle">
                                    <input type="checkbox" {% if u.status=='online' or u.status=='active' %}checked{% endif %} onchange="toggleUser('{{u.user}}', this.checked)">
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
        <i class="fas fa-sign-out-alt"></i> {{t.logout}}
    </a>
</div>
{% endif %}

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
ADMIN_PASS = os.environ.get("WEB_ADMIN_PASSWORD","").strip()
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

def init_database():
    """Initialize database with new columns"""
    db = get_db()
    try:
        # Add new columns if they don't exist
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                expires DATE,
                port INTEGER,
                status TEXT DEFAULT 'active',
                bandwidth_limit INTEGER DEFAULT 0,
                bandwidth_used INTEGER DEFAULT 0,
                speed_limit_up INTEGER DEFAULT 0,
                speed_limit_down INTEGER DEFAULT 0,
                concurrent_conn INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                email TEXT DEFAULT '',
                data_limit INTEGER DEFAULT 0,
                total_traffic TEXT DEFAULT '0 GB'
            )
        ''')
        
        # Check if new columns exist, if not add them
        columns = [row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()]
        
        if 'email' not in columns:
            db.execute('ALTER TABLE users ADD COLUMN email TEXT DEFAULT ""')
        if 'data_limit' not in columns:
            db.execute('ALTER TABLE users ADD COLUMN data_limit INTEGER DEFAULT 0')
        if 'total_traffic' not in columns:
            db.execute('ALTER TABLE users ADD COLUMN total_traffic TEXT DEFAULT "0 GB"')
            
        db.commit()
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        db.close()

def load_users():
    db = get_db()
    users = db.execute('''
        SELECT username as user, password, expires, port, status, 
               bandwidth_limit, bandwidth_used, speed_limit_up as speed_limit,
               concurrent_conn, email, data_limit, total_traffic
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
        
        # Calculate bandwidth limit in bytes
        data_limit_gb = user_data.get('data_limit', 0)
        bandwidth_limit = data_limit_gb * 1024 * 1024 * 1024  # Convert GB to bytes
        
        db.execute('''
            INSERT OR REPLACE INTO users 
            (username, password, expires, port, status, bandwidth_limit, speed_limit_up, 
             concurrent_conn, email, data_limit, total_traffic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_data['user'], user_data['password'], user_data.get('expires'),
            user_data.get('port'), 'active', bandwidth_limit,
            user_data.get('speed_limit', 0), user_data.get('concurrent_conn', 1),
            user_data.get('email', ''), data_limit_gb, '0 GB'
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
    return render_template_string(FALLBACK_HTML, authed=False, logo=LOGO_URL, err=session.pop("login_err", None), 
                                  t=t, lang=g.lang, theme=theme)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("auth", None)
    return redirect(url_for('login') if login_enabled() else url_for('index'))

def build_view(msg="", err=""):
    t = g.t
    if not require_login():
        return render_template_string(FALLBACK_HTML, authed=False, logo=LOGO_URL, err=session.pop("login_err", None), 
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
    return render_template_string(FALLBACK_HTML, authed=True, logo=LOGO_URL, 
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
    # Initialize database on startup
    init_database()
    
    web_port = int(os.environ.get("WEB_PORT", "19432"))
    app.run(host="0.0.0.0", port=web_port)
EOF

# ===== Download Updated Telegram Bot =====
say "${Y}🤖 Updated Telegram Bot ထည့်သွင်းနေပါတယ်...${Z}"
cat > /etc/zivpn/bot.py << 'EOF'
#!/usr/bin/env python3
"""
ZIVPN Telegram Bot - X-UI Style with UUID Generation
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

def generate_uuid():
    """Generate UUID for password"""
    return str(uuid.uuid4())

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
/adduser <email> [days] - Add user with UUID (Auto-generated)
/adduserpass <email> <password> [days] - Add user with custom password  
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
/toggle <username> - Toggle user on/off
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
/adduser <email> [days] - Add user with UUID (Auto-generated)
/adduserpass <email> <password> [days] - Add user with custom password
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
/toggle <username> - Toggle user on/off
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
🛠️ *Admin Panel*
🌐 Server IP: `{get_server_ip()}`
📊 Total Users: *{total_users}* (Active: *{active_users}*)

*User Management:*
• /adduser <email> [days] - Add user with UUID
• /adduserpass <email> <password> [days] - Add user with custom password
• /changepass <user> <newpass> - Change password
• /deluser <username> - Delete user
• /suspend <username> - Suspend user  
• /activate <username> - Activate user
• /ban <username> - Ban user
• /unban <username> - Unban user
• /renew <username> <days> - Renew user (extend from current)
• /reset <username> <days> - Reset expiry (from today)
• /toggle <username> - Toggle user on/off

*Information (With Passwords):*
• /users - List all users with passwords
• /myinfo <username> - User details with password
• /stats - Server statistics

*Usage Examples:*
/adduser customer@email.com 30
/adduserpass customer@email.com mypassword 30
/toggle username - Toggle user status
/users - See all users with passwords
"""
    update.message.reply_text(admin_text, parse_mode='Markdown')

def adduser_command(update, context):
    """Add new user with UUID - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 1:
        update.message.reply_text("Usage: /adduser <email/remark> [days]\nExample: /adduser customer@email.com 30")
        return
    
    email = context.args[0]
    days = 30  # default 30 days
    
    if len(context.args) > 1:
        try:
            days = int(context.args[1])
        except:
            update.message.reply_text("❌ Invalid days format")
            return
    
    # Generate UUID and username
    password = generate_uuid()
    username = password.split('-')[0]  # Use first part of UUID as username
    
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
            INSERT INTO users (username, password, email, status, expires, concurrent_conn, created_at)
            VALUES (?, ?, ?, 'active', ?, 1, datetime('now'))
        ''', (username, password, email, expiry_date))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        if sync_config_passwords():
            success_text = f"""
✅ *User Added Successfully*

📧 Email/Remark: `{email}`
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

📧 Email/Remark: `{email}`
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

def adduserpass_command(update, context):
    """Add new user with custom password - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Usage: /adduserpass <email/remark> <password> [days]\nExample: /adduserpass customer@email.com mypassword 30")
        return
    
    email = context.args[0]
    password = context.args[1]
    days = 30  # default 30 days
    
    if len(context.args) > 2:
        try:
            days = int(context.args[2])
        except:
            update.message.reply_text("❌ Invalid days format")
            return
    
    # Generate username from password or use first part
    username = password.split('-')[0] if '-' in password else password[:8]
    
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
            INSERT INTO users (username, password, email, status, expires, concurrent_conn, created_at)
            VALUES (?, ?, ?, 'active', ?, 1, datetime('now'))
        ''', (username, password, email, expiry_date))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        if sync_config_passwords():
            success_text = f"""
✅ *User Added Successfully*

📧 Email/Remark: `{email}`
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

📧 Email/Remark: `{email}`
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

def toggle_command(update, context):
    """Toggle user on/off - PRIVATE (Admin only)"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /toggle <username>")
        return
    
    username = context.args[0]
    db = get_db()
    try:
        # Check if user exists and get current status
        user = db.execute('SELECT username, status FROM users WHERE username = ?', (username,)).fetchone()
        if not user:
            update.message.reply_text(f"❌ User `{username}` not found")
            return
        
        current_status = user['status']
        new_status = 'suspended' if current_status == 'active' else 'active'
        
        db.execute('UPDATE users SET status = ? WHERE username = ?', (new_status, username))
        db.commit()
        
        # ✅ SYNC PASSWORDS TO ZIVPN CONFIG
        sync_config_passwords()
        
        status_text = "🔴 Suspended" if new_status == 'suspended' else "🟢 Activated"
        update.message.reply_text(f"✅ User *{username}* {status_text}")
        logger.info(f"User {username} toggled to {new_status} by admin {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error toggling user: {e}")
        update.message.reply_text("❌ Error toggling user")
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
            SELECT username, password, email, status, expires, bandwidth_used, concurrent_conn
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
                email = user['email'] or 'No email'
                users_text += f"{status_icon} *{user['username']}*\n"
                users_text += f"📧 Email: `{email}`\n"
                users_text += f"🔐 Password: `{user['password']}`\n"
                users_text += f"📊 Status: {user['status']}\n"
                users_text += f"📦 Bandwidth: {bandwidth}\n"
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
                email = user['email'] or 'No email'
                users_text += f"{status_icon} *{user['username']}*\n"
                users_text += f"📧 Email: `{email}`\n"
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
            SELECT username, password, email, status, expires, bandwidth_used, bandwidth_limit,
                   speed_limit_up, concurrent_conn, created_at, data_limit
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
        
        # Calculate data limit
        data_limit_gb = user['data_limit'] or 0
        data_limit_text = f"{data_limit_gb} GB" if data_limit_gb > 0 else "Unlimited"
        bandwidth_used_gb = (user['bandwidth_used'] or 0) / 1024 / 1024 / 1024
                
        user_text = f"""
🔍 *User Information: {user['username']}*
📧 Email: `{user['email'] or 'No email'}`
🔐 Password: `{user['password']}`
📊 Status: *{user['status'].upper()}*
⏰ Expires: *{user['expires'] or 'Never'}{days_remaining}*
📦 Bandwidth Used: *{bandwidth_used_gb:.2f} GB*
🎯 Data Limit: *{data_limit_text}*
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
        dp.add_handler(CommandHandler("adduserpass", adduserpass_command))
        dp.add_handler(CommandHandler("changepass", changepass_command))
        dp.add_handler(CommandHandler("deluser", deluser_command))
        dp.add_handler(CommandHandler("toggle", toggle_command))
        dp.add_handler(CommandHandler("suspend", suspend_command))
        dp.add_handler(CommandHandler("activate", activate_command))
        dp.add_handler(CommandHandler("ban", ban_user))
        dp.add_handler(CommandHandler("unban", unban_user))
        dp.add_handler(CommandHandler("renew", renew_command))
        dp.add_handler(CommandHandler("reset", reset_command))
        dp.add_handler(CommandHandler("users", users_command))
        dp.add_handler(CommandHandler("myinfo", myinfo_command))

        dp.add_error_handler(error_handler)

        logger.info("🤖 ZIVPN Telegram Bot Started Successfully")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
EOF

# ===== API Service =====
say "${Y}🔌 API Service ထည့်သွင်းနေပါတယ်...${Z}"
cat >/etc/zivpn/api.py <<'EOF'
from flask import Flask, jsonify, request
import sqlite3, datetime
from datetime import timedelta
import os

app = Flask(__name__)
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    db = get_db()
    stats = db.execute('''
        SELECT 
            COUNT(*) as total_users,
            SUM(CASE WHEN status = "active" AND (expires IS NULL OR expires >= CURRENT_DATE) THEN 1 ELSE 0 END) as active_users,
            SUM(bandwidth_used) as total_bandwidth
        FROM users
    ''').fetchone()
    db.close()
    return jsonify({
        "total_users": stats['total_users'],
        "active_users": stats['active_users'],
        "total_bandwidth_bytes": stats['total_bandwidth']
    })

@app.route('/api/v1/users', methods=['GET'])
def get_users():
    db = get_db()
    users = db.execute('SELECT username, status, expires, bandwidth_used, concurrent_conn FROM users').fetchall()
    db.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/v1/user/<username>', methods=['GET'])
def get_user(username):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    db.close()
    if user:
        return jsonify(dict(user))
    return jsonify({"error": "User not found"}), 404

@app.route('/api/v1/bandwidth/<username>', methods=['POST'])
def update_bandwidth(username):
    data = request.get_json()
    bytes_used = data.get('bytes_used', 0)
    
    db = get_db()
    # 1. Update total usage
    db.execute('''
        UPDATE users 
        SET bandwidth_used = bandwidth_used + ?, updated_at = CURRENT_TIMESTAMP 
        WHERE username = ?
    ''', (bytes_used, username))
    
    # 2. Log bandwidth usage
    db.execute('''
        INSERT INTO bandwidth_logs (username, bytes_used) 
        VALUES (?, ?)
    ''', (username, bytes_used))
    
    db.commit()
    db.close()
    return jsonify({"message": "Bandwidth updated"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
EOF

# ===== Daily Cleanup Script =====
say "${Y}🧹 Daily Cleanup Service ထည့်သွင်းနေပါတယ်...${Z}"
cat >/etc/zivpn/cleanup.py <<'EOF'
import sqlite3
import datetime
import os
import subprocess
import json
import tempfile

DATABASE_PATH = "/etc/zivpn/zivpn.db"
CONFIG_FILE = "/etc/zivpn/config.json"

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

def sync_config_passwords():
    # Only sync passwords for non-suspended/non-expired users
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
    
    write_json_atomic(CONFIG_FILE,cfg)
    subprocess.run("systemctl restart zivpn.service", shell=True)

def daily_cleanup():
    db = get_db()
    today = datetime.datetime.now().date().strftime("%Y-%m-%d")
    suspended_count = 0
    
    try:
        # 1. Auto-suspend expired users
        expired_users = db.execute('''
            SELECT username, expires, status FROM users
            WHERE status = 'active' AND expires < ?
        ''', (today,)).fetchall()
        
        for user in expired_users:
            db.execute('UPDATE users SET status = "suspended" WHERE username = ?', (user['username'],))
            suspended_count += 1
            print(f"User {user['username']} expired on {user['expires']} and was suspended.")
            
        db.commit()

        # 2. Re-sync passwords to exclude the newly suspended users
        if suspended_count > 0:
            print(f"Total {suspended_count} users suspended. Restarting ZIVPN service...")
            sync_config_passwords()
        
        print(f"Cleanup finished. {suspended_count} users suspended today.")
        
    except Exception as e:
        print(f"An error occurred during daily cleanup: {e}")
        
    finally:
        db.close()

if __name__ == '__main__':
    daily_cleanup()
EOF

# ===== Backup Script =====
say "${Y}💾 Backup System ထည့်သွင်းနေပါတယ်...${Z}"
cat >/etc/zivpn/backup.py <<'EOF'
import sqlite3, shutil, datetime, os, gzip

BACKUP_DIR = "/etc/zivpn/backups"
DATABASE_PATH = "/etc/zivpn/zivpn.db"

def backup_database():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"zivpn_backup_{timestamp}.db.gz")
    
    # Backup database
    with open(DATABASE_PATH, 'rb') as f_in:
        with gzip.open(backup_file, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    # Cleanup old backups (keep last 7 days)
    for file in os.listdir(BACKUP_DIR):
        file_path = os.path.join(BACKUP_DIR, file)
        if os.path.isfile(file_path):
            file_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
            if (datetime.datetime.now() - file_time).days > 7:
                os.remove(file_path)
    
    print(f"Backup created: {backup_file}")

if __name__ == '__main__':
    backup_database()
EOF

# ===== Connection Manager =====
say "${Y}🔗 Connection Manager ထည့်သွင်းနေပါတယ်...${Z}"
cat >/etc/zivpn/connection_manager.py <<'EOF'
import sqlite3
import subprocess
import time
import threading
from datetime import datetime
import os

DATABASE_PATH = "/etc/zivpn/zivpn.db"

class ConnectionManager:
    def __init__(self):
        self.connection_tracker = {}
        self.lock = threading.Lock()
        
    def get_db(self):
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
        
    def get_active_connections(self):
        """Get active connections using conntrack"""
        try:
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null | grep -E 'dport=(5667|[6-9][0-9]{3}|[1-9][0-9]{4})' | awk '{print $7,$8}'",
                shell=True, capture_output=True, text=True
            )
            
            connections = {}
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
                            connections[f"{src_ip}:{dport}"] = True
                    except:
                        continue
            return connections
        except:
            return {}
            
    def enforce_connection_limits(self):
        """Enforce connection limits for all users"""
        db = self.get_db()
        try:
            # Get all active users with their connection limits
            users = db.execute('''
                SELECT username, concurrent_conn, port 
                FROM users 
                WHERE status = "active" AND (expires IS NULL OR expires >= CURRENT_DATE)
            ''').fetchall()
            
            active_connections = self.get_active_connections()
            
            for user in users:
                username = user['username']
                max_connections = user['concurrent_conn']
                user_port = str(user['port'] or '5667')
                
                # Count connections for this user (by port)
                user_conn_count = 0
                user_connections = []
                
                for conn_key in active_connections:
                    if conn_key.endswith(f":{user_port}"):
                        user_conn_count += 1
                        user_connections.append(conn_key)
                
                # If over limit, drop oldest connections
                if user_conn_count > max_connections:
                    print(f"User {username} has {user_conn_count} connections (limit: {max_connections})")
                    
                    # Drop excess connections (FIFO - we'll drop the first ones we find)
                    excess = user_conn_count - max_connections
                    for i in range(excess):
                        if i < len(user_connections):
                            conn_to_drop = user_connections[i]
                            self.drop_connection(conn_to_drop)
                            
        finally:
            db.close()
            
    def drop_connection(self, connection_key):
        """Drop a specific connection using conntrack"""
        try:
            # connection_key format: "IP:PORT"
            ip, port = connection_key.split(':')
            subprocess.run(
                f"conntrack -D -p udp --dport {port} --src {ip}",
                shell=True, capture_output=True
            )
            print(f"Dropped connection: {connection_key}")
        except Exception as e:
            print(f"Error dropping connection {connection_key}: {e}")
            
    def start_monitoring(self):
        """Start the connection monitoring loop"""
        def monitor_loop():
            while True:
                try:
                    self.enforce_connection_limits()
                    time.sleep(10)  # Check every 10 seconds
                except Exception as e:
                    print(f"Monitoring error: {e}")
                    time.sleep(30)
                    
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
# Global instance
connection_manager = ConnectionManager()

if __name__ == "__main__":
    print("Starting Connection Manager...")
    connection_manager.start_monitoring()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping Connection Manager...")
EOF

# ===== systemd Services =====
say "${Y}🧰 systemd services များ ထည့်သွင်းနေပါတယ်...${Z}"

# ZIVPN Service
cat >/etc/systemd/system/zivpn.service <<'EOF'
[Unit]
Description=ZIVPN UDP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/local/bin/zivpn server -c /etc/zivpn/config.json
Restart=always
RestartSec=3
Environment=ZIVPN_LOG_LEVEL=info
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

# Web Panel Service
cat >/etc/systemd/system/zivpn-web.service <<'EOF'
[Unit]
Description=ZIVPN Web Panel
After=network.target

[Service]
Type=simple
User=root
EnvironmentFile=-/etc/zivpn/web.env
ExecStart=/usr/bin/python3 /etc/zivpn/web.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# API Service
cat >/etc/systemd/system/zivpn-api.service <<'EOF'
[Unit]
Description=ZIVPN API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/api.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Telegram Bot Service
cat >/etc/systemd/system/zivpn-bot.service <<'EOF'
[Unit]
Description=ZIVPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
EnvironmentFile=-/etc/zivpn/web.env
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/bot.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Connection Manager Service
cat >/etc/systemd/system/zivpn-connection.service <<'EOF'
[Unit]
Description=ZIVPN Connection Manager
After=network.target zivpn.service

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/connection_manager.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Backup Service
cat >/etc/systemd/system/zivpn-backup.service <<'EOF'
[Unit]
Description=ZIVPN Backup Service
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/backup.py

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/zivpn-backup.timer <<'EOF'
[Unit]
Description=Daily ZIVPN Backup
Requires=zivpn-backup.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Cleanup Service
cat >/etc/systemd/system/zivpn-cleanup.service <<'EOF'
[Unit]
Description=ZIVPN Daily Cleanup
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/cleanup.py

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/zivpn-cleanup.timer <<'EOF'
[Unit]
Description=Daily ZIVPN Cleanup Timer
Requires=zivpn-cleanup.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

# ===== Networking Setup =====
echo -e "${Y}🌐 Network Configuration ပြုလုပ်နေပါတယ်...${Z}"
sysctl -w net.ipv4.ip_forward=1 >/dev/null
grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

IFACE=$(ip -4 route ls | awk '/default/ {print $5; exit}')
[ -n "${IFACE:-}" ] || IFACE=eth0

# DNAT Rules
iptables -t nat -F
iptables -t nat -A PREROUTING -i "$IFACE" -p udp --dport 6000:19999 -j DNAT --to-destination :5667
iptables -t nat -A POSTROUTING -o "$IFACE" -j MASQUERADE

# UFW Rules
ufw allow 1:65535/tcp >/dev/null 2>&1 || true
ufw allow 1:65535/udp >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

# ===== Final Setup =====
say "${Y}🔧 Final Configuration ပြုလုပ်နေပါတယ်...${Z}"
chmod +x /etc/zivpn/*.py
sed -i 's/\r$//' /etc/zivpn/*.py /etc/systemd/system/zivpn* || true

systemctl daemon-reload
systemctl enable --now zivpn.service
systemctl enable --now zivpn-web.service
systemctl enable --now zivpn-api.service
systemctl enable --now zivpn-bot.service
systemctl enable --now zivpn-connection.service
systemctl enable --now zivpn-backup.timer
systemctl enable --now zivpn-cleanup.timer

# Initial setup
python3 /etc/zivpn/backup.py
python3 /etc/zivpn/cleanup.py
systemctl restart zivpn.service

# ===== Completion Message =====
IP=$(hostname -I | awk '{print $1}')
echo -e "\n$LINE\n${G}✅ ZIVPN Enterprise Edition Completed!${Z}"
echo -e "${C}🌐 WEB PANEL:${Z} ${Y}http://$IP:19432${Z}"
echo -e "\n${G}🔐 LOGIN CREDENTIALS${Z}"
echo -e "  ${Y}• Username:${Z} ${Y}$WEB_USER${Z}"
echo -e "  ${Y}• Password:${Z} ${Y}$WEB_PASS${Z}"
echo -e "\n${M}📊 SERVICES STATUS:${Z}"
echo -e "  ${Y}systemctl status zivpn-web${Z}      - Web Panel"
echo -e "  ${Y}systemctl status zivpn-bot${Z}      - Telegram Bot"
echo -e "  ${Y}systemctl status zivpn-connection${Z} - Connection Manager"
echo -e "$LINE"
