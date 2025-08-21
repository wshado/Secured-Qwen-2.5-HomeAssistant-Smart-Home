#!/usr/bin/env python3
"""
Simple PyQt5 Chat Client for Home Assistant Conversation
--------------------------------------------------------

This client sends user messages as `conversation_utterance` events to Home Assistant
and listens for `conversation_response` events via the HA WebSocket API.

Dependencies:
  pip install PyQt5 requests websocket-client

Usage:
  python3 chat_client.py

Configure your HA URL and Long-Lived Token below.
"""

import sys
import json
import threading
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit,
    QLineEdit, QPushButton, QVBoxLayout, QWidget
)
from PyQt5.QtCore import pyqtSignal, QObject
from websocket import WebSocketApp
import os
from pathlib import Path

# Load environment variables
def load_env():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

load_env()

# ==== Configuration ====
HA_URL = os.getenv("HA_URL", "http://localhost:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "your-token-here")
# =======================

class EventListener(QObject):
    new_message = pyqtSignal(str)

    def __init__(self, ha_url, token):
        super().__init__()
        self.ws_url = ha_url.replace("http://", "ws://") \
                            .replace("https://", "wss://") + "/api/websocket"
        self.token = token
        self.ws_app = WebSocketApp(
            self.ws_url,
            on_open    = self.on_open,
            on_message = self.on_message,
            on_close   = self.on_close,
            on_error   = self.on_error
        )

    def start(self):
        print(f"[ChatClient] Connecting to {self.ws_url}")
        threading.Thread(target=self.ws_app.run_forever, daemon=True).start()

    def on_open(self, ws):
        print("[ChatClient] WebSocket opened, waiting for auth_required")

    def on_message(self, ws, message):
        data = json.loads(message)
        msg_type = data.get("type")
        print(f"[ChatClient] Received WS message: {data}")

        if msg_type == "auth_required":
            print("[ChatClient] Sending auth")
            ws.send(json.dumps({
                "type":         "auth",
                "access_token": self.token
            }))
            return

        if msg_type == "auth_ok":
            print("[ChatClient] Auth OK, subscribing to conversation_response")
            ws.send(json.dumps({
                "id":         1,
                "type":       "subscribe_events",
                "event_type": "conversation_response"
            }))
            return

        # subscription confirmation comes back as type: "result"
        if msg_type == "result" and data.get("id") == 1:
            print("[ChatClient] Successfully subscribed to conversation_response")
            return

        # now handle actual events
        if msg_type == "event" and data["event"]["event_type"] == "conversation_response":
            text = data["event"]["data"].get("text", "")
            print(f"[ChatClient] conversation_response → {text}")
            self.new_message.emit(text)

    def on_close(self, ws, close_status, close_msg):
        print(f"[ChatClient] WebSocket closed: {close_status} / {close_msg}")

    def on_error(self, ws, error):
        print(f"[ChatClient] WebSocket error: {error}")

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Home Assistant Qwen Chat")
        self.resize(400, 600)

        self.chat_area = QTextEdit(self)
        self.chat_area.setReadOnly(True)

        self.input_line = QLineEdit(self)
        self.input_line.returnPressed.connect(self.send_message)

        self.send_button = QPushButton("Send", self)
        self.send_button.clicked.connect(self.send_message)

        layout = QVBoxLayout()
        layout.addWidget(self.chat_area)
        layout.addWidget(self.input_line)
        layout.addWidget(self.send_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Start listening for HA events
        self.listener = EventListener(HA_URL, HA_TOKEN)
        self.listener.new_message.connect(self.display_bot_message)
        self.listener.start()

    def display_bot_message(self, text):
        self.chat_area.append(f"<b>Qwen:</b> {text}")

    def send_message(self):
        message = self.input_line.text().strip()
        if not message:
            return
        self.chat_area.append(f"<b>You:</b> {message}")
        self.input_line.clear()

        url = f"{HA_URL}/api/events/conversation_utterance"
        headers = {
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {"text": message}
        try:
            requests.post(url, headers=headers, json=payload, timeout=5)
        except Exception as e:
            self.chat_area.append(f"<span style='color:red;'>Error: {e}</span>")


def main():
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
