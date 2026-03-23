import eventlet
eventlet.monkey_patch()

from flask import Flask
from flask_socketio import SocketIO, emit
import time
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

timers = {}

@app.route("/")
def home():
    return "Server is running ✅"

def clean_expired_timers():
    current_time = int(time.time() * 1000)
    expired_keys = []

    for key, timer in timers.items():
        elapsed = (current_time - timer['startedAt']) // 1000
        if elapsed >= timer['duration']:
            expired_keys.append(key)

    for key in expired_keys:
        del timers[key]

@socketio.on('connect')
def handle_connect():
    print("Client connected")
    clean_expired_timers()
    emit('current_timers', list(timers.values()))

@socketio.on('start_timer')
def start_timer(data):
    timer_key = f"{data['boss']}_{data['level']}_{data['channel']}"
    timers[timer_key] = data
    print("Timer started:", timer_key)
    socketio.emit('timer_started', data)

@socketio.on('reset_timer')
def reset_timer(data):
    if not all(k in data for k in ['boss', 'level', 'channel']):
        return

    timer_key = f"{data['boss']}_{data['level']}_{data['channel']}"
    if timer_key in timers:
        del timers[timer_key]
        socketio.emit('timer_reset', data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)