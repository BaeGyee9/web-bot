#!/usr/bin/env python3
"""
ZIVPN Enhanced Connection Manager
Features: Real-time Dashboard, Connection Scheduling, Device Fingerprinting
Author: BaeGyee9
"""

import sqlite3
import subprocess
import time
import threading
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
import os

DATABASE_PATH = "/etc/zivpn/zivpn.db"

class EnhancedConnectionManager:
    def __init__(self):
        self.connection_tracker = {}
        self.device_registry = {}
        self.schedule_cache = {}
        self.lock = threading.Lock()
        self.load_device_registry()
        
    def get_db(self):
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
        
    def generate_device_fingerprint(self, client_ip, user_agent=""):
        """Generate unique device fingerprint"""
        fingerprint_data = f"{client_ip}_{user_agent}_{datetime.now().timestamp()}"
        device_hash = hashlib.md5(fingerprint_data.encode()).hexdigest()
        return device_hash
        
    def load_device_registry(self):
        """Load device fingerprints from database"""
        db = self.get_db()
        try:
            devices = db.execute('SELECT username, device_hash, mac_address, registered_at FROM device_fingerprints').fetchall()
            for device in devices:
                username = device['username']
                if username not in self.device_registry:
                    self.device_registry[username] = []
                self.device_registry[username].append({
                    'device_hash': device['device_hash'],
                    'mac_address': device['mac_address'],
                    'registered_at': device['registered_at']
                })
        except sqlite3.OperationalError:
            # Table doesn't exist yet, will be created later
            pass
        finally:
            db.close()
            
    def register_device(self, username, client_ip, user_agent="", mac_address=""):
        """Register new device for user"""
        device_hash = self.generate_device_fingerprint(client_ip, user_agent)
        
        db = self.get_db()
        try:
            db.execute('''
                INSERT OR REPLACE INTO device_fingerprints 
                (username, device_hash, mac_address, client_ip, user_agent, registered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, device_hash, mac_address, client_ip, user_agent, datetime.now()))
            db.commit()
            
            # Update cache
            if username not in self.device_registry:
                self.device_registry[username] = []
            self.device_registry[username].append({
                'device_hash': device_hash,
                'mac_address': mac_address,
                'registered_at': datetime.now().isoformat()
            })
            
            return device_hash
        finally:
            db.close()
            
    def validate_device(self, username, device_hash):
        """Validate if device is authorized for user"""
        if username not in self.device_registry:
            return False
            
        authorized_devices = self.device_registry[username]
        for device in authorized_devices:
            if device['device_hash'] == device_hash:
                return True
        return False
        
    def get_user_schedule(self, username):
        """Get connection schedule for user"""
        if username in self.schedule_cache:
            return self.schedule_cache[username]
            
        db = self.get_db()
        try:
            schedule = db.execute(
                'SELECT schedule_data FROM user_schedules WHERE username = ?', 
                (username,)
            ).fetchone()
            
            if schedule and schedule['schedule_data']:
                schedule_obj = json.loads(schedule['schedule_data'])
                self.schedule_cache[username] = schedule_obj
                return schedule_obj
            return None
        finally:
            db.close()
            
    def is_within_schedule(self, username):
        """Check if current time is within user's allowed schedule"""
        schedule = self.get_user_schedule(username)
        if not schedule:
            return True  # No schedule restrictions
            
        current_time = datetime.now().time()
        current_day = datetime.now().strftime("%A").lower()
        
        if 'allowed_hours' in schedule:
            start_time = datetime.strptime(schedule['allowed_hours']['start'], "%H:%M").time()
            end_time = datetime.strptime(schedule['allowed_hours']['end'], "%H:%M").time()
            
            if not (start_time <= current_time <= end_time):
                return False
                
        if 'allowed_days' in schedule:
            if current_day not in schedule['allowed_days']:
                return False
                
        return True
        
    def get_active_connections(self):
        """Get all active connections with enhanced details"""
        try:
            # Get conntrack data
            result = subprocess.run(
                "conntrack -L -p udp 2>/dev/null | grep -E 'dport=(5667|[6-9][0-9]{3}|[1-9][0-9]{4})'",
                shell=True, capture_output=True, text=True
            )
            
            connections = []
            for line in result.stdout.split('\n'):
                if 'src=' in line and 'dport=' in line:
                    try:
                        parts = line.split()
                        connection_info = {
                            'src_ip': None,
                            'dport': None,
                            'bytes': 0,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        for part in parts:
                            if part.startswith('src='):
                                connection_info['src_ip'] = part.split('=')[1]
                            elif part.startswith('dport='):
                                connection_info['dport'] = part.split('=')[1]
                            elif part.startswith('bytes='):
                                connection_info['bytes'] = int(part.split('=')[1])
                                
                        if connection_info['src_ip'] and connection_info['dport']:
                            connections.append(connection_info)
                    except Exception as e:
                        continue
            return connections
        except Exception as e:
            print(f"Error getting connections: {e}")
            return []
            
    def get_connection_dashboard(self):
        """Get comprehensive connection dashboard data"""
        db = self.get_db()
        try:
            # Get user connection statistics
            user_stats = db.execute('''
                SELECT u.username, u.status, u.concurrent_conn, 
                       COUNT(df.device_hash) as registered_devices,
                       (SELECT COUNT(*) FROM user_schedules WHERE username = u.username) as has_schedule
                FROM users u
                LEFT JOIN device_fingerprints df ON u.username = df.username
                GROUP BY u.username
            ''').fetchall()
            
            active_connections = self.get_active_connections()
            
            # Group connections by port/user
            connections_by_port = {}
            for conn in active_connections:
                port = conn['dport']
                if port not in connections_by_port:
                    connections_by_port[port] = []
                connections_by_port[port].append(conn)
            
            dashboard_data = {
                'total_active_connections': len(active_connections),
                'total_registered_users': len(user_stats),
                'connections_by_port': connections_by_port,
                'user_statistics': [dict(user) for user in user_stats],
                'timestamp': datetime.now().isoformat()
            }
            
            return dashboard_data
        finally:
            db.close()
            
    def enforce_connection_policies(self, username, client_ip, user_agent=""):
        """Enforce all connection policies for a user"""
        violations = []
        
        # 1. Check device fingerprint
        device_hash = self.generate_device_fingerprint(client_ip, user_agent)
        if not self.validate_device(username, device_hash):
            # Auto-register device if not exists
            self.register_device(username, client_ip, user_agent)
            # violations.append("New device registered")
        
        # 2. Check connection schedule
        if not self.is_within_schedule(username):
            violations.append("Connection not allowed at this time")
            
        # 3. Check concurrent connections
        db = self.get_db()
        try:
            user_data = db.execute(
                'SELECT concurrent_conn FROM users WHERE username = ?', 
                (username,)
            ).fetchone()
            
            if user_data:
                max_connections = user_data['concurrent_conn']
                active_connections = self.get_active_connections()
                user_conn_count = sum(1 for conn in active_connections 
                                    if self.get_username_by_ip(conn['src_ip']) == username)
                
                if user_conn_count >= max_connections:
                    violations.append(f"Maximum connections ({max_connections}) exceeded")
                    
        finally:
            db.close()
            
        return violations
        
    def get_username_by_ip(self, ip_address):
        """Get username by IP address (simplified - in real implementation would need mapping)"""
        # This is a simplified version - real implementation would need proper IP-username mapping
        db = self.get_db()
        try:
            # You would need to maintain an IP-username mapping table
            user = db.execute(
                'SELECT username FROM ip_assignments WHERE ip_address = ?', 
                (ip_address,)
            ).fetchone()
            return user['username'] if user else None
        except:
            return None
        finally:
            db.close()

# Global instance
connection_manager = EnhancedConnectionManager()

# Flask Blueprint for API routes
connection_api = Blueprint('connection_api', __name__)

@connection_api.route('/api/connections/dashboard', methods=['GET'])
def get_dashboard():
    """Get real-time connection dashboard"""
    dashboard_data = connection_manager.get_connection_dashboard()
    return jsonify(dashboard_data)

@connection_api.route('/api/connections/device/register', methods=['POST'])
def register_device():
    """Register a new device for user"""
    data = request.get_json()
    username = data.get('username')
    client_ip = data.get('client_ip')
    user_agent = data.get('user_agent', '')
    mac_address = data.get('mac_address', '')
    
    device_hash = connection_manager.register_device(username, client_ip, user_agent, mac_address)
    return jsonify({'device_hash': device_hash, 'status': 'registered'})

@connection_api.route('/api/connections/schedule', methods=['POST'])
def set_schedule():
    """Set connection schedule for user"""
    data = request.get_json()
    username = data.get('username')
    schedule_data = data.get('schedule_data')
    
    db = connection_manager.get_db()
    try:
        db.execute('''
            INSERT OR REPLACE INTO user_schedules 
            (username, schedule_data, updated_at)
            VALUES (?, ?, ?)
        ''', (username, json.dumps(schedule_data), datetime.now()))
        db.commit()
        
        # Update cache
        connection_manager.schedule_cache[username] = schedule_data
        
        return jsonify({'status': 'success'})
    finally:
        db.close()

@connection_api.route('/api/connections/validate', methods=['POST'])
def validate_connection():
    """Validate connection against all policies"""
    data = request.get_json()
    username = data.get('username')
    client_ip = data.get('client_ip')
    user_agent = data.get('user_agent', '')
    
    violations = connection_manager.enforce_connection_policies(username, client_ip, user_agent)
    
    if violations:
        return jsonify({'allowed': False, 'violations': violations})
    else:
        return jsonify({'allowed': True, 'violations': []})

def start_connection_monitoring():
    """Start the connection monitoring loop"""
    def monitor_loop():
        while True:
            try:
                # Update dashboard data every 30 seconds
                connection_manager.get_connection_dashboard()
                time.sleep(30)
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(60)
                
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()

if __name__ == "__main__":
    print("Starting Enhanced Connection Manager...")
    start_connection_monitoring()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping Enhanced Connection Manager...")
