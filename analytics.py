#!/usr/bin/env python3
"""
ZIVPN Analytics Engine - Business Intelligence & Reporting
Enterprise Edition
"""
import sqlite3
import json
from datetime import datetime, timedelta
import os
import logging
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")

class ZIVPNAnalytics:
    def __init__(self):
        self.db_path = DATABASE_PATH
        
    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def get_revenue_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get revenue analytics for specified period"""
        db = self.get_db()
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Revenue by plan type
            revenue_by_plan = db.execute('''
                SELECT 
                    plan_type,
                    COUNT(*) as user_count,
                    SUM(amount) as total_revenue,
                    AVG(amount) as avg_revenue
                FROM billing 
                WHERE created_at >= ? AND payment_status = 'completed'
                GROUP BY plan_type
                ORDER BY total_revenue DESC
            ''', (cutoff_date,)).fetchall()
            
            # Daily revenue trend
            daily_revenue = db.execute('''
                SELECT 
                    date(created_at) as revenue_date,
                    SUM(amount) as daily_revenue,
                    COUNT(*) as daily_transactions
                FROM billing 
                WHERE created_at >= ? AND payment_status = 'completed'
                GROUP BY date(created_at)
                ORDER BY revenue_date
            ''', (cutoff_date,)).fetchall()
            
            # Total revenue metrics
            total_metrics = db.execute('''
                SELECT 
                    SUM(amount) as total_revenue,
                    COUNT(*) as total_transactions,
                    AVG(amount) as avg_transaction_value
                FROM billing 
                WHERE created_at >= ? AND payment_status = 'completed'
            ''', (cutoff_date,)).fetchone()
            
            return {
                'revenue_by_plan': [dict(row) for row in revenue_by_plan],
                'daily_revenue_trend': [dict(row) for row in daily_revenue],
                'total_metrics': dict(total_metrics) if total_metrics else {},
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting revenue analytics: {e}")
            return {}
        finally:
            db.close()
            
    def get_user_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get user growth and engagement analytics"""
        db = self.get_db()
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # User growth trend
            user_growth = db.execute('''
                SELECT 
                    date(created_at) as growth_date,
                    COUNT(*) as new_users,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_users
                FROM users 
                WHERE created_at >= ?
                GROUP BY date(created_at)
                ORDER BY growth_date
            ''', (cutoff_date,)).fetchall()
            
            # User retention analysis
            retention_analysis = db.execute('''
                SELECT 
                    plan_type,
                    COUNT(*) as total_users,
                    AVG(julianday(expires) - julianday(created_at)) as avg_days_retained,
                    SUM(CASE WHEN expires >= date('now') THEN 1 ELSE 0 END) as active_users,
                    SUM(CASE WHEN expires < date('now') THEN 1 ELSE 0 END) as expired_users
                FROM users u
                LEFT JOIN billing b ON u.username = b.username
                WHERE u.created_at >= ?
                GROUP BY plan_type
            ''', (cutoff_date,)).fetchall()
            
            # User activity levels
            activity_levels = db.execute('''
                SELECT 
                    u.username,
                    u.plan_type,
                    u.status,
                    u.bandwidth_used,
                    COUNT(DISTINCT date(us.start_time)) as active_days,
                    SUM(us.duration_seconds) as total_connection_time
                FROM users u
                LEFT JOIN user_sessions us ON u.username = us.username AND us.start_time >= ?
                WHERE u.created_at >= ?
                GROUP BY u.username
                ORDER BY u.bandwidth_used DESC
                LIMIT 50
            ''', (cutoff_date, cutoff_date)).fetchall()
            
            return {
                'user_growth_trend': [dict(row) for row in user_growth],
                'retention_analysis': [dict(row) for row in retention_analysis],
                'top_active_users': [dict(row) for row in activity_levels],
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}
        finally:
            db.close()
            
    def get_bandwidth_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get bandwidth usage analytics"""
        db = self.get_db()
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Daily bandwidth usage
            daily_bandwidth = db.execute('''
                SELECT 
                    date(start_time) as usage_date,
                    SUM(bytes_received) as daily_bandwidth,
                    COUNT(DISTINCT username) as daily_active_users
                FROM user_sessions 
                WHERE start_time >= ?
                GROUP BY date(start_time)
                ORDER BY usage_date
            ''', (cutoff_date,)).fetchall()
            
            # Bandwidth by user plan
            bandwidth_by_plan = db.execute('''
                SELECT 
                    b.plan_type,
                    COUNT(DISTINCT u.username) as user_count,
                    SUM(u.bandwidth_used) as total_bandwidth,
                    AVG(u.bandwidth_used) as avg_bandwidth_per_user
                FROM users u
                LEFT JOIN billing b ON u.username = b.username
                WHERE u.created_at >= ?
                GROUP BY b.plan_type
                ORDER BY total_bandwidth DESC
            ''', (cutoff_date,)).fetchall()
            
            # Peak usage hours
            peak_usage = db.execute('''
                SELECT 
                    strftime('%H:00', start_time) as hour_of_day,
                    COUNT(*) as connection_count,
                    SUM(bytes_received) as bandwidth_used
                FROM user_sessions 
                WHERE start_time >= ?
                GROUP BY strftime('%H', start_time)
                ORDER BY bandwidth_used DESC
                LIMIT 10
            ''', (cutoff_date,)).fetchall()
            
            return {
                'daily_bandwidth': [dict(row) for row in daily_bandwidth],
                'bandwidth_by_plan': [dict(row) for row in bandwidth_by_plan],
                'peak_usage_hours': [dict(row) for row in peak_usage],
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting bandwidth analytics: {e}")
            return {}
        finally:
            db.close()
            
    def get_system_health_analytics(self) -> Dict[str, Any]:
        """Get system health and performance analytics"""
        db = self.get_db()
        try:
            # Connection success rate
            connection_stats = db.execute('''
                SELECT 
                    date(start_time) as stat_date,
                    COUNT(*) as total_connections,
                    SUM(CASE WHEN duration_seconds > 60 THEN 1 ELSE 0 END) as successful_connections,
                    AVG(duration_seconds) as avg_duration
                FROM user_sessions 
                WHERE start_time >= datetime('now', '-7 days')
                GROUP BY date(start_time)
                ORDER BY stat_date DESC
                LIMIT 7
            ''').fetchall()
            
            # Server load estimation
            server_load = db.execute('''
                SELECT 
                    date(start_time) as load_date,
                    MAX((
                        SELECT COUNT(*) 
                        FROM live_connections lc 
                        WHERE datetime(lc.last_update) >= datetime(us.start_time, '-5 minutes')
                    )) as peak_concurrent,
                    COUNT(DISTINCT username) as daily_active_users
                FROM user_sessions us
                WHERE start_time >= datetime('now', '-7 days')
                GROUP BY date(start_time)
                ORDER BY load_date DESC
                LIMIT 7
            ''').fetchall()
            
            # User satisfaction metrics (based on connection duration)
            satisfaction_metrics = db.execute('''
                SELECT 
                    plan_type,
                    COUNT(*) as total_users,
                    AVG(total_duration) as avg_connection_duration,
                    SUM(CASE WHEN total_duration > 3600 THEN 1 ELSE 0 END) as satisfied_users,
                    SUM(CASE WHEN total_duration < 300 THEN 1 ELSE 0 END) as unsatisfied_users
                FROM (
                    SELECT 
                        u.username,
                        b.plan_type,
                        SUM(us.duration_seconds) as total_duration
                    FROM users u
                    LEFT JOIN billing b ON u.username = b.username
                    LEFT JOIN user_sessions us ON u.username = us.username AND us.start_time >= datetime('now', '-7 days')
                    GROUP BY u.username
                ) user_stats
                GROUP BY plan_type
            ''').fetchall()
            
            return {
                'connection_stats': [dict(row) for row in connection_stats],
                'server_load': [dict(row) for row in server_load],
                'satisfaction_metrics': [dict(row) for row in satisfaction_metrics]
            }
            
        except Exception as e:
            logger.error(f"Error getting system health analytics: {e}")
            return {}
        finally:
            db.close()
            
    def get_business_intelligence(self) -> Dict[str, Any]:
        """Comprehensive business intelligence report"""
        return {
            'revenue_analytics': self.get_revenue_analytics(30),
            'user_analytics': self.get_user_analytics(30),
            'bandwidth_analytics': self.get_bandwidth_analytics(30),
            'system_health': self.get_system_health_analytics(),
            'report_generated': datetime.now().isoformat()
        }
        
    def export_analytics_report(self, file_path: str = None) -> str:
        """Export analytics report to JSON file"""
        if not file_path:
            file_path = f"/etc/zivpn/analytics/analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        report_data = self.get_business_intelligence()
        
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
            
        logger.info(f"Analytics report exported to: {file_path}")
        return file_path

# Global instance
analytics_engine = ZIVPNAnalytics()

if __name__ == "__main__":
    # Test the analytics engine
    report = analytics_engine.get_business_intelligence()
    print("ZIVPN Analytics Report Generated Successfully!")
    print(f"Revenue Analytics: {len(report['revenue_analytics'])} metrics")
    print(f"User Analytics: {len(report['user_analytics'])} metrics") 
    print(f"Bandwidth Analytics: {len(report['bandwidth_analytics'])} metrics")
    
    # Export report
    export_path = analytics_engine.export_analytics_report()
    print(f"Report exported to: {export_path}")
  
