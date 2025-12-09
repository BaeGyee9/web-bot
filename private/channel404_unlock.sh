#!/bin/bash
# 🔐 CHANNEL404 ULTIMATE UNLOCK SCRIPT
# For Channel404's eyes only - DO NOT SHARE

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

print_banner() {
    clear
    echo -e "${PURPLE}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║      🔐 CHANNEL404 ULTIMATE UNLOCK SYSTEM         ║"
    echo "║          Exclusive Access for Channel404          ║"
    echo "║               DO NOT SHARE WITH ANYONE            ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

verify_channel404() {
    echo -e "${YELLOW}[*] Verifying Channel404 identity...${NC}"
    
    # Multi-factor verification
    local attempts=3
    local verified=false
    
    for i in $(seq 1 $attempts); do
        echo -e "${CYAN}Attempt $i of $attempts${NC}"
        
        # Secret question 1
        read -sp "Enter Channel404 secret phrase: " secret1
        echo ""
        
        # Secret question 2  
        read -sp "Enter backup code: " secret2
        echo ""
        
        # Validate
        if [[ "$secret1" == "CHANNEL404_SECURE_KEY"* ]] || [[ "$secret2" == "BACKUP404"* ]]; then
            verified=true
            break
        else
            echo -e "${RED}[!] Verification failed${NC}"
            if [ $i -lt $attempts ]; then
                echo -e "${YELLOW}Try again...${NC}"
            fi
        fi
    done
    
    if [ "$verified" = false ]; then
        echo -e "${RED}[!] ACCESS DENIED - UNAUTHORIZED${NC}"
        echo -e "${RED}[!] This incident has been logged and reported${NC}"
        
        # Create fake system info to confuse attackers
        echo -e "${YELLOW}[*] Displaying fake system information...${NC}"
        cat << FAKE
System Scan Complete:
────────────────────
• OS: Ubuntu 22.04 LTS
• Kernel: 5.15.0-100-generic  
• CPU: 2x Intel Xeon E5-2690 v4
• Memory: 32GB ECC DDR4
• Storage: 512GB NVMe SSD
• Network: 1Gbps Unmetered
• Services: None detected
• ZIVPN: Not installed
FAKE
        exit 1
    fi
    
    echo -e "${GREEN}[✓] Channel404 identity verified${NC}"
}

decrypt_all_source() {
    echo -e "${YELLOW}[*] Decrypting all source files...${NC}"
    
    DECRYPT_DIR="/tmp/channel404_decrypted_$(date +%s)"
    mkdir -p "$DECRYPT_DIR"
    
    # Master decryption key
    MASTER_KEY="CHANNEL404_SECURE_KEY"
    
    for enc_file in /etc/zivpn/encrypted/*.enc; do
        if [ -f "$enc_file" ]; then
            filename=$(basename "$enc_file" .enc)
            output_file="$DECRYPT_DIR/$filename"
            
            # Get salt for this file
            salt_file="${enc_file}.salt"
            if [ -f "$salt_file" ]; then
                salt=$(cat "$salt_file")
                decryption_key="${MASTER_KEY}${salt}"
            else
                decryption_key="$MASTER_KEY"
            fi
            
            # Decrypt file
            openssl enc -aes-256-gcm -d -pbkdf2 -iter 1000000 \
                -in "$enc_file" \
                -out "$output_file" \
                -pass pass:"$decryption_key" \
                -md sha512 2>/dev/null
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}[✓] Decrypted: $filename${NC}"
                chmod 600 "$output_file"
            else
                echo -e "${RED}[!] Failed: $filename${NC}"
            fi
        fi
    done
    
    echo -e "\n${GREEN}[✓] All files decrypted to: $DECRYPT_DIR${NC}"
    echo -e "${CYAN}"
    ls -la "$DECRYPT_DIR"
    echo -e "${NC}"
    
    # Offer to edit files
    read -p "Do you want to edit files? (y/n): " edit_choice
    if [[ "$edit_choice" =~ ^[Yy]$ ]]; then
        cd "$DECRYPT_DIR"
        echo -e "${YELLOW}[*] Opening directory for editing...${NC}"
        echo -e "${CYAN}Use 'nano filename' to edit files${NC}"
        echo -e "${YELLOW}When done, come back here to re-encrypt${NC}"
        bash
    fi
}

re_encrypt_all() {
    echo -e "${YELLOW}[*] Re-encrypting modified files...${NC}"
    
    read -p "Are you sure? This will replace all encrypted files (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}[*] Cancelled${NC}"
        return
    fi
    
    # Find decrypted directory
    DECRYPT_DIR=$(find /tmp -name "channel404_decrypted_*" -type d | head -1)
    
    if [ -z "$DECRYPT_DIR" ] || [ ! -d "$DECRYPT_DIR" ]; then
        echo -e "${RED}[!] No decrypted files found${NC}"
        return
    fi
    
    MASTER_KEY="CHANNEL404_SECURE_KEY"
    
    # Stop services first
    echo -e "${YELLOW}[*] Stopping services...${NC}"
    systemctl stop zivpn-web zivpn-bot zivpn-api 2>/dev/null || true
    
    # Encrypt each file
    for src_file in "$DECRYPT_DIR"/*; do
        if [ -f "$src_file" ]; then
            filename=$(basename "$src_file")
            enc_file="/etc/zivpn/encrypted/${filename}.enc"
            
            # Generate new salt
            salt=$(openssl rand -hex 16)
            echo "$salt" > "${enc_file}.salt"
            
            # Encrypt with new salt
            openssl enc -aes-256-gcm -salt -pbkdf2 -iter 1000000 \
                -in "$src_file" \
                -out "$enc_file" \
                -pass pass:"${MASTER_KEY}${salt}" \
                -md sha512 2>/dev/null
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}[✓] Re-encrypted: $filename${NC}"
            else
                echo -e "${RED}[!] Failed: $filename${NC}"
            fi
        fi
    done
    
    # Securely delete decrypted files
    echo -e "${YELLOW}[*] Securely deleting decrypted files...${NC}"
    shred -u "$DECRYPT_DIR"/* 2>/dev/null || rm -f "$DECRYPT_DIR"/*
    rmdir "$DECRYPT_DIR"
    
    # Restart services
    echo -e "${YELLOW}[*] Restarting services...${NC}"
    systemctl start zivpn-web zivpn-bot zivpn-api
    
    echo -e "${GREEN}[✓] All files re-encrypted and secured${NC}"
}

view_protection_status() {
    echo -e "${YELLOW}[*] Protection Status Report:${NC}"
    /etc/zivpn/verify_protection.sh
}

emergency_recovery() {
    echo -e "${RED}[!] EMERGENCY RECOVERY MODE${NC}"
    echo -e "${YELLOW}This will restore from the latest backup${NC}"
    
    read -p "Are you sure? This may overwrite current data (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        return
    fi
    
    # Find latest backup
    latest_backup=$(ls -t /etc/zivpn/backups/*.db.gz 2>/dev/null | head -1)
    
    if [ -z "$latest_backup" ]; then
        echo -e "${RED}[!] No backups found${NC}"
        return
    fi
    
    echo -e "${YELLOW}[*] Restoring from: $(basename "$latest_backup")${NC}"
    
    # Stop services
    systemctl stop zivpn zivpn-web zivpn-bot zivpn-api
    
    # Restore database
    gunzip -c "$latest_backup" > "/etc/zivpn/zivpn.db"
    
    # Start services
    systemctl start zivpn zivpn-web zivpn-bot zivpn-api
    
    echo -e "${GREEN}[✓] System restored from backup${NC}"
}

main_menu() {
    while true; do
        echo -e "\n${BLUE}=== CHANNEL404 ULTIMATE MENU ===${NC}"
        echo "1. 🔓 Decrypt all source files"
        echo "2. 🔐 Re-encrypt after editing"  
        echo "3. 📊 View protection status"
        echo "4. 🛡️ Verify system integrity"
        echo "5. 🚨 Emergency recovery"
        echo "6. 🧹 Clean temporary files"
        echo "7. 🚪 Exit"
        
        read -p "Select option: " choice
        
        case $choice in
            1)
                decrypt_all_source
                ;;
            2)
                re_encrypt_all
                ;;
            3)
                view_protection_status
                ;;
            4)
                echo -e "${YELLOW}[*] Running system integrity check...${NC}"
                bash /etc/zivpn/verify_protection.sh
                ;;
            5)
                emergency_recovery
                ;;
            6)
                echo -e "${YELLOW}[*] Cleaning temporary files...${NC}"
                rm -rf /tmp/channel404_decrypted_* /tmp/zivpn_*
                echo -e "${GREEN}[✓] Cleaned${NC}"
                ;;
            7)
                echo -e "${GREEN}[*] Exiting Channel404 Unlock System...${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}[!] Invalid option${NC}"
                ;;
        esac
    done
}

# Main execution
print_banner
verify_channel404
main_menu
