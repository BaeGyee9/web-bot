#!/bin/bash
# ZIVPN Encrypted Services Restart Script
# Author: Gemini
set -euo pipefail

# ===== Pretty Colors =====
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

echo -e "\n$LINE"
echo -e "${G}🔄 ZIVPN Encrypted Services Restarting...${Z}"
echo -e "$LINE"

# Check if master key exists
KEY_FILE="/etc/zivpn/.master_key.dat"
if [ ! -f "$KEY_FILE" ]; then
    echo -e "${R}❌ ERROR: Master key not found!${Z}"
    echo -e "${Y}Please restore master key from your backup.${Z}"
    exit 1
fi

# Verify encrypted files exist
ENCRYPTED_DIR="/etc/zivpn/encrypted"
if [ ! -d "$ENCRYPTED_DIR" ] || [ -z "$(ls -A $ENCRYPTED_DIR 2>/dev/null)" ]; then
    echo -e "${R}❌ ERROR: Encrypted files not found!${Z}"
    echo -e "${Y}Reinstall may be necessary.${Z}"
    exit 1
fi

echo -e "${C}🔍 Checking encrypted files...${Z}"
for enc_file in "$ENCRYPTED_DIR"/*.enc; do
    if [ -f "$enc_file" ]; then
        filename=$(basename "$enc_file")
        echo -e "${G}  ✓ ${filename}${Z}"
    fi
done

# Restart services in order
echo -e "\n${Y}🔄 Restarting services...${Z}"

services=(
    "zivpn.service"
    "zivpn-web.service" 
    "zivpn-bot.service"
    "zivpn-api.service"
    "zivpn-connection.service"
)

for service in "${services[@]}"; do
    echo -e "${C}* Restarting ${service}...${Z}"
    
    # Stop if running
    if systemctl is-active --quiet "$service"; then
        systemctl stop "$service"
        sleep 1
    fi
    
    # Start the service
    if systemctl start "$service"; then
        sleep 2
        if systemctl is-active --quiet "$service"; then
            echo -e "${G}  ✅ ${service} restarted successfully${Z}"
        else
            echo -e "${R}  ❌ ${service} failed to start${Z}"
            echo -e "${Y}  Checking logs:${Z}"
            journalctl -u "$service" --since "1 minute ago" --no-pager | tail -5
        fi
    else
        echo -e "${R}  ❌ Failed to execute restart for ${service}${Z}"
    fi
done

# Enable and restart timers
echo -e "\n${Y}⏰ Restarting timers...${Z}"
timer_services=("zivpn-backup.timer" "zivpn-cleanup.timer")
for timer in "${timer_services[@]}"; do
    systemctl enable --now "$timer" 2>/dev/null && \
    echo -e "${G}  ✅ ${timer} enabled${Z}" || \
    echo -e "${Y}  ⚠️  ${timer} already enabled${Z}"
done

echo -e "\n$LINE"
echo -e "${G}✨ All ZIVPN Encrypted Services restarted successfully!${Z}"
echo -e "$LINE"

# Display status
echo -e "\n${C}📊 Current Service Status:${Z}"
for service in "${services[@]}"; do
    status=$(systemctl is-active "$service")
    if [ "$status" = "active" ]; then
        echo -e "${G}  ✓ ${service}: ACTIVE${Z}"
    else
        echo -e "${R}  ✗ ${service}: INACTIVE${Z}"
    fi
done

echo -e "\n${Y}🔧 Useful Commands:${Z}"
echo -e "  ${C}• View logs:${Z} journalctl -u zivpn-web.service -f"
echo -e "  ${C}• Decrypt code:${Z} zivpn-decrypt"
echo -e "  ${C}• Check master key:${Z} cat /etc/zivpn/.master_key.dat"
