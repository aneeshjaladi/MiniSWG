import json
import os
import time
import urllib.parse
from datetime import datetime, timezone
from miniswg.winproxy import (
    is_windows_proxy_enabled,
    enable_windows_proxy,
    disable_windows_proxy,
)

SERVER_START_TIME = time.time()

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MiniSWG - Secure Web Gateway Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0a0d14;
            --bg-card: rgba(18, 24, 38, 0.75);
            --bg-card-hover: rgba(26, 35, 55, 0.85);
            --border-subtle: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(59, 130, 246, 0.3);
            --primary: #3b82f6;
            --primary-glow: rgba(59, 130, 246, 0.4);
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --text-dim: #6b7280;
            --radius-md: 12px;
            --radius-lg: 16px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, sans-serif;
        }

        body {
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(16, 185, 129, 0.05) 0%, transparent 40%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 2.5rem;
            border-bottom: 1px solid var(--border-subtle);
            background: rgba(10, 13, 20, 0.85);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }

        .brand-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 20px rgba(37, 99, 235, 0.4);
        }

        .brand-icon svg {
            width: 22px;
            height: 22px;
            fill: white;
        }

        .brand-text h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 1.35rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #ffffff, #cbd5e1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-text p {
            font-size: 0.75rem;
            color: var(--text-muted);
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 1.25rem;
        }

        .status-pill {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.4rem 0.9rem;
            border-radius: 9999px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            font-size: 0.8rem;
            font-weight: 500;
            color: #34d399;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #34d399;
            box-shadow: 0 0 8px #34d399;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(52, 211, 153, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
        }

        .proxy-toggle-btn {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            padding: 0.5rem 1.1rem;
            border-radius: 10px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid var(--border-subtle);
            background: rgba(30, 41, 59, 0.6);
            color: var(--text-main);
        }

        .proxy-toggle-btn.active {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            border-color: #3b82f6;
            box-shadow: 0 0 15px rgba(37, 99, 235, 0.35);
        }

        .proxy-toggle-btn:hover {
            transform: translateY(-1px);
        }

        /* Container & Tabs */
        .container {
            max-width: 1280px;
            margin: 0 auto;
            padding: 2rem 2.5rem;
            width: 100%;
            flex: 1;
        }

        .nav-tabs {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 0.5rem;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 0.65rem 1.25rem;
            font-size: 0.9rem;
            font-weight: 500;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .tab-btn:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.04);
        }

        .tab-btn.active {
            color: #60a5fa;
            background: rgba(59, 130, 246, 0.12);
            font-weight: 600;
        }

        /* Tab Panes */
        .tab-pane {
            display: none;
            animation: fadeIn 0.25s ease forwards;
        }

        .tab-pane.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }

        .metric-card {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 1.25rem 1.5rem;
            backdrop-filter: blur(10px);
            position: relative;
            overflow: hidden;
            transition: all 0.2s ease;
        }

        .metric-card:hover {
            border-color: var(--border-glow);
            transform: translateY(-2px);
        }

        .metric-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.4rem;
        }

        .metric-value {
            font-family: 'Outfit', sans-serif;
            font-size: 1.85rem;
            font-weight: 700;
            color: var(--text-main);
        }

        .metric-sub {
            font-size: 0.75rem;
            color: var(--text-dim);
            margin-top: 0.3rem;
        }

        /* Cards and Sections */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 1.75rem;
            backdrop-filter: blur(12px);
            margin-bottom: 1.75rem;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
        }

        .card-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.15rem;
            font-weight: 600;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }

        .card-subtitle {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 0.2rem;
        }

        /* Category Cards Grid */
        .categories-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1.25rem;
        }

        .cat-card {
            background: rgba(26, 34, 52, 0.6);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 1.25rem;
            transition: all 0.2s ease;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .cat-card:hover {
            border-color: rgba(255, 255, 255, 0.15);
        }

        .cat-card.blocked {
            border-left: 4px solid var(--accent-red);
        }

        .cat-card.allowed {
            border-left: 4px solid var(--accent-green);
        }

        .cat-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }

        .cat-name {
            font-size: 1rem;
            font-weight: 600;
            text-transform: capitalize;
        }

        .cat-status-badge {
            font-size: 0.72rem;
            padding: 0.2rem 0.6rem;
            border-radius: 9999px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-blocked {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .badge-allowed {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .badge-ratelimited {
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .chips-container {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-bottom: 1rem;
            max-height: 110px;
            overflow-y: auto;
        }

        .chip {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            padding: 0.2rem 0.55rem;
            font-size: 0.75rem;
            font-family: monospace;
            color: #e2e8f0;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }

        .chip-del {
            cursor: pointer;
            color: var(--text-dim);
            font-weight: bold;
        }

        .chip-del:hover {
            color: var(--accent-red);
        }

        .cat-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 0.75rem;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        /* Toggle Switch */
        .switch {
            position: relative;
            display: inline-block;
            width: 44px;
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
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: #334155;
            transition: .3s;
            border-radius: 24px;
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .3s;
            border-radius: 50%;
        }

        input:checked + .slider {
            background-color: var(--accent-red);
        }

        input:checked + .slider:before {
            transform: translateX(20px);
        }

        /* Form Controls */
        .form-row {
            display: flex;
            gap: 0.85rem;
            margin-bottom: 1rem;
        }

        .input-text, .select-input {
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            color: var(--text-main);
            padding: 0.7rem 1rem;
            font-size: 0.9rem;
            outline: none;
            transition: all 0.2s;
            flex: 1;
        }

        .input-text:focus, .select-input:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 10px rgba(59, 130, 246, 0.25);
        }

        .btn-primary {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.7rem 1.4rem;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }

        .btn-primary:hover {
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            box-shadow: 0 0 15px rgba(37, 99, 235, 0.4);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.07);
            border: 1px solid var(--border-subtle);
            color: var(--text-main);
            border-radius: 8px;
            padding: 0.7rem 1.4rem;
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.12);
        }

        /* Table */
        .table-responsive {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }

        th {
            text-align: left;
            padding: 0.85rem 1rem;
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-muted);
            font-weight: 600;
            border-bottom: 1px solid var(--border-subtle);
        }

        td {
            padding: 0.85rem 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: var(--text-main);
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        /* Tester Verdict Box */
        .verdict-box {
            margin-top: 1.25rem;
            padding: 1.25rem;
            border-radius: var(--radius-md);
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border-subtle);
            display: none;
            animation: fadeIn 0.3s ease;
        }

        .quick-pill {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-subtle);
            color: var(--text-main);
            padding: 0.35rem 0.8rem;
            border-radius: 9999px;
            font-size: 0.78rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }

        .quick-pill:hover {
            transform: translateY(-1px);
        }

        .pill-blocked:hover {
            border-color: #f87171;
            background: rgba(239, 68, 68, 0.18);
            color: #fca5a5;
        }

        .pill-allowed:hover {
            border-color: #4ade80;
            background: rgba(34, 197, 94, 0.18);
            color: #86efac;
        }

        /* Toast */
        #toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: #1e293b;
            color: white;
            padding: 0.9rem 1.5rem;
            border-radius: 10px;
            border: 1px solid #3b82f6;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
            font-size: 0.85rem;
            font-weight: 500;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            z-index: 1000;
        }

        #toast.show {
            transform: translateY(0);
            opacity: 1;
        }
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <div class="brand-icon">
                <svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>
            </div>
            <div class="brand-text">
                <h1>MiniSWG Admin</h1>
                <p>Secure Web Gateway</p>
            </div>
        </div>

        <div class="header-actions">
            <div class="status-pill">
                <div class="pulse-dot"></div>
                <span id="proxy-status-text">Proxy Active: 127.0.0.1:8080</span>
            </div>
            <button class="proxy-toggle-btn" id="win-proxy-btn" onclick="toggleWindowsProxy()">
                <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                <span id="win-proxy-label">Windows Proxy: Checking...</span>
            </button>
        </div>
    </header>

    <div class="container">
        <!-- Tabs Navigation -->
        <div class="nav-tabs">
            <button class="tab-btn active" onclick="switchTab('overview')">📊 Overview & Traffic</button>
            <button class="tab-btn" onclick="switchTab('categories')">🛡️ Category Policies</button>
            <button class="tab-btn" onclick="switchTab('rules')">➕ Add Custom Rules</button>
            <button class="tab-btn" onclick="switchTab('tester')">🔍 Domain Tester</button>
            <button class="tab-btn" onclick="switchTab('settings')">⚙️ Rate Limits & Policy</button>
        </div>

        <!-- Tab 1: Overview -->
        <div id="tab-overview" class="tab-pane active">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Total Requests</div>
                    <div class="metric-value" id="stat-total-requests">0</div>
                    <div class="metric-sub">Processed through gateway</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Blocked Threats</div>
                    <div class="metric-value" id="stat-blocked-requests" style="color: #f87171;">0</div>
                    <div class="metric-sub">Blocked by security policy</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Active Blocked Categories</div>
                    <div class="metric-value" id="stat-blocked-cats" style="color: #60a5fa;">0</div>
                    <div class="metric-sub">Categories denied by policy</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Rate Limit Capacity</div>
                    <div class="metric-value" id="stat-rate-limit">120 RPM</div>
                    <div class="metric-sub" id="stat-burst-limit">Burst cap: 20 tokens</div>
                </div>
            </div>

            <!-- Live Traffic Table -->
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title">Live Access Telemetry</div>
                        <div class="card-subtitle">Real-time HTTP and CONNECT requests passing through MiniSWG</div>
                    </div>
                    <button class="btn-secondary" onclick="fetchLogs()" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;">🔄 Refresh</button>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Time (UTC)</th>
                                <th>Client IP</th>
                                <th>Method</th>
                                <th>Target Host</th>
                                <th>Action</th>
                                <th>Category / Reason</th>
                                <th>Status</th>
                                <th>Latency</th>
                            </tr>
                        </thead>
                        <tbody id="logs-table-body">
                            <tr><td colspan="8" style="text-align: center; color: var(--text-dim);">Loading activity logs...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab 2: Categories -->
        <div id="tab-categories" class="tab-pane">
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title">Security Category Controls</div>
                        <div class="card-subtitle">Toggle entire threat categories on or off with instant zero-downtime policy reloads.</div>
                    </div>
                </div>
                <div class="categories-grid" id="categories-container">
                    <!-- Populated dynamically via JS -->
                </div>
            </div>
        </div>

        <!-- Tab 3: Custom Rules -->
        <div id="tab-rules" class="tab-pane">
            <div class="card">
                <div class="card-title">Add Website Rule</div>
                <div class="card-subtitle" style="margin-bottom: 1.25rem;">Quickly add a domain pattern to a security category or the global allowlist.</div>
                
                <div class="form-row">
                    <input type="text" id="new-domain-input" class="input-text" placeholder="Domain name (e.g. *.gambling.com, scam.site, internal.app)">
                    <select id="new-domain-target" class="select-input" style="max-width: 240px;">
                        <option value="allowlist">⭐️ Allowlist (Always Allow)</option>
                        <!-- Populated with categories via JS -->
                    </select>
                    <button class="btn-primary" onclick="addDomainRule()">➕ Add Rule</button>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Global Allowlist</div>
                <div class="card-subtitle" style="margin-bottom: 1rem;">Domains that completely bypass category blocks and rate limits.</div>
                <div class="chips-container" id="allowlist-chips">
                    <!-- Allowlist chips -->
                </div>
            </div>
        </div>

        <!-- Tab 4: Domain Tester -->
        <div id="tab-tester" class="tab-pane">
            <div class="card">
                <div class="card-title">Domain Policy Inspector</div>
                <div class="card-subtitle" style="margin-bottom: 1.25rem;">Test how MiniSWG evaluates any domain name against the active Trie policy.</div>
                
                <div class="form-row">
                    <input type="text" id="test-domain-input" class="input-text" placeholder="Enter domain to inspect (e.g. evil.example, poker.casino.com, google.com)" onkeydown="if(event.key === 'Enter') testDomain()">
                    <button class="btn-primary" onclick="testDomain()">Inspect Verdict</button>
                </div>

                <div style="margin-top: 0.85rem; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                    <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 500;">1-Click Quick Test:</span>
                    <button type="button" class="quick-pill pill-blocked" onclick="quickTest('evil.example')">🛑 evil.example (Malware)</button>
                    <button type="button" class="quick-pill pill-blocked" onclick="quickTest('test.badsite.com')">🛑 test.badsite.com (Wildcard)</button>
                    <button type="button" class="quick-pill pill-blocked" onclick="quickTest('poker.casino.com')">🛑 poker.casino.com (Gambling)</button>
                    <button type="button" class="quick-pill pill-allowed" onclick="quickTest('google.com')">✅ google.com (Allowed)</button>
                    <button type="button" class="quick-pill pill-allowed" onclick="quickTest('internal.company.com')">🛡️ internal.company.com (Allowlist)</button>
                </div>

                <div id="verdict-result" class="verdict-box">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                        <span id="verdict-host" style="font-weight: 600; font-size: 1.1rem;"></span>
                        <span id="verdict-badge" class="cat-status-badge"></span>
                    </div>
                    <div style="font-size: 0.85rem; color: var(--text-muted);">
                        Reason: <strong id="verdict-reason" style="color: var(--text-main);"></strong> &bull; 
                        Category: <strong id="verdict-category" style="color: var(--text-main);"></strong>
                    </div>
                    <div id="verdict-hint" style="display: none; margin-top: 0.75rem; padding: 0.65rem 0.95rem; border-radius: 8px; font-size: 0.84rem; background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.35); color: #93c5fd; line-height: 1.4;"></div>
                    <div style="margin-top: 0.85rem;">
                        <a id="verdict-preview-link" target="_blank" class="btn-primary" style="display: none; text-decoration: none; font-size: 0.82rem; padding: 0.45rem 0.95rem;">👁️ Open Block Page in New Tab</a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab 5: Settings -->
        <div id="tab-settings" class="tab-pane">
            <div class="card">
                <div class="card-title">Token Bucket Rate Limiting</div>
                <div class="card-subtitle" style="margin-bottom: 1.25rem;">Adjust per-client-IP request limits and burst tolerance.</div>
                
                <div class="form-row">
                    <div style="flex: 1;">
                        <label style="font-size: 0.8rem; color: var(--text-muted); display: block; margin-bottom: 0.3rem;">Requests Per Minute</label>
                        <input type="number" id="setting-rpm" class="input-text" value="120">
                    </div>
                    <div style="flex: 1;">
                        <label style="font-size: 0.8rem; color: var(--text-muted); display: block; margin-bottom: 0.3rem;">Burst Token Capacity</label>
                        <input type="number" id="setting-burst" class="input-text" value="20">
                    </div>
                    <div style="display: flex; align-items: flex-end;">
                        <button class="btn-primary" onclick="saveRateLimits()">Save Rate Limits</button>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title">Raw Policy File (config/policy.json)</div>
                        <div class="card-subtitle">Direct JSON configuration editor with syntax validation.</div>
                    </div>
                    <button class="btn-primary" onclick="saveRawPolicy()">💾 Save & Hot-Reload</button>
                </div>
                <textarea id="policy-raw-json" class="input-text" style="width: 100%; height: 260px; font-family: monospace; font-size: 0.85rem;"></textarea>
            </div>
        </div>
    </div>

    <div id="toast">Policy updated successfully!</div>

    <script>
        let currentPolicy = null;

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 3000);
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tabId).classList.add('active');
        }

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                const btn = document.getElementById('win-proxy-btn');
                const lbl = document.getElementById('win-proxy-label');
                if (data.windows_proxy_enabled) {
                    btn.classList.add('active');
                    lbl.innerText = 'Windows Proxy: ON';
                } else {
                    btn.classList.remove('active');
                    lbl.innerText = 'Windows Proxy: OFF';
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function toggleWindowsProxy() {
            try {
                const btn = document.getElementById('win-proxy-btn');
                const willEnable = !btn.classList.contains('active');
                const res = await fetch('/api/windows-proxy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({enable: willEnable})
                });
                const data = await res.json();
                showToast(data.message);
                fetchStatus();
            } catch (e) {
                showToast('Failed to toggle Windows proxy');
            }
        }

        async function loadPolicy() {
            try {
                const res = await fetch('/api/policy');
                currentPolicy = await res.json();

                // Update settings tab
                document.getElementById('policy-raw-json').value = JSON.stringify(currentPolicy, null, 2);
                if (currentPolicy.rate_limit) {
                    document.getElementById('setting-rpm').value = currentPolicy.rate_limit.requests_per_minute || 120;
                    document.getElementById('setting-burst').value = currentPolicy.rate_limit.burst || 20;
                    document.getElementById('stat-rate-limit').innerText = (currentPolicy.rate_limit.requests_per_minute || 120) + ' RPM';
                    document.getElementById('stat-burst-limit').innerText = 'Burst cap: ' + (currentPolicy.rate_limit.burst || 20) + ' tokens';
                }

                document.getElementById('stat-blocked-cats').innerText = (currentPolicy.blocked_categories || []).length;

                renderCategories();
                renderAllowlist();
            } catch (e) {
                console.error(e);
            }
        }

        function renderCategories() {
            const container = document.getElementById('categories-container');
            const targetSelect = document.getElementById('new-domain-target');
            container.innerHTML = '';
            
            // Re-populate select options
            targetSelect.innerHTML = '<option value="allowlist">⭐️ Allowlist (Always Allow)</option>';

            const blockedSet = new Set(currentPolicy.blocked_categories || []);

            for (const [cat, domains] of Object.entries(currentPolicy.categories || {})) {
                const isBlocked = blockedSet.has(cat);
                const opt = document.createElement('option');
                opt.value = cat;
                opt.innerText = 'Category: ' + cat;
                targetSelect.appendChild(opt);

                const card = document.createElement('div');
                card.className = 'cat-card ' + (isBlocked ? 'blocked' : 'allowed');

                const chipsHtml = domains.map(d => `
                    <span class="chip">
                        ${d}
                        <span class="chip-del" onclick="removeDomainFromCat('${cat}', '${d}')">&times;</span>
                    </span>
                `).join('');

                card.innerHTML = `
                    <div>
                        <div class="cat-header">
                            <div>
                                <div class="cat-name">${cat}</div>
                                <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 2px;">${domains.length} domain rules</div>
                            </div>
                            <span class="cat-status-badge ${isBlocked ? 'badge-blocked' : 'badge-allowed'}">
                                ${isBlocked ? 'Blocked' : 'Allowed'}
                            </span>
                        </div>
                        <div class="chips-container">${chipsHtml || '<span style="font-size:0.75rem;color:var(--text-dim);">No domains added</span>'}</div>
                    </div>
                    <div class="cat-footer">
                        <span style="font-size: 0.8rem; color: var(--text-muted);">${isBlocked ? 'Traffic Denied (403)' : 'Traffic Allowed'}</span>
                        <label class="switch">
                            <input type="checkbox" ${isBlocked ? 'checked' : ''} onchange="toggleCategoryBlock('${cat}', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                `;
                container.appendChild(card);
            }
        }

        function renderAllowlist() {
            const chips = document.getElementById('allowlist-chips');
            const list = currentPolicy.allowlist || [];
            chips.innerHTML = list.map(d => `
                <span class="chip" style="border-color: rgba(16, 185, 129, 0.3);">
                    ${d}
                    <span class="chip-del" onclick="removeAllowlistDomain('${d}')">&times;</span>
                </span>
            `).join('') || '<span style="font-size:0.8rem;color:var(--text-dim);">No allowlisted domains</span>';
        }

        async function toggleCategoryBlock(cat, shouldBlock) {
            let blocked = new Set(currentPolicy.blocked_categories || []);
            if (shouldBlock) blocked.add(cat);
            else blocked.delete(cat);
            currentPolicy.blocked_categories = Array.from(blocked);
            await savePolicyToServer();
        }

        async function removeDomainFromCat(cat, domain) {
            if (!currentPolicy.categories[cat]) return;
            currentPolicy.categories[cat] = currentPolicy.categories[cat].filter(d => d !== domain);
            await savePolicyToServer();
        }

        async function removeAllowlistDomain(domain) {
            currentPolicy.allowlist = (currentPolicy.allowlist || []).filter(d => d !== domain);
            await savePolicyToServer();
        }

        async function addDomainRule() {
            let domain = document.getElementById('new-domain-input').value.trim();
            const target = document.getElementById('new-domain-target').value;
            if (!domain) return;
            if (domain.includes('://')) {
                domain = domain.split('://')[1];
            }
            domain = domain.split('/')[0].split(':')[0].trim();

            if (target === 'allowlist') {
                if (!currentPolicy.allowlist) currentPolicy.allowlist = [];
                if (!currentPolicy.allowlist.includes(domain)) currentPolicy.allowlist.push(domain);
            } else {
                if (!currentPolicy.categories[target]) currentPolicy.categories[target] = [];
                if (!currentPolicy.categories[target].includes(domain)) currentPolicy.categories[target].push(domain);
            }

            document.getElementById('new-domain-input').value = '';
            await savePolicyToServer();
        }

        async function saveRateLimits() {
            const rpm = parseInt(document.getElementById('setting-rpm').value);
            const burst = parseInt(document.getElementById('setting-burst').value);
            currentPolicy.rate_limit = { requests_per_minute: rpm, burst: burst };
            await savePolicyToServer();
        }

        async function saveRawPolicy() {
            try {
                const parsed = JSON.parse(document.getElementById('policy-raw-json').value);
                currentPolicy = parsed;
                await savePolicyToServer();
            } catch (e) {
                showToast('Invalid JSON syntax!');
            }
        }

        async function savePolicyToServer() {
            try {
                const res = await fetch('/api/policy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(currentPolicy)
                });
                const data = await res.json();
                showToast(data.message || 'Policy saved & reloaded!');
                loadPolicy();
            } catch (e) {
                showToast('Failed to save policy');
            }
        }

        function quickTest(domain) {
            document.getElementById('test-domain-input').value = domain;
            testDomain();
        }

        async function testDomain() {
            let rawInput = document.getElementById('test-domain-input').value.trim();
            if (!rawInput) return;
            let domain = rawInput;
            if (domain.includes('://')) {
                domain = domain.split('://')[1];
            }
            domain = domain.split('/')[0].split(':')[0].trim();
            try {
                const res = await fetch('/api/test-domain?domain=' + encodeURIComponent(domain), {
                    cache: 'no-store'
                });
                const data = await res.json();
                
                const box = document.getElementById('verdict-result');
                const hostSpan = document.getElementById('verdict-host');
                const badge = document.getElementById('verdict-badge');
                const reason = document.getElementById('verdict-reason');
                const cat = document.getElementById('verdict-category');
                const hintDiv = document.getElementById('verdict-hint');

                hostSpan.innerText = data.domain || rawInput;
                reason.innerText = data.reason;
                cat.innerText = data.category || 'none';

                if (data.hint) {
                    hintDiv.innerText = data.hint;
                    hintDiv.style.display = 'block';
                } else if (rawInput === '.example' || rawInput === 'example') {
                    hintDiv.innerText = "💡 Notice: '.example' is a top-level domain suffix (TLD). The blocked malware rule in your policy is 'evil.example'. Click the '🛑 evil.example' button above!";
                    hintDiv.style.display = 'block';
                } else if (domain === 'evil.com') {
                    hintDiv.innerText = "💡 Notice: In config/policy.json, the test site is 'evil.example' (RFC test domain), not 'evil.com'. Click the '🛑 evil.example' button above!";
                    hintDiv.style.display = 'block';
                } else {
                    hintDiv.style.display = 'none';
                }

                const previewLink = document.getElementById('verdict-preview-link');
                if (data.action === 'block') {
                    badge.className = 'cat-status-badge badge-blocked';
                    badge.innerText = 'BLOCKED (403)';
                    if (previewLink) {
                        previewLink.href = '/blocked?host=' + encodeURIComponent(data.domain || rawInput) + '&category=' + encodeURIComponent(data.category || 'unknown');
                        previewLink.style.display = 'inline-flex';
                    }
                } else {
                    badge.className = 'cat-status-badge badge-allowed';
                    badge.innerText = 'ALLOWED';
                    if (previewLink) previewLink.style.display = 'none';
                }
                box.style.display = 'block';
            } catch (e) {
                showToast('Error inspecting domain');
            }
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs?limit=40');
                const data = await res.json();
                const tbody = document.getElementById('logs-table-body');
                
                document.getElementById('stat-total-requests').innerText = data.total_count || data.logs.length;
                document.getElementById('stat-blocked-requests').innerText = data.blocked_count || 0;

                if (!data.logs || data.logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-dim);">No requests logged yet</td></tr>';
                    return;
                }

                tbody.innerHTML = data.logs.map(log => {
                    let actionBadge = '<span class="cat-status-badge badge-allowed">allow</span>';
                    if (log.action === 'block') actionBadge = '<span class="cat-status-badge badge-blocked">block</span>';
                    if (log.action === 'rate_limited') actionBadge = '<span class="cat-status-badge badge-ratelimited">rate_limited</span>';

                    const timeStr = (log.timestamp || '').split('T')[1]?.split('.')[0] || '-';
                    const categoryText = log.category !== '-' ? log.category : (log.reason || '-');

                    return `
                        <tr>
                            <td>${timeStr}</td>
                            <td style="font-family: monospace;">${log.client_ip || '-'}</td>
                            <td><strong>${log.method || '-'}</strong></td>
                            <td style="font-family: monospace;">${log.host || '-'}</td>
                            <td>${actionBadge}</td>
                            <td>${categoryText}</td>
                            <td>${log.status || '-'}</td>
                            <td>${log.latency_ms !== undefined ? log.latency_ms + 'ms' : '-'}</td>
                        </tr>
                    `;
                }).join('');
            } catch (e) {
                console.error(e);
            }
        }

        // Initialize and polling
        fetchStatus();
        loadPolicy();
        fetchLogs();
        setInterval(fetchLogs, 4000);
        setInterval(fetchStatus, 8000);
    </script>
</body>
</html>
"""


async def handle_admin_request(req, reader, writer, ctx, get_policy_cb, reload_policy_cb):
    """Processes requests directed to the Admin Dashboard and Admin REST APIs."""
    path = req.target
    if path.startswith("http://") or path.startswith("https://"):
        parsed = urllib.parse.urlparse(path)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

    raw_path = path.split("?")[0]
    query_str = path.split("?")[1] if "?" in path else ""
    query_params = urllib.parse.parse_qs(query_str)

    # 1. GET / or /admin -> Serves the dashboard HTML
    if raw_path in ("/", "/admin"):
        body = DASHBOARD_HTML.encode("utf-8")
        resp = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"Cache-Control: no-cache, no-store, must-revalidate\r\n"
            f"Pragma: no-cache\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8") + body
        writer.write(resp)
        await writer.drain()
        ctx.status = 200
        return True

    # 1b. GET /blocked -> Preview block page directly in browser
    if raw_path == "/blocked":
        from miniswg.proxy import make_html_block_page
        b_host = query_params.get("host", ["blocked.example"])[0]
        b_cat = query_params.get("category", ["malware"])[0]
        body = make_html_block_page(b_host, b_cat)
        resp = (
            f"HTTP/1.1 403 Forbidden\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8") + body
        writer.write(resp)
        await writer.drain()
        ctx.status = 403
        return True

    # 2. GET /api/status -> Server and proxy status
    if raw_path == "/api/status" and req.method == "GET":
        win_enabled, win_server = is_windows_proxy_enabled()
        status_data = {
            "status": "online",
            "uptime_seconds": int(time.time() - SERVER_START_TIME),
            "windows_proxy_enabled": win_enabled,
            "windows_proxy_server": win_server,
        }
        body = json.dumps(status_data).encode("utf-8")
        resp = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8") + body
        writer.write(resp)
        await writer.drain()
        ctx.status = 200
        return True

    # 3. GET /api/policy -> Fetch current policy JSON
    if raw_path == "/api/policy" and req.method == "GET":
        policy_path = "config/policy.json"
        if os.path.exists(policy_path):
            with open(policy_path, "r", encoding="utf-8") as f:
                body = f.read().encode("utf-8")
        else:
            body = b"{}"
        resp = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8") + body
        writer.write(resp)
        await writer.drain()
        ctx.status = 200
        return True

    # 4. POST /api/policy -> Update policy JSON and reload
    if raw_path == "/api/policy" and req.method == "POST":
        try:
            payload = json.loads(req.body.decode("utf-8"))
            policy_path = "config/policy.json"
            os.makedirs(os.path.dirname(policy_path), exist_ok=True)
            with open(policy_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            reload_policy_cb(policy_path)
            res_body = json.dumps({"success": True, "message": "Policy updated and reloaded live!"}).encode("utf-8")
            status_code = 200
        except Exception as e:
            res_body = json.dumps({"success": False, "error": str(e)}).encode("utf-8")
            status_code = 400

        resp = (
            f"HTTP/1.1 {status_code} OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(res_body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8") + res_body
        writer.write(resp)
        await writer.drain()
        ctx.status = status_code
        return True

    # 5. GET /api/test-domain -> Inspect policy verdict for a domain
    if raw_path == "/api/test-domain" and req.method == "GET":
        raw_domain = query_params.get("domain", [""])[0].strip()
        if "://" in raw_domain:
            parsed = urllib.parse.urlparse(raw_domain)
            domain = parsed.hostname or raw_domain
        else:
            domain = raw_domain.split("/")[0].split(":")[0]

        policy = get_policy_cb()
        if policy:
            decision = policy.evaluate(domain)
            result = {
                "domain": domain,
                "action": decision.action,
                "reason": decision.reason,
                "category": decision.category,
            }
        else:
            result = {
                "domain": domain,
                "action": "allow",
                "reason": "no_policy_loaded",
                "category": None,
            }

        # Contextual guidance hints for common misunderstandings
        if raw_domain in (".example", "example") or domain in (".example", "example") or domain.startswith("."):
            result["hint"] = "💡 Notice: '.example' is a top-level domain suffix (TLD). The blocked malware rule in your policy is 'evil.example'. Try inspecting 'evil.example'!"
        elif domain == "evil.com":
            result["hint"] = "💡 Notice: In config/policy.json, the test site is 'evil.example' (RFC test domain), not 'evil.com'. Try inspecting 'evil.example'!"

        body = json.dumps(result).encode("utf-8")
        resp = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Cache-Control: no-cache, no-store, must-revalidate\r\n"
            f"Pragma: no-cache\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8") + body
        writer.write(resp)
        await writer.drain()
        ctx.status = 200
        return True

    # 6. GET /api/logs -> Recent access logs
    if raw_path == "/api/logs" and req.method == "GET":
        limit = int(query_params.get("limit", ["50"])[0])
        log_file = "logs/access.log"
        entries = []
        blocked_count = 0
        total_count = 0
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                total_count = len(lines)
                for line in lines:
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        e = json.loads(line_s)
                        if e.get("action") == "block":
                            blocked_count += 1
                        entries.append(e)
                    except Exception:
                        pass
                entries = entries[-limit:]
                entries.reverse()  # Newest first
            except Exception:
                pass

        body = json.dumps({
            "logs": entries,
            "total_count": total_count,
            "blocked_count": blocked_count,
        }).encode("utf-8")
        resp = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8") + body
        writer.write(resp)
        await writer.drain()
        ctx.status = 200
        return True

    # 7. POST /api/windows-proxy -> Enable or disable Windows system proxy
    if raw_path == "/api/windows-proxy" and req.method == "POST":
        try:
            payload = json.loads(req.body.decode("utf-8")) if req.body else {}
            enable = payload.get("enable", True)
            port = payload.get("port", 8080)
            if enable:
                success = enable_windows_proxy(port=port)
                msg = f"Windows system proxy enabled on 127.0.0.1:{port}"
            else:
                success = disable_windows_proxy()
                msg = "Windows system proxy disabled. Direct internet connection restored."
            body = json.dumps({"success": success, "message": msg}).encode("utf-8")
            status_code = 200
        except Exception as e:
            body = json.dumps({"success": False, "error": str(e)}).encode("utf-8")
            status_code = 400

        resp = (
            f"HTTP/1.1 {status_code} OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8") + body
        writer.write(resp)
        await writer.drain()
        ctx.status = status_code
        return True

    return False
