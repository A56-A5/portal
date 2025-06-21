import logging
import platform
import socket
import subprocess
import time
import threading
from config import app_config

PORT = 50009
CHUNK_SIZE = 1024  # matches ffmpeg output block
RATE = 44100
CHANNELS = 1
VIRTUAL_CABLE_DEVICE = "CABLE Output"

is_streaming = True
udp_socket = None

def log_info(msg):
    print(msg)
    logging.info(msg)

def cleanup():
    global udp_socket, is_streaming
    is_streaming = False
    if udp_socket:
        try:
            udp_socket.close()
            log_info("[Audio] UDP socket closed.")
        except Exception as e:
            log_info(f"[Audio] Cleanup error: {e}")
        udp_socket = None

def run_audio_receiver():
    global udp_socket, is_streaming

    import pyaudio
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(('0.0.0.0', PORT))
    log_info(f"🎧 [Audio] UDP Receiver started on port {PORT}")

    try:
        while is_streaming:
            data, _ = udp_socket.recvfrom(CHUNK_SIZE * 2)
            if data:
                stream.write(data)
    except Exception as e:
        log_info(f"[Audio] Receiver error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        udp_socket.close()
        log_info("[Audio] Receiver stopped")

def run_audio_sender_linux():
    global udp_socket, is_streaming

    try:
        subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "mute"], check=True)
        log_info("[Audio] Muted speaker output.")
    except Exception as e:
        log_info(f"[Audio] Failed to mute audio: {e}")

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    cmd = [
        "ffmpeg", "-f", "pulse", "-i", "default",
        "-ac", str(CHANNELS), "-ar", str(RATE), "-f", "s16le", "-"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    log_info("[Audio] Streaming audio with FFmpeg via UDP...")
    try:
        while is_streaming:
            data = proc.stdout.read(CHUNK_SIZE * 2)
            if not data:
                break
            udp_socket.sendto(data, (app_config.audio_ip, PORT))
    except Exception as e:
        log_info(f"[Audio] Sender error: {e}")
    finally:
        proc.terminate()
        udp_socket.close()
        log_info("[Audio] Sender stopped")

def run_audio_sender_windows():
    global udp_socket, is_streaming

    try:
        subprocess.run(["nircmd.exe", "mutesysvolume", "1"], check=True)
        log_info("[Audio] Muted system volume.")
    except Exception as e:
        log_info(f"[Audio] Failed to mute system volume: {e}")

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    cmd = [
        "ffmpeg", "-f", "dshow", "-i", f"audio={VIRTUAL_CABLE_DEVICE}",
        "-ac", str(CHANNELS), "-ar", str(RATE), "-f", "s16le", "-"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    log_info("[Audio] Streaming audio with FFmpeg via UDP (Windows)...")
    try:
        while is_streaming:
            data = proc.stdout.read(CHUNK_SIZE * 2)
            if not data:
                break
            udp_socket.sendto(data, (app_config.audio_ip, PORT))
    except Exception as e:
        log_info(f"[Audio] Sender error: {e}")
    finally:
        proc.terminate()
        udp_socket.close()
        log_info("[Audio] Sender stopped")

def main():
    os_type = platform.system().lower()

    def stop_monitor():
        while app_config.is_running and not app_config.stop_flag:
            time.sleep(0.5)
        cleanup()

    threading.Thread(target=stop_monitor, daemon=True).start()

    if app_config.audio_mode == "Share_Audio":
        if "windows" in os_type:
            run_audio_sender_windows()
        elif "linux" in os_type:
            run_audio_sender_linux()
    elif app_config.audio_mode == "Receive_Audio":
        run_audio_receiver()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a", format="%(levelname)s - %(message)s")
    try:
        main()
    except Exception as e:
        log_info(f"[Audio] Fatal error: {e}")
        cleanup()
