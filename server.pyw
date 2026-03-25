import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QThread, pyqtSignal
import webbrowser
from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from datetime import datetime, timedelta
import time
import json
import threading

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ===== FLASK APP SETUP =====
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode=None,
    ping_timeout=60,
    ping_interval=25,
    engineio_logger=False,
    socketio_logger=False
)

timers = {}
history_file = "timer_history.json"

def load_history():
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history):
    try:
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save history: {e}")

history = load_history()

@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    print(f"\n[CONNECT] Client connected: {client_id}")
    
    active_timers = []
    current_time = int(time.time() * 1000)
    
    for timer_key, timer_data in timers.items():
        elapsed = (current_time - timer_data['startedAt']) // 1000
        if elapsed < timer_data['duration']:
            active_timers.append({
                'boss': timer_data['boss'],
                'level': timer_data['level'],
                'channel': timer_data['channel'],
                'duration': timer_data['duration'],
                'startedAt': timer_data['startedAt']
            })
    
    print(f"[SEND] Sending {len(active_timers)} timers\n")
    emit('current_timers', active_timers)

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[DISCONNECT] Client disconnected\n")

@socketio.on('start_timer')
def start_timer(data):
    try:
        print(f"\n[START_TIMER] Received")
        
        boss = data.get('boss')
        level = data.get('level')
        channel = data.get('channel')
        duration = data.get('duration')
        started_at = data.get('startedAt', int(time.time() * 1000))
        
        if not all([boss, level, channel, duration]):
            print(f"[ERROR] Missing fields")
            return
        
        timer_key = f"{boss}_{level}_{channel}"
        timers[timer_key] = {
            'boss': boss,
            'level': level,
            'channel': channel,
            'duration': duration,
            'startedAt': started_at
        }
        
        print(f"[STORE] {timer_key}")
        print(f"[TOTAL] {len(timers)} timers active")
        
        broadcast_data = {
            'boss': boss,
            'level': level,
            'channel': channel,
            'duration': duration,
            'startedAt': started_at
        }
        
        print(f"[BROADCAST] Sending to all clients\n")
        socketio.emit('timer_started', broadcast_data)
    
    except Exception as e:
        print(f"[ERROR] {e}\n")

@socketio.on('reset_timer')
def reset_timer(data):
    try:
        print(f"\n[RESET_TIMER] Received")
        
        if data.get('boss') == 'ALL':
            print(f"[RESET] Clearing all timers")
            timers.clear()
            
            broadcast_data = {
                'boss': 'ALL',
                'level': 'ALL',
                'channel': 'ALL',
                'reset': True
            }
            
            print(f"[BROADCAST] Sending reset to all clients\n")
            socketio.emit('timer_reset', broadcast_data)
            return
        
        timer_key = f"{data['boss']}_{data['level']}_{data['channel']}"
        if timer_key in timers:
            del timers[timer_key]
            print(f"[DELETE] {timer_key}")
        
        broadcast_data = {
            'boss': data.get('boss'),
            'level': data.get('level'),
            'channel': data.get('channel'),
            'reset': True
        }
        
        print(f"[BROADCAST] Sending reset to all clients\n")
        socketio.emit('timer_reset', broadcast_data)
    
    except Exception as e:
        print(f"[ERROR] {e}\n")

@socketio.on('timer_completed')
def timer_completed(data):
    try:
        print(f"\n[TIMER_COMPLETED] {data.get('boss')} {data.get('level')}")
        
        history_entry = {
            'boss': data.get('boss'),
            'level': data.get('level'),
            'channel': data.get('channel'),
            'completed_at': datetime.now().isoformat(),
            'duration': data.get('duration')
        }
        history.append(history_entry)
        save_history(history)
        
        print(f"[HISTORY] Saved completion. Total: {len(history)}\n")
        
    except Exception as e:
        print(f"[ERROR] {e}\n")

# ===== REST API ENDPOINTS =====

@app.route('/server-time', methods=['GET'])
def get_server_time():
    return jsonify({
        'timestamp': int(time.time() * 1000),
        'datetime': datetime.now().isoformat()
    })

@app.route('/timers', methods=['GET'])
def get_timers():
    active_timers = []
    current_time = int(time.time() * 1000)
    
    for timer_key, timer_data in timers.items():
        elapsed = (current_time - timer_data['startedAt']) // 1000
        remaining = max(0, timer_data['duration'] - elapsed)
        
        active_timers.append({
            'boss': timer_data['boss'],
            'level': timer_data['level'],
            'channel': timer_data['channel'],
            'duration': timer_data['duration'],
            'elapsed': elapsed,
            'remaining': remaining,
            'started_at': timer_data['startedAt']
        })
    
    return jsonify({'timers': active_timers, 'count': len(active_timers)})

@app.route('/history', methods=['GET'])
def get_history():
    days = request.args.get('days', 7, type=int)
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_history = [
        h for h in history 
        if datetime.fromisoformat(h['completed_at']) > cutoff_date
    ]
    return jsonify({'history': recent_history, 'count': len(recent_history)})

@app.route('/statistics', methods=['GET'])
def get_statistics():
    if not history:
        return jsonify({'stats': {}, 'message': 'No history data'})
    
    stats = {}
    for entry in history:
        boss = entry.get('boss')
        level = entry.get('level')
        key = f"{boss} {level}"
        
        if key not in stats:
            stats[key] = {'count': 0, 'last_spawn': None}
        
        stats[key]['count'] += 1
        stats[key]['last_spawn'] = entry.get('completed_at')
    
    return jsonify({
        'stats': stats,
        'total_spawns': len(history),
        'unique_bosses': len(set([h['boss'] for h in history]))
    })

@app.route('/clear', methods=['POST'])
def clear_all():
    timers.clear()
    socketio.emit('timer_reset', {
        'boss': 'ALL',
        'level': 'ALL',
        'channel': 'ALL',
        'reset': True
    })
    return jsonify({'status': 'cleared', 'message': 'All timers cleared'})

@app.route('/')
def index():
    return serve_dashboard()

def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Stronghold Boss Timer - Web Dashboard</title>
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                background: linear-gradient(135deg, #0D0D0D 0%, #1A1A1A 100%);
                color: #EAEAEA;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            
            header {
                text-align: center;
                margin-bottom: 40px;
                padding: 20px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                border: 1px solid rgba(193, 18, 31, 0.3);
            }
            
            h1 {
                font-size: 2.5em;
                color: #E63946;
                margin-bottom: 10px;
            }
            
            .status {
                display: flex;
                justify-content: center;
                gap: 30px;
                margin-top: 15px;
                flex-wrap: wrap;
            }
            
            .status-item {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 0.95em;
            }
            
            .status-dot {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background: #2ECC71;
                animation: pulse 2s infinite;
            }
            
            .status-dot.offline {
                background: #E74C3C;
                animation: none;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }
            
            .card {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(193, 18, 31, 0.3);
                border-radius: 12px;
                padding: 20px;
                backdrop-filter: blur(10px);
            }
            
            .card h2 {
                color: #E63946;
                margin-bottom: 15px;
                font-size: 1.3em;
            }
            
            .timer-item {
                background: rgba(255, 255, 255, 0.05);
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 10px;
                border-left: 4px solid #E63946;
            }
            
            .timer-item:last-child {
                margin-bottom: 0;
            }
            
            .timer-boss {
                font-weight: bold;
                color: #E63946;
                font-size: 1.1em;
            }
            
            .timer-info {
                font-size: 0.9em;
                color: #AAA;
                margin-top: 5px;
            }
            
            .timer-bar {
                background: rgba(0, 0, 0, 0.3);
                height: 6px;
                border-radius: 3px;
                margin-top: 8px;
                overflow: hidden;
            }
            
            .timer-bar-fill {
                background: linear-gradient(90deg, #E63946, #C1121F);
                height: 100%;
                transition: width 0.3s ease;
                border-radius: 3px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
            }
            
            .stat-box {
                background: rgba(230, 57, 70, 0.1);
                border: 1px solid rgba(230, 57, 70, 0.3);
                border-radius: 8px;
                padding: 15px;
                text-align: center;
            }
            
            .stat-number {
                font-size: 2em;
                color: #E63946;
                font-weight: bold;
            }
            
            .stat-label {
                font-size: 0.9em;
                color: #AAA;
                margin-top: 5px;
            }
            
            .history-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9em;
            }
            
            .history-table thead {
                background: rgba(230, 57, 70, 0.1);
            }
            
            .history-table th {
                padding: 12px;
                text-align: left;
                color: #E63946;
                font-weight: bold;
            }
            
            .history-table td {
                padding: 10px 12px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
            
            .history-table tbody tr:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            
            .empty-message {
                text-align: center;
                color: #AAA;
                padding: 20px;
                font-style: italic;
            }
            
            button {
                background: #E63946;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s;
                margin-right: 10px;
                margin-bottom: 10px;
            }
            
            button:hover {
                background: #C1121F;
                transform: translateY(-2px);
            }
            
            button:active {
                transform: translateY(0);
            }
            
            .button-group {
                margin-bottom: 15px;
            }
            
            @media (max-width: 768px) {
                h1 {
                    font-size: 1.8em;
                }
                
                .grid {
                    grid-template-columns: 1fr;
                }
                
                .status {
                    flex-direction: column;
                    gap: 10px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>⚔️ STRONGHOLD BOSS TIMER</h1>
                <p>Web Dashboard & Real-time Monitoring</p>
                <div class="status">
                    <div class="status-item">
                        <div class="status-dot" id="connection-status"></div>
                        <span id="connection-text">Connecting...</span>
                    </div>
                    <div class="status-item">
                        <span>Active Timers: <strong id="timer-count">0</strong></span>
                    </div>
                    <div class="status-item">
                        <span>Server: <strong id="server-time">--:--:--</strong></span>
                    </div>
                </div>
            </header>
            
            <div class="grid">
                <div class="card">
                    <h2>⏱️ Active Timers</h2>
                    <div id="active-timers" class="empty-message">No active timers</div>
                </div>
                
                <div class="card">
                    <h2>📊 Statistics</h2>
                    <div class="stats-grid" id="statistics">
                        <div class="stat-box">
                            <div class="stat-number" id="total-spawns">0</div>
                            <div class="stat-label">Total Spawns</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-number" id="unique-bosses">0</div>
                            <div class="stat-label">Unique Bosses</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h2>🎮 Controls</h2>
                    <div class="button-group">
                        <button onclick="clearAllTimers()">🗑️ Clear All Timers</button>
                        <button onclick="refreshData()">🔄 Refresh Data</button>
                    </div>
                    <p style="font-size: 0.9em; color: #AAA;">Last updated: <span id="last-updated">--:--:--</span></p>
                </div>
            </div>
            
            <div class="card">
                <h2>📜 Recent Spawns (Last 7 Days)</h2>
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>Boss</th>
                            <th>Level</th>
                            <th>Channel</th>
                            <th>Time</th>
                        </tr>
                    </thead>
                    <tbody id="history-table">
                        <tr><td colspan="4" class="empty-message">No history data</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            const socket = io();
            let timers = [];
            let history = [];
            
            socket.on('connect', () => {
                console.log('Connected to server');
                updateConnectionStatus(true);
            });
            
            socket.on('disconnect', () => {
                console.log('Disconnected from server');
                updateConnectionStatus(false);
            });
            
            socket.on('timer_started', (data) => {
                refreshData();
            });
            
            socket.on('timer_reset', (data) => {
                refreshData();
            });
            
            socket.on('current_timers', (data) => {
                timers = data;
                renderTimers();
            });
            
            function updateConnectionStatus(connected) {
                const dot = document.getElementById('connection-status');
                const text = document.getElementById('connection-text');
                
                if (connected) {
                    dot.className = 'status-dot';
                    text.textContent = 'Connected';
                } else {
                    dot.className = 'status-dot offline';
                    text.textContent = 'Disconnected';
                }
            }
            
            function renderTimers() {
                fetch('/timers')
                    .then(r => r.json())
                    .then(data => {
                        timers = data.timers;
                        document.getElementById('timer-count').textContent = timers.length;
                        
                        const container = document.getElementById('active-timers');
                        
                        if (timers.length === 0) {
                            container.innerHTML = '<div class="empty-message">No active timers</div>';
                            return;
                        }
                        
                        let html = '';
                        timers.forEach(timer => {
                            const percent = Math.min(100, (timer.elapsed / timer.duration) * 100);
                            const minutes = Math.floor(timer.remaining / 60);
                            const seconds = timer.remaining % 60;
                            
                            html += `
                                <div class="timer-item">
                                    <div class="timer-boss">${timer.boss} - ${timer.level}</div>
                                    <div class="timer-info">
                                        Channel: ${timer.channel} | 
                                        Remaining: ${minutes}m ${seconds}s
                                    </div>
                                    <div class="timer-bar">
                                        <div class="timer-bar-fill" style="width: ${percent}%"></div>
                                    </div>
                                </div>
                            `;
                        });
                        
                        container.innerHTML = html;
                    });
            }
            
            function loadStatistics() {
                fetch('/statistics')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('total-spawns').textContent = data.total_spawns || 0;
                        document.getElementById('unique-bosses').textContent = data.unique_bosses || 0;
                    });
            }
            
            function loadHistory() {
                fetch('/history?days=7')
                    .then(r => r.json())
                    .then(data => {
                        history = data.history || [];
                        renderHistory();
                    });
            }
            
            function renderHistory() {
                const tbody = document.getElementById('history-table');
                
                if (history.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" class="empty-message">No history data</td></tr>';
                    return;
                }
                
                let html = '';
                history.slice().reverse().slice(0, 20).forEach(entry => {
                    const date = new Date(entry.completed_at);
                    const time = date.toLocaleTimeString();
                    
                    html += `
                        <tr>
                            <td>${entry.boss}</td>
                            <td>${entry.level}</td>
                            <td>${entry.channel}</td>
                            <td>${time}</td>
                        </tr>
                    `;
                });
                
                tbody.innerHTML = html;
            }
            
            function refreshData() {
                renderTimers();
                loadStatistics();
                loadHistory();
                updateServerTime();
            }
            
            function updateServerTime() {
                fetch('/server-time')
                    .then(r => r.json())
                    .then(data => {
                        const date = new Date(data.datetime);
                        document.getElementById('server-time').textContent = date.toLocaleTimeString();
                        document.getElementById('last-updated').textContent = date.toLocaleTimeString();
                    });
            }
            
            function clearAllTimers() {
                if (confirm('Are you sure you want to clear ALL timers?')) {
                    fetch('/clear', { method: 'POST' })
                        .then(() => {
                            refreshData();
                            alert('All timers cleared!');
                        });
                }
            }
            
            setInterval(refreshData, 1000);
            refreshData();
        </script>
    </body>
    </html>
    """

# ===== PYQT6 TRAY APP =====

class ServerThread(QThread):
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.daemon = True
    
    def run(self):
        try:
            logger.info(f"Starting server on port {self.port}")
            self.status_changed.emit(f"Starting on port {self.port}...")
            
            print(f"\n{'='*60}")
            print("STRONGHOLD BOSS TIMER SERVER v1.0.0")
            print(f"{'='*60}")
            print(f"Starting on 0.0.0.0:{self.port}")
            print(f"\n🌐 Web Dashboard: http://localhost:{self.port}")
            print(f"{'='*60}\n")
            
            self.status_changed.emit(f"Running on port {self.port}")
            socketio.run(app, host='0.0.0.0', port=self.port, debug=False, allow_unsafe_werkzeug=True)
        
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.error_occurred.emit(str(e))
            self.status_changed.emit(f"Error: {e}")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ServerTrayApp:
    def __init__(self):
        try:
            self.port = int(os.environ.get('PORT', 10000))
        except ValueError:
            logger.error("Invalid PORT value")
            raise ValueError("PORT must be an integer")
        
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.error("System tray not available")
            QMessageBox.critical(None, "Error", "System tray not available on this system.")
            sys.exit(1)
        
        self.tray = QSystemTrayIcon()
        self._set_icon()
        self.tray.setToolTip("Stronghold Boss Timer Server")
        
        menu = QMenu()
        
        self.status_action = menu.addAction("Status: Starting...")
        self.status_action.setEnabled(False)
        
        menu.addSeparator()
        
        dashboard_action = menu.addAction("🌐 Open Dashboard")
        dashboard_action.triggered.connect(self.open_dashboard)
        
        menu.addSeparator()
        
        exit_action = menu.addAction("❌ Exit Server")
        exit_action.triggered.connect(self.quit_app)
        
        self.tray.setContextMenu(menu)
        self.tray.show()
        
        self.server_thread = ServerThread(self.port)
        self.server_thread.status_changed.connect(self.update_status)
        self.server_thread.error_occurred.connect(self.on_error)
        self.server_thread.start()
        
        self.tray.showMessage(
            "Server Started",
            f"Stronghold Boss Timer Server is running on port {self.port}!",
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )
        
        logger.info(f"Tray app initialized on port {self.port}")
    
    def _set_icon(self):
        icon_path = resource_path("2icon.ico")
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
            logger.info(f"Loaded icon from {icon_path}")
        else:
            logger.warning(f"Icon not found at {icon_path}, using default")
    
    def update_status(self, status):
        self.status_action.setText(f"Status: {status}")
    
    def on_error(self, error_msg):
        logger.error(f"Server error: {error_msg}")
        self.tray.showMessage(
            "Server Error",
            error_msg,
            QSystemTrayIcon.MessageIcon.Critical,
            5000
        )
    
    def open_dashboard(self):
        url = f"http://localhost:{self.port}"
        logger.info(f"Opening dashboard at {url}")
        webbrowser.open(url)
    
    def quit_app(self):
        logger.info("Shutting down server...")
        self.tray.showMessage(
            "Shutdown",
            "Server shutting down...",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )
        self.server_thread.quit()
        self.server_thread.wait(timeout=5000)
        self.tray.hide()
        self.app.quit()
        sys.exit(0)

if __name__ == '__main__':
    logger.info("Stronghold Boss Timer Tray App Starting")
    tray_app = ServerTrayApp()
    sys.exit(tray_app.app.exec())