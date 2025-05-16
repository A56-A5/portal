import sys
import socket
import threading
import platform
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QRadioButton, QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import pyqtSignal

try:
    import pyaudio
except ImportError:
    pyaudio = None

class AudioShareWidget(QWidget):
    status_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.mode = 'client'
        self.audio_thread = None
        self.running = False
        self.init_ui()

    def init_ui(self):
        self.layout().addWidget(QLabel("Audio Share Mode:"))
        self.rb_client = QRadioButton("Client")
        self.rb_server = QRadioButton("Server")
        self.rb_client.setChecked(True)
        self.layout().addWidget(self.rb_client)
        self.layout().addWidget(self.rb_server)
        self.rb_client.toggled.connect(lambda checked: self.set_mode('client' if checked else 'server'))
        self.layout().addWidget(QLabel("Server IP (Client Only):"))
        self.ip_entry = QLineEdit()
        self.layout().addWidget(self.ip_entry)
        self.start_btn = QPushButton("Start Audio Share")
        self.stop_btn = QPushButton("Stop Audio Share")
        self.stop_btn.setEnabled(False)
        self.layout().addWidget(self.start_btn)
        self.layout().addWidget(self.stop_btn)
        self.status_label = QLabel("")
        self.layout().addWidget(self.status_label)
        self.start_btn.clicked.connect(self.start_audio)
        self.stop_btn.clicked.connect(self.stop_audio)
        self.set_mode('client')

    def set_mode(self, mode):
        self.mode = mode
        self.ip_entry.setEnabled(mode == 'client')

    def start_audio(self):
        if not pyaudio:
            QMessageBox.critical(self, "Error", "PyAudio is not installed.")
            return
        self.running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Audio sharing started.")
        if self.mode == 'server':
            self.audio_thread = threading.Thread(target=self.run_server, daemon=True)
        else:
            ip = self.ip_entry.text().strip()
            if not ip:
                QMessageBox.critical(self, "Error", "Please enter a server IP.")
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                return
            self.audio_thread = threading.Thread(target=self.run_client, args=(ip,), daemon=True)
        self.audio_thread.start()

    def stop_audio(self):
        self.running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Audio sharing stopped.")

    def run_server(self):
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        PORT = 50007
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)
        s = socket.socket()
        s.bind(('0.0.0.0', PORT))
        s.listen(1)
        self.status_label.setText("Waiting for audio connection...")
        try:
            conn, addr = s.accept()
            self.status_label.setText(f"Connected by {addr}")
            while self.running:
                data = conn.recv(CHUNK * 2)
                if not data:
                    break
                stream.write(data)
        except Exception as e:
            self.status_label.setText(f"Audio server error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            s.close()
            self.status_label.setText("Audio server stopped.")

    def run_client(self, ip):
        PORT = 50007
        CHUNK_SIZE = 4096
        p = pyaudio.PyAudio()
        # Try to find a working input device
        device_index = None
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                device_index = i
                break
        if device_index is None:
            self.status_label.setText("No input device found.")
            return
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, input_device_index=device_index, frames_per_buffer=CHUNK_SIZE)
        s = socket.socket()
        try:
            s.connect((ip, PORT))
            self.status_label.setText(f"Connected to server {ip}")
            while self.running:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                if not data:
                    break
                s.sendall(data)
        except Exception as e:
            self.status_label.setText(f"Audio client error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            s.close()
            self.status_label.setText("Audio client stopped.") 