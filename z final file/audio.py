import logging
import platform
import socket
import subprocess
import time
import pyaudio
import threading
from config import app_config

PORT = 50009
CHUNK_SIZE = 1024
RATE = 44100
CHANNELS = 1
VIRTUAL_CABLE_DEVICE = "CABLE Output"

# Globals for shutdown
audio_socket = None
is_streaming = True

def log_info(msg):
    print(msg)
    logging.info(msg)

def cleanup():
    global audio_socket, is_streaming
    is_streaming = False
    if audio_socket:
        try:
            audio_socket.shutdown(socket.SHUT_RDWR)
            audio_socket.close()
            log_info("[Audio] Socket closed.")
        except Exception as e:
            log_info(f"[Audio] Cleanup error: {e}")
        audio_socket = None

def run_audio_receiver():
    global audio_socket, is_streaming

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    audio_socket.bind(('0.0.0.0', PORT))
    audio_socket.listen(1)
    log_info("🎧 [Audio] Receiver waiting for connection...")

    conn, addr = audio_socket.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    log_info(f"✅ [Audio] Connected by {addr}")

    try:
        while is_streaming:
            data = conn.recv(CHUNK_SIZE * 2)
            if not data:
                break
            stream.write(data)
    except Exception as e:
        log_info(f"[Audio] Receiver error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        conn.close()
        audio_socket.close()
        log_info("[Audio] Receiver stopped")

def run_audio_sender_windows():
    global audio_socket, is_streaming

    p = pyaudio.PyAudio()
    device_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if VIRTUAL_CABLE_DEVICE in info.get('name'):
            device_index = i
            break
    if device_index is None:
        raise RuntimeError(f"[Audio] Could not find device: {VIRTUAL_CABLE_DEVICE}")

    audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    audio_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    for attempt in range(10):
        try:
            audio_socket.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            log_info(f"[Audio] Attempt {attempt + 1}: {e}")
            time.sleep(1)
    else:
        log_info("[Audio] Connection failed.")
        return

    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK_SIZE)

    log_info("[Audio] Streaming audio from Virtual Cable...")
    try:
        while is_streaming:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_socket.sendall(data)
    except Exception as e:
        log_info(f"[Audio] Sender error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        audio_socket.close()
        log_info("[Audio] Sender stopped")

def run_audio_sender_linux():
    global audio_socket, is_streaming

    def get_monitor():
        try:
            sink = subprocess.check_output(["pactl", "get-default-sink"], text=True).strip()
            return f"{sink}.monitor"
        except Exception as e:
            raise RuntimeError(f"Failed to get monitor source: {e}")

    monitor_source = get_monitor()
    audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    audio_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    for attempt in range(10):
        try:
            audio_socket.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            log_info(f"[Audio] Attempt {attempt + 1}: {e}")
            time.sleep(1)
    else:
        log_info("[Audio] Connection failed.")
        return

    cmd = ["parec", "--format=s16le", "--rate=44100", "--channels=1", "-d", monitor_source]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    log_info("[Audio] Streaming audio from PulseAudio...")
    try:
        while is_streaming:
            data = proc.stdout.read(CHUNK_SIZE)
            if not data:
                break
            audio_socket.sendall(data)
    except Exception as e:
        log_info(f"[Audio] Sender error: {e}")
    finally:
        proc.terminate()
        audio_socket.close()
        log_info("[Audio] Sender stopped")

def main():
    os_type = platform.system().lower()

    def stop_monitor():
        while app_config.is_running and not app_config.stop_flag:
            time.sleep(0.5)
        cleanup()

    if app_config.audio_mode == "Share_Audio":
        if "windows" in os_type:
            run_audio_sender_windows()
        elif "linux" in os_type:
            run_audio_sender_linux()
    elif app_config.audio_mode == "Receive_Audio":
        run_audio_receiver()

    threading.Thread(target=stop_monitor, daemon=True).start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a", format="%(levelname)s - %(message)s")
    try:
        main()
    except Exception as e:
        log_info(f"[Audio] Fatal error: {e}")
        cleanup()
