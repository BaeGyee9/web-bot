#!/bin/bash
# ZIVPN Enterprise - Complete Installation Script
# Author: မောင်သုည [🇲🇲]
# Features: Complete Enterprise Management System with Advanced Monitoring

set -euo pipefail

# ===== Pretty Colors =====
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

echo -e "\n$LINE\n${G}🚀 ZIVPN Enterprise - Complete Installation ${Z}\n${M}🧑‍💻 Enhanced By မောင်သုည [🇲🇲] ${Z}\n$LINE"

# ===== Root check =====
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${R}❌ Root privileges required. Run: sudo -i ${Z}"; exit 1
fi

# ===== Configuration =====
read -p "🌐 Enter your server IP [auto-detect]: " SERVER_IP
SERVER_IP=${SERVER_IP:-$(curl -s icanhazip.com)}

read -p "🔧 Enter ZIVPN listen port [5667]: " LISTEN_PORT
LISTEN_PORT=${LISTEN_PORT:-5667}

read -p "🌍 Enter Web Panel port [19432]: " WEB_PORT
WEB_PORT=${WEB_PORT:-19432}

echo -e "\n${G}🔐 Web Admin Setup ${Z}"
read -p "👤 Admin username [admin]: " WEB_USER
WEB_USER=${WEB_USER:-admin}
read -s -p "🔒 Admin password: " WEB_PASS; echo

read -p "🤖 Telegram Bot Token [optional]: " BOT_TOKEN

# ===== Installation =====
echo -e "\n${Y}📦 Installing dependencies...${Z}"
apt-get update -y
apt-get install -y curl wget python3 python3-pip python3-venv sqlite3 jq

# ===== Download and setup ZIVPN =====
echo -e "\n${Y}⬇️ Downloading ZIVPN binary...${Z}"
ZIVPN_URL="https://github.com/zahidbd2/udp-zivpn/releases/latest/download/udp-zivpn-linux-amd64"
curl -fSL -o /usr/local/bin/zivpn "$ZIVPN_URL"
chmod +x /usr/local/bin/zivpn

# ===== Create directory structure =====
mkdir -p /etc/zivpn /var/log/zivpn

# ===== Setup enhanced database =====
echo -e "\n${Y}🗃️ Setting up enhanced database...${Z}"
sqlite3 /etc/zivpn/zivpn.db <<'EOF'
-- Core users table
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
    last_login DATETIME,
    last_ip TEXT,
    total_connections INTEGER DEFAULT 0,
    is_online INTEGER DEFAULT 0,
    current_server TEXT
);

-- Enhanced monitoring tables
CREATE TABLE IF NOT EXISTS connection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    client_ip TEXT NOT NULL,
    connect_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    disconnect_time DATETIME,
    bytes_sent INTEGER DEFAULT 0,
    bytes_received INTEGER DEFAULT 0,
    duration INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    session_id TEXT UNIQUE NOT NULL,
    client_ip TEXT NOT NULL,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS server_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    total_bandwidth INTEGER DEFAULT 0,
    server_load REAL DEFAULT 0,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_connection_logs_username ON connection_logs(username);
CREATE INDEX IF NOT EXISTS idx_connection_logs_time ON connection_logs(connect_time);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_user_sessions_username ON user_sessions(username);
EOF

# ===== Generate SSL certificates =====
echo -e "\n${Y}🔐 Generating SSL certificates...${Z}"
openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 \
    -subj "/C=MM/ST=Yangon/L=Yangon/O=ZIVPN/OU=Enterprise/CN=zivpn" \
    -keyout "/etc/zivpn/zivpn.key" -out "/etc/zivpn/zivpn.crt" >/dev/null 2>&1

# ===== Create config file =====
echo -e "\n${Y}📄 Creating configuration...${Z}"
cat > /etc/zivpn/config.json <<EOF
{
    "listen": ":$LISTEN_PORT",
    "cert": "/etc/zivpn/zivpn.crt",
    "key": "/etc/zivpn/zivpn.key",
    "obfs": "zivpn",
    "auth": {
        "mode": "passwords",
        "config": ["defaultpass123"]
    },
    "server": "$SERVER_IP"
}
EOF

# ===== Create environment file =====
cat > /etc/zivpn/web.env <<EOF
WEB_ADMIN_USER=$WEB_USER
WEB_ADMIN_PASSWORD=$WEB_PASS
WEB_SECRET=$(openssl rand -hex 32)
DATABASE_PATH=/etc/zivpn/zivpn.db
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
DEFAULT_LANGUAGE=my
WEB_PORT=$WEB_PORT
SERVER_IP=$SERVER_IP
EOF

# ===== Download enhanced components =====
echo -e "\n${Y}📥 Downloading enhanced components...${Z}"

# Download enhanced web panel
curl -fSL -o /etc/zivpn/web.py \
    "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/templates/web.py"

# Download enhanced Telegram bot
curl -fSL -o /etc/zivpn/bot.py \
    "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/telegram/bot.py"

# Download advanced monitor
curl -fSL -o /etc/zivpn/advanced_monitor.py \
    "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/services/advanced_monitor.py"

# Download enhanced connection manager
curl -fSL -o /etc/zivpn/connection_manager.py \
    "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/services/connection_manager.py"

# ===== Create systemd services =====
echo -e "\n${Y}⚙️ Creating systemd services...${Z}"

# ZIVPN Main Service
cat > /etc/systemd/system/zivpn.service <<EOF
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

[Install]
WantedBy=multi-user.target
EOF

# Web Panel Service
cat > /etc/systemd/system/zivpn-web.service <<EOF
[Unit]
Description=ZIVPN Web Panel
After=network.target

[Service]
Type=simple
User=root
EnvironmentFile=/etc/zivpn/web.env
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/web.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Telegram Bot Service
cat > /etc/systemd/system/zivpn-bot.service <<EOF
[Unit]
Description=ZIVPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
EnvironmentFile=/etc/zivpn/web.env
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/bot.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Advanced Monitor Service
cat > /etc/systemd/system/zivpn-monitor.service <<EOF
[Unit]
Description=ZIVPN Advanced Connection Monitor
After=network.target zivpn.service

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/advanced_monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# ===== Setup networking =====
echo -e "\n${Y}🌐 Configuring network...${Z}"
sysctl -w net.ipv4.ip_forward=1
echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

# Setup iptables rules
iptables -t nat -A PREROUTING -p udp --dport 6000:19999 -j DNAT --to-destination :$LISTEN_PORT
iptables -t nat -A POSTROUTING -j MASQUERADE

# ===== Start services =====
echo -e "\n${Y}🚀 Starting services...${Z}"
systemctl daemon-reload
systemctl enable zivpn.service zivpn-web.service zivpn-bot.service zivpn-monitor.service
systemctl start zivpn.service zivpn-web.service zivpn-bot.service zivpn-monitor.service

# ===== Completion message =====
echo -e "\n$LINE\n${G}✅ ZIVPN Enterprise Installation Completed! ${Z}\n$LINE"
echo -e "${C}🌐 Web Panel:${Z} ${Y}http://$SERVER_IP:$WEB_PORT${Z}"
echo -e "${C}👤 Admin:${Z} ${Y}$WEB_USER${Z}"
echo -e "${C}🔐 Password:${Z} ${Y}[Your chosen password]${Z}"
echo -e "\n${M}📊 Services Status:${Z}"
echo -e "  ${Y}systemctl status zivpn-web${Z}      - Web Panel"
echo -e "  ${Y}systemctl status zivpn-bot${Z}      - Telegram Bot"
echo -e "  ${Y}systemctl status zivpn-monitor${Z}  - Advanced Monitor"
echo -e "\n${G}🎯 Enhanced Features:${Z}"
echo -e "  • Real-time connection monitoring"
echo -e "  • Live user tracking"
echo -e "  • Advanced statistics"
echo -e "  • Bandwidth usage tracking"
echo -e "  • Multi-server support"
echo -e "$LINE"
