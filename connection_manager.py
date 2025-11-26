#!/usr/bin/env python3
"""
ZIVPN Connection Manager - Real-time Monitoring & Analytics
Enterprise Edition
"""
import sqlite3
import subprocess
import time
import threading
from datetime import datetime, timedelta
import os
import logging
import json

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
        self.analytics_data = {
            'daily_connections': {},
            'user_sessions': {},
            'bandwidth_usage': {}
        }
        
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
                    port INTEGER,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_update DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Analytics table
            db.execute('''
                CREATE TABLE IF NOT EXISTS connection_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE DEFAULT CURRENT_DATE,
                    total_connections INTEGER DEFAULT 0,
                    unique_users INTEGER DEFAULT 0,
                    total_bandwidth INTEGER DEFAULT 0,
                    peak_concurrent INTEGER DEFAULT 0
                )
            ''')
            
            db.commit()
            logger.info("Database tables initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
        finally:
            db.close()
            
    def get_active_connections(self):
        """Get active connections using conntrack with enhanced detection"""
        try:
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null | grep -E 'dport=(5667|[6-9][0-9]{3}|[1-9][0-9]{4})' | grep -v 'UNREPLIED'",
                shell=True, capture_output=True, text=True
            )
            
            connections = {}
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'src=' in line and 'dport=' in line:
                        try:
                            parts = line.split()
                            src_ip = None
                            dport = None
                            sport = None
                            
                            for part in parts:
                                if part.startswith('src='):
                                    src_ip = part.split('=')[1]
                                elif part.startswith('dport='):
                                    dport = part.split('=')[1]
                                elif part.startswith('sport='):
                                    sport = part.split('=')[1]
                            
                            if src_ip and dport:
                                connection_key = f"{src_ip}:{dport}"
                                connections[connection_key] = {
                                    'client_ip': src_ip,
                                    'server_port': dport,
                                    'client_port': sport,
                                    'timestamp': datetime.now()
                                }
                        except Exception as e:
                            logger.debug(f"Error parsing connection: {e}")
                            continue
            
            return connections
            
        except Exception as e:
            logger.error(f"Error getting active connections: {e}")
            return {}
            
    def map_connection_to_user(self, client_ip, server_port):
        """Map connection to username"""
        db = self.get_db()
        try:
            # First try to find by port
            user = db.execute(
                'SELECT username FROM users WHERE port = ?', 
                (server_port,)
            ).fetchone()
            
            if user:
                return user['username']
            
            # If port not found, check default port (5667) users
            if server_port == '5667':
                # Get users without specific port (using default)
                users = db.execute(
                    'SELECT username FROM users WHERE port IS NULL OR port = ""'
                ).fetchall()
                # For default port, we can't map 1:1, so return first active user
                # In production, you'd need better mapping logic
                if users:
                    return users[0]['username']
            
            return None
            
        except Exception as e:
            logger.error(f"Error mapping connection to user: {e}")
            return None
        finally:
            db.close()
            
    def update_user_session(self, username, client_ip, action='connect', bytes_used=0):
        """Update user session tracking"""
        db = self.get_db()
        try:
            session_id = f"{username}_{client_ip}_{int(datetime.now().timestamp())}"
            
            if action == 'connect':
                db.execute('''
                    INSERT INTO user_sessions 
                    (session_id, username, ip_address, start_time, status)
                    VALUES (?, ?, ?, datetime('now'), 'active')
                ''', (session_id, username, client_ip))
                
                # Update live connections
                db.execute('''
                    INSERT OR REPLACE INTO live_connections 
                    (connection_id, username, client_ip, start_time, last_update, is_active)
                    VALUES (?, ?, ?, datetime('now'), datetime('now'), 1)
                ''', (session_id, username, client_ip))
                
            elif action == 'disconnect':
                # Update session end time and duration
                db.execute('''
                    UPDATE user_sessions 
                    SET end_time = datetime('now'),
                        duration_seconds = CAST((julianday('now') - julianday(start_time)) * 86400 AS INTEGER),
                        status = 'completed'
                    WHERE username = ? AND ip_address = ? AND status = 'active'
                ''', (username, client_ip))
                
                # Remove from live connections
                db.execute('''
                    DELETE FROM live_connections 
                    WHERE username = ? AND client_ip = ?
                ''', (username, client_ip))
                
            elif action == 'update':
                # Update bandwidth usage
                db.execute('''
                    UPDATE user_sessions 
                    SET bytes_received = bytes_received + ?
                    WHERE username = ? AND ip_address = ? AND status = 'active'
                ''', (bytes_used, username, client_ip))
                
                # Update live connections timestamp
                db.execute('''
                    UPDATE live_connections 
                    SET last_update = datetime('now')
                    WHERE username = ? AND client_ip = ?
                ''', (username, client_ip))
                
                # Update user bandwidth in main table
                db.execute('''
                    UPDATE users 
                    SET bandwidth_used = bandwidth_used + ?,
                        updated_at = datetime('now')
                    WHERE username = ?
                ''', (bytes_used, username))
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating user session: {e}")
        finally:
            db.close()
            
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
                
                # Count connections for this user
                user_conn_count = 0
                user_connections = []
                
                for conn_key, conn_info in active_connections.items():
                    if conn_info['server_port'] == user_port:
                        user_conn_count += 1
                        user_connections.append(conn_info)
                
                # If over limit, drop oldest connections
                if user_conn_count > max_connections:
                    logger.info(f"User {username} has {user_conn_count} connections (limit: {max_connections})")
                    
                    # Drop excess connections (FIFO)
                    excess = user_conn_count - max_connections
                    for i in range(excess):
                        if i < len(user_connections):
                            conn_to_drop = user_connections[i]
                            self.drop_connection(conn_to_drop['client_ip'], user_port)
                            
        except Exception as e:
            logger.error(f"Error enforcing connection limits: {e}")
        finally:
            db.close()
            
    def drop_connection(self, client_ip, server_port):
        """Drop a specific connection using conntrack"""
        try:
            result = subprocess.run(
                f"conntrack -D -p udp --dport {server_port} --src {client_ip}",
                shell=True, capture_output=True, text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Dropped connection: {client_ip}:{server_port}")
                return True
            else:
                logger.warning(f"Failed to drop connection: {client_ip}:{server_port}")
                return False
                
        except Exception as e:
            logger.error(f"Error dropping connection: {e}")
            return False
            
    def cleanup_stale_connections(self):
        """Clean up stale connections from database"""
        db = self.get_db()
        try:
            # Remove connections older than 10 minutes
            cutoff_time = (datetime.now() - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
            
            stale_connections = db.execute('''
                SELECT connection_id, username, client_ip 
                FROM live_connections 
                WHERE last_update < ?
            ''', (cutoff_time,)).fetchall()
            
            for conn in stale_connections:
                logger.info(f"Cleaning up stale connection: {conn['username']} - {conn['client_ip']}")
                db.execute('DELETE FROM live_connections WHERE connection_id = ?', (conn['connection_id'],))
                
                # Update session as completed
                db.execute('''
                    UPDATE user_sessions 
                    SET end_time = datetime('now'),
                        duration_seconds = CAST((julianday('now') - julianday(start_time)) * 86400 AS INTEGER),
                        status = 'completed'
                    WHERE username = ? AND ip_address = ? AND status = 'active'
                ''', (conn['username'], conn['client_ip']))
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error cleaning up stale connections: {e}")
        finally:
            db.close()
            
    def get_live_connections_stats(self):
        """Get statistics about live connections"""
        db = self.get_db()
        try:
            # Total live connections
            total_live = db.execute('SELECT COUNT(*) as count FROM live_connections').fetchone()['count']
            
            # Connections by user
            user_stats = db.execute('''
                SELECT username, COUNT(*) as connection_count
                FROM live_connections 
                GROUP BY username
                ORDER BY connection_count DESC
            ''').fetchall()
            
            # Recent connections (last 1 hour)
            recent_cutoff = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            recent_connections = db.execute('''
                SELECT COUNT(*) as count 
                FROM user_sessions 
                WHERE start_time > ?
            ''', (recent_cutoff,)).fetchone()['count']
            
            return {
                'total_live_connections': total_live,
                'user_connection_stats': [dict(row) for row in user_stats],
                'recent_connections_1h': recent_connections
            }
            
        except Exception as e:
            logger.error(f"Error getting live connections stats: {e}")
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
            logger.error(f"Error getting user connection history: {e}")
            return []
        finally:
            db.close()
            
    def start_monitoring(self):
        """Start the connection monitoring loop"""
        def monitor_loop():
            logger.info("Starting connection monitoring loop...")
            self.initialize_database()
            
            while True:
                try:
                    # 1. Get current active connections
                    active_connections = self.get_active_connections()
                    
                    # 2. Update connection tracking
                    for conn_key, conn_info in active_connections.items():
                        username = self.map_connection_to_user(
                            conn_info['client_ip'], 
                            conn_info['server_port']
                        )
                        
                        if username:
                            self.update_user_session(
                                username, 
                                conn_info['client_ip'], 
                                'update', 
                                bytes_used=0  # In real implementation, track actual bytes
                            )
                    
                    # 3. Enforce connection limits
                    self.enforce_connection_limits()
                    
                    # 4. Clean up stale connections
                    self.cleanup_stale_connections()
                    
                    # 5. Update analytics
                    self.update_analytics()
                    
                    time.sleep(15)  # Check every 15 seconds
                    
                except Exception as e:
                    logger.error(f"Monitoring loop error: {e}")
                    time.sleep(30)  # Longer delay on error
                    
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("Connection monitoring started successfully")
        
    def update_analytics(self):
        """Update connection analytics"""
        db = self.get_db()
        try:
            today = datetime.now().date().isoformat()
            
            # Get today's stats
            total_connections = db.execute('''
                SELECT COUNT(*) as count FROM user_sessions 
                WHERE date(start_time) = date('now')
            ''').fetchone()['count']
            
            unique_users = db.execute('''
                SELECT COUNT(DISTINCT username) as count FROM user_sessions 
                WHERE date(start_time) = date('now')
            ''').fetchone()['count']
            
            total_bandwidth = db.execute('''
                SELECT SUM(bytes_received) as total FROM user_sessions 
                WHERE date(start_time) = date('now')
            ''').fetchone()['total'] or 0
            
            peak_concurrent = db.execute('''
                SELECT COUNT(*) as count FROM live_connections
            ''').fetchone()['count']
            
            # Update or insert analytics for today
            db.execute('''
                INSERT OR REPLACE INTO connection_analytics 
                (date, total_connections, unique_users, total_bandwidth, peak_concurrent)
                VALUES (date('now'), ?, ?, ?, ?)
            ''', (total_connections, unique_users, total_bandwidth, peak_concurrent))
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating analytics: {e}")
        finally:
            db.close()

# Global instance
connection_manager = ConnectionManager()

if __name__ == "__main__":
    print("Starting ZIVPN Connection Manager...")
    connection_manager.start_monitoring()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping Connection Manager...")
      
