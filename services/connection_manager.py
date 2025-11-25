#!/usr/bin/env python3
"""
ZIVPN Enhanced Connection Manager
Connection limiting and management with real-time tracking
"""

import sqlite3
import subprocess
import time
import threading
from datetime import datetime
import os
import logging

# Configuration
DATABASE_PATH = "/etc/zivpn/zivpn.db"
LOG_FILE = "/var/log/zivpn_connection.log"

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

class EnhancedConnectionManager:
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
                            connections[f"{src_ip}:{dport}"] = {
                                'src_ip': src_ip,
                                'dport': dport,
                                'timestamp': datetime.now()
                            }
                    except:
                        continue
            return connections
        except Exception as e:
            logger.error(f"Error getting connections: {e}")
            return {}
            
    def get_user_by_port(self, port):
        """Get username by port"""
        db = self.get_db()
        try:
            user = db.execute(
                'SELECT username, concurrent_conn FROM users WHERE port = ? OR ? = "5667"',
                (port, port)
            ).fetchone()
            return dict(user) if user else None
        finally:
            db.close()
            
    def enforce_connection_limits(self):
        """Enforce connection limits for all users"""
        active_connections = self.get_active_connections()
        
        # Group connections by port
        connections_by_port = {}
        for conn_key, conn_info in active_connections.items():
            port = conn_info['dport']
            if port not in connections_by_port:
                connections_by_port[port] = []
            connections_by_port[port].append(conn_info)
        
        # Check limits for each port
        for port, connections in connections_by_port.items():
            user_info = self.get_user_by_port(port)
            if user_info:
                max_connections = user_info['concurrent_conn']
                current_connections = len(connections)
                
                if current_connections > max_connections:
                    logger.info(f"User {user_info['username']} has {current_connections} connections (limit: {max_connections})")
                    
                    # Drop excess connections (oldest first)
                    excess = current_connections - max_connections
                    for i in range(excess):
                        if i < len(connections):
                            conn_to_drop = connections[i]
                            self.drop_connection(conn_to_drop['src_ip'], conn_to_drop['dport'])
                            
    def drop_connection(self, src_ip, dport):
        """Drop a specific connection"""
        try:
            subprocess.run(
                f"conntrack -D -p udp --dport {dport} --src {src_ip}",
                shell=True, capture_output=True
            )
            logger.info(f"Dropped connection: {src_ip}:{dport}")
        except Exception as e:
            logger.error(f"Error dropping connection {src_ip}:{dport}: {e}")
            
    def get_connection_stats(self):
        """Get connection statistics"""
        active_connections = self.get_active_connections()
        
        stats = {
            'total_connections': len(active_connections),
            'connections_by_port': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Count connections by port
        for conn_info in active_connections.values():
            port = conn_info['dport']
            if port not in stats['connections_by_port']:
                stats['connections_by_port'][port] = 0
            stats['connections_by_port'][port] += 1
            
        return stats
            
    def start_monitoring(self):
        """Start the connection monitoring loop"""
        def monitor_loop():
            while True:
                try:
                    self.enforce_connection_limits()
                    time.sleep(15)  # Check every 15 seconds
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                    time.sleep(30)
                    
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("Enhanced Connection Manager started")

# Global instance
connection_manager = EnhancedConnectionManager()

if __name__ == "__main__":
    print("🚀 Starting ZIVPN Enhanced Connection Manager...")
    connection_manager.start_monitoring()
    
    try:
        while True:
            stats = connection_manager.get_connection_stats()
            print(f"📊 Connection Stats - Total: {stats['total_connections']}")
            time.sleep(60)
    except KeyboardInterrupt:
        print("🛑 Stopping connection manager...")
