#!/usr/bin/env python3
"""
ZIVPN Enterprise Web Panel - Enhanced UUID Version
X-UI Style Modern Interface with UUID Authentication
"""

from flask import Flask, jsonify, render_template_string, request, redirect, url_for, session, make_response, g
import json, re, subprocess, os, tempfile, hmac, sqlite3, datetime, uuid
from datetime import datetime, timedelta
import statistics
import requests

# Configuration
USERS_FILE = "/etc/zivpn/users.json"
CONFIG_FILE = "/etc/zivpn/config.json"
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")
LISTEN_FALLBACK = "5667"
RECENT_SECONDS = 120
LOGO_URL = "https://raw.githubusercontent.com/BaeGyee9/khaing/main/logo.png"

# GitHub Template URL
HTML_TEMPLATE_URL = "https://raw.githubusercontent.com/BaeGyee9/web-bot/main/templates/index.html"

# --- Localization Data ---
TRANSLATIONS = {
    'en': {
        'title': 'ZIVPN Enterprise Panel', 'login_title': 'ZIVPN Panel Login',
        'login_err': 'Invalid Username or Password', 'username': 'Username',
        'password': 'Password', 'login': 'Login', 'logout': 'Logout',
        'contact': 'Contact', 'total_users': 'Total Users',
        'active_users': 'Online Users', 'bandwidth_used': 'Bandwidth Used',
        'server_load': 'Server Load', 'user_management': 'User Management',
        'add_user': 'Add New User', 'bulk_ops': 'Bulk Operations',
        'reports': 'Reports', 'user': 'User', 'expires': 'Expires',
        'port': 'Port', 'bandwidth': 'Bandwidth', 'speed': 'Speed',
        'status': 'Status', 'actions': 'Actions', 'online': 'ONLINE',
        'offline': 'OFFLINE', 'expired': 'EXPIRED', 'suspended': 'SUSPENDED',
        'save_user': 'Save User', 'max_conn': 'Max Connections',
        'speed_limit': 'Speed Limit (MB/s)', 'bw_limit': 'Bandwidth Limit (GB)',
        'required_fields': 'User and Password are required',
        'invalid_exp': 'Invalid Expires format',
        'invalid_port': 'Port range must be 6000-19999',
        'delete_confirm': 'Are you sure you want to delete {user}?',
        'deleted': 'Deleted: {user}', 'success_save': 'User saved successfully',
        'select_action': 'Select Action', 'extend_exp': 'Extend Expiry (+7 days)',
        'suspend_users': 'Suspend Users', 'activate_users': 'Activate Users',
        'delete_users': 'Delete Users', 'execute': 'Execute',
        'user_search': 'Search users...', 'search': 'Search',
        'export_csv': 'Export Users CSV', 'import_users': 'Import Users',
        'bulk_success': 'Bulk action {action} completed',
        'report_range': 'Date Range Required', 'report_bw': 'Bandwidth Usage',
        'report_users': 'User Activity', 'report_revenue': 'Revenue',
        'home': 'Home', 'manage': 'Manage Users', 'settings': 'Settings',
        'dashboard': 'Dashboard', 'system_status': 'System Status',
        'quick_actions': 'Quick Actions', 'recent_activity': 'Recent Activity',
        'server_info': 'Server Information', 'vpn_status': 'VPN Status',
        'active_connections': 'Active Connections',
        'email_remark': 'Email/Remark', 'data_limit': 'Data Limit (GB)',
        'generate_account': 'Generate Account', 'unlimited': 'Unlimited',
        'user_details': 'User Details', 'copy_uuid': 'Copy UUID',
        'extend_days': 'Extend Days', 'toggle_status': 'Toggle Status'
    },
    'my': {
        'title': 'ZIVPN စီမံခန့်ခွဲမှု Panel', 'login_title': 'ZIVPN Panel ဝင်ရန်',
        'login_err': 'အသုံးပြုသူအမည် (သို့) စကားဝှက် မမှန်ပါ', 'username': 'အသုံးပြုသူအမည်',
        'password': 'စကားဝှက်', 'login': 'ဝင်မည်', 'logout': 'ထွက်မည်',
        'contact': 'ဆက်သွယ်ရန်', 'total_users': 'စုစုပေါင်းအသုံးပြုသူ',
        'active_users': 'အွန်လိုင်းအသုံးပြုသူ', 'bandwidth_used': 'အသုံးပြုပြီး Bandwidth',
        'server_load': 'ဆာဗာ ဝန်ပမာဏ', 'user_management': 'အသုံးပြုသူ စီမံခန့်ခွဲမှု',
        'add_user': 'အသုံးပြုသူ အသစ်ထည့်ရန်', 'bulk_ops': 'အစုလိုက် လုပ်ဆောင်ချက်များ',
        'reports': 'အစီရင်ခံစာများ', 'user': 'အသုံးပြုသူ', 'expires': 'သက်တမ်းကုန်ဆုံးမည်',
        'port': 'ပေါက်', 'bandwidth': 'Bandwidth', 'speed': 'မြန်နှုန်း',
        'status': 'အခြေအနေ', 'actions': 'လုပ်ဆောင်ချက်များ', 'online': 'အွန်လိုင်း',
        'offline': 'အော့ဖ်လိုင်း', 'expired': 'သက်တမ်းကုန်ဆုံး', 'suspended': 'ဆိုင်းငံ့ထားသည်',
        'save_user': 'အသုံးပြုသူ သိမ်းမည်', 'max_conn': 'အများဆုံးချိတ်ဆက်မှု',
        'speed_limit': 'မြန်နှုန်း ကန့်သတ်ချက် (MB/s)', 'bw_limit': 'Bandwidth ကန့်သတ်ချက် (GB)',
        'required_fields': 'အသုံးပြုသူအမည်နှင့် စကားဝှက် လိုအပ်သည်',
        'invalid_exp': 'သက်တမ်းကုန်ဆုံးရက်ပုံစံ မမှန်ကန်ပါ',
        'invalid_port': 'Port အကွာအဝေး 6000-19999 သာ ဖြစ်ရမည်',
        'delete_confirm': '{user} ကို ဖျက်ရန် သေချာပါသလား?',
        'deleted': 'ဖျက်လိုက်သည်: {user}', 'success_save': 'အသုံးပြုသူကို အောင်မြင်စွာ သိမ်းဆည်းလိုက်သည်',
        'select_action': 'လုပ်ဆောင်ချက် ရွေးပါ', 'extend_exp': 'သက်တမ်းတိုးမည် (+၇ ရက်)',
        'suspend_users': 'အသုံးပြုသူများ ဆိုင်းငံ့မည်', 'activate_users': 'အသုံးပြုသူများ ဖွင့်မည်',
        'delete_users': 'အသုံးပြုသူများ ဖျက်မည်', 'execute': 'စတင်လုပ်ဆောင်မည်',
        'user_search': 'အသုံးပြုသူ ရှာဖွေပါ...', 'search': 'ရှာဖွေပါ',
        'export_csv': 'အသုံးပြုသူများ CSV ထုတ်ယူမည်', 'import_users': 'အသုံးပြုသူများ ထည့်သွင်းမည်',
        'bulk_success': 'အစုလိုက် လုပ်ဆောင်ချက် {action} ပြီးမြောက်ပါပြီ',
        'report_range': 'ရက်စွဲ အပိုင်းအခြား လိုအပ်သည်', 'report_bw': 'Bandwidth အသုံးပြုမှု',
        'report_users': 'အသုံးပြုသူ လှုပ်ရှားမှု', 'report_revenue': 'ဝင်ငွေ',
        'home': 'ပင်မစာမျက်နှာ', 'manage': 'အသုံးပြုသူများ စီမံခန့်ခွဲမှု',
        'settings': 'ချိန်ညှိချက်များ', 'dashboard': 'ပင်မစာမျက်နှာ',
        'system_status': 'စနစ်အခြေအနေ', 'quick_actions': 'အမြန်လုပ်ဆောင်ချက်များ',
        'recent_activity': 'လတ်တလောလုပ်ဆောင်မှုများ', 'server_info': 'ဆာဗာအချက်အလက်',
        'vpn_status': 'VPN အခြေအနေ', 'active_connections': 'တက်ကြွလင့်ချိတ်ဆက်မှုများ',
        'email_remark': 'အီးမေးလ်/မှတ်ချက်', 'data_limit': 'ဒေတာ အကန့်အသတ် (GB)',
        'generate_account': 'အကောင့်ဖန်တီးမည်', 'unlimited': 'အကန့်အသတ်မရှိ',
        'user_details': 'အသုံးပြုသူ အချက်အလက်', 'copy_uuid': 'UUID ကူးမည်',
        'extend_days': 'ရက်ပိုမိုတိုးမည်', 'toggle_status': 'အခြေအနေ ပြောင်းမည်'
    }
}

def load_html_template():
    """Load HTML template from GitHub or fallback to local template"""
    try:
        response = requests.get(HTML_TEMPLATE_URL, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"HTTP {response.status_code}")
    except Exception as e:
        print(f"Failed to load template from GitHub: {e}")
        # Fallback to enhanced UUID template
        return ENHANCED_HTML_TEMPLATE

# Enhanced HTML Template with UUID Support
ENHANCED_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="{{lang}}">
<head>
    <meta charset="utf-8">
    <title>{{t.title}} - UUID Edition</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="refresh" content="120">
    <link href="https://fonts.googleapis.com/css2?family=Padauk:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <style>
:root{
    --bg-dark: #0f172a; --fg-dark: #f1f5f9; --card-dark: #1e293b; --bd-dark: #334155; --primary-dark: #3b82f6;
    --bg-light: #f8fafc; --fg-light: #1e293b; --card-light: #ffffff; --bd-light: #e2e8f0; --primary-light: #2563eb;
    --ok: #10b981; --bad: #ef4444; --unknown: #f59e0b; --expired: #8b5cf6;
    --success: #06d6a0; --delete-btn: #ef4444; --logout-btn: #f97316;
    --shadow: 0 10px 25px -5px rgba(0,0,0,0.3), 0 8px 10px -6px rgba(0,0,0,0.2);
    --radius: 16px; --gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
[data-theme='dark']{
    --bg: var(--bg-dark); --fg: var(--fg-dark); --card: var(--card-dark);
    --bd: var(--bd-dark); --primary-btn: var(--primary-dark); --input-text: var(--fg-dark);
}
[data-theme='light']{
    --bg: var(--bg-light); --fg: var(--fg-light); --card: var(--card-light);
    --bd: var(--bd-light); --primary-btn: var(--primary-light); --input-text: var(--fg-light);
}
* {
    box-sizing: border-box;
}
html,body{
    background:var(--bg);color:var(--fg);font-family:'Padauk',sans-serif;
    line-height:1.6;margin:0;padding:0;transition:all 0.3s ease;
    min-height: 100vh;
}
.container{
    max-width:1400px;margin:auto;padding:20px;padding-bottom: 80px;
}

/* Modern Header */
.header {
    background: var(--gradient);
    padding: 20px;
    margin-bottom: 20px;
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    text-align: center;
    position: relative;
    overflow: hidden;
}

.header::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(45deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
    pointer-events: none;
}

.header-content {
    position: relative;
    z-index: 2;
}

.logo-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 15px;
    margin-bottom: 10px;
}

.logo {
    height: 50px;
    width: 50px;
    border-radius: 50%;
    border: 2px solid rgba(255,255,255,0.9);
    background: white;
    padding: 3px;
}

.header h1 {
    margin: 0;
    font-size: 1.8em;
    font-weight: 900;
    color: white;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.header .subtitle {
    color: rgba(255,255,255,0.9);
    font-size: 0.9em;
    margin-top: 5px;
}

/* Bottom Navigation Bar */
.bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--card);
    border-top: 1px solid var(--bd);
    padding: 8px 0;
    z-index: 1000;
    backdrop-filter: blur(10px);
    box-shadow: 0 -4px 20px rgba(0,0,0,0.1);
}

.nav-items {
    display: flex;
    justify-content: space-around;
    align-items: center;
    max-width: 500px;
    margin: 0 auto;
}

.nav-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-decoration: none;
    color: var(--fg);
    padding: 8px 12px;
    border-radius: var(--radius);
    transition: all 0.3s ease;
    flex: 1;
    max-width: 80px;
}

.nav-item:hover {
    background: rgba(59, 130, 246, 0.1);
    color: var(--primary-btn);
}

.nav-item.active {
    color: var(--primary-btn);
    background: rgba(59, 130, 246, 0.15);
}

.nav-icon {
    font-size: 1.2em;
    margin-bottom: 4px;
    transition: transform 0.3s ease;
}

.nav-item.active .nav-icon {
    transform: scale(1.1);
}

.nav-label {
    font-size: 0.75em;
    font-weight: 600;
    text-align: center;
}

/* Content Sections */
.content-section {
    display: none;
    animation: fadeIn 0.3s ease;
}

.content-section.active {
    display: block;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 15px;
    margin: 20px 0;
}

.stat-card {
    padding: 20px;
    background: var(--card);
    border-radius: var(--radius);
    text-align: center;
    box-shadow: var(--shadow);
    border: 1px solid var(--bd);
    transition: transform 0.3s ease;
}

.stat-card:hover {
    transform: translateY(-2px);
}

.stat-icon {
    font-size: 2em;
    margin-bottom: 10px;
    opacity: 0.9;
}

.stat-number {
    font-size: 1.8em;
    font-weight: 900;
    margin: 8px 0;
    background: var(--gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.stat-label {
    font-size: 0.85em;
    color: var(--bd);
    font-weight: 600;
}

/* Quick Actions */
.quick-actions {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
    margin: 20px 0;
}

.quick-btn {
    padding: 15px 10px;
    background: var(--card);
    border: 1px solid var(--bd);
    border-radius: var(--radius);
    text-align: center;
    cursor: pointer;
    transition: all 0.3s ease;
    text-decoration: none;
    color: var(--fg);
}

.quick-btn:hover {
    background: var(--primary-btn);
    color: white;
    transform: translateY(-2px);
}

.quick-btn i {
    font-size: 1.3em;
    margin-bottom: 6px;
    display: block;
}

.quick-btn span {
    font-size: 0.8em;
    font-weight: 600;
}

/* Forms and Tables */
.form-card {
    background: var(--card);
    padding: 20px;
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    border: 1px solid var(--bd);
    margin-bottom: 20px;
}

.form-title {
    color: var(--primary-btn);
    margin: 0 0 15px 0;
    font-size: 1.3em;
    display: flex;
    align-items: center;
    gap: 10px;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin-top: 15px;
}

.form-group {
    margin-bottom: 15px;
}

label {
    display: block;
    margin-bottom: 6px;
    font-weight: 600;
    color: var(--fg);
    font-size: 0.9em;
}

input, select {
    width: 100%;
    padding: 12px;
    border: 2px solid var(--bd);
    border-radius: var(--radius);
    background: var(--bg);
    color: var(--input-text);
    font-size: 0.9em;
    transition: all 0.3s ease;
}

input:focus, select:focus {
    outline: none;
    border-color: var(--primary-btn);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Buttons */
.btn {
    padding: 12px 20px;
    border: none;
    border-radius: var(--radius);
    color: white;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.3s ease;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9em;
}

.btn-primary { background: var(--primary-btn); }
.btn-primary:hover { background: #2563eb; transform: translateY(-1px); }

.btn-success { background: var(--success); }
.btn-success:hover { background: #05c189; transform: translateY(-1px); }

.btn-danger { background: var(--delete-btn); }
.btn-danger:hover { background: #dc2626; transform: translateY(-1px); }

.btn-warning { background: var(--unknown); }
.btn-warning:hover { background: #d97706; transform: translateY(-1px); }

.btn-info { background: var(--expired); }
.btn-info:hover { background: #7c3aed; transform: translateY(-1px); }

.btn-sm { padding: 8px 12px; font-size: 0.8em; }

.btn-block {
    width: 100%;
    justify-content: center;
}

/* Table */
.table-container {
    overflow-x: auto;
    border-radius: var(--radius);
    background: var(--card);
    border: 1px solid var(--bd);
    margin: 20px 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
}

th, td {
    padding: 12px 15px;
    text-align: left;
    border-bottom: 1px solid var(--bd);
    font-size: 0.85em;
}

th {
    background: var(--primary-btn);
    color: white;
    font-weight: 600;
    text-transform: uppercase;
}

tr:hover {
    background: rgba(59, 130, 246, 0.05);
}

/* Status Pills */
.pill {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.75em;
    font-weight: 700;
    color: white;
}

.pill-online { background: var(--ok); }
.pill-offline { background: var(--bad); }
.pill-expired { background: var(--expired); }
.pill-suspended { background: var(--unknown); }

/* Toggle Switch */
.switch {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 24px;
}

.switch input { 
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #ccc;
    transition: .4s;
    border-radius: 24px;
}

.slider:before {
    position: absolute;
    content: "";
    height: 16px;
    width: 16px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: .4s;
    border-radius: 50%;
}

input:checked + .slider {
    background-color: var(--ok);
}

input:checked + .slider:before {
    transform: translateX(26px);
}

.status-text {
    margin-left: 8px;
    font-size: 0.8em;
    font-weight: 600;
}

/* UUID Display */
.uuid-display {
    cursor: pointer;
    padding: 4px 8px;
    background: var(--bg);
    border: 1px solid var(--bd);
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 0.75em;
    transition: all 0.3s ease;
}

.uuid-display:hover {
    background: var(--primary-btn);
    color: white;
}

/* Action Buttons */
.action-btns {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
}

.action-btn {
    padding: 6px 10px;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 0.8em;
}

.action-btn i {
    font-size: 0.9em;
}

/* Modal */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
}

.modal-content {
    background: var(--card);
    padding: 25px;
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    max-width: 500px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
}

.detail-grid {
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 10px;
    margin: 15px 0;
}

.detail-grid label {
    font-weight: 600;
    color: var(--primary-btn);
}

/* Notifications */
.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 15px 20px;
    border-radius: var(--radius);
    color: white;
    font-weight: 600;
    z-index: 3000;
    animation: slideIn 0.3s ease;
}

.notification.success { background: var(--success); }
.notification.error { background: var(--delete-btn); }
.notification.info { background: var(--primary-btn); }

@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

/* Settings Modal */
.settings-modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    z-index: 2000;
    backdrop-filter: blur(5px);
}

.settings-content {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--card);
    padding: 25px;
    border-radius: var(--radius) var(--radius) 0 0;
    box-shadow: 0 -10px 30px rgba(0,0,0,0.3);
    max-height: 80vh;
    overflow-y: auto;
}

.settings-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 1px solid var(--bd);
}

.settings-header h3 {
    margin: 0;
    color: var(--primary-btn);
    display: flex;
    align-items: center;
    gap: 10px;
}

.close-settings {
    background: none;
    border: none;
    font-size: 1.5em;
    color: var(--fg);
    cursor: pointer;
    padding: 5px;
}

.setting-group {
    margin-bottom: 20px;
}

.setting-label {
    display: block;
    margin-bottom: 10px;
    font-weight: 600;
    color: var(--fg);
}

.theme-options, .lang-options {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}

.theme-option, .lang-option {
    padding: 12px;
    border: 2px solid var(--bd);
    border-radius: var(--radius);
    background: var(--bg);
    color: var(--fg);
    cursor: pointer;
    text-align: center;
    transition: all 0.3s ease;
    font-weight: 600;
}

.theme-option:hover, .lang-option:hover {
    border-color: var(--primary-btn);
}

.theme-option.active, .lang-option.active {
    border-color: var(--primary-btn);
    background: var(--primary-btn);
    color: white;
}

/* Login Styles */
.login-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--gradient);
    padding: 20px;
}

.login-card {
    background: var(--card);
    padding: 30px;
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    width: 100%;
    max-width: 400px;
    text-align: center;
}

.login-logo {
    height: 80px;
    width: 80px;
    border-radius: 50%;
    border: 3px solid var(--primary-btn);
    margin: 0 auto 20px;
    padding: 5px;
    background: white;
}

.login-title {
    margin: 0 0 20px 0;
    color: var(--fg);
    font-size: 1.5em;
    font-weight: 700;
}

/* Messages */
.alert {
    padding: 12px 15px;
    border-radius: var(--radius);
    margin: 15px 0;
    font-weight: 600;
}

.alert-success {
    background: var(--success);
    color: white;
}

.alert-error {
    background: var(--delete-btn);
    color: white;
}

/* Responsive Design */
@media (max-width: 768px) {
    .container {
        padding: 15px;
        padding-bottom: 70px;
    }
    
    .header {
        padding: 15px;
        margin-bottom: 15px;
    }
    
    .header h1 {
        font-size: 1.5em;
    }
    
    .stats-grid {
        grid-template-columns: 1fr 1fr;
        gap: 12px;
    }
    
    .quick-actions {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .form-grid {
        grid-template-columns: 1fr;
    }
    
    th, td {
        padding: 10px 12px;
        font-size: 0.8em;
    }
    
    .nav-label {
        font-size: 0.7em;
    }
    
    .action-btns {
        flex-direction: column;
    }
}

@media (max-width: 480px) {
    .stats-grid {
        grid-template-columns: 1fr;
    }
    
    .quick-actions {
        grid-template-columns: 1fr;
    }
    
    .nav-item {
        padding: 6px 8px;
    }
    
    .nav-label {
        font-size: 0.65em;
    }
    
    .detail-grid {
        grid-template-columns: 1fr;
    }
}
    </style>
</head>
<body data-theme="{{theme}}">

{% if not authed %}
<div class="login-container">
    <div class="login-card">
        <img src="{{ logo }}" alt="ZIVPN" class="login-logo">
        <h2 class="login-title">{{t.login_title}}</h2>
        {% if err %}<div class="alert alert-error">{{err}}</div>{% endif %}
        <form method="post" action="/login">
            <div class="form-group">
                <label><i class="fas fa-user"></i> {{t.username}}</label>
                <input name="u" autofocus required>
            </div>
            <div class="form-group">
                <label><i class="fas fa-lock"></i> {{t.password}}</label>
                <input name="p" type="password" required>
            </div>
            <button type="submit" class="btn btn-primary btn-block">
                <i class="fas fa-sign-in-alt"></i>{{t.login}}
            </button>
        </form>
    </div>
</div>
{% else %}

<div class="container">
    <!-- Modern Header -->
    <header class="header">
        <div class="header-content">
            <div class="logo-container">
                <img src="{{ logo }}" alt="ZIVPN" class="logo">
                <h1>ZIVPN Enterprise - UUID Edition</h1>
            </div>
            <div class="subtitle">Modern X-UI Style Management System</div>
        </div>
    </header>

    <!-- Home Section -->
    <div id="home" class="content-section active">
        <!-- Stats Overview -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon" style="color:var(--primary-btn);">
                    <i class="fas fa-users"></i>
                </div>
                <div class="stat-number">{{ stats.total_users }}</div>
                <div class="stat-label">{{t.total_users}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color:var(--ok);">
                    <i class="fas fa-signal"></i>
                </div>
                <div class="stat-number">{{ stats.active_users }}</div>
                <div class="stat-label">{{t.active_users}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color:var(--delete-btn);">
                    <i class="fas fa-database"></i>
                </div>
                <div class="stat-number">{{ stats.total_bandwidth }}</div>
                <div class="stat-label">{{t.bandwidth_used}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color:var(--unknown);">
                    <i class="fas fa-server"></i>
                </div>
                <div class="stat-number">{{ stats.server_load }}%</div>
                <div class="stat-label">{{t.server_load}}</div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="form-card">
            <h3 class="form-title"><i class="fas fa-bolt"></i> {{t.quick_actions}}</h3>
            <div class="quick-actions">
                <a href="javascript:void(0)" class="quick-btn" onclick="showSection('manage')">
                    <i class="fas fa-users"></i>
                    <span>{{t.manage}}</span>
                </a>
                <a href="javascript:void(0)" class="quick-btn" onclick="showSection('adduser')">
                    <i class="fas fa-user-plus"></i>
                    <span>{{t.add_user}}</span>
                </a>
                <a href="javascript:void(0)" class="quick-btn" onclick="showSection('bulk')">
                    <i class="fas fa-cogs"></i>
                    <span>{{t.bulk_ops}}</span>
                </a>
                <a href="javascript:void(0)" class="quick-btn" onclick="showSection('reports')">
                    <i class="fas fa-chart-bar"></i>
                    <span>{{t.reports}}</span>
                </a>
            </div>
        </div>

        <!-- Recent Activity -->
        <div class="form-card">
            <h3 class="form-title"><i class="fas fa-clock"></i> {{t.recent_activity}}</h3>
            <div style="max-height: 200px; overflow-y: auto;">
                {% for u in users[:5] %}
                <div style="padding: 10px; border-bottom: 1px solid var(--bd); display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{{u.email_remark or u.user}}</strong>
                        <div style="font-size: 0.8em; color: var(--bd);">UUID: {{u.password[:8]}}...</div>
                    </div>
                    <span class="pill pill-{{u.status|lower}}">{{u.status}}</span>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <!-- Manage Users Section -->
    <div id="manage" class="content-section">
        <div class="form-card">
            <h3 class="form-title"><i class="fas fa-users"></i> {{t.user_management}}</h3>
            <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                <input type="text" id="searchUser" placeholder="{{t.user_search}}" style="flex: 1;">
                <button class="btn btn-primary" onclick="filterUsers()">
                    <i class="fas fa-search"></i>
                </button>
            </div>
        </div>

        <div class="table-container">
            <table id="userTable">
                <thead>
                    <tr>
                        <th>{{t.email_remark}}</th>
                        <th>UUID</th>
                        <th>{{t.expires}}</th>
                        <th>{{t.data_limit}}</th>
                        <th>{{t.status}}</th>
                        <th>{{t.actions}}</th>
                    </tr>
                </thead>
                <tbody>
                {% for u in users %}
                <tr>
                    <td>
                        <strong>{{u.email_remark or u.user}}</strong>
                        {% if u.email_remark and u.user != u.email_remark %}
                        <br><small style="color: var(--bd);">@{{u.user}}</small>
                        {% endif %}
                    </td>
                    <td>
                        <code class="uuid-display" onclick="copyToClipboard('{{u.password}}')" title="{{t.copy_uuid}}">
                            {{u.password|truncate(20)}}
                        </code>
                    </td>
                    <td>{{u.expires or '-'}}</td>
                    <td>
                        {% if u.bandwidth_limit and u.bandwidth_limit > 0 %}
                            {{u.bandwidth_limit}} GB
                        {% else %}
                            <span style="color: var(--success);">{{t.unlimited}}</span>
                        {% endif %}
                    </td>
                    <td>
                        <label class="switch">
                            <input type="checkbox" {% if u.status=='active' %}checked{% endif %} 
                                   onchange="toggleUserStatus('{{u.user}}', this.checked)">
                            <span class="slider"></span>
                        </label>
                        <span class="status-text">{{u.status}}</span>
                    </td>
                    <td>
                        <div class="action-btns">
                            <button class="btn btn-sm btn-info" onclick="showUserDetails('{{u.user}}')" title="{{t.user_details}}">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-sm btn-warning" onclick="extendUser('{{u.user}}')" title="{{t.extend_days}}">
                                <i class="fas fa-calendar-plus"></i>
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="deleteUser('{{u.user}}')" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Add User Section -->
    <div id="adduser" class="content-section">
        <form method="post" action="/add" class="form-card" id="addUserForm">
            <h3 class="form-title"><i class="fas fa-user-plus"></i> {{t.add_user}}</h3>
            {% if msg %}<div class="alert alert-success">{{msg}}</div>{% endif %}
            {% if err %}<div class="alert alert-error">{{err}}</div>{% endif %}
            
            <div class="form-grid">
                <div class="form-group">
                    <label><i class="fas fa-tag"></i> {{t.email_remark}}</label>
                    <input name="email_remark" placeholder="Customer email or remark" required>
                </div>
                <div class="form-group">
                    <label><i class="fas fa-calendar"></i> {{t.expires}}</label>
                    <input type="date" name="expires" id="expiryDate" required>
                </div>
            </div>

            <div class="form-grid">
                <div class="form-group">
                    <label><i class="fas fa-database"></i> {{t.data_limit}}</label>
                    <input name="bandwidth_limit" type="number" min="0" value="0" 
                           title="0 = {{t.unlimited}}">
                </div>
                <div class="form-group">
                    <label><i class="fas fa-plug"></i> {{t.max_conn}}</label>
                    <input name="concurrent_conn" type="number" min="1" max="10" value="1">
                </div>
            </div>

            <button type="submit" class="btn btn-success btn-block">
                <i class="fas fa-plus-circle"></i> {{t.generate_account}}
            </button>
        </form>
    </div>

    <!-- Bulk Operations Section -->
    <div id="bulk" class="content-section">
        <div class="form-card">
            <h3 class="form-title"><i class="fas fa-cogs"></i> {{t.bulk_ops}}</h3>
            <div class="form-grid">
                <div class="form-group">
                    <label>{{t.actions}}</label>
                    <select id="bulkAction">
                        <option value="">{{t.select_action}}</option>
                        <option value="extend">{{t.extend_exp}}</option>
                        <option value="suspend">{{t.suspend_users}}</option>
                        <option value="activate">{{t.activate_users}}</option>
                        <option value="delete">{{t.delete_users}}</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>{{t.user}}</label>
                    <input type="text" id="bulkUsers" placeholder="user1,user2,user3">
                </div>
            </div>
            <button class="btn btn-primary btn-block" onclick="executeBulkAction()">
                <i class="fas fa-play"></i> {{t.execute}}
            </button>
        </div>
    </div>

    <!-- Reports Section -->
    <div id="reports" class="content-section">
        <div class="form-card">
            <h3 class="form-title"><i class="fas fa-chart-bar"></i> {{t.reports}}</h3>
            <div class="form-grid">
                <div class="form-group">
                    <label>From Date</label>
                    <input type="date" id="fromDate">
                </div>
                <div class="form-group">
                    <label>To Date</label>
                    <input type="date" id="toDate">
                </div>
                <div class="form-group">
                    <label>Report Type</label>
                    <select id="reportType">
                        <option value="bandwidth">{{t.report_bw}}</option>
                        <option value="users">{{t.report_users}}</option>
                        <option value="revenue">{{t.report_revenue}}</option>
                    </select>
                </div>
            </div>
            <button class="btn btn-primary btn-block" onclick="generateReport()">
                <i class="fas fa-chart-line"></i> Generate Report
            </button>
        </div>
        <div id="reportResults"></div>
    </div>
</div>

<!-- Bottom Navigation Bar -->
<nav class="bottom-nav">
    <div class="nav-items">
        <a href="javascript:void(0)" class="nav-item active" onclick="showSection('home')">
            <i class="fas fa-home nav-icon"></i>
            <span class="nav-label">{{t.home}}</span>
        </a>
        <a href="javascript:void(0)" class="nav-item" onclick="showSection('manage')">
            <i class="fas fa-users nav-icon"></i>
            <span class="nav-label">{{t.manage}}</span>
        </a>
        <a href="javascript:void(0)" class="nav-item" onclick="showSection('adduser')">
            <i class="fas fa-user-plus nav-icon"></i>
            <span class="nav-label">Add User</span>
        </a>
        <a href="javascript:void(0)" class="nav-item" onclick="showSection('bulk')">
            <i class="fas fa-cogs nav-icon"></i>
            <span class="nav-label">Bulk</span>
        </a>
        <a href="javascript:void(0)" class="nav-item" onclick="showSection('reports')">
            <i class="fas fa-chart-bar nav-icon"></i>
            <span class="nav-label">{{t.reports}}</span>
        </a>
        <a href="javascript:void(0)" class="nav-item" onclick="openSettings()">
            <i class="fas fa-cog nav-icon"></i>
            <span class="nav-label">{{t.settings}}</span>
        </a>
    </div>
</nav>

<!-- Settings Modal -->
<div id="settingsModal" class="settings-modal">
    <div class="settings-content">
        <div class="settings-header">
            <h3><i class="fas fa-cog"></i> {{t.settings}}</h3>
            <button class="close-settings" onclick="closeSettings()">&times;</button>
        </div>
        
        <div class="setting-group">
            <label class="setting-label"><i class="fas fa-palette"></i> Theme</label>
            <div class="theme-options">
                <div class="theme-option active" data-theme="dark" onclick="changeTheme('dark')">
                    <i class="fas fa-moon"></i> Dark
                </div>
                <div class="theme-option" data-theme="light" onclick="changeTheme('light')">
                    <i class="fas fa-sun"></i> Light
                </div>
            </div>
        </div>
        
        <div class="setting-group">
            <label class="setting-label"><i class="fas fa-language"></i> Language</label>
            <div class="lang-options">
                <div class="lang-option active" data-lang="my" onclick="changeLanguage('my')">
                    <i class="fas fa-language"></i> မြန်မာ
                </div>
                <div class="lang-option" data-lang="en" onclick="changeLanguage('en')">
                    <i class="fas fa-language"></i> English
                </div>
            </div>
        </div>
        
        <div class="setting-group">
            <a class="btn btn-primary btn-block" href="/api/export/users">
                <i class="fas fa-download"></i> Export Users CSV
            </a>
        </div>

        <div class="setting-group">
            <a class="btn btn-danger btn-block" href="/logout">
                <i class="fas fa-sign-out-alt"></i> {{t.logout}}
            </a>
        </div>
    </div>
</div>

{% endif %}

<script>
// Navigation Functions
function showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Remove active class from all nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Show selected section and activate nav item
    document.getElementById(sectionId).classList.add('active');
    event.currentTarget.classList.add('active');
}

// Settings Modal Functions
function openSettings() {
    document.getElementById('settingsModal').style.display = 'block';
}

function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

// Theme Functions
function changeTheme(theme) {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // Update active state
    document.querySelectorAll('.theme-option').forEach(option => {
        option.classList.remove('active');
    });
    event.currentTarget.classList.add('active');
}

// Language Functions
function changeLanguage(lang) {
    window.location.href = '/set_lang?lang=' + lang;
}

// Initialize theme from localStorage
document.addEventListener('DOMContentLoaded', () => {
    const storedTheme = localStorage.getItem('theme') || 'dark';
    document.body.setAttribute('data-theme', storedTheme);
    
    // Set active theme option
    document.querySelectorAll('.theme-option').forEach(option => {
        option.classList.remove('active');
        if (option.getAttribute('data-theme') === storedTheme) {
            option.classList.add('active');
        }
    });
    
    // Set default expiry date to 30 days from now
    const defaultExpiry = new Date();
    defaultExpiry.setDate(defaultExpiry.getDate() + 30);
    document.getElementById('expiryDate').value = defaultExpiry.toISOString().split('T')[0];
});

// Notification System
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// User Management Functions
function filterUsers() {
    const search = document.getElementById('searchUser').value.toLowerCase();
    document.querySelectorAll('#userTable tbody tr').forEach(row => {
        const user = row.cells[0].textContent.toLowerCase();
        row.style.display = user.includes(search) ? '' : 'none';
    });
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('UUID copied to clipboard!', 'success');
    }).catch(err => {
        showNotification('Failed to copy UUID', 'error');
    });
}

function toggleUserStatus(username, isActive) {
    const action = isActive ? 'activate' : 'suspend';
    const actionText = isActive ? 'activated' : 'suspended';
    
    fetch(`/api/user/${action}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user: username})
    }).then(r => r.json()).then(data => {
        showNotification(data.message, 'success');
        // Update status text
        const statusText = event.target.closest('td').querySelector('.status-text');
        statusText.textContent = isActive ? 'active' : 'suspended';
    }).catch(e => {
        showNotification('Error: ' + e.message, 'error');
        // Revert checkbox on error
        event.target.checked = !isActive;
    });
}

function showUserDetails(username) {
    fetch(`/api/user/${username}`)
        .then(r => r.json())
        .then(user => {
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content">
                    <h3><i class="fas fa-user"></i> User Details: ${user.email_remark || user.username}</h3>
                    <div class="detail-grid">
                        <label>Username:</label><span>${user.username}</span>
                        <label>UUID:</label>
                        <span>
                            <code style="background: var(--bg); padding: 5px; border-radius: 4px; display: block; margin: 5px 0;">${user.password}</code>
                            <button class="btn btn-sm btn-primary" onclick="copyToClipboard('${user.password}')">
                                <i class="fas fa-copy"></i> Copy UUID
                            </button>
                        </span>
                        <label>Expires:</label><span>${user.expires || 'Never'}</span>
                        <label>Data Limit:</label>
                        <span>${user.bandwidth_limit > 0 ? user.bandwidth_limit + ' GB' : 'Unlimited'}</span>
                        <label>Max Connections:</label><span>${user.concurrent_conn}</span>
                        <label>Status:</label><span>${user.status}</span>
                    </div>
                    <div style="margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end;">
                        <button class="btn btn-warning" onclick="extendUser('${user.username}')">
                            <i class="fas fa-calendar-plus"></i> Extend
                        </button>
                        <button class="btn btn-danger" onclick="deleteUser('${user.username}')">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                        <button class="btn" onclick="this.closest('.modal-overlay').remove()" style="background: var(--bd);">
                            Close
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }).catch(e => {
            showNotification('Error loading user details: ' + e.message, 'error');
        });
}

function extendUser(username) {
    const days = prompt('Extend by how many days?', '30');
    if (days && !isNaN(days)) {
        fetch('/api/user/extend', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user: username, days: parseInt(days)})
        }).then(r => r.json()).then(data => {
            showNotification(data.message, 'success');
            setTimeout(() => location.reload(), 1000);
        }).catch(e => {
            showNotification('Error: ' + e.message, 'error');
        });
    }
}

function deleteUser(username) {
    const t = {{t|tojson}};
    if (confirm(t.delete_confirm.replace('{user}', username))) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/delete';
        
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'user';
        input.value = username;
        
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    }
}

// Bulk Action Function
function executeBulkAction() {
    const t = {{t|tojson}};
    const action = document.getElementById('bulkAction').value;
    const users = document.getElementById('bulkUsers').value;
    
    if (!action || !users) { 
        alert(t.select_action + ' / ' + t.user + ' လိုအပ်သည်'); 
        return; 
    }

    if (action === 'delete' && !confirm(t.delete_users + ' ' + users + ' ကို ဖျက်ရန် သေချာပါသလား?')) return;
    
    fetch('/api/bulk', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action, users: users.split(',').map(u => u.trim()).filter(u => u)})
    }).then(r => r.json()).then(data => {
        showNotification(data.message.replace('{action}', action), 'success'); 
        setTimeout(() => location.reload(), 1000);
    }).catch(e => {
        showNotification('Error: ' + e.message, 'error');
    });
}

// Report Generation Function
function generateReport() {
    const from = document.getElementById('fromDate').value;
    const to = document.getElementById('toDate').value;
    const type = document.getElementById('reportType').value;
    const reportResults = document.getElementById('reportResults');
    const t = {{t|tojson}};

    if (!from || !to) {
        alert(t.report_range);
        return;
    }

    reportResults.innerHTML = '<div class="form-card" style="text-align: center; padding: 30px;"><i class="fas fa-spinner fa-spin"></i> Generating Report...</div>';

    fetch(`/api/reports?from=${from}&to=${to}&type=${type}`)
        .then(r => r.json())
        .then(data => {
            reportResults.innerHTML = `
                <div class="form-card">
                    <h3 class="form-title">${type.toUpperCase()} Report (${from} to ${to})</h3>
                    <pre style="background: var(--bg); padding: 15px; border-radius: var(--radius); border: 1px solid var(--bd); overflow-x: auto;">${JSON.stringify(data, null, 2)}</pre>
                </div>
            `;
        })
        .catch(e => {
            reportResults.innerHTML = '<div class="alert alert-error">Error loading report: ' + e.message + '</div>';
        });
}

// Close settings when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('settingsModal');
    if (event.target === modal) {
        closeSettings();
    }
}

// Close modal when clicking outside modal content
document.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal-overlay')) {
        event.target.remove();
    }
});
</script>
</body>
</html>
"""

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET","dev-secret-change-me")
ADMIN_USER = os.environ.get("WEB_ADMIN_USER","").strip()
ADMIN_PASS = os.environ.get("WEB_ADMIN_PASSWORD","").strip()
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/etc/zivpn/zivpn.db")

# --- Utility Functions ---

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def read_json(path, default):
    try:
        with open(path,"r") as f: return json.load(f)
    except Exception:
        return default

def write_json_atomic(path, data):
    d=json.dumps(data, ensure_ascii=False, indent=2)
    dirn=os.path.dirname(path); fd,tmp=tempfile.mkstemp(prefix=".tmp-", dir=dirn)
    try:
        with os.fdopen(fd,"w") as f: f.write(d)
        os.replace(tmp,path)
    finally:
        try: os.remove(tmp)
        except: pass

def generate_uuid():
    """Generate UUID for user authentication"""
    return str(uuid.uuid4())

def update_database_schema():
    """Add email_remark column to users table if not exists"""
    db = get_db()
    try:
        # Check if email_remark column exists
        columns = db.execute("PRAGMA table_info(users)").fetchall()
        column_names = [col[1] for col in columns]
        
        if 'email_remark' not in column_names:
            db.execute('ALTER TABLE users ADD COLUMN email_remark TEXT')
            db.commit()
            print("Added email_remark column to users table")
    except Exception as e:
        print(f"Database schema update error: {e}")
    finally:
        db.close()

# Update schema on startup
update_database_schema()

def load_users():
    db = get_db()
    users = db.execute('''
        SELECT username as user, password, email_remark, expires, port, status, 
               bandwidth_limit, bandwidth_used, speed_limit_up as speed_limit,
               concurrent_conn
        FROM users
    ''').fetchall()
    db.close()
    return [dict(u) for u in users]

def create_user_with_uuid(user_data):
    """Create user with auto-generated UUID"""
    db = get_db()
    try:
        user_uuid = generate_uuid()
        username = f"user_{int(datetime.now().timestamp())}_{user_uuid[:8]}"
        
        db.execute('''
            INSERT INTO users 
            (username, password, email_remark, expires, port, status, 
             bandwidth_limit, speed_limit_up, concurrent_conn, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username,
            user_uuid,  # Use UUID as password
            user_data.get('email_remark', ''),
            user_data.get('expires'),
            user_data.get('port'),
            'active',
            user_data.get('bandwidth_limit', 0),
            user_data.get('speed_limit', 0),
            user_data.get('concurrent_conn', 1),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        db.commit()
        return username, user_uuid
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def save_user(user_data):
    """Save user with UUID authentication"""
    try:
        username, user_uuid = create_user_with_uuid(user_data)
        return username, user_uuid
    except Exception as e:
        raise e

def delete_user(username):
    db = get_db()
    try:
        db.execute('DELETE FROM users WHERE username = ?', (username,))
        db.execute('DELETE FROM billing WHERE username = ?', (username,))
        db.execute('DELETE FROM bandwidth_logs WHERE username = ?', (username,))
        db.commit()
    finally:
        db.close()

def get_server_stats():
    db = get_db()
    try:
        total_users = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        active_users_db = db.execute('SELECT COUNT(*) FROM users WHERE status = "active" AND (expires IS NULL OR expires >= CURRENT_DATE)').fetchone()[0]
        total_bandwidth = db.execute('SELECT SUM(bandwidth_used) FROM users').fetchone()[0] or 0
        
        server_load = min(100, (active_users_db * 5) + 10)
        
        return {
            'total_users': total_users,
            'active_users': active_users_db,
            'total_bandwidth': f"{total_bandwidth / 1024 / 1024 / 1024:.2f} GB",
            'server_load': server_load
        }
    finally:
        db.close()

def get_listen_port_from_config():
    cfg=read_json(CONFIG_FILE,{})
    listen=str(cfg.get("listen","")).strip()
    m=re.search(r":(\d+)$", listen) if listen else None
    return (m.group(1) if m else LISTEN_FALLBACK)

def has_recent_udp_activity(port):
    if not port: return False
    try:
        out=subprocess.run("conntrack -L -p udp 2>/dev/null | grep 'dport=%s\\b'"%port,
                           shell=True, capture_output=True, text=True).stdout
        return bool(out)
    except Exception:
        return False

def status_for_user(u, listen_port):
    port=str(u.get("port",""))
    check_port=port if port else listen_port

    if u.get('status') == 'suspended': return "suspended"

    expires_str = u.get("expires", "")
    is_expired = False
    if expires_str:
        try:
            expires_dt = datetime.strptime(expires_str, "%Y-%m-%d").date()
            if expires_dt < datetime.now().date():
                is_expired = True
        except ValueError:
            pass

    if is_expired: return "Expired"

    if has_recent_udp_activity(check_port): return "Online"
    
    return "Offline"

def sync_config_passwords(mode="mirror"):
    db = get_db()
    active_users = db.execute('''
        SELECT password FROM users 
        WHERE status = "active" AND password IS NOT NULL AND password != "" 
              AND (expires IS NULL OR expires >= CURRENT_DATE)
    ''').fetchall()
    db.close()
    
    users_pw = sorted({str(u["password"]) for u in active_users})
    
    cfg=read_json(CONFIG_FILE,{})
    if not isinstance(cfg.get("auth"),dict): cfg["auth"]={}
    cfg["auth"]["mode"]="passwords"
    cfg["auth"]["config"]=users_pw
    cfg["listen"]=cfg.get("listen") or ":5667"
    cfg["cert"]=cfg.get("cert") or "/etc/zivpn/zivpn.crt"
    cfg["key"]=cfg.get("key") or "/etc/zivpn/zivpn.key"
    cfg["obfs"]=cfg.get("obfs") or "zivpn"
    
    write_json_atomic(CONFIG_FILE,cfg)
    subprocess.run("systemctl restart zivpn.service", shell=True)

def login_enabled(): return bool(ADMIN_USER and ADMIN_PASS)
def is_authed(): return session.get("auth") == True
def require_login():
    if login_enabled() and not is_authed():
        return False
    return True

# --- Request Hooks ---
@app.before_request
def set_language_and_translations():
    lang = session.get('lang', os.environ.get('DEFAULT_LANGUAGE', 'my'))
    g.lang = lang
    g.t = TRANSLATIONS.get(lang, TRANSLATIONS['my'])

# --- Routes ---

@app.route("/set_lang", methods=["GET"])
def set_lang():
    lang = request.args.get('lang')
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route("/login", methods=["GET","POST"])
def login():
    t = g.t
    if not login_enabled(): return redirect(url_for('index'))
    if request.method=="POST":
        u=(request.form.get("u") or "").strip()
        p=(request.form.get("p") or "").strip()
        if hmac.compare_digest(u, ADMIN_USER) and hmac.compare_digest(p, ADMIN_PASS):
            session["auth"]=True
            return redirect(url_for('index'))
        else:
            session["auth"]=False
            session["login_err"]=t['login_err']
            return redirect(url_for('login'))
    
    theme = session.get('theme', 'dark')
    html_template = load_html_template()
    return render_template_string(html_template, authed=False, logo=LOGO_URL, err=session.pop("login_err", None), 
                                  t=t, lang=g.lang, theme=theme)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("auth", None)
    return redirect(url_for('login') if login_enabled() else url_for('index'))

def build_view(msg="", err=""):
    t = g.t
    if not require_login():
        html_template = load_html_template()
        return render_template_string(html_template, authed=False, logo=LOGO_URL, err=session.pop("login_err", None), 
                                      t=t, lang=g.lang, theme=session.get('theme', 'dark'))
    
    users=load_users()
    listen_port=get_listen_port_from_config()
    stats = get_server_stats()
    
    view=[]
    today_date=datetime.now().date()
    
    for u in users:
        status = status_for_user(u, listen_port)
        expires_str=u.get("expires","")
        
        view.append(type("U",(),{
            "user":u.get("user",""),
            "password":u.get("password",""),
            "email_remark":u.get("email_remark",""),
            "expires":expires_str,
            "port":u.get("port",""),
            "status":status,
            "bandwidth_limit": u.get('bandwidth_limit', 0),
            "bandwidth_used": f"{u.get('bandwidth_used', 0) / 1024 / 1024 / 1024:.2f}",
            "speed_limit": u.get('speed_limit', 0),
            "concurrent_conn": u.get('concurrent_conn', 1)
        }))
    
    view.sort(key=lambda x:(x.user or "").lower())
    today=today_date.strftime("%Y-%m-%d")
    
    theme = session.get('theme', 'dark')
    html_template = load_html_template()
    return render_template_string(html_template, authed=True, logo=LOGO_URL, 
                                 users=view, msg=msg, err=err, today=today, stats=stats, 
                                 t=t, lang=g.lang, theme=theme)

@app.route("/", methods=["GET"])
def index(): 
    return build_view()

@app.route("/add", methods=["POST"])
def add_user():
    t = g.t
    if not require_login(): return redirect(url_for('login'))
    
    user_data = {
        'email_remark': (request.form.get("email_remark") or "").strip(),
        'expires': (request.form.get("expires") or "").strip(),
        'port': (request.form.get("port") or "").strip(),
        'bandwidth_limit': int(request.form.get("bandwidth_limit") or 0),
        'speed_limit': int(request.form.get("speed_limit") or 0),
        'concurrent_conn': int(request.form.get("concurrent_conn") or 1)
    }
    
    if not user_data['email_remark']:
        return build_view(err="Email/Remark field is required")
    
    if user_data['expires']:
        try: 
            datetime.strptime(user_data['expires'],"%Y-%m-%d")
        except ValueError:
            return build_view(err=t['invalid_exp'])
    
    if user_data['port']:
        try:
            port_num = int(user_data['port'])
            if not (6000 <= port_num <= 19999):
                 return build_view(err=t['invalid_port'])
        except ValueError:
             return build_view(err=t['invalid_port'])

    try:
        username, user_uuid = save_user(user_data)
        sync_config_passwords()
        
        success_msg = f"""
        ✅ User account created successfully!
        
        📧 Remark: {user_data['email_remark']}
        🔐 UUID: {user_uuid}
        👤 Username: {username}
        ⏰ Expires: {user_data['expires']}
        📊 Data Limit: {'Unlimited' if user_data['bandwidth_limit'] == 0 else f"{user_data['bandwidth_limit']} GB"}
        """
        
        return build_view(msg=success_msg)
    except Exception as e:
        return build_view(err=f"Error creating user: {str(e)}")

@app.route("/delete", methods=["POST"])
def delete_user_html():
    t = g.t
    if not require_login(): return redirect(url_for('login'))
    user = (request.form.get("user") or "").strip()
    if not user: return build_view(err=t['required_fields'])
    
    delete_user(user)
    sync_config_passwords(mode="mirror")
    return build_view(msg=t['deleted'].format(user=user))

@app.route("/suspend", methods=["POST"])
def suspend_user():
    if not require_login(): return redirect(url_for('login'))
    user = (request.form.get("user") or "").strip()
    if user:
        db = get_db()
        db.execute('UPDATE users SET status = "suspended" WHERE username = ?', (user,))
        db.commit()
        db.close()
        sync_config_passwords()
    return redirect(url_for('index'))

@app.route("/activate", methods=["POST"])
def activate_user():
    if not require_login(): return redirect(url_for('login'))
    user = (request.form.get("user") or "").strip()
    if user:
        db = get_db()
        db.execute('UPDATE users SET status = "active" WHERE username = ?', (user,))
        db.commit()
        db.close()
        sync_config_passwords()
    return redirect(url_for('index'))

# --- API Routes ---

@app.route("/api/bulk", methods=["POST"])
def bulk_operations():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    action = data.get('action')
    users = data.get('users', [])
    
    db = get_db()
    try:
        if action == 'extend':
            for user in users:
                db.execute('UPDATE users SET expires = date(expires, "+7 days") WHERE username = ?', (user,))
        elif action == 'suspend':
            for user in users:
                db.execute('UPDATE users SET status = "suspended" WHERE username = ?', (user,))
        elif action == 'activate':
            for user in users:
                db.execute('UPDATE users SET status = "active" WHERE username = ?', (user,))
        elif action == 'delete':
            for user in users:
                delete_user(user)
        
        db.commit()
        sync_config_passwords()
        return jsonify({"ok": True, "message": t['bulk_success'].format(action=action)})
    finally:
        db.close()

@app.route("/api/user/activate", methods=["POST"])
def api_activate_user():
    if not require_login(): return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    user = data.get('user')
    if user:
        db = get_db()
        db.execute('UPDATE users SET status = "active" WHERE username = ?', (user,))
        db.commit()
        db.close()
        sync_config_passwords()
        return jsonify({"message": f"User {user} activated"})
    return jsonify({"error": "Invalid user"}), 400

@app.route("/api/user/suspend", methods=["POST"])
def api_suspend_user():
    if not require_login(): return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    user = data.get('user')
    if user:
        db = get_db()
        db.execute('UPDATE users SET status = "suspended" WHERE username = ?', (user,))
        db.commit()
        db.close()
        sync_config_passwords()
        return jsonify({"message": f"User {user} suspended"})
    return jsonify({"error": "Invalid user"}), 400

@app.route("/api/user/extend", methods=["POST"])
def api_extend_user():
    if not require_login(): return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    user = data.get('user')
    days = data.get('days', 30)
    
    db = get_db()
    user_data = db.execute('SELECT expires FROM users WHERE username = ?', (user,)).fetchone()
    if user_data:
        if user_data['expires']:
            new_expiry = (datetime.strptime(user_data['expires'], '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')
        else:
            new_expiry = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        
        db.execute('UPDATE users SET expires = ? WHERE username = ?', (new_expiry, user))
        db.commit()
        db.close()
        return jsonify({"message": f"User {user} extended by {days} days"})
    
    return jsonify({"error": "User not found"}), 404

@app.route("/api/user/<username>", methods=["GET"])
def api_get_user(username):
    if not require_login(): return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    user = db.execute('''
        SELECT username, password, email_remark, expires, port, status, 
               bandwidth_limit, bandwidth_used, speed_limit_up as speed_limit,
               concurrent_conn, created_at
        FROM users WHERE username = ?
    ''', (username,)).fetchone()
    db.close()
    
    if user:
        return jsonify(dict(user))
    return jsonify({"error": "User not found"}), 404

@app.route("/api/export/users")
def export_users():
    if not require_login(): return "Unauthorized", 401
    
    users = load_users()
    csv_data = "Remark/Email,Username,UUID,Expires,Data Limit (GB),Bandwidth Used (GB),Status,Max Connections\n"
    for u in users:
        csv_data += f"\"{u['email_remark'] or u['user']}\",{u['user']},{u['password']},{u.get('expires','')},{u.get('bandwidth_limit',0)},{float(u.get('bandwidth_used',0)) / 1024 / 1024 / 1024:.2f},{u.get('status','')},{u.get('concurrent_conn',1)}\n"
    
    response = make_response(csv_data)
    response.headers["Content-Disposition"] = "attachment; filename=users_export.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route("/api/reports")
def generate_reports():
    if not require_login(): return jsonify({"error": "Unauthorized"}), 401
    
    report_type = request.args.get('type', 'bandwidth')
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    
    db = get_db()
    try:
        if report_type == 'bandwidth':
            data = db.execute('''
                SELECT username, SUM(bytes_used) / 1024 / 1024 / 1024 as total_gb_used 
                FROM bandwidth_logs 
                WHERE log_date BETWEEN ? AND ?
                GROUP BY username
                ORDER BY total_gb_used DESC
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()
        
        elif report_type == 'users':
            data = db.execute('''
                SELECT strftime('%Y-%m-%d', created_at) as date, COUNT(*) as new_users
                FROM users 
                WHERE created_at BETWEEN ? AND datetime(?, '+1 day')
                GROUP BY date
                ORDER BY date ASC
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()

        elif report_type == 'revenue':
            data = db.execute('''
                SELECT plan_type, currency, SUM(amount) as total_revenue
                FROM billing
                WHERE created_at BETWEEN ? AND datetime(?, '+1 day')
                GROUP BY plan_type, currency
            ''', (from_date or '2000-01-01', to_date or '2030-12-31')).fetchall()
        
        else:
            return jsonify({"message": "Invalid report type"}), 400

        return jsonify([dict(d) for d in data])
    finally:
        db.close()

@app.route("/api/user/update", methods=["POST"])
def update_user():
    t = g.t
    if not require_login(): return jsonify({"ok": False, "err": t['login_err']}), 401
    
    data = request.get_json() or {}
    user = data.get('user')
    password = data.get('password')
    
    if user and password:
        db = get_db()
        db.execute('UPDATE users SET password = ? WHERE username = ?', (password, user))
        db.commit()
        db.close()
        sync_config_passwords()
        return jsonify({"ok": True, "message": "User password updated"})
    
    return jsonify({"ok": False, "err": "Invalid data"})

if __name__ == "__main__":
    web_port = int(os.environ.get("WEB_PORT", "19432"))
    app.run(host="0.0.0.0", port=web_port)
