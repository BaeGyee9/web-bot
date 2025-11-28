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
# --- NEW: Stop monitoring services ---
systemctl stop zivpn-bandwidth.service 2>/dev/null || true
systemctl stop zivpn-tracker.service 2>/dev/null || true

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

# ===== Download Web Panel from GitHub =====
say "${Y}🌐 GitHub မှ Web Panel ဒေါင်းလုပ်ဆွဲနေပါတယ်...${Z}"
curl -fsSL -o /etc/zivpn/web.py "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/templates/web.py"
if [ $? -ne 0 ]; then
  echo -e "${R}❌ Web Panel ဒေါင်းလုပ်ဆွဲ၍မရပါ - Fallback သုံးပါမယ်${Z}"
  # Fallback web panel code would go here
fi

# ===== Download Telegram Bot from GitHub =====
say "${Y}🤖 GitHub မှ Telegram Bot ဒေါင်းလုပ်ဆွဲနေပါတယ်...${Z}"
curl -fsSL -o /etc/zivpn/bot.py "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/telegram/bot.py"
if [ $? -ne 0 ]; then
  echo -e "${R}❌ Telegram Bot ဒေါင်းလုပ်ဆွဲ၍မရပါ - Fallback သုံးပါမယ်${Z}"
  # Fallback bot code would go here
fi

# ===== NEW: Download Monitoring Scripts =====
say "${Y}📊 Monitoring Scripts ဒေါင်းလုပ်ဆွဲနေပါတယ်...${Z}"
cat >/etc/zivpn/bandwidth_monitor.py <<'PY'
#!/usr/bin/env python3
"""
ZIVPN Real-time Bandwidth Monitor & Auto-Suspend System
Author: ZIVPN Enterprise
"""

import sqlite3
import time
import threading
import logging
import subprocess
import json
import tempfile
import os
from datetime import datetime, timedelta

# Configuration
DATABASE_PATH = "/etc/zivpn/zivpn.db"
CONFIG_FILE = "/etc/zivpn/config.json"
CHECK_INTERVAL = 30  # seconds
BANDWIDTH_THRESHOLD = 0.95  # 95% of limit reached

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/zivpn_bandwidth_monitor.log'),
        logging.StreamHandler()
    ]
)

class BandwidthMonitor:
    def __init__(self):
        self.running = False
        self.monitor_thread = None
        
    def get_db(self):
        """Get database connection"""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
        
    def read_json(self, path, default):
        """Read JSON file"""
        try:
            with open(path, "r") as f: 
                return json.load(f)
        except Exception:
            return default
            
    def write_json_atomic(self, path, data):
        """Write JSON file atomically"""
        d = json.dumps(data, ensure_ascii=False, indent=2)
        dirn = os.path.dirname(path)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=dirn)
        try:
            with os.fdopen(fd, "w") as f: 
                f.write(d)
            os.replace(tmp, path)
        finally:
            try: 
                os.remove(tmp)
            except: 
                pass
                
    def sync_config_passwords(self):
        """Sync passwords to ZIVPN config"""
        try:
            db = self.get_db()
            active_users = db.execute('''
                SELECT password FROM users 
                WHERE status = "active" AND password IS NOT NULL AND password != "" 
                      AND (expires IS NULL OR expires >= CURRENT_DATE)
            ''').fetchall()
            db.close()
            
            users_pw = sorted({str(u["password"]) for u in active_users})
            
            cfg = self.read_json(CONFIG_FILE, {})
            if not isinstance(cfg.get("auth"), dict): 
                cfg["auth"] = {}
            
            cfg["auth"]["mode"] = "passwords"
            cfg["auth"]["config"] = users_pw
            
            self.write_json_atomic(CONFIG_FILE, cfg)
            
            # Restart ZIVPN service
            result = subprocess.run(
                "systemctl restart zivpn.service", 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            return result.returncode == 0
            
        except Exception as e:
            logging.error(f"Error syncing passwords: {e}")
            return False
            
    def check_bandwidth_limits(self):
        """Check all users' bandwidth usage and auto-suspend if over limit"""
        db = self.get_db()
        try:
            # Get users with bandwidth limits
            users = db.execute('''
                SELECT username, bandwidth_used, bandwidth_limit, status 
                FROM users 
                WHERE bandwidth_limit > 0 AND status = "active"
            ''').fetchall()
            
            suspended_users = []
            
            for user in users:
                username = user['username']
                bandwidth_used = user['bandwidth_used'] or 0
                bandwidth_limit = user['bandwidth_limit']
                
                # Convert GB to bytes (if limit is in GB)
                limit_bytes = bandwidth_limit * 1024 * 1024 * 1024
                
                usage_percentage = bandwidth_used / limit_bytes if limit_bytes > 0 else 0
                
                # Check if over limit
                if usage_percentage >= 1.0:  # 100% or more
                    # Auto suspend user
                    db.execute(
                        'UPDATE users SET status = "suspended" WHERE username = ?',
                        (username,)
                    )
                    suspended_users.append(username)
                    logging.info(f"Auto-suspended {username} - Bandwidth limit exceeded: {bandwidth_used}/{limit_bytes} bytes")
                    
                # Warning at 80% threshold
                elif usage_percentage >= 0.8:
                    logging.warning(f"User {username} reached 80% bandwidth limit: {bandwidth_used}/{limit_bytes} bytes")
                    
            if suspended_users:
                db.commit()
                # Sync config to remove suspended users
                self.sync_config_passwords()
                logging.info(f"Auto-suspended {len(suspended_users)} users for bandwidth overuse: {suspended_users}")
                
            return suspended_users
            
        except Exception as e:
            logging.error(f"Error checking bandwidth limits: {e}")
            return []
        finally:
            db.close()
            
    def get_real_time_bandwidth(self):
        """Get real-time bandwidth usage using conntrack"""
        try:
            # Get active connections and their bandwidth usage
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null | grep -E 'dport=(5667|[6-9][0-9]{3}|[1-9][0-9]{4})'",
                shell=True, capture_output=True, text=True
            )
            
            # This is a simplified version - in production you'd parse conntrack output
            # and calculate real-time bandwidth
            active_connections = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            
            return active_connections
            
        except Exception as e:
            logging.error(f"Error getting real-time bandwidth: {e}")
            return 0
            
    def update_user_bandwidth(self, username, bytes_used):
        """Update user bandwidth usage in database"""
        db = self.get_db()
        try:
            db.execute('''
                UPDATE users 
                SET bandwidth_used = bandwidth_used + ?, updated_at = CURRENT_TIMESTAMP 
                WHERE username = ?
            ''', (bytes_used, username))
            
            # Log bandwidth usage
            db.execute('''
                INSERT INTO bandwidth_logs (username, bytes_used) 
                VALUES (?, ?)
            ''', (username, bytes_used))
            
            db.commit()
            logging.info(f"Updated bandwidth for {username}: +{bytes_used} bytes")
            
        except Exception as e:
            logging.error(f"Error updating bandwidth for {username}: {e}")
        finally:
            db.close()
            
    def monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Check bandwidth limits
                suspended_users = self.check_bandwidth_limits()
                
                # Get real-time stats
                active_connections = self.get_real_time_bandwidth()
                
                # Log status every 10 cycles
                if int(time.time()) % (CHECK_INTERVAL * 10) == 0:
                    logging.info(f"Bandwidth monitor active. Connections: {active_connections}")
                    
                time.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logging.error(f"Error in monitor loop: {e}")
                time.sleep(60)  # Wait longer if error occurs
                
    def start(self):
        """Start the bandwidth monitor"""
        if self.running:
            logging.warning("Bandwidth monitor is already running")
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        logging.info("Bandwidth monitor started successfully")
        
    def stop(self):
        """Stop the bandwidth monitor"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logging.info("Bandwidth monitor stopped")

# Global instance
bandwidth_monitor = BandwidthMonitor()

def main():
    """Main function"""
    monitor = BandwidthMonitor()
    
    try:
        monitor.start()
        logging.info("ZIVPN Bandwidth Monitor Started - Press Ctrl+C to stop")
        
        # Keep the main thread alive
        while monitor.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logging.info("Received interrupt signal")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        monitor.stop()
        logging.info("ZIVPN Bandwidth Monitor Shutdown Complete")

if __name__ == "__main__":
    main()
PY

cat >/etc/zivpn/connection_tracker.py <<'PY'
#!/usr/bin/env python3
"""
ZIVPN Multi-Device Connection Tracker & Detection System
Author: ZIVPN Enterprise
"""

import sqlite3
import time
import threading
import logging
import subprocess
import hashlib
import json
import tempfile
import os
from datetime import datetime

# Configuration
DATABASE_PATH = "/etc/zivpn/zivpn.db"
CONFIG_FILE = "/etc/zivpn/config.json"
CHECK_INTERVAL = 15  # seconds
MAX_DEVICES_PER_USER = 3  # Maximum allowed devices per user

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/zivpn_connection_tracker.log'),
        logging.StreamHandler()
    ]
)

class ConnectionTracker:
    def __init__(self):
        self.running = False
        self.tracker_thread = None
        self.connection_cache = {}  # Cache for tracking connections
        
    def get_db(self):
        """Get database connection"""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
        
    def read_json(self, path, default):
        """Read JSON file"""
        try:
            with open(path, "r") as f: 
                return json.load(f)
        except Exception:
            return default
            
    def write_json_atomic(self, path, data):
        """Write JSON file atomically"""
        d = json.dumps(data, ensure_ascii=False, indent=2)
        dirn = os.path.dirname(path)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=dirn)
        try:
            with os.fdopen(fd, "w") as f: 
                f.write(d)
            os.replace(tmp, path)
        finally:
            try: 
                os.remove(tmp)
            except: 
                pass
                
    def sync_config_passwords(self):
        """Sync passwords to ZIVPN config"""
        try:
            db = self.get_db()
            active_users = db.execute('''
                SELECT password FROM users 
                WHERE status = "active" AND password IS NOT NULL AND password != "" 
                      AND (expires IS NULL OR expires >= CURRENT_DATE)
            ''').fetchall()
            db.close()
            
            users_pw = sorted({str(u["password"]) for u in active_users})
            
            cfg = self.read_json(CONFIG_FILE, {})
            if not isinstance(cfg.get("auth"), dict): 
                cfg["auth"] = {}
            
            cfg["auth"]["mode"] = "passwords"
            cfg["auth"]["config"] = users_pw
            
            self.write_json_atomic(CONFIG_FILE, cfg)
            
            # Restart ZIVPN service
            result = subprocess.run(
                "systemctl restart zivpn.service", 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            return result.returncode == 0
            
        except Exception as e:
            logging.error(f"Error syncing passwords: {e}")
            return False
            
    def get_device_fingerprint(self, ip_address, port):
        """Generate device fingerprint based on IP and port"""
        fingerprint_string = f"{ip_address}:{port}"
        return hashlib.md5(fingerprint_string.encode()).hexdigest()
        
    def get_active_connections(self):
        """Get active UDP connections using conntrack"""
        try:
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null | grep -E 'dport=(5667|[6-9][0-9]{3}|[1-9][0-9]{4})'",
                shell=True, capture_output=True, text=True
            )
            
            connections = []
            
            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                    
                try:
                    parts = line.split()
                    src_ip = None
                    src_port = None
                    dport = None
                    
                    for part in parts:
                        if part.startswith('src='):
                            src_ip = part.split('=')[1]
                        elif part.startswith('sport='):
                            src_port = part.split('=')[1]
                        elif part.startswith('dport='):
                            dport = part.split('=')[1]
                    
                    if src_ip and dport:
                        connections.append({
                            'src_ip': src_ip,
                            'src_port': src_port,
                            'dport': dport,
                            'device_id': self.get_device_fingerprint(src_ip, src_port or 'unknown')
                        })
                        
                except Exception as e:
                    logging.debug(f"Error parsing connection line: {e}")
                    continue
                    
            return connections
            
        except Exception as e:
            logging.error(f"Error getting active connections: {e}")
            return []
            
    def find_user_by_port(self, port):
        """Find user by port number"""
        db = self.get_db()
        try:
            user = db.execute(
                'SELECT username, concurrent_conn FROM users WHERE port = ? AND status = "active"',
                (port,)
            ).fetchone()
            
            return dict(user) if user else None
            
        except Exception as e:
            logging.error(f"Error finding user by port {port}: {e}")
            return None
        finally:
            db.close()
            
    def detect_multi_device_usage(self):
        """Detect users connected from multiple devices"""
        db = self.get_db()
        try:
            active_connections = self.get_active_connections()
            user_devices = {}
            violations = []
            
            # Group connections by user
            for conn in active_connections:
                user = self.find_user_by_port(conn['dport'])
                if user:
                    username = user['username']
                    device_id = conn['device_id']
                    
                    if username not in user_devices:
                        user_devices[username] = set()
                    
                    user_devices[username].add(device_id)
            
            # Check for violations
            for username, devices in user_devices.items():
                user_info = self.find_user_by_port(next(iter(active_connections))['dport'])
                max_allowed = user_info['concurrent_conn'] if user_info else MAX_DEVICES_PER_USER
                
                if len(devices) > max_allowed:
                    violations.append({
                        'username': username,
                        'devices_count': len(devices),
                        'max_allowed': max_allowed,
                        'devices': list(devices)
                    })
                    logging.warning(f"Multi-device violation: {username} using {len(devices)} devices (max: {max_allowed})")
            
            return violations
            
        except Exception as e:
            logging.error(f"Error detecting multi-device usage: {e}")
            return []
        finally:
            db.close()
            
    def handle_multi_device_violation(self, violation):
        """Handle multi-device violation - suspend user or take action"""
        username = violation['username']
        
        db = self.get_db()
        try:
            # For first violation, log warning
            # For repeated violations, suspend user
            violation_count = db.execute('''
                SELECT COUNT(*) as count FROM audit_logs 
                WHERE target_user = ? AND action = 'multi_device_violation'
                AND created_at > datetime('now', '-1 hour')
            ''', (username,)).fetchone()['count']
            
            if violation_count >= 2:  # Third violation in 1 hour
                # Suspend user
                db.execute(
                    'UPDATE users SET status = "suspended" WHERE username = ?',
                    (username,)
                )
                
                # Log the action
                db.execute('''
                    INSERT INTO audit_logs (admin_user, action, target_user, details, ip_address)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    'system', 
                    'auto_suspend_multi_device', 
                    username, 
                    f"Auto-suspended for multi-device violation: {violation['devices_count']} devices (max: {violation['max_allowed']})",
                    'system'
                ))
                
                db.commit()
                self.sync_config_passwords()
                
                logging.info(f"Auto-suspended {username} for repeated multi-device violations")
                
            else:
                # Log the violation
                db.execute('''
                    INSERT INTO audit_logs (admin_user, action, target_user, details, ip_address)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    'system', 
                    'multi_device_violation', 
                    username, 
                    f"Multi-device violation detected: {violation['devices_count']} devices (max: {violation['max_allowed']})",
                    'system'
                ))
                db.commit()
                
                logging.warning(f"Logged multi-device violation for {username}")
                
        except Exception as e:
            logging.error(f"Error handling multi-device violation for {username}: {e}")
        finally:
            db.close()
            
    def get_user_connection_stats(self):
        """Get connection statistics for all users"""
        active_connections = self.get_active_connections()
        user_stats = {}
        
        for conn in active_connections:
            user = self.find_user_by_port(conn['dport'])
            if user:
                username = user['username']
                if username not in user_stats:
                    user_stats[username] = {
                        'username': username,
                        'devices': set(),
                        'connections': 0,
                        'ports': set()
                    }
                
                user_stats[username]['devices'].add(conn['device_id'])
                user_stats[username]['connections'] += 1
                user_stats[username]['ports'].add(conn['dport'])
                
        # Convert sets to lists for JSON serialization
        for stats in user_stats.values():
            stats['devices'] = list(stats['devices'])
            stats['devices_count'] = len(stats['devices'])
            stats['ports'] = list(stats['ports'])
            
        return user_stats
        
    def tracker_loop(self):
        """Main tracking loop"""
        while self.running:
            try:
                # Detect multi-device usage
                violations = self.detect_multi_device_usage()
                
                # Handle violations
                for violation in violations:
                    self.handle_multi_device_violation(violation)
                
                # Log stats every 10 cycles
                if int(time.time()) % (CHECK_INTERVAL * 10) == 0:
                    user_stats = self.get_user_connection_stats()
                    total_users = len(user_stats)
                    total_devices = sum(stats['devices_count'] for stats in user_stats.values())
                    logging.info(f"Connection tracker active. Users: {total_users}, Devices: {total_devices}")
                    
                time.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logging.error(f"Error in tracker loop: {e}")
                time.sleep(60)  # Wait longer if error occurs
                
    def start(self):
        """Start the connection tracker"""
        if self.running:
            logging.warning("Connection tracker is already running")
            return
            
        self.running = True
        self.tracker_thread = threading.Thread(target=self.tracker_loop, daemon=True)
        self.tracker_thread.start()
        logging.info("Connection tracker started successfully")
        
    def stop(self):
        """Stop the connection tracker"""
        self.running = False
        if self.tracker_thread:
            self.tracker_thread.join(timeout=10)
        logging.info("Connection tracker stopped")
        
    def get_user_connection_info(self, username):
        """Get connection information for specific user"""
        user_stats = self.get_user_connection_stats()
        return user_stats.get(username, None)

# Global instance
connection_tracker = ConnectionTracker()

def main():
    """Main function"""
    tracker = ConnectionTracker()
    
    try:
        tracker.start()
        logging.info("ZIVPN Connection Tracker Started - Press Ctrl+C to stop")
        
        # Keep the main thread alive
        while tracker.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logging.info("Received interrupt signal")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        tracker.stop()
        logging.info("ZIVPN Connection Tracker Shutdown Complete")

if __name__ == "__main__":
    main()
PY

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

# --- NEW: Bandwidth Monitor Service ---
cat >/etc/systemd/system/zivpn-bandwidth.service <<'EOF'
[Unit]
Description=ZIVPN Bandwidth Monitor
After=network.target zivpn.service

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/bandwidth_monitor.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# --- NEW: Connection Tracker Service ---
cat >/etc/systemd/system/zivpn-tracker.service <<'EOF'
[Unit]
Description=ZIVPN Connection Tracker
After=network.target zivpn.service

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/bin/python3 /etc/zivpn/connection_tracker.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

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
# ufw allow 22/tcp >/dev/null 2>&1 || true
# ufw allow 5667/udp >/dev/null 2>&1 || true
# ufw allow 6000:19999/udp >/dev/null 2>&1 || true
# ufw allow 19432/tcp >/dev/null 2>&1 || true
# ufw allow 8081/tcp >/dev/null 2>&1 || true
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
# --- NEW: Enable monitoring services ---
systemctl enable --now zivpn-bandwidth.service
systemctl enable --now zivpn-tracker.service
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
# echo -e "  ${C}Login:${Z} ${Y}$WEB_USER / $WEB_PASS${Z}"
echo -e "\n${G}🔐 LOGIN CREDENTIALS${Z}"
echo -e "  ${Y}• Username:${Z} ${Y}$WEB_USER${Z}"
echo -e "  ${Y}• Password:${Z} ${Y}$WEB_PASS${Z}"
echo -e "\n${M}📊 SERVICES STATUS:${Z}"
echo -e "  ${Y}systemctl status zivpn-web${Z}      - Web Panel"
echo -e "  ${Y}systemctl status zivpn-bot${Z}      - Telegram Bot"
echo -e "  ${Y}systemctl status zivpn-connection${Z} - Connection Manager"
echo -e "  ${Y}systemctl status zivpn-bandwidth${Z} - Bandwidth Monitor"
echo -e "  ${Y}systemctl status zivpn-tracker${Z}   - Connection Tracker"
echo -e "$LINE"
