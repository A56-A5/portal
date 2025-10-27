import socket
import subprocess
import platform
import time
import logging
import threading
import sounddevice as sd
import numpy as np
from utils.config import app_config

target_ip = app_config.audio_ip

PORT = app_config.audio_port
CHANNELS = 2
RATE = 44100 
FORMAT = 's16le'
CHUNK_SIZE = 1024

sock , process = None , None 

INPUT = 'audio=Stereo Mix (Realtek(R) Audio)'

logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a", format="[Audio] - %(message)s")

def cleanup(sock=None, process=None):
    try:
        if process:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception as e:
                logging.error(f"Error terminating process: {e}")
        if sock:
            try:
                sock.close()
            except Exception as e:
                logging.error(f"Error closing socket: {e}")
    finally:
        logging.info("Cleaned up audio resources.")

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
    print(f"Sending audio  {target_ip}:{PORT}")
    logging.info(f"Sending audio {target_ip}:{PORT}")

    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'pulse',
        '-i', monitor,
        '-ac', str(CHANNELS),
        '-ar', str(RATE),
        '-f', 's16le',
        '-loglevel', 'info',
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
            sock.sendto(data, (target_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
    finally:
        unmute_output()
        cleanup(sock,process)

def send_audio_windows():
    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'dshow',
        '-i', str(INPUT),  
        '-ar', str(RATE),
        '-ac' , str(CHANNELS),
        '-f', 's16le',
        '-loglevel', 'info',
        '-'
    ]

    print(f"Sending audio  {target_ip}:{PORT}")
    logging.info(f"Sending audio {target_ip}:{PORT}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = process.stdout.read(CHUNK_SIZE)
            if not data:
                break
            sock.sendto(data, (target_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Audio sending stopped.")
    finally:
        cleanup(sock,process)
def receive_audio():
    print(f"Playing Audio...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))

    stream = sd.OutputStream(
        samplerate=RATE,
        channels=CHANNELS,
        dtype='int16',
        blocksize=CHUNK_SIZE
    )

    try:
        with stream:
            while True:
                data, _ = sock.recvfrom(CHUNK_SIZE * CHANNELS * 2) 
                audio_array = np.frombuffer(data, dtype='int16').reshape(-1, CHANNELS)
                stream.write(audio_array)
    except KeyboardInterrupt:
        print("❌ Receiver stopped.")
    finally:
        cleanup(sock)

def receive_audio_ffplay():
    print(f"🎧 Receiving audio via ffplay on port {PORT}...")
    cmd = [
        'ffplay',
        '-f', FORMAT,
        '-ac', str(CHANNELS),
        '-ar', str(RATE),
        '-i', f'udp://0.0.0.0:{PORT}',
        '-autoexit'  
    ]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("❌ Receiver stopped.")

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
            receive_audio_ffplay()
        elif os_type == "windows":
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
