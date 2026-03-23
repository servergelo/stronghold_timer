from flask import request
from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================= TIMER STORAGE =================
timers = {}

# ================= SOCKET.IO EVENTS =================
@socketio.on('connect')
def handle_connect():
    print(f"✅ Client connected: {request.sid if 'request' in dir() else 'unknown'}")
    
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
    
    # 🔥 IMPORTANT: OUTSIDE LOOP
    emit('current_timers', active_timers)
    print(f"📤 Sent {len(active_timers)} active timers to new client")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"❌ Client disconnected: {request.sid if 'request' in dir() else 'unknown'}")

@socketio.on('start_timer')
def start_timer(data):
    try:
        print(f"🚀 Timer started: {data}")
        
        boss = data.get('boss')
        level = data.get('level')
        channel = data.get('channel')
        duration = data.get('duration')
        started_at = data.get('startedAt', int(time.time() * 1000))
        
        # Create timer key
        timer_key = f"{boss}_{level}_{channel}"
        
        # Store timer
        timers[timer_key] = {
            'boss': boss,
            'level': level,
            'channel': channel,
            'duration': duration,
            'startedAt': started_at
        }
        
        print(f"💾 Stored timer: {timer_key}")
        print(f"📊 Total active timers: {len(timers)}")
        
        # Broadcast to all clients
        socketio.emit('timer_started', {
            'boss': boss,
            'level': level,
            'channel': channel,
            'duration': duration,
            'startedAt': started_at
        }, broadcast=True)
    
    except Exception as e:
        print(f"❌ Error starting timer: {e}")

@socketio.on('reset_timer')
def reset_timer(data):
    try:
        print("🔄 RESET RECEIVED:", data)
        
        # 🔥 HANDLE BROADCAST RESET (ALL)
        if data.get('boss') == 'ALL':
            print("🔄 CLEARING ALL TIMERS")
            timers.clear()
            # Broadcast reset to all clients with reset flag
            socketio.emit('timer_reset', {
                **data,
                "reset": True
            }, broadcast=True)
            print(f"✅ All timers cleared. Total timers: {len(timers)}")
            return
        
        # 🔥 HANDLE SPECIFIC TIMER RESET
        timer_key = f"{data['boss']}_{data['level']}_{data['channel']}"
        
        if timer_key in timers:
            del timers[timer_key]
            print(f"✅ Deleted timer: {timer_key}")
            print(f"📊 Remaining timers: {len(timers)}")
        else:
            print(f"⚠️ Timer not found: {timer_key}")
        
        # 🔥 BROADCAST RESET TO ALL CLIENTS with reset flag
        socketio.emit('timer_reset', {
            **data,
            "reset": True
        }, broadcast=True)
    
    except Exception as e:
        print(f"❌ Error resetting timer: {e}")

@socketio.on('boss_up')
def boss_up(data):
    try:
        print(f"🎉 BOSS UP: {data}")
        
        boss = data.get('boss')
        level = data.get('level')
        channel = data.get('channel', 'BOSS_UP')
        
        # Remove timer from storage
        timer_key = f"{boss}_{level}_{channel}"
        if timer_key in timers:
            del timers[timer_key]
            print(f"💾 Removed timer: {timer_key}")
        
        # Broadcast to all clients
        socketio.emit('timer_started', {
            'boss': boss,
            'level': level,
            'channel': 'BOSS_UP'
        }, broadcast=True)
    
    except Exception as e:
        print(f"❌ Error broadcasting boss up: {e}")

# ================= CLEANUP OLD TIMERS =================
def cleanup_expired_timers():
    """Remove expired timers from storage"""
    current_time = int(time.time() * 1000)
    expired_keys = []
    
    for timer_key, timer_data in timers.items():
        elapsed = (current_time - timer_data['startedAt']) // 1000
        
        if elapsed >= timer_data['duration']:
            expired_keys.append(timer_key)
    
    for key in expired_keys:
        del timers[key]
        print(f"🧹 Cleaned up expired timer: {key}")
    
    if expired_keys:
        print(f"📊 Total active timers after cleanup: {len(timers)}")

# ================= ROUTES =================
@app.route('/')
def index():
    return {
        'status': 'running',
        'service': 'Stronghold Boss Timer Server',
        'version': '1.0.0',
        'active_timers': len(timers)
    }

@app.route('/timers')
def get_timers():
    """Get all active timers"""
    cleanup_expired_timers()
    
    active_timers = []
    current_time = int(time.time() * 1000)
    
    for timer_key, timer_data in timers.items():
        elapsed = (current_time - timer_data['startedAt']) // 1000
        
        active_timers.append({
            'boss': timer_data['boss'],
            'level': timer_data['level'],
            'channel': timer_data['channel'],
            'duration': timer_data['duration'],
            'startedAt': timer_data['startedAt'],
            'elapsed': elapsed,
            'remaining': timer_data['duration'] - elapsed
        })
    
    return {
        'timers': active_timers,
        'count': len(active_timers)
    }

@app.route('/clear')
def clear_all():
    """Clear all timers (admin endpoint)"""
    timers.clear()
    socketio.emit('timer_reset', {
        'boss': 'ALL',
        'level': 'ALL',
        'channel': 'ALL',
        'reset': True
    }, broadcast=True)
    
    return {
        'status': 'cleared',
        'message': 'All timers cleared'
    }

# ================= RUN SERVER =================
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 STRONGHOLD BOSS TIMER SERVER")
    print("=" * 50)
    print("📡 Starting Socket.IO server...")
    print("🌐 CORS enabled for all origins")
    print("=" * 50)
    
    # Run with production settings for Render
    socketio.run(
        app,
        host='0.0.0.0',
        port=10000,
        debug=False,
        allow_unsafe_werkzeug=True
    )
