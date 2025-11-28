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
  
