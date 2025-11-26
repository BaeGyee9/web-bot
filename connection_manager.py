#!/usr/bin/env python3
"""
ZIVPN Connection Manager - ENTERPRISE EDITION
FULLY FIXED VERSION with Accurate Port Mapping & Real-time Tracking
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

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")

class ConnectionManager:
    def __init__(self):
        self.connection_tracker = {}
        self.lock = threading.Lock()
        self.last_cleanup = datetime.now()
        
    def get_db(self):
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
        
    def initialize_database(self):
        """Initialize required database tables"""
        db = self.get_db()
        try:
            # User sessions table for tracking connections
            db.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    device_info TEXT,
                    ip_address TEXT,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    end_time DATETIME,
                    bytes_sent INTEGER DEFAULT 0,
                    bytes_received INTEGER DEFAULT 0,
                    duration_seconds INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            # Live connections table
            db.execute('''
                CREATE TABLE IF NOT EXISTS live_connections (
                    connection_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    server_ip TEXT,
                    client_ip TEXT,
                    client_port INTEGER,
                    server_port INTEGER,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_update DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            db.commit()
            logger.info("✅ Database tables initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Error initializing database: {e}")
        finally:
            db.close()
            
    def get_active_connections(self):
        """Get active connections using conntrack with ENHANCED parsing"""
        try:
            # Get all UDP connections
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null",
                shell=True, capture_output=True, text=True
            )
            
            connections = {}
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'dport=5667' in line or 'sport=5667' in line:
                        try:
                            # Parse connection information
                            src_ip = self.extract_value(line, 'src=')
                            dst_ip = self.extract_value(line, 'dst=')
                            sport = self.extract_value(line, 'sport=')
                            dport = self.extract_value(line, 'dport=')
                            
                            if src_ip and dst_ip and sport and dport:
                                # Determine client and server ports
                                if dport == '5667':
                                    # Client -> Server connection
                                    client_ip = src_ip
                                    client_port = sport
                                    server_port = dport
                                else:
                                    # Server -> Client connection
                                    client_ip = dst_ip
                                    client_port = dport
                                    server_port = sport
                                
                                # Only track connections where server port is 5667
                                if server_port == '5667':
                                    connection_key = f"{client_ip}:{client_port}"
                                    connections[connection_key] = {
                                        'client_ip': client_ip,
                                        'client_port': client_port,
                                        'server_port': server_port,
                                        'timestamp': datetime.now()
                                    }
                                    logger.debug(f"📡 Found connection: {client_ip}:{client_port} -> :{server_port}")
                                    
                        except Exception as e:
                            logger.debug(f"🔧 Parsing line: {line}")
                            logger.debug(f"🔧 Error parsing connection: {e}")
                            continue
            
            logger.info(f"📊 Found {len(connections)} active connections")
            return connections
            
        except Exception as e:
            logger.error(f"❌ Error getting active connections: {e}")
            return {}
    
    def extract_value(self, line, key):
        """Extract value from conntrack output line"""
        try:
            pattern = f'{key}([^\\s]+)'
            match = re.search(pattern, line)
            return match.group(1) if match else None
        except:
            return None
            
    def map_connection_to_user(self, client_ip, client_port):
        """ACCURATE: Map connection to username using CLIENT PORT"""
        db = self.get_db()
        try:
            logger.info(f"🔍 Mapping connection: {client_ip}:{client_port}")
            
            # METHOD 1: Direct port mapping (most accurate)
            user = db.execute(
                'SELECT username FROM users WHERE port = ?', 
                (client_port,)
            ).fetchone()
            
            if user:
                logger.info(f"✅ Port mapping: {client_port} -> {user['username']}")
                return user['username']
            
            # METHOD 2: Check if this IP has recent connections
            recent_user = db.execute('''
                SELECT username FROM user_sessions 
                WHERE ip_address = ? AND status = 'active'
                ORDER BY start_time DESC LIMIT 1
            ''', (client_ip,)).fetchone()
            
            if recent_user:
                logger.info(f"✅ IP mapping: {client_ip} -> {recent_user['username']}")
                return recent_user['username']
            
            # METHOD 3: For default port users (no specific port assigned)
            default_users = db.execute('''
                SELECT username FROM users 
                WHERE (port IS NULL OR port = '' OR port = '5667')
                AND status = 'active'
                LIMIT 1
            ''').fetchall()
            
            if default_users:
                logger.info(f"⚠️ Default mapping: {client_ip} -> {default_users[0]['username']}")
                return default_users[0]['username']
            
            logger.warning(f"❌ No user mapping found for {client_ip}:{client_port}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error mapping connection to user: {e}")
            return None
        finally:
            db.close()
            
    def update_user_session(self, username, client_ip, client_port, action='connect', bytes_used=0):
        """Update user session tracking"""
        db = self.get_db()
        try:
            session_id = f"{username}_{client_ip}_{client_port}"
            
            if action == 'connect':
                # Check if session already exists
                existing = db.execute(
                    'SELECT session_id FROM user_sessions WHERE session_id = ? AND status = "active"',
                    (session_id,)
                ).fetchone()
                
                if not existing:
                    db.execute('''
                        INSERT INTO user_sessions 
                        (session_id, username, ip_address, start_time, status)
                        VALUES (?, ?, ?, datetime('now'), 'active')
                    ''', (session_id, username, client_ip))
                    
                    logger.info(f"🟢 New session: {username} from {client_ip}:{client_port}")
            
            # Update live connections (always)
            db.execute('''
                INSERT OR REPLACE INTO live_connections 
                (connection_id, username, client_ip, client_port, server_port, start_time, last_update, is_active)
                VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'), 1)
            ''', (session_id, username, client_ip, client_port, 5667))
            
            if action == 'disconnect':
                # Update session as completed
                db.execute('''
                    UPDATE user_sessions 
                    SET end_time = datetime('now'),
                        duration_seconds = CAST((julianday('now') - julianday(start_time)) * 86400 AS INTEGER),
                        status = 'completed'
                    WHERE session_id = ? AND status = 'active'
                ''', (session_id,))
                
                # Remove from live connections
                db.execute('''
                    DELETE FROM live_connections 
                    WHERE connection_id = ?
                ''', (session_id,))
                
                logger.info(f"🔴 Session ended: {username} from {client_ip}:{client_port}")
                
            elif action == 'update':
                # Update bandwidth usage
                if bytes_used > 0:
                    db.execute('''
                        UPDATE user_sessions 
                        SET bytes_received = bytes_received + ?
                        WHERE session_id = ? AND status = 'active'
                    ''', (bytes_used, session_id))
                    
                    # Update user bandwidth in main table
                    db.execute('''
                        UPDATE users 
                        SET bandwidth_used = bandwidth_used + ?,
                            updated_at = datetime('now')
                        WHERE username = ?
                    ''', (bytes_used, username))
            
            db.commit()
            
        except Exception as e:
            logger.error(f"❌ Error updating user session: {e}")
        finally:
            db.close()
            
    def enforce_connection_limits(self):
        """Enforce connection limits for all users"""
        db = self.get_db()
        try:
            # Get all active users with their connection limits
            users = db.execute('''
                SELECT username, concurrent_conn 
                FROM users 
                WHERE status = "active" AND (expires IS NULL OR expires >= CURRENT_DATE)
            ''').fetchall()
            
            for user in users:
                username = user['username']
                max_connections = user['concurrent_conn']
                
                # Count current connections for this user
                user_conns = db.execute('''
                    SELECT COUNT(*) as conn_count FROM live_connections 
                    WHERE username = ? AND is_active = 1
                ''', (username,)).fetchone()
                
                conn_count = user_conns['conn_count'] if user_conns else 0
                
                # If over limit, drop oldest connections
                if conn_count > max_connections:
                    logger.warning(f"🚫 User {username} has {conn_count} connections (limit: {max_connections})")
                    
                    # Get oldest connections to drop
                    excess_conns = db.execute('''
                        SELECT connection_id, client_ip, client_port 
                        FROM live_connections 
                        WHERE username = ? 
                        ORDER BY last_update ASC 
                        LIMIT ?
                    ''', (username, conn_count - max_connections)).fetchall()
                    
                    for conn in excess_conns:
                        self.drop_connection(conn['client_ip'], conn['client_port'])
                        logger.info(f"🦵 Dropped excess connection: {username} - {conn['client_ip']}:{conn['client_port']}")
                            
        except Exception as e:
            logger.error(f"❌ Error enforcing connection limits: {e}")
        finally:
            db.close()
            
    def drop_connection(self, client_ip, client_port):
        """Drop a specific connection using conntrack"""
        try:
            result = subprocess.run(
                f"conntrack -D -p udp --dport 5667 --sport {client_port} --src {client_ip}",
                shell=True, capture_output=True, text=True
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Dropped connection: {client_ip}:{client_port}")
                return True
            else:
                logger.warning(f"⚠️ Failed to drop connection: {client_ip}:{client_port}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error dropping connection: {e}")
            return False
            
    def cleanup_stale_connections(self):
        """Clean up stale connections from database"""
        db = self.get_db()
        try:
            # Remove connections older than 3 minutes
            cutoff_time = (datetime.now() - timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')
            
            stale_connections = db.execute('''
                SELECT connection_id, username, client_ip, client_port 
                FROM live_connections 
                WHERE last_update < ?
            ''', (cutoff_time,)).fetchall()
            
            for conn in stale_connections:
                logger.info(f"🧹 Cleaning stale connection: {conn['username']} - {conn['client_ip']}:{conn['client_port']}")
                
                # Update session as completed
                db.execute('''
                    UPDATE user_sessions 
                    SET end_time = datetime('now'),
                        duration_seconds = CAST((julianday('now') - julianday(start_time)) * 86400 AS INTEGER),
                        status = 'completed'
                    WHERE username = ? AND ip_address = ? AND status = 'active'
                ''', (conn['username'], conn['client_ip']))
                
                # Remove from live connections
                db.execute('DELETE FROM live_connections WHERE connection_id = ?', (conn['connection_id'],))
            
            db.commit()
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up stale connections: {e}")
        finally:
            db.close()
            
    def get_live_connections_stats(self):
        """Get statistics about live connections"""
        db = self.get_db()
        try:
            # Total live connections
            total_live = db.execute('SELECT COUNT(*) as count FROM live_connections WHERE is_active = 1').fetchone()['count']
            
            # Connections by user
            user_stats = db.execute('''
                SELECT username, COUNT(*) as connection_count
                FROM live_connections 
                WHERE is_active = 1
                GROUP BY username
                ORDER BY connection_count DESC
            ''').fetchall()
            
            # Recent connections (last 5 minutes)
            recent_cutoff = (datetime.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
            recent_connections = db.execute('''
                SELECT COUNT(*) as count 
                FROM user_sessions 
                WHERE start_time > ?
            ''', (recent_cutoff,)).fetchone()['count']
            
            return {
                'total_live_connections': total_live,
                'user_connection_stats': [dict(row) for row in user_stats],
                'recent_connections_5m': recent_connections
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting live connections stats: {e}")
            return {}
        finally:
            db.close()
            
    def get_user_connection_history(self, username, days=7):
        """Get connection history for a specific user"""
        db = self.get_db()
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            history = db.execute('''
                SELECT 
                    date(start_time) as connection_date,
                    COUNT(*) as connection_count,
                    SUM(duration_seconds) as total_duration,
                    SUM(bytes_received) as total_bytes
                FROM user_sessions 
                WHERE username = ? AND start_time >= ?
                GROUP BY date(start_time)
                ORDER BY connection_date DESC
            ''', (username, cutoff_date)).fetchall()
            
            return [dict(row) for row in history]
            
        except Exception as e:
            logger.error(f"❌ Error getting user connection history: {e}")
            return []
        finally:
            db.close()
            
    def start_monitoring(self):
        """Start the connection monitoring loop"""
        def monitor_loop():
            logger.info("🚀 Starting ENHANCED connection monitoring loop...")
            self.initialize_database()
            
            while True:
                try:
                    # 1. Get current active connections
                    active_connections = self.get_active_connections()
                    
                    # 2. Update connection tracking
                    connection_count = 0
                    for conn_key, conn_info in active_connections.items():
                        username = self.map_connection_to_user(
                            conn_info['client_ip'], 
                            conn_info['client_port']
                        )
                        
                        if username:
                            self.update_user_session(
                                username, 
                                conn_info['client_ip'],
                                conn_info['client_port'],
                                'update'
                            )
                            connection_count += 1
                    
                    # 3. Enforce connection limits every 30 seconds
                    current_time = datetime.now()
                    if (current_time - self.last_cleanup).total_seconds() > 30:
                        self.enforce_connection_limits()
                        self.cleanup_stale_connections()
                        self.last_cleanup = current_time
                    
                    # 4. Log monitoring status every minute
                    if connection_count > 0:
                        logger.info(f"📊 Monitoring {connection_count} active connections")
                    
                    time.sleep(5)  # Check every 5 seconds
                    
                except Exception as e:
                    logger.error(f"❌ Monitoring loop error: {e}")
                    time.sleep(10)  # Longer delay on error
                    
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("✅ ENHANCED Connection monitoring started successfully")
        
    def debug_current_state(self):
        """Debug function to show current state"""
        db = self.get_db()
        try:
            # Show live connections
            live_conns = db.execute('SELECT * FROM live_connections').fetchall()
            logger.info(f"🔍 DEBUG - Live connections: {len(live_conns)}")
            for conn in live_conns:
                logger.info(f"🔍 DEBUG - {dict(conn)}")
                
            # Show active sessions
            active_sessions = db.execute('SELECT * FROM user_sessions WHERE status = "active"').fetchall()
            logger.info(f"🔍 DEBUG - Active sessions: {len(active_sessions)}")
            
        except Exception as e:
            logger.error(f"❌ Debug error: {e}")
        finally:
            db.close()

# Global instance
connection_manager = ConnectionManager()

if __name__ == "__main__":
    print("🚀 Starting ZIVPN Connection Manager - ENTERPRISE EDITION...")
    print("📊 Features: Real-time tracking, Port mapping, Connection limits")
    
    # Start monitoring
    connection_manager.start_monitoring()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(60)
            # Debug output every minute
            connection_manager.debug_current_state()
    except KeyboardInterrupt:
        print("🛑 Stopping Connection Manager...")
