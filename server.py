from flask import Flask, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ===== WEBSOCKET OPTIMIZATION =====
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    engineio_logger=False,
    socketio_logger=False
)

timers = {}

@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    print(f"\n[CONNECT] Client connected: {client_id}")
    print(f"[TRANSPORT] {request.environ.get('engineio.transport', 'unknown')}")
    print(f"[INFO] Current timers: {len(timers)}")
    
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
        socketio.emit('timer_started', broadcast_data, broadcast=True)
    
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
            socketio.emit('timer_reset', broadcast_data, broadcast=True)
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
        socketio.emit('timer_reset', broadcast_data, broadcast=True)
    
    except Exception as e:
        print(f"[ERROR] {e}\n")

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
    active_timers = []
    current_time = int(time.time() * 1000)
    
    for timer_key, timer_data in timers.items():
        elapsed = (current_time - timer_data['startedAt']) // 1000
        active_timers.append({
            'boss': timer_data['boss'],
            'level': timer_data['level'],
            'channel': timer_data['channel'],
            'duration': timer_data['duration'],
            'elapsed': elapsed,
            'remaining': max(0, timer_data['duration'] - elapsed)
        })
    
    return {'timers': active_timers, 'count': len(active_timers)}

@app.route('/clear')
def clear_all():
    timers.clear()
    socketio.emit('timer_reset', {
        'boss': 'ALL',
        'level': 'ALL',
        'channel': 'ALL',
        'reset': True
    }, broadcast=True)
    return {'status': 'cleared', 'message': 'All timers cleared'}

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("STRONGHOLD BOSS TIMER SERVER v1.0.0")
    print("=" * 60)
    print("Starting on 0.0.0.0:10000")
    print("=" * 60 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=10000, debug=False)