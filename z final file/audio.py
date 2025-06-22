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
VIRTUAL_CABLE_DEVICE = "CABLE Output (VB-Audio Virtual Cable)"

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
def run_audio_receiver():
    p = pyaudio.PyAudio()

    # Try to find a PulseAudio output device
    pulse_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        host_api_index = info['hostApi']
        host_api_name = p.get_host_api_info_by_index(host_api_index)['name'].lower()
        if "pulse" in info['name'].lower() or "pulse" in host_api_name:
            pulse_index = i
            print(f"[Audio] Using PulseAudio device: {info['name']} ({host_api_name})")
            break

    if pulse_index is None:
        print("[Audio] No PulseAudio output device found. Using default.")
        pulse_index = None  # fallback to default device

    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    output_device_index=pulse_index,
                    frames_per_buffer=CHUNK_SIZE)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', PORT))
    s.listen(1)
    print("Audio waiting")

    conn, addr = s.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print("Audio Connected by", addr)
    logging.info("[Audio] Connected")

    try:
        while True:
            data = conn.recvfrom(CHUNK_SIZE * 2)
            if not data:
                break
            stream.write(data)
    except KeyboardInterrupt:
        print("Server interrupted.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        conn.close()
        s.close()

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
    ffmpeg_cmd = [
           'ffmpeg',
           '-f', 'dshow',
           '-i', f'audio={VIRTUAL_CABLE_DEVICE}',
           '-ac', str(CHANNELS),
           '-ar', str(RATE),
           '-f', 's16le',
           '-loglevel', 'quiet',
           '-'
       ]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
    print(f"📤 Sending audio from {VIRTUAL_CABLE_DEVICE} using FFmpeg...")
    try:
        while True:
            data = process.stdout.read(CHUNK_SIZE)
            if not data:
                break
            sock.sendto(data, (app_config.audio_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
    finally:
        sock.close()
        process.terminate()

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
        if os_type == "linux":
            run_audio_receiver()
        else:
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
