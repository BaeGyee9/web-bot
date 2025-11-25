#!/bin/bash
# ZIVPN Enterprise - Fixed Installation Script
# Fixes "Text file busy" error

set -euo pipefail

# ===== Pretty Colors =====
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

echo -e "\n$LINE\n${G}🚀 ZIVPN Enterprise - Fixed Installation ${Z}\n${M}🧑‍💻 No More 'Text File Busy' Error! ${Z}\n$LINE"

# ===== Root check =====
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${R}❌ Root privileges required. Run: sudo -i ${Z}"; exit 1
fi

# ===== KILL EXISTING ZIVPN PROCESSES =====
echo -e "\n${Y}🛑 Stopping existing ZIVPN processes...${Z}"

# Stop services
systemctl stop zivpn.service 2>/dev/null || echo -e "${C}No zivpn.service found${Z}"
systemctl stop zivpn-web.service 2>/dev/null || echo -e "${C}No zivpn-web.service found${Z}"
systemctl stop zivpn-bot.service 2>/dev/null || echo -e "${C}No zivpn-bot.service found${Z}"
systemctl stop zivpn-monitor.service 2>/dev/null || echo -e "${C}No zivpn-monitor.service found${Z}"

# Kill processes
pkill -f "zivpn server" 2>/dev/null || echo -e "${C}No zivpn processes found${Z}"
pkill -f "/usr/local/bin/zivpn" 2>/dev/null || echo -e "${C}No zivpn binary processes found${Z}"

# Wait for processes to stop
sleep 3

# Force remove if still busy
rm -f /usr/local/bin/zivpn 2>/dev/null || echo -e "${C}Could not remove zivpn (might be busy)${Z}"

# Force kill with SIGKILL
pkill -9 -f zivpn 2>/dev/null || true

# Final cleanup
sync
rm -f /usr/local/bin/zivpn 2>/dev/null || true

echo -e "${G}✅ Cleanup completed${Z}"

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

# Download to temporary location first
TMP_BIN=$(mktemp)
if curl -fSL -o "$TMP_BIN" "$ZIVPN_URL"; then
    # Move to final location
    mv "$TMP_BIN" /usr/local/bin/zivpn
    chmod +x /usr/local/bin/zivpn
    echo -e "${G}✅ ZIVPN binary downloaded successfully${Z}"
else
    echo -e "${R}❌ Failed to download ZIVPN binary${Z}"
    exit 1
fi

# ===== Continue with the rest of installation... =====
# (The rest of your existing install.sh script continues here)
# Create directories, setup database, download components, etc.

echo -e "\n${Y}🗃️ Setting up enhanced database...${Z}"
mkdir -p /etc/zivpn /var/log/zivpn

# ... [Rest of your existing install.sh content] ...

echo -e "\n$LINE\n${G}✅ ZIVPN Enterprise Installation Completed! ${Z}\n$LINE"
