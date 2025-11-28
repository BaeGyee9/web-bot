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
  
