#!/usr/bin/env python3
"""
ZIVPN Connection Manager - SIMPLE WORKING VERSION
No External Imports - 100% Standalone
"""

import sqlite3
import subprocess
import time
import threading
from datetime import datetime, timedelta
import os
import logging
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DATABASE_PATH = "/etc/zivpn/zivpn.db"

class SimpleConnectionManager:
    def __init__(self):
        self.active_connections = {}
        
    def get_db(self):
        """Get database connection"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return None

    def setup_tables(self):
        """Create necessary tables if they don't exist"""
        db = self.get_db()
        if not db:
            return False
            
        try:
            # Live connections table
            db.execute('''
                CREATE TABLE IF NOT EXISTS live_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    client_port INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_online BOOLEAN DEFAULT 1
                )
            ''')
            
            # User sessions table
            db.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    client_port INTEGER NOT NULL,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    end_time DATETIME,
                    duration_seconds INTEGER DEFAULT 0
                )
            ''')
            
            db.commit()
            logger.info("✅ Database tables ready")
            return True
            
        except Exception as e:
            logger.error(f"❌ Table setup failed: {e}")
            return False
        finally:
            db.close()

    def get_conntrack_connections(self):
        """Get UDP connections from conntrack"""
        try:
            # Run conntrack command
            cmd = "conntrack -L -p udp 2>/dev/null | grep -E 'dport=5667|sport=5667' | grep -v UNREPLIED"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            connections = {}
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if not line.strip():
                        continue
                        
                    # Parse the line
                    parts = line.split()
                    src_ip = None
                    src_port = None
                    dst_ip = None
                    dst_port = None
                    
                    for part in parts:
                        if part.startswith('src='):
                            src_ip = part.split('=')[1]
                        elif part.startswith('sport='):
                            src_port = part.split('=')[1]
                        elif part.startswith('dst='):
                            dst_ip = part.split('=')[1]
                        elif part.startswith('dport='):
                            dst_port = part.split('=')[1]
                    
                    # Determine client connection
                    if src_ip and src_port and dst_port == '5667':
                        # Client -> Server
                        connections[f"{src_ip}:{src_port}"] = {
                            'client_ip': src_ip,
                            'client_port': src_port,
                            'type': 'client_to_server'
                        }
                    elif dst_ip and dst_port and src_port == '5667':
                        # Server -> Client
                        connections[f"{dst_ip}:{dst_port}"] = {
                            'client_ip': dst_ip,
                            'client_port': dst_port,
                            'type': 'server_to_client'
                        }
            
            return connections
            
        except Exception as e:
            logger.error(f"❌ Conntrack error: {e}")
            return {}

    def find_user_by_port(self, port):
        """Find user by port number"""
        db = self.get_db()
        if not db:
            return None
            
        try:
            user = db.execute(
                "SELECT username FROM users WHERE port = ? AND status = 'active'",
                (port,)
            ).fetchone()
            
            return user['username'] if user else None
            
        except Exception as e:
            logger.error(f"❌ User lookup error: {e}")
            return None
        finally:
            db.close()

    def update_live_connection(self, username, client_ip, client_port):
        """Update live connection in database"""
        db = self.get_db()
        if not db:
            return
            
        try:
            # Check if connection already exists
            existing = db.execute(
                "SELECT id FROM live_connections WHERE username = ? AND client_ip = ? AND client_port = ?",
                (username, client_ip, client_port)
            ).fetchone()
            
            if existing:
                # Update existing connection
                db.execute(
                    "UPDATE live_connections SET last_seen = datetime('now'), is_online = 1 WHERE id = ?",
                    (existing['id'],)
                )
            else:
                # Insert new connection
                db.execute(
                    "INSERT INTO live_connections (username, client_ip, client_port, created_at, last_seen, is_online) VALUES (?, ?, ?, datetime('now'), datetime('now'), 1)",
                    (username, client_ip, client_port)
                )
                
                # Also create session record
                db.execute(
                    "INSERT INTO user_sessions (username, client_ip, client_port, start_time) VALUES (?, ?, ?, datetime('now'))",
                    (username, client_ip, client_port)
                )
                
                logger.info(f"🟢 NEW CONNECTION: {username} from {client_ip}:{client_port}")
            
            db.commit()
            
        except Exception as e:
            logger.error(f"❌ Database update error: {e}")
        finally:
            db.close()

    def cleanup_old_connections(self):
        """Remove connections older than 2 minutes"""
        db = self.get_db()
        if not db:
            return
            
        try:
            cutoff_time = (datetime.now() - timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Find connections to cleanup
            old_conns = db.execute(
                "SELECT id, username, client_ip, client_port FROM live_connections WHERE last_seen < ?",
                (cutoff_time,)
            ).fetchall()
            
            for conn in old_conns:
                logger.info(f"🔴 CLEANUP: {conn['username']} from {conn['client_ip']}:{conn['client_port']}")
                
                # Update session end time
                db.execute(
                    "UPDATE user_sessions SET end_time = datetime('now'), duration_seconds = CAST((julianday('now') - julianday(start_time)) * 86400 AS INTEGER) WHERE username = ? AND client_ip = ? AND client_port = ? AND end_time IS NULL",
                    (conn['username'], conn['client_ip'], conn['client_port'])
                )
            
            # Remove from live connections
            db.execute("DELETE FROM live_connections WHERE last_seen < ?", (cutoff_time,))
            db.commit()
            
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
        finally:
            db.close()

    def get_live_stats(self):
        """Get current live connection statistics"""
        db = self.get_db()
        if not db:
            return {'total': 0, 'users': []}
            
        try:
            # Total connections
            total_result = db.execute("SELECT COUNT(*) as count FROM live_connections WHERE is_online = 1").fetchone()
            total = total_result['count'] if total_result else 0
            
            # Users with connections
            users_result = db.execute('''
                SELECT username, COUNT(*) as connections 
                FROM live_connections 
                WHERE is_online = 1 
                GROUP BY username 
                ORDER BY connections DESC
            ''').fetchall()
            
            users = [dict(row) for row in users_result]
            
            return {
                'total_live_connections': total,
                'user_connection_stats': users
            }
            
        except Exception as e:
            logger.error(f"❌ Stats error: {e}")
            return {'total_live_connections': 0, 'user_connection_stats': []}
        finally:
            db.close()

    def start_monitoring(self):
        """Start the monitoring loop"""
        logger.info("🚀 STARTING SIMPLE CONNECTION MONITOR")
        
        # Setup database
        if not self.setup_tables():
            logger.error("❌ Failed to setup database")
            return
        
        def monitor_loop():
            cycle = 0
            while True:
                try:
                    cycle += 1
                    
                    # Get current connections from conntrack
                    connections = self.get_conntrack_connections()
                    tracked = 0
                    
                    # Process each connection
                    for conn_id, conn_info in connections.items():
                        client_ip = conn_info['client_ip']
                        client_port = conn_info['client_port']
                        
                        # Find user by port
                        username = self.find_user_by_port(client_port)
                        
                        if username:
                            self.update_live_connection(username, client_ip, client_port)
                            tracked += 1
                    
                    # Cleanup every 5 cycles
                    if cycle % 5 == 0:
                        self.cleanup_old_connections()
                        stats = self.get_live_stats()
                        logger.info(f"📊 Cycle {cycle}: {tracked} active, {stats['total_live_connections']} in DB")
                    
                    time.sleep(5)  # Check every 5 seconds
                    
                except Exception as e:
                    logger.error(f"❌ Monitor error: {e}")
                    time.sleep(10)
        
        # Start monitoring
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        logger.info("✅ SIMPLE MONITOR RUNNING!")

# Create global instance
connection_manager = SimpleConnectionManager()

if __name__ == "__main__":
    print("🎯 ZIVPN SIMPLE CONNECTION MANAGER - NO IMPORTS")
    connection_manager.start_monitoring()
    
    try:
        # Keep running
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("🛑 Stopped")
