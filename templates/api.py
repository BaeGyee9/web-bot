from flask import Flask, jsonify, request
import sqlite3, datetime
from datetime import timedelta
import os
import subprocess
import json

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
    
    # Get active connections from connection manager
    try:
        import requests
        conn_stats = requests.get('http://localhost:8082/api/v1/connection_stats', timeout=2).json()
        active_connections = conn_stats.get('total_connections', 0)
        unique_connected_users = conn_stats.get('unique_users', 0)
    except:
        active_connections = 0
        unique_connected_users = 0
    
    db.close()
    return jsonify({
        "total_users": stats['total_users'],
        "active_users": stats['active_users'],
        "active_connections": active_connections,
        "unique_connected_users": unique_connected_users,
        "total_bandwidth_bytes": stats['total_bandwidth']
    })

@app.route('/api/v1/users', methods=['GET'])
def get_users():
    db = get_db()
    users = db.execute('''
        SELECT username, status, expires, bandwidth_used, concurrent_conn,
               (SELECT COUNT(*) FROM active_connections WHERE username = users.username) as active_connections
        FROM users
    ''').fetchall()
    db.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/v1/user/<username>', methods=['GET'])
def get_user(username):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    
    # Get active connections for this user
    try:
        import requests
        user_conns = requests.get(f'http://localhost:8082/api/v1/users/{username}/connections', timeout=2).json()
        active_connections = user_conns.get('connections', [])
    except:
        active_connections = []
    
    db.close()
    
    if user:
        user_data = dict(user)
        user_data['active_connections'] = active_connections
        return jsonify(user_data)
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

@app.route('/api/v1/connections', methods=['GET'])
def get_connections():
    """Get active connections from connection manager"""
    try:
        import requests
        connections = requests.get('http://localhost:8082/api/v1/connections', timeout=2).json()
        return jsonify(connections)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/connections/stats', methods=['GET'])
def get_connections_stats():
    """Get connection statistics"""
    try:
        import requests
        stats = requests.get('http://localhost:8082/api/v1/connection_stats', timeout=2).json()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/top_users', methods=['GET'])
def get_top_users():
    """Get top users by bandwidth usage"""
    db = get_db()
    try:
        top_users = db.execute('''
            SELECT username, bandwidth_used, 
                   (SELECT COUNT(*) FROM active_connections WHERE username = users.username) as active_connections
            FROM users 
            WHERE bandwidth_used > 0 
            ORDER BY bandwidth_used DESC 
            LIMIT 10
        ''').fetchall()
        
        return jsonify([dict(user) for user in top_users])
    finally:
        db.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
