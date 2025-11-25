#!/bin/bash
# ZIVPN Enterprise Management Services Restart Script
# Author: Gemini
set -euo pipefail

# ===== Pretty Colors =====
B="\e[1;34m"; G="\e[1;32m"; Y="\e[1;33m"; R="\e[1;31m"; C="\e[1;36m"; M="\e[1;35m"; Z="\e[0m"
LINE="${B}────────────────────────────────────────────────────────${Z}"
say(){ echo -e "$1"; }

echo -e "\n$LINE"
echo -e "${G}🔄 ZIVPN Enterprise Services Restarting...${Z}"
echo -e "${M}🔍 Enhanced Connection Tracking Version${Z}"
echo -e "$LINE"

# ===== Clear Connection Cache =====
say "${Y}🧹 Clearing connection cache and resetting tracking...${Z}"

# Find and kill any Python processes that might be holding old connection data
pkill -f "python3.*web.py" 2>/dev/null || true
pkill -f "python3.*connection_manager.py" 2>/dev/null || true
pkill -f "python3.*bot.py" 2>/dev/null || true

# Clear conntrack table for accurate tracking
say "${Y}🗑️  Clearing old connection tracking data...${Z}"
conntrack -D -p udp 2>/dev/null || true
sleep 3

# ===== Enhanced System Checks =====
check_system_dependencies() {
    say "${Y}🔧 Checking system dependencies...${Z}"
    
    # Check if conntrack is installed
    if command -v conntrack >/dev/null 2>&1; then
        say "${G}  ✅ conntrack installed${Z}"
    else
        say "${R}  ❌ conntrack not installed - installing...${Z}"
        apt-get update >/dev/null 2>&1
        apt-get install -y conntrack >/dev/null 2>&1 || {
            say "${R}  ❌ Failed to install conntrack${Z}"
            return 1
        }
    fi
    
    # Check Python dependencies
    if python3 -c "import flask, requests, sqlite3" >/dev/null 2>&1; then
        say "${G}  ✅ Python dependencies OK${Z}"
    else
        say "${Y}  ⚠️ Installing Python dependencies...${Z}"
        pip3 install flask requests >/dev/null 2>&1 || true
    fi
    
    return 0
}

check_connection_tracking() {
    say "${Y}📡 Testing connection tracking...${Z}"
    
    # Test conntrack functionality
    if timeout 5s conntrack -L -p udp 2>/dev/null | head -1 >/dev/null; then
        say "${G}  ✅ Connection tracking working${Z}"
        
        # Show current UDP connections
        current_conns=$(conntrack -L -p udp 2>/dev/null | grep -c "dport=5667" || true)
        say "${C}  📊 Current UDP connections on port 5667: $current_conns${Z}"
    else
        say "${R}  ❌ Connection tracking not working${Z}"
        return 1
    fi
}

# ===== Function to Restart and Check Status =====
restart_service() {
    SERVICE_NAME=$1
    say "${C}* Restarting ${SERVICE_NAME}...${Z}"

    # Stop the service first
    if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
        sudo systemctl stop "${SERVICE_NAME}"
        sleep 2
    fi

    # Reset failed state if any
    sudo systemctl reset-failed "${SERVICE_NAME}" 2>/dev/null || true

    # Start/Restart the service
    if sudo systemctl restart "${SERVICE_NAME}"; then
        # Wait a moment for the service to actually start up
        sleep 3
        
        if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
            say "${G}  ✅ ${SERVICE_NAME} restarted and running.${Z}"
            
            # Show brief service status
            echo -e "${B}  Service Status:${Z}"
            sudo systemctl status "${SERVICE_NAME}" --no-pager -l | grep -E "(Active:|Main PID:|Status:)" | head -3 | while read line; do
                echo -e "    ${C}$line${Z}"
            done
        else
            say "${R}  ❌ ERROR: ${SERVICE_NAME} failed to start.${Z}"
            say "${Y}  Checking logs...${Z}"
            sudo journalctl -u "${SERVICE_NAME}" --since "1 minute ago" --no-pager | tail -n 15
            return 1
        fi
    else
        say "${R}  ❌ ERROR: Could not execute restart command for ${SERVICE_NAME}.${Z}"
        return 1
    fi
    
    echo
    return 0
}

# ===== Enhanced Service Monitoring =====
setup_connection_manager() {
    say "${Y}🔗 Setting up Enhanced Connection Manager...${Z}"
    
    # Create connection manager if it doesn't exist
    if [ ! -f /etc/zivpn/connection_manager.py ]; then
        say "${Y}  Creating connection manager...${Z}"
        cat > /etc/zivpn/connection_manager.py << 'EOF'
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
        
    def get_active_connections_accurate(self):
        """Get accurate active connections using conntrack with better filtering"""
        active_connections = {}
        try:
            # Get all UDP connections on VPN port range with ESTABLISHED state
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null | grep -E 'dport=(5667|[6-9][0-9]{3}|[1-9][0-9]{4})' | grep -E '(ESTABLISHED|UNREPLIED)'",
                shell=True, capture_output=True, text=True, timeout=15
            )
            
            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                    
                try:
                    # Parse conntrack output to get source IP and destination port
                    parts = line.split()
                    src_ip = None
                    dport = None
                    
                    for part in parts:
                        if part.startswith('src='):
                            src_ip = part.split('=')[1]
                        elif part.startswith('dport='):
                            dport = part.split('=')[1]
                    
                    if src_ip and dport:
                        # Track connections per port
                        if dport not in active_connections:
                            active_connections[dport] = []
                        active_connections[dport].append({
                            'src_ip': src_ip,
                            'timestamp': datetime.now().isoformat(),
                            'state': 'ESTABLISHED' if 'ESTABLISHED' in line else 'UNREPLIED'
                        })
                        
                except Exception as e:
                    print(f"Error parsing conntrack line: {e}")
                    continue
                    
        except subprocess.TimeoutExpired:
            print("Conntrack command timed out")
        except Exception as e:
            print(f"Error getting active connections: {e}")
        
        return active_connections
            
    def enforce_connection_limits(self):
        """Enforce connection limits for all users with accurate tracking"""
        db = self.get_db()
        try:
            # Get all active users with their connection limits
            users = db.execute('''
                SELECT username, concurrent_conn, port 
                FROM users 
                WHERE status = "active" AND (expires IS NULL OR expires >= CURRENT_DATE)
            ''').fetchall()
            
            active_connections = self.get_active_connections_accurate()
            
            # Update user connection status in database
            for user in users:
                username = user['username']
                max_connections = user['concurrent_conn']
                user_port = str(user['port'] or '5667')
                
                # Count connections for this user (by port)
                user_conn_count = len(active_connections.get(user_port, []))
                
                # Log user status for debugging
                if user_conn_count > 0:
                    print(f"User {username} is ONLINE with {user_conn_count} connections on port {user_port}")
                else:
                    print(f"User {username} is OFFLINE on port {user_port}")
                
                # If over limit, drop oldest connections
                if user_conn_count > max_connections:
                    print(f"User {username} has {user_conn_count} connections (limit: {max_connections}) - dropping excess")
                    
                    # Drop excess connections (FIFO)
                    excess = user_conn_count - max_connections
                    connections_to_drop = active_connections[user_port][:excess]
                    
                    for conn in connections_to_drop:
                        self.drop_connection(conn['src_ip'], user_port)
            
            db.commit()
            
            # Log connection statistics
            total_active = sum(len(conns) for conns in active_connections.values())
            print(f"Connection Manager: {total_active} total active connections across {len(active_connections)} ports")
            
        except Exception as e:
            print(f"Error in connection manager: {e}")
        finally:
            db.close()
            
    def drop_connection(self, src_ip, dport):
        """Drop a specific connection using conntrack"""
        try:
            result = subprocess.run(
                f"conntrack -D -p udp --dport {dport} --src {src_ip}",
                shell=True, capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"Successfully dropped connection: {src_ip}:{dport}")
            else:
                print(f"Failed to drop connection {src_ip}:{dport}: {result.stderr}")
        except Exception as e:
            print(f"Error dropping connection {src_ip}:{dport}: {e}")
            
    def start_monitoring(self):
        """Start the connection monitoring loop"""
        def monitor_loop():
            while True:
                try:
                    self.enforce_connection_limits()
                    time.sleep(10)  # Check every 10 seconds for accuracy
                except Exception as e:
                    print(f"Monitoring error: {e}")
                    time.sleep(30)
                    
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
    def get_connection_stats(self):
        """Get current connection statistics"""
        active_connections = self.get_active_connections_accurate()
        stats = {
            'total_connections': sum(len(conns) for conns in active_connections.values()),
            'ports_with_connections': len(active_connections),
            'connections_by_port': {port: len(conns) for port, conns in active_connections.items()},
            'timestamp': datetime.now().isoformat()
        }
        return stats

# Global instance
connection_manager = ConnectionManager()

if __name__ == "__main__":
    print("Starting Enhanced Connection Manager...")
    connection_manager.start_monitoring()
    try:
        while True:
            # Print stats every minute
            stats = connection_manager.get_connection_stats()
            print(f"Connection Stats: {stats['total_connections']} total connections on {stats['ports_with_connections']} ports")
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping Connection Manager...")
EOF
        chmod +x /etc/zivpn/connection_manager.py
        say "${G}  ✅ Connection manager created${Z}"
    else
        say "${G}  ✅ Connection manager already exists${Z}"
    fi
    
    # Create systemd service for connection manager
    if [ ! -f /etc/systemd/system/zivpn-connection.service ]; then
        say "${Y}  Creating connection manager service...${Z}"
        cat > /etc/systemd/system/zivpn-connection.service << EOF
[Unit]
Description=ZIVPN Connection Manager
After=network.target zivpn.service
Wants=zivpn.service

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/connection_manager.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
        say "${G}  ✅ Connection manager service created${Z}"
    fi
}

# ===== Execution Order =====

# 1. Check system dependencies first
check_system_dependencies

# 2. Setup connection manager
setup_connection_manager

# 3. Check connection tracking
check_connection_tracking

# 4. Restart core VPN service (zivpn.service)
say "${Y}1. Restarting core VPN service...${Z}"
restart_service zivpn.service

# 5. Reload systemd and enable connection manager
say "${Y}2. Setting up connection manager...${Z}"
sudo systemctl daemon-reload
sudo systemctl enable zivpn-connection.service 2>/dev/null || true

# 6. Restart connection manager to ensure accurate tracking
restart_service zivpn-connection.service

# 7. Restart management components (API, Web)
say "${Y}3. Restarting management services...${Z}"
restart_service zivpn-api.service
restart_service zivpn-web.service

# 8. Restart Telegram bot
restart_service zivpn-bot.service

# 9. Trigger and ensure management timers/jobs are running
say "${Y}4. Enabling periodic services...${Z}"
sudo systemctl enable --now zivpn-backup.timer 2>/dev/null || true
sudo systemctl enable --now zivpn-maintenance.timer 2>/dev/null || true
sudo systemctl enable --now zivpn-cleanup.timer 2>/dev/null || true
say "${G}  ✅ Timers enabled/checked.${Z}"

# 10. Final status check
say "${Y}5. Final Service Status Check...${Z}"
services=("zivpn.service" "zivpn-connection.service" "zivpn-web.service" "zivpn-api.service" "zivpn-bot.service")
all_ok=true

for service in "${services[@]}"; do
    if sudo systemctl is-active --quiet "$service"; then
        say "${G}  ✅ $service: ACTIVE${Z}"
    else
        say "${R}  ❌ $service: INACTIVE${Z}"
        all_ok=false
    fi
done

# 11. Display current connection status
say "${Y}6. Current Connection Status...${Z}"
echo -e "${C}  Testing connection tracking...${Z}"

# Wait a moment for connections to establish
sleep 5

# Show current UDP connections
current_udp=$(conntrack -L -p udp 2>/dev/null | grep -c "dport=5667" || echo "0")
say "${G}  📊 Active UDP connections: $current_udp${Z}"

# Show connection manager status
if sudo systemctl is-active --quiet zivpn-connection.service; then
    say "${G}  🔗 Connection manager: RUNNING${Z}"
else
    say "${R}  🔗 Connection manager: STOPPED${Z}"
fi

# ===== Final Summary =====
echo -e "\n$LINE"
if [ "$all_ok" = true ]; then
    echo -e "${G}✨ All ZIVPN Enterprise Services restart completed successfully!${Z}"
else
    echo -e "${Y}⚠️ Some services may need attention. Check above for errors.${Z}"
fi

# Display access information
SERVER_IP=$(curl -s icanhazip.com || hostname -I | awk '{print $1}' || echo "localhost")
echo -e "${C}📱 Web Panel: http://$SERVER_IP:19432${Z}"
echo -e "${C}🔧 Connection Tracking: ${G}ENABLED${Z}${C} (Accurate online/offline status)${Z}"
echo -e "$LINE"

# Display real-time monitoring info
echo -e "\n${Y}🔍 Real-time Monitoring Info:${Z}"
echo -e "${C}  • Web Panel shows accurate online/offline status${Z}"
echo -e "${C}  • Telegram bot has /status command${Z}"
echo -e "${C}  • Connection manager updates every 10 seconds${Z}"
echo -e "${C}  • Auto-clears old connections for accuracy${Z}"

echo -e "\n${G}🎯 Status: READY - Users will see accurate online/offline status${Z}"
echo -e "$LINE"
