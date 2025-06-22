import socket
import subprocess
import platform
import time
import logging
import threading
import pyaudio
from config import app_config

PORT = 50009
CHUNK_SIZE = 512
RATE = 44100 
CHANNELS = 1
VIRTUAL_CABLE_DEVICE = "CABLE Output"

logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a", format="[Audio] - %(message)s")

def cleanup(sock=None, process=None, unmute=False):
    try:
        if process:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception as e:
                logging.error(f"⚠️ Error terminating process: {e}")
        if sock:
            try:
                sock.close()
            except Exception as e:
                logging.error(f"⚠️ Error closing socket: {e}")
    finally:
        logging.info("Cleaned up audio resources.")

def receive_audio():
    
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', PORT))

    print("🔊 Receiving audio...")
    logging.info("[Audio] Listening...")
    try:
        while True:
            data, _ = sock.recvfrom(CHUNK_SIZE)
            stream.write(data)
    except KeyboardInterrupt:
        print("❌ Receiver stopped.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        sock.close()

def send_audio_linux():
    def get_monitor_source():
        result = subprocess.run(['pactl', 'list', 'short', 'sources'], capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if '.monitor' in line:
                return line.split('\t')[1]
        raise RuntimeError("❌ No monitor source found.")

    def mute_output():
        subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '1'])

    def unmute_output():
        subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '0'])

    def send_audio_linux():
        monitor = get_monitor_source()
        mute_output()

        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'pulse',
            '-i', monitor,
            '-ac', str(CHANNELS),
            '-ar', str(RATE),
            '-f', 's16le',
            '-loglevel', 'quiet',
            '-'
        ]
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

        print(f"📤 Sending audio from {monitor} (muted locally)")
        try:
            while True:
                data = process.stdout.read(CHUNK_SIZE)
                if not data:
                    break
                sock.sendto(data, (app_config.audio_ip, PORT))
        except KeyboardInterrupt:
            print("❌ Sender stopped.")
        finally:
            unmute_output()
            sock.close()
            process.terminate()

def send_audio_windows():

    device_index = None
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        if VIRTUAL_CABLE_DEVICE in device_info.get('name'):
            device_index = i
            break

    if device_index is None:
        raise RuntimeError(f"[Audio] Could not find device: {VIRTUAL_CABLE_DEVICE}")

    device_info = p.get_device_info_by_index(device_index)
    if device_info['maxInputChannels'] < 1:
        raise RuntimeError(f"[Audio] Device '{VIRTUAL_CABLE_DEVICE}' does not support input channels.")
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK_SIZE)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    print("📤 Sending audio from VB-Cable...")
    try:
        while True:
            data = stream.read(CHUNK_SIZE)
            sock.sendto(data, (app_config.audio_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
    finally:
        sock.close()

def main():
    def monitor_stop():
        while True:
            if not app_config.is_running:
                cleanup()
                break
            time.sleep(1)

    threading.Thread(target=monitor_stop, daemon=True).start()

    os_type = platform.system().lower()
    if app_config.audio_mode == "Receive_Audio":
        receive_audio()
    elif app_config.audio_mode == "Share_Audio":
        if os_type == "linux":
            send_audio_linux()
        elif os_type == "windows":
            send_audio_windows()
        else:
            print(f"❌ Unsupported OS: {os_type}")
            logging.info("Unsupported OS")
    else:
        print("❌ Invalid audio_mode in config.")
        logging.info("Invalid audio_mode in config.")

if __name__ == "__main__":
    main()
