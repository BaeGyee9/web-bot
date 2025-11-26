import sqlite3
import subprocess
import time
import threading
from datetime import datetime
import os
import requests
import json

DATABASE_PATH = "/etc/zivpn/zivpn.db"

class ConnectionManager:
    def __init__(self):
        self.connection_tracker = {}
        self.lock = threading.Lock()
        self.running = True
        
    def get_db(self):
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
        
    def initialize_database(self):
        """Initialize database with connection tracking tables"""
        db = self.get_db()
        try:
            # Connection logs table
            db.execute('''
                CREATE TABLE IF NOT EXISTS connection_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    server_port INTEGER,
                    connected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    disconnected_at DATETIME,
                    bytes_sent INTEGER DEFAULT 0,
                    bytes_recv INTEGER DEFAULT 0,
                    duration INTEGER DEFAULT 0
                )
            ''')
            
            # Active connections table for real-time tracking
            db.execute('''
                CREATE TABLE IF NOT EXISTS active_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    server_port INTEGER,
                    connected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    bytes_sent INTEGER DEFAULT 0,
                    bytes_recv INTEGER DEFAULT 0,
                    UNIQUE(username, client_ip, server_port)
                )
            ''')
            
            db.commit()
            print("✅ Database tables initialized for connection tracking")
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
        finally:
            db.close()
            
    def get_active_connections_conntrack(self):
        """Get active connections using conntrack with detailed information"""
        try:
            # Get UDP connections on VPN ports
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
                    dst_ip = None
                    src_port = None
                    dst_port = None
                    bytes_sent = 0
                    bytes_recv = 0
                    timestamp = None
                    
                    for part in parts:
                        if part.startswith('src='):
                            src_ip = part.split('=')[1]
                        elif part.startswith('dst='):
                            dst_ip = part.split('=')[1]
                        elif part.startswith('sport='):
                            src_port = part.split('=')[1]
                        elif part.startswith('dport='):
                            dst_port = part.split('=')[1]
                        elif part.startswith('bytes='):
                            bytes_info = part.split('=')[1]
                            if '=' in bytes_info:
                                sent, recv = bytes_info.split('=')
                                bytes_sent = int(sent)
                                bytes_recv = int(recv)
                    
                    # Extract timestamp from conntrack output
                    for part in parts:
                        if part.startswith('[') and ']' in part:
                            timestamp_str = part.strip('[]')
                            try:
                                timestamp = datetime.fromtimestamp(int(timestamp_str))
                            except:
                                pass
                    
                    if src_ip and dst_port:
                        connections.append({
                            'client_ip': src_ip,
                            'server_port': dst_port,
                            'bytes_sent': bytes_sent,
                            'bytes_recv': bytes_recv,
                            'timestamp': timestamp or datetime.now()
                        })
                        
                except Exception as e:
                    continue
                    
            return connections
        except Exception as e:
            print(f"Error getting conntrack connections: {e}")
            return []
            
    def get_user_from_port(self, port):
        """Find username from port number"""
        db = self.get_db()
        try:
            user = db.execute(
                'SELECT username FROM users WHERE port = ? OR ? = "5667"',
                (port, port)
            ).fetchone()
            return user['username'] if user else None
        finally:
            db.close()
            
    def update_connection_logs(self, active_connections):
        """Update connection logs with current active connections"""
        db = self.get_db()
        try:
            current_time = datetime.now()
            
            # Get existing active connections from database
            existing_conns = db.execute(
                'SELECT username, client_ip, server_port, connected_at FROM active_connections'
            ).fetchall()
            existing_conns = {f"{row['username']}_{row['client_ip']}_{row['server_port']}": row for row in existing_conns}
            
            # Process current active connections
            for conn_info in active_connections:
                username = conn_info.get('username')
                if not username:
                    continue
                    
                conn_key = f"{username}_{conn_info['client_ip']}_{conn_info['server_port']}"
                
                if conn_key in existing_conns:
                    # Update existing connection
                    db.execute('''
                        UPDATE active_connections 
                        SET last_updated = ?, bytes_sent = ?, bytes_recv = ?
                        WHERE username = ? AND client_ip = ? AND server_port = ?
                    ''', (current_time, conn_info.get('bytes_sent', 0), 
                          conn_info.get('bytes_recv', 0), username, 
                          conn_info['client_ip'], conn_info['server_port']))
                    
                    # Remove from existing connections dict
                    existing_conns.pop(conn_key)
                else:
                    # New connection - add to active_connections and connection_logs
                    db.execute('''
                        INSERT INTO active_connections 
                        (username, client_ip, server_port, bytes_sent, bytes_recv)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (username, conn_info['client_ip'], conn_info['server_port'],
                          conn_info.get('bytes_sent', 0), conn_info.get('bytes_recv', 0)))
                    
                    db.execute('''
                        INSERT INTO connection_logs 
                        (username, client_ip, server_port, connected_at, bytes_sent, bytes_recv)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (username, conn_info['client_ip'], conn_info['server_port'],
                          current_time, conn_info.get('bytes_sent', 0), 
                          conn_info.get('bytes_recv', 0)))
            
            # Mark disconnected connections
            for conn_key, conn_data in existing_conns.items():
                disconnected_time = current_time
                connected_time = datetime.strptime(conn_data['connected_at'], '%Y-%m-%d %H:%M:%S')
                duration = (disconnected_time - connected_time).total_seconds()
                
                # Update connection_logs with disconnect time and duration
                db.execute('''
                    UPDATE connection_logs 
                    SET disconnected_at = ?, duration = ?
                    WHERE username = ? AND client_ip = ? AND server_port = ? 
                    AND disconnected_at IS NULL
                ''', (disconnected_time, duration, conn_data['username'], 
                      conn_data['client_ip'], conn_data['server_port']))
                
                # Remove from active_connections
                db.execute('''
                    DELETE FROM active_connections 
                    WHERE username = ? AND client_ip = ? AND server_port = ?
                ''', (conn_data['username'], conn_data['client_ip'], conn_data['server_port']))
                
                print(f"📤 User {conn_data['username']} disconnected from {conn_data['client_ip']}")
            
            db.commit()
            
        except Exception as e:
            print(f"Error updating connection logs: {e}")
        finally:
            db.close()
            
    def get_live_connections(self):
        """Get live connections with username mapping"""
        conntrack_conns = self.get_active_connections_conntrack()
        live_connections = []
        
        for conn in conntrack_conns:
            username = self.get_user_from_port(conn['server_port'])
            if username:
                connected_time = conn.get('timestamp', datetime.now())
                duration = (datetime.now() - connected_time).total_seconds()
                
                live_connections.append({
                    'username': username,
                    'client_ip': conn['client_ip'],
                    'server_port': conn['server_port'],
                    'connected_at': connected_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': duration,
                    'bytes_sent': conn.get('bytes_sent', 0),
                    'bytes_recv': conn.get('bytes_recv', 0)
                })
        
        return live_connections
        
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
            
            active_connections = self.get_live_connections()
            
            for user in users:
                username = user['username']
                max_connections = user['concurrent_conn']
                user_port = str(user['port'] or '5667')
                
                # Count connections for this user
                user_connections = [conn for conn in active_connections if conn['username'] == username]
                user_conn_count = len(user_connections)
                
                # If over limit, drop oldest connections
                if user_conn_count > max_connections:
                    print(f"⚠️ User {username} has {user_conn_count} connections (limit: {max_connections})")
                    
                    # Sort by duration (oldest first) and drop excess
                    user_connections.sort(key=lambda x: x['duration'])
                    excess = user_conn_count - max_connections
                    
                    for i in range(excess):
                        if i < len(user_connections):
                            conn_to_drop = user_connections[i]
                            self.drop_connection(conn_to_drop['client_ip'], conn_to_drop['server_port'])
                            
        except Exception as e:
            print(f"Error enforcing connection limits: {e}")
        finally:
            db.close()
            
    def drop_connection(self, client_ip, server_port):
        """Drop a specific connection using conntrack"""
        try:
            subprocess.run(
                f"conntrack -D -p udp --dport {server_port} --src {client_ip}",
                shell=True, capture_output=True
            )
            print(f"🔴 Dropped connection: {client_ip}:{server_port}")
        except Exception as e:
            print(f"Error dropping connection {client_ip}:{server_port}: {e}")
            
    def update_user_bandwidth(self):
        """Update user bandwidth usage from connection logs"""
        db = self.get_db()
        try:
            # Get total bandwidth used from active connections
            active_bw = db.execute('''
                SELECT username, SUM(bytes_sent + bytes_recv) as total_bytes
                FROM active_connections 
                GROUP BY username
            ''').fetchall()
            
            for row in active_bw:
                db.execute('''
                    UPDATE users 
                    SET bandwidth_used = bandwidth_used + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE username = ?
                ''', (row['total_bytes'], row['username']))
            
            db.commit()
            
        except Exception as e:
            print(f"Error updating user bandwidth: {e}")
        finally:
            db.close()
            
    def get_connection_stats(self):
        """Get connection statistics"""
        db = self.get_db()
        try:
            # Total active connections
            total_conns = db.execute('SELECT COUNT(*) as count FROM active_connections').fetchone()['count']
            
            # Unique users connected
            unique_users = db.execute('SELECT COUNT(DISTINCT username) as count FROM active_connections').fetchone()['count']
            
            # Total bandwidth in active connections
            total_bw = db.execute('SELECT SUM(bytes_sent + bytes_recv) as total FROM active_connections').fetchone()['total'] or 0
            
            return {
                'total_connections': total_conns,
                'unique_users': unique_users,
                'total_bandwidth': total_bw
            }
        finally:
            db.close()
            
    def cleanup_old_connections(self):
        """Cleanup connection logs older than 30 days"""
        db = self.get_db()
        try:
            db.execute('''
                DELETE FROM connection_logs 
                WHERE connected_at < datetime('now', '-30 days')
            ''')
            db.commit()
            print("🧹 Cleaned up old connection logs")
        except Exception as e:
            print(f"Error cleaning up old connections: {e}")
        finally:
            db.close()
            
    def monitoring_loop(self):
        """Main monitoring loop"""
        print("🔄 Starting connection monitoring loop...")
        
        while self.running:
            try:
                # Get live connections and update database
                live_connections = self.get_live_connections()
                self.update_connection_logs(live_connections)
                
                # Enforce connection limits
                self.enforce_connection_limits()
                
                # Update bandwidth usage
                self.update_user_bandwidth()
                
                # Cleanup every hour
                if datetime.now().minute == 0:
                    self.cleanup_old_connections()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"Monitoring loop error: {e}")
                time.sleep(30)
                
    def start_monitoring(self):
        """Start the connection monitoring"""
        self.initialize_database()
        monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        monitor_thread.start()
        print("✅ Connection Manager started successfully")

# Global instance
connection_manager = ConnectionManager()

# Flask API for connection data
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/v1/connections', methods=['GET'])
def get_connections_api():
    """API endpoint to get active connections"""
    connections = connection_manager.get_live_connections()
    return jsonify({'connections': connections})

@app.route('/api/v1/connection_stats', methods=['GET'])
def get_connection_stats_api():
    """API endpoint to get connection statistics"""
    stats = connection_manager.get_connection_stats()
    return jsonify(stats)

@app.route('/api/v1/users/<username>/connections', methods=['GET'])
def get_user_connections_api(username):
    """API endpoint to get user connections"""
    connections = connection_manager.get_live_connections()
    user_connections = [conn for conn in connections if conn['username'] == username]
    return jsonify({'connections': user_connections})

def start_api_server():
    """Start the API server"""
    print("🌐 Starting Connection Manager API on port 8082...")
    app.run(host='0.0.0.0', port=8082, debug=False, threaded=True)

if __name__ == "__main__":
    print("🚀 Starting ZIVPN Connection Manager...")
    
    # Start connection monitoring
    connection_manager.start_monitoring()
    
    # Start API server
    start_api_server()
  
