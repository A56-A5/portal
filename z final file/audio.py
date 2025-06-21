# audio.py
import socket
import platform
import threading
import time
import pyaudio
from config import app_config

PORT = 50009
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

s = None

def cleanup():
    global s
    try:
        s.shutdown(socket.SHUT_RDWR)
        s.close()
    except:
        pass

# Receiver: plays raw audio received via UDP
def run_audio_receiver():
    global s
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    output=True, frames_per_buffer=CHUNK)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", PORT))
    print("[Audio] Listening on UDP port", PORT)

    try:
        while True:
            data, _ = s.recvfrom(CHUNK * 2)  # 2 bytes per sample
            stream.write(data)
    except KeyboardInterrupt:
        print("[Audio] Stopped by user")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        cleanup()

# Sender: sends raw audio from input device via UDP
def run_audio_sender():
    global s
    p = pyaudio.PyAudio()
    print("[Audio] Looking for input device...")

    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, frames_per_buffer=CHUNK)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((app_config.audio_ip, PORT))
    print(f"[Audio] Sending audio to {app_config.audio_ip}:{PORT}")

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            s.send(data)
    except KeyboardInterrupt:
        print("[Audio] Stopped by user")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        cleanup()

def main():
    os_type = platform.system().lower()
    def monitor_stop():
        while app_config.is_running and not app_config.stop_flag:
            time.sleep(0.5)
        cleanup()

    threading.Thread(target=monitor_stop, daemon=True).start()

    if app_config.audio_mode == "Share_Audio":
        run_audio_sender()
    elif app_config.audio_mode == "Receive_Audio":
        run_audio_receiver()

if __name__ == "__main__":
    main()
