#!/bin/bash
# ZIVPN Enterprise Upgrade Script
# Upgrades existing installation with enhanced features

set -euo pipefail

# ===== Pretty Colors =====
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

echo -e "\n$LINE\n${G}🔄 ZIVPN Enterprise Upgrade Script ${Z}\n${M}🧑‍💻 Upgrading to Enhanced Version ${Z}\n$LINE"

# ===== Root check =====
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${R}❌ Root privileges required. Run: sudo -i ${Z}"; exit 1
fi

# ===== Check existing installation =====
echo -e "\n${Y}🔍 Checking existing installation...${Z}"

if [ ! -f "/etc/zivpn/zivpn.db" ]; then
    echo -e "${R}❌ ZIVPN not found. Run install.sh first.${Z}"
    exit 1
fi

# ===== Download enhanced components =====
echo -e "\n${Y}📥 Downloading enhanced components...${Z}"

# Create directories
mkdir -p /etc/zivpn /var/log/zivpn

# Download enhanced web panel
echo -e "${C}* Downloading enhanced web panel...${Z}"
curl -fSL -o /etc/zivpn/web.py \
    "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/templates/web.py"

# Download enhanced Telegram bot
echo -e "${C}* Downloading enhanced Telegram bot...${Z}"
curl -fSL -o /etc/zivpn/bot.py \
    "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/telegram/bot.py"

# Download advanced monitor
echo -e "${C}* Downloading advanced monitor...${Z}"
curl -fSL -o /etc/zivpn/advanced_monitor.py \
    "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/services/advanced_monitor.py"

# Download enhanced connection manager
echo -e "${C}* Downloading connection manager...${Z}"
curl -fSL -o /etc/zivpn/connection_manager.py \
    "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/services/connection_manager.py"

# ===== Upgrade database schema =====
echo -e "\n${Y}🗃️ Upgrading database schema...${Z}"
sqlite3 /etc/zivpn/zivpn.db <<'EOF'
-- Add new columns if they don't exist
BEGIN TRANSACTION;

-- Check and add last_login column
SELECT COUNT(*) FROM pragma_table_info('users') WHERE name='last_login';
EOF

db_has_column() {
    sqlite3 /etc/zivpn/zivpn.db "SELECT COUNT(*) FROM pragma_table_info('users') WHERE name='$1';"
}

if [ $(db_has_column "last_login") -eq 0 ]; then
    echo -e "${C}* Adding last_login column...${Z}"
    sqlite3 /etc/zivpn/zivpn.db "ALTER TABLE users ADD COLUMN last_login DATETIME;"
fi

if [ $(db_has_column "last_ip") -eq 0 ]; then
    echo -e "${C}* Adding last_ip column...${Z}"
    sqlite3 /etc/zivpn/zivpn.db "ALTER TABLE users ADD COLUMN last_ip TEXT;"
fi

if [ $(db_has_column "is_online") -eq 0 ]; then
    echo -e "${C}* Adding is_online column...${Z}"
    sqlite3 /etc/zivpn/zivpn.db "ALTER TABLE users ADD COLUMN is_online INTEGER DEFAULT 0;"
fi

if [ $(db_has_column "total_connections") -eq 0 ]; then
    echo -e "${C}* Adding total_connections column...${Z}"
    sqlite3 /etc/zivpn/zivpn.db "ALTER TABLE users ADD COLUMN total_connections INTEGER DEFAULT 0;"
fi

# Create enhanced tables
echo -e "${C}* Creating enhanced tables...${Z}"
sqlite3 /etc/zivpn/zivpn.db <<'EOF'
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

CREATE INDEX IF NOT EXISTS idx_connection_logs_username ON connection_logs(username);
CREATE INDEX IF NOT EXISTS idx_connection_logs_time ON connection_logs(connect_time);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_user_sessions_username ON user_sessions(username);
EOF

# ===== Create systemd service for monitor =====
echo -e "\n${Y}⚙️ Creating enhanced services...${Z}"
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
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ===== Set permissions =====
echo -e "${C}* Setting permissions...${Z}"
chmod +x /etc/zivpn/*.py
chmod 600 /etc/zivpn/zivpn.db

# ===== Restart services =====
echo -e "\n${Y}🚀 Restarting services...${Z}"
systemctl daemon-reload

# Enable and start monitor service
systemctl enable zivpn-monitor.service
systemctl start zivpn-monitor.service

# Restart other services
systemctl restart zivpn-bot.service 2>/dev/null || true
systemctl restart zivpn-web.service 2>/dev/null || true

# ===== Completion message =====
echo -e "\n$LINE\n${G}✅ ZIVPN Enterprise Upgrade Completed! ${Z}\n$LINE"
echo -e "${M}🎯 New Features Available:${Z}"
echo -e "  • Real-time connection monitoring"
echo -e "  • Live user tracking" 
echo -e "  • Enhanced Telegram bot commands"
echo -e "  • Connection history logging"
echo -e "  • Bandwidth usage tracking"
echo -e "\n${Y}📋 Usage:${Z}"
echo -e "  /online - Show online users"
echo -e "  /userinfo <username> - User details"
echo -e "  /estats - Enhanced statistics"
echo -e "$LINE"
