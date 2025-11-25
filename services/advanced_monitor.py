#!/usr/bin/env python3
"""
ZIVPN Advanced Connection Monitor
Real-time user tracking and connection management
"""

import sqlite3
import subprocess
import time
import threading
import json
from datetime import datetime, timedelta
import logging
import os

# Configuration
DATABASE_PATH = "/etc/zivpn/zivpn.db"
LOG_FILE = "/var/log/zivpn_monitor.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedConnectionMonitor:
    def __init__(self):
        self.active_connections = {}
        self.connection_stats = {}
        
    def get_db(self):
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
        
    def get_detailed_connections(self):
        """Get detailed connection information using conntrack"""
        try:
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null | grep -E 'dport=(5667|[6-9][0-9]{3}|[1-9][0-9]{4})'",
                shell=True, capture_output=True, text=True
            )
            
            connections = {}
            for line in result.stdout.split('\n'):
                if 'src=' in line and 'dport=' in line:
                    try:
                        parts = line.split()
                        src_ip = None
                        dst_ip = None
                        dport = None
                        sport = None
                        
                        for part in parts:
                            if part.startswith('src='):
                                src_ip = part.split('=')[1]
                            elif part.startswith('dst='):
                                dst_ip = part.split('=')[1]
                            elif part.startswith('sport='):
                                sport = part.split('=')[1]
                            elif part.startswith('dport='):
                                dport = part.split('=')[1]
                        
                        if src_ip and dport:
                            conn_key = f"{src_ip}:{dport}"
                            connections[conn_key] = {
                                'src_ip': src_ip,
                                'dst_ip': dst_ip,
                                'sport': sport,
                                'dport': dport,
                                'last_seen': datetime.now()
                            }
                    except Exception as e:
                        continue
            return connections
        except Exception as e:
            logger.error(f"Error getting connections: {e}")
            return {}
            
    def map_port_to_user(self, port):
        """Map port number to username"""
        db = self.get_db()
        try:
            user = db.execute(
                'SELECT username FROM users WHERE port = ? OR ? = "5667"',
                (port, port)
            ).fetchone()
            return user['username'] if user else f"unknown_{port}"
        finally:
            db.close()
            
    def update_online_status(self):
        """Update online status for all users"""
        active_conns = self.get_detailed_connections()
        db = self.get_db()
        
        try:
            # Reset all users to offline
            db.execute('UPDATE users SET is_online = 0')
            
            # Update online users and log connections
            for conn_key, conn_info in active_conns.items():
                username = self.map_port_to_user(conn_info['dport'])
                if username and not username.startswith('unknown'):
                    # Update user online status
                    db.execute(
                        'UPDATE users SET is_online = 1, last_login = ?, last_ip = ? WHERE username = ?',
                        (datetime.now(), conn_info['src_ip'], username)
                    )
                    
                    # Update total connections count
                    db.execute(
                        'UPDATE users SET total_connections = total_connections + 1 WHERE username = ?',
                        (username,)
                    )
                    
                    # Log connection session
                    db.execute('''
                        INSERT OR REPLACE INTO user_sessions 
                        (username, session_id, client_ip, last_activity, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (username, conn_key, conn_info['src_ip'], datetime.now()))
            
            db.commit()
            logger.info(f"Updated online status - Active connections: {len(active_conns)}")
            
        except Exception as e:
            logger.error(f"Error updating online status: {e}")
        finally:
            db.close()
            
    def cleanup_old_sessions(self):
        """Clean up old sessions"""
        db = self.get_db()
        try:
            # Mark sessions older than 10 minutes as inactive
            ten_min_ago = datetime.now() - timedelta(minutes=10)
            db.execute(
                'UPDATE user_sessions SET is_active = 0 WHERE last_activity < ?',
                (ten_min_ago,)
            )
            db.commit()
        finally:
            db.close()
            
    def get_connection_stats(self):
        """Get connection statistics"""
        db = self.get_db()
        try:
            # Total online users
            online_users = db.execute(
                'SELECT COUNT(*) as count FROM users WHERE is_online = 1'
            ).fetchone()['count']
            
            # Today's connections
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_connections = db.execute(
                'SELECT COUNT(DISTINCT username) as count FROM connection_logs WHERE connect_time >= ?',
                (today_start,)
            ).fetchone()['count']
            
            return {
                'online_users': online_users,
                'today_connections': today_connections,
                'timestamp': datetime.now().isoformat()
            }
        finally:
            db.close()
            
    def start_monitoring(self):
        """Start the monitoring loop"""
        def monitor_loop():
            while True:
                try:
                    self.update_online_status()
                    self.cleanup_old_sessions()
                    time.sleep(10)  # Check every 10 seconds
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                    time.sleep(30)
                    
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("Advanced Connection Monitor started")

# Global instance
monitor = AdvancedConnectionMonitor()

if __name__ == "__main__":
    print("🚀 Starting ZIVPN Advanced Connection Monitor...")
    monitor.start_monitoring()
    
    try:
        while True:
            stats = monitor.get_connection_stats()
            print(f"📊 Stats - Online: {stats['online_users']}, Today: {stats['today_connections']}")
            time.sleep(60)
    except KeyboardInterrupt:
        print("🛑 Stopping monitor...")
      
