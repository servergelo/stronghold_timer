APP_VERSION = "1.0.0"

import requests
import sys
import subprocess
import os
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QDialog, QCheckBox, QComboBox,
    QSystemTrayIcon, QStyle, QMenu,
    QSizePolicy, QGraphicsDropShadowEffect,
    QMessageBox, QProgressDialog)

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QFontDatabase

import winsound
from winotify import Notification
import socketio
import threading
import time

def force_update(parent=None):
    print("Auto-update check disabled for development")
    return

def download_update(url, parent=None):
    try:
        print("Downloading update...")
        progress = QProgressDialog(
            "Downloading update...", 
            "Cancel", 
            0, 
            100, 
            parent
        )
        progress.setWindowTitle("Downloading Update")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        progress.show()
        
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        update_filename = "stronghold_timer_update.exe"
        
        with open(update_filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if progress.wasCanceled():
                    print("Download cancelled by user")
                    if os.path.exists(update_filename):
                        os.remove(update_filename)
                    return False
                
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        progress.setValue(percent)
        
        progress.setValue(100)
        print(f"Download complete: {update_filename}")
        
        try:
            subprocess.Popen([update_filename])
            print("Launched new version")
            return True
        except Exception as e:
            print(f"Failed to launch update: {e}")
            return False
        
    except requests.exceptions.RequestException as e:
        print(f"Download failed (network error): {e}")
        return False
    except Exception as e:
        print(f"Download failed (unexpected error): {e}")
        return False

def check_for_optional_update(parent=None):
    try:
        print(f"Checking for optional updates... Current version: {APP_VERSION}")
        url = "https://raw.githubusercontent.com/servergelo/stronghold_timer/main/version.json"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()
        
        latest_version = data.get("version")
        download_url = data.get("url")
        
        if latest_version and latest_version != APP_VERSION:
            msg = QMessageBox(parent)
            msg.setWindowTitle("Update Available")
            msg.setText(
                f"A new version is available!\n\n"
                f"Current Version: {APP_VERSION}\n"
                f"Latest Version: {latest_version}\n\n"
                f"Would you like to update now?"
            )
            msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | 
                QMessageBox.StandardButton.No
            )
            msg.setIcon(QMessageBox.Icon.Information)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                if download_update(download_url, parent):
                    sys.exit(0)
            
    except Exception as e:
        print(f"Optional update check failed: {e}")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

SETTINGS_FILE = "stronghold_settings.json"
TIMERS_FILE = "stronghold_timers.json"
PRIMARY_RED = "#C1121F"
DARK_RED = "#780000"
SOFT_RED = "#E63946"
GOLD = "#D4AF37"
LOGO_FILE = "1logo.png"
ICON_FILE = "2icon.ico"

# ===== WEBSOCKET OPTIMIZATION =====
sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1,
    reconnection_delay_max=5,
    request_timeout=10,
    engineio_logger=False,
    logger=False,
    transports=['websocket', 'polling']
)

class SocketSignals(QObject):
    timer_received = pyqtSignal(dict)

socket_signals = SocketSignals()

def load_gaming_fonts():
    fonts = [
        "Orbitron-Bold.ttf",
        "Rajdhani-SemiBold.ttf",
        "JetBrainsMono-Bold.ttf"
    ]
    for font in fonts:
        font_path = resource_path(font)
        if os.path.exists(font_path):
            QFontDatabase.addApplicationFont(font_path)

THEMES = {
    "Light": {
        "name": "Light",
        "bg": "#FFFFFF",
        "frame_bg": "#F4F4F4",
        "frame_border": "#444444",
        "text": "#000000",
        "button_bg": "#D0D0D0",
        "button_border": "#888888",
        "button_hover": "#E0E0E0",
        "timer_idle": "#C1121F",
        "timer_idle_border": "#780000",
        "timer_active": "#E63946",
        "timer_active_border": "#780000",
        "timer_ready": "#2ECC71",
        "timer_ready_border": "#27AE60",
        "timer_text": "#FFFFFF"
    },
    "Dark": {
        "name": "Dark",
        "bg": "#0D0D0D",
        "frame_bg": "#1A1A1A",
        "frame_border": "#2A2A2A",
        "text": "#EAEAEA",
        "button_bg": "#2A2A2A",
        "button_border": "#404040",
        "button_hover": "#353535",
        "timer_idle": "#3A3A3A",
        "timer_idle_border": "#2A2A2A",
        "timer_active": "#4A4A4A",
        "timer_active_border": "#2A2A2A",
        "timer_ready": "#1E7E34",
        "timer_ready_border": "#155724",
        "timer_text": "#FFFFFF"
    },
    "Ocean Blue": {
        "name": "Ocean Blue",
        "bg": "#0A1929",
        "frame_bg": "#132F4C",
        "frame_border": "#1E4976",
        "text": "#E3F2FD",
        "button_bg": "#1E4976",
        "button_border": "#2E5F8F",
        "button_hover": "#2A5F8F",
        "timer_idle": "#1565C0",
        "timer_idle_border": "#0D47A1",
        "timer_active": "#1976D2",
        "timer_active_border": "#0D47A1",
        "timer_ready": "#00897B",
        "timer_ready_border": "#00695C",
        "timer_text": "#FFFFFF"
    },
    "Purple Night": {
        "name": "Purple Night",
        "bg": "#1A0B2E",
        "frame_bg": "#2D1B4E",
        "frame_border": "#4A2C6D",
        "text": "#E8D9FF",
        "button_bg": "#4A2C6D",
        "button_border": "#6B3FA0",
        "button_hover": "#5B3C80",
        "timer_idle": "#7B2CBF",
        "timer_idle_border": "#5A1E9D",
        "timer_active": "#9D4EDD",
        "timer_active_border": "#7B2CBF",
        "timer_ready": "#06B6D4",
        "timer_ready_border": "#0891B2",
        "timer_text": "#FFFFFF"
    },
    "Forest Green": {
        "name": "Forest Green",
        "bg": "#0D1F0D",
        "frame_bg": "#1B3A1B",
        "frame_border": "#2D5A2D",
        "text": "#D4F1D4",
        "button_bg": "#2D5A2D",
        "button_border": "#3D7A3D",
        "button_hover": "#3D6A3D",
        "timer_idle": "#2E7D32",
        "timer_idle_border": "#1B5E20",
        "timer_active": "#43A047",
        "timer_active_border": "#2E7D32",
        "timer_ready": "#FFB300",
        "timer_ready_border": "#FF8F00",
        "timer_text": "#FFFFFF"
    },
    "Midnight": {
        "name": "Midnight",
        "bg": "#000000",
        "frame_bg": "#0F0F0F",
        "frame_border": "#1F1F1F",
        "text": "#F5F5F5",
        "button_bg": "#1F1F1F",
        "button_border": "#2F2F2F",
        "button_hover": "#2A2A2A",
        "timer_idle": "#424242",
        "timer_idle_border": "#212121",
        "timer_active": "#616161",
        "timer_active_border": "#424242",
        "timer_ready": "#00BCD4",
        "timer_ready_border": "#0097A7",
        "timer_text": "#FFFFFF"
    }
}

HEADER_FONT = QFont("Orbitron", 16, QFont.Weight.Bold)

class EarlySpawnDialog(QDialog):
    def __init__(self, theme_name="Light"):
        super().__init__()
        self.theme = THEMES[theme_name]
        self.setWindowTitle("Stronghold Boss Timer")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        icon_path = resource_path(ICON_FILE)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setFixedSize(320, 140)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.content = QWidget()
        
        self.content.setStyleSheet(f"""
            background-color:{self.theme['frame_bg']};
            border-radius:12px;
            border:2px solid {self.theme['frame_border']};
        """)
        
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        label = QLabel("Confirm Early Spawn?")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"font-size:16px;font-weight:bold;color:{self.theme['text']};background:transparent;")
        
        button_layout = QHBoxLayout()
        yes_btn = QPushButton("Yes")
        no_btn = QPushButton("No*
