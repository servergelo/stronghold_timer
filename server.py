from flask import request
from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import time
import threading

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ================= TIMER STORAGE =================
timers = {}

# ================= SOCKET.IO EVENTS =================
@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    print(f"\n✅ Client connected: {client_id}")
    print(f"📊 Current timers in storage: {len(timers)}")
    
    # Build active timers list
    active_timers = []
    current_time = int(time.time() * 1000)
    
    for timer_key, timer_data in timers.items():
        elapsed = (current_time - timer_data['startedAt']) // 1000
        
        if elapsed < timer_data['duration']:
            timer_obj = {
                'boss': timer_data['boss'],
                'level': timer_data['level'],
                'channel': timer_data['channel'],
                'duration': timer_data['duration'],
                'startedAt': timer_data['startedAt']
            }
            active_timers.append(timer_obj)
            print(f"  ✓ Adding timer: {timer_key} (elapsed: {elapsed}s)")
    
    print(f"📤 Emitting 'current_timers' with {len(active_timers)} timers")
    print(f"   Timers: {active_timers}\n")
    
    # 🔥 Emit to THIS CLIENT ONLY
    emit('current_timers', active_timers)

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    print(f"❌ Client disconnected: {client_id}\n")

@socketio.on('start_timer')
def start_timer(data):
    try:
        print(f"\n🚀 'start_timer' event received!")
        print(f"   Data: {data}")
        
        boss = data.get('boss')
        level = data.get('level')
        channel = data.get('channel')
        duration = data.get('duration')
        started_at = data.get('startedAt', int(time.time() * 1000))
        
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
        
        # 🔥 BROADCAST TO ALL CLIENTS
        broadcast_data = {
            'boss': boss,
            'level': level,
            'channel': channel,
            'duration': duration,
            'startedAt': started_at
        }
        
        print(f"📡 Broadcasting 'timer_started' to ALL clients:")
        print(f"   {broadcast_data}\n")
        
        socketio.emit('timer_started', broadcast_data, broadcast=True)
    
    except Exception as e:
        print(f"❌ Error in start_timer: {e}\n")
        import traceback
        traceback.print_exc()

@socketio.on('reset_timer')
def reset_timer(data):
    try:
        print(f"\n🔄 'reset_timer' event received!")
        print(f"   Data: {data}")
        
        # HANDLE BROADCAST RESET (ALL)
        if data.get('boss') == 'ALL':
            print("🔄 CLEARING ALL TIMERS")
            timers.clear()
            
            broadcast_data = {
                'boss': 'ALL',
                'level': 'ALL',
                'channel': 'ALL',
                'reset': True
            }
            
            print(f"📡 Broadcasting 'timer_reset' to ALL clients:")
            print(f"   {broadcast_data}\n")
            
            socketio.emit('timer_reset', broadcast_data, broadcast=True)
            print(f"✅ All timers cleared\n")
            return
        
        # HANDLE SPECIFIC TIMER RESET
        timer_key = f"{data['boss']}_{data['level']}_{data['channel']}"
        
        if timer_key in timers:
            del timers[timer_key]
            print(f"✅ Deleted timer: {timer_key}")
        else:
            print(f"⚠️ Timer not found: {timer_key}")
        
        print(f"📊 Remaining timers: {len(timers)}")
        
        broadcast_data = {
            'boss': data.get('boss'),
            'level': data.get('level'),
            'channel': data.get('channel'),
            'reset': True
        }
        
        print(f"📡 Broadcasting 'timer_reset' to ALL clients:")
        print(f"   {broadcast_data}\n")
        
        socketio.emit('timer_reset', broadcast_data, broadcast=True)
    
    except Exception as e:
        print(f"❌ Error in reset_timer: {e}\n")
        import traceback
        traceback.print_exc()

@socketio.on('request_sync')
def request_sync():
    """Manual sync request from client"""
    client_id = request.sid
    print(f"\n🔄 'request_sync' event received from {client_id}")
    
    active_timers = []
    current_time = int(time.time() * 1000)
    
    for timer_key, timer_data in timers.items():
        elapsed = (current_time - timer_data['startedAt']) // 1000
        
        if elapsed < timer_data['duration']:
            timer_obj = {
                'boss': timer_data['boss'],
                'level': timer_data['level'],
                'channel': timer_data['channel'],
                'duration': timer_data['duration'],
                'startedAt': timer_data['startedAt']
            }
            active_timers.append(timer_obj)
    
    print(f"📤 Emitting 'current_timers' to {client_id} with {len(active_timers)} timers")
    print(f"   Timers: {active_timers}\n")
    
    emit('current_timers', active_timers)

@socketio.on('boss_up')
def boss_up(data):
    try:
        print(f"\n🎉 'boss_up' event received!")
        print(f"   Data: {data}")
        
        boss = data.get('boss')
        level = data.get('level')
        channel = data.get('channel', 'BOSS_UP')
        
        timer_key = f"{boss}_{level}_{channel}"
        if timer_key in timers:
            del timers[timer_key]
            print(f"💾 Removed timer: {timer_key}")
        
        broadcast_data = {
            'boss': boss,
            'level': level,
            'channel': 'BOSS_UP'
        }
        
        print(f"📡 Broadcasting 'timer_started' (BOSS_UP) to ALL clients:")
        print(f"   {broadcast_data}\n")
        
        socketio.emit('timer_started', broadcast_data, broadcast=True)
    
    except Exception as e:
        print(f"❌ Error in boss_up: {e}\n")
        import traceback
        traceback.print_exc()

# ================= ROUTES =================
@app.route('/')
def index():
    return {
        'status': 'running',
        'service': 'Stronghold Boss Timer Server',
        'version': '1.0.0',
        'active_timers': len(timers),
        'timers': timers
    }

@app.route('/timers')
def get_timers():
    """Get all active timers"""
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
            'remaining': max(0, timer_data['duration'] - elapsed)
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
    print("\n" + "=" * 60)
    print("🚀 STRONGHOLD BOSS TIMER SERVER v1.0.0")
    print("=" * 60)
    print("📡 Starting Socket.IO server...")
    print("🌐 CORS enabled for all origins")
    print("🔗 Listening on 0.0.0.0:10000")
    print("=" * 60 + "\n")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=10000,
        debug=False,
        allow_unsafe_werkzeug=True
    )