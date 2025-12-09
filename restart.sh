#!/bin/bash
# ZIVPN Enterprise Management Services Restart Script
# Author: Gemini
# ENHANCED VERSION - With source protection check
set -euo pipefail

# ===== Pretty Colors =====
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

echo -e "\n$LINE"
echo -e "${G}🔄 ZIVPN Enterprise Services Restarting...${Z}"
echo -e "${Y}🔒 Source Code Protection: ACTIVE${Z}"
echo -e "$LINE"

# ===== Check Source Protection Status =====
check_protection() {
    echo -e "${C}🔍 Checking source code protection...${Z}"
    
    protected_count=0
    total_count=0
    
    for file in /etc/zivpn/*.py /etc/zivpn/templates/*.html 2>/dev/null; do
        if [ -f "$file" ]; then
            ((total_count++))
            if grep -q "ENCRYPTED SOURCE\|Runtime Decryptor" "$file" 2>/dev/null; then
                ((protected_count++))
                echo -e "  ${G}✓${Z} $(basename "$file") - Protected"
            else
                echo -e "  ${R}✗${Z} $(basename "$file") - Not Protected"
            fi
        fi
    done
    
    if [ $total_count -gt 0 ]; then
        protection_percent=$(( (protected_count * 100) / total_count ))
        echo -e "${C}📊 Protection: ${protection_percent}% (${protected_count}/${total_count} files)${Z}"
        
        if [ $protection_percent -lt 80 ]; then
            echo -e "${Y}⚠️  Warning: Low protection level detected${Z}"
        fi
    fi
}

check_protection

# ===== Function to Restart and Check Status =====
restart_service() {
    SERVICE_NAME=$1
    say "${C}* Restarting ${SERVICE_NAME}...${Z}"

    # Stop the service first
    if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
        sudo systemctl stop "${SERVICE_NAME}"
        sleep 1
    fi

    # Start/Restart the service
    if sudo systemctl restart "${SERVICE_NAME}"; then
        # Wait a moment for the service to actually start up
        sleep 3
        
        if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
            say "${G}  ✅ ${SERVICE_NAME} restarted and running.${Z}"
            
            # Show service status briefly
            echo -e "${Y}  📋 Status:${Z}"
            sudo systemctl status "${SERVICE_NAME}" --no-pager -l | grep -A 3 "Active:" || true
            
        else
            say "${R}  ❌ ERROR: ${SERVICE_NAME} failed to start. Checking logs...${Z}"
            sudo journalctl -u "${SERVICE_NAME}" --since "1 minute ago" --no-pager | tail -n 15
        fi
    else
        say "${R}  ❌ ERROR: Could not execute restart command for ${SERVICE_NAME}.${Z}"
    fi
    
    echo ""
}

# ===== Execution Order =====

echo -e "\n${M}🚀 Starting Services Restart Sequence...${Z}"

# 1. Restart core VPN service
restart_service zivpn.service

# 2. Restart management components
restart_service zivpn-api.service
restart_service zivpn-web.service
restart_service zivpn-bot.service
restart_service zivpn-connection.service

# 3. Trigger and ensure management timers/jobs are running
echo -e "${Y}* Re-enabling and triggering periodic timers...${Z}"
sudo systemctl enable --now zivpn-backup.timer 2>/dev/null || true
sudo systemctl enable --now zivpn-cleanup.timer 2>/dev/null || true
sudo systemctl start zivpn-backup.timer 2>/dev/null || true
sudo systemctl start zivpn-cleanup.timer 2>/dev/null || true
echo -e "${G}  ✅ Timers enabled/checked.${Z}"

# 4. Verify all services are running
echo -e "\n${M}📊 Final Services Status Check:${Z}"
sudo systemctl list-units --type=service --state=running | grep zivpn || true

echo -e "\n$LINE"
echo -e "${G}✨ All ZIVPN Enterprise Services restart sequence completed!${Z}"
echo -e "${C}🔒 Source code protection remains active${Z}"
echo -e "${Y}⚠️  Note: Source files are encrypted and cannot be viewed directly${Z}"
echo -e "$LINE"

# Offer to show protection details
echo -e "\n${C}ℹ️  To check source protection details, run:${Z}"
echo -e "  ${Y}sudo bash /etc/zivpn/verify_protection.sh${Z}"
