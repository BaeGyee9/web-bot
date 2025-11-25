#!/bin/bash
# ZIVPN Enterprise Enhanced Restart Script
# Author: Gemini
set -euo pipefail

# ===== Pretty Colors =====
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

echo -e "\n$LINE"
echo -e "${G}🔄 ZIVPN Enterprise Enhanced Services Restarting...${Z}"
echo -e "$LINE"

# ===== Enhanced Service Restart Function =====
restart_service() {
    SERVICE_NAME=$1
    say "${C}* Restarting ${SERVICE_NAME}...${Z}"

    # Stop the service first
    if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
        sudo systemctl stop "${SERVICE_NAME}"
    fi

    # Start/Restart the service
    if sudo systemctl restart "${SERVICE_NAME}"; then
        sleep 3
        
        if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
            say "${G}  ✅ ${SERVICE_NAME} restarted and running.${Z}"
        else
            say "${R}  ❌ ERROR: ${SERVICE_NAME} failed to start.${Z}"
            sudo journalctl -u "${SERVICE_NAME}" --since "1 minute ago" | tail -n 5
        fi
    else
        say "${R}  ❌ ERROR: Could not restart ${SERVICE_NAME}.${Z}"
    fi
}

# ===== Enhanced Execution Order =====

# 1. Restart core VPN service
restart_service zivpn.service

# 2. Restart enhanced monitoring
restart_service zivpn-monitor.service

# 3. Restart management components
restart_service zivpn-web.service
restart_service zivpn-api.service
restart_service zivpn-bot.service

# 4. Trigger maintenance services
say "${Y}* Running maintenance tasks...${Z}"
sudo systemctl start zivpn-cleanup.service 2>/dev/null || true
sudo systemctl start zivpn-backup.service 2>/dev/null || true

# 5. Enable timers
sudo systemctl enable --now zivpn-backup.timer 2>/dev/null || true
sudo systemctl enable --now zivpn-maintenance.timer 2>/dev/null || true
say "${G}  ✅ Timers enabled.${Z}"

# ===== Final Status Check =====
echo -e "\n${Y}📊 Final Service Status:${Z}"
services=("zivpn.service" "zivpn-web.service" "zivpn-bot.service" "zivpn-monitor.service")
for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        echo -e "  ${G}✅ $service - RUNNING${Z}"
    else
        echo -e "  ${R}❌ $service - STOPPED${Z}"
    fi
done

echo -e "\n$LINE"
echo -e "${G}✨ ZIVPN Enterprise Enhanced Restart Completed!${Z}"
echo -e "$LINE"
