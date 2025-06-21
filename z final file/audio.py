import socket
import subprocess
import platform
import re
import pyaudio
import time
from config import app_config

PORT = 50009
CHUNK_SIZE = 1024
RATE = 44100
CHANNELS = 1

# === RECEIVER (works cross-platform) ===
def receive_audio():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', PORT))

    print("🔊 Receiving audio...")
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


# === SENDER LINUX ===
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


# === SENDER WINDOWS ===
def send_audio_windows():
    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'dshow',
        '-i', 'audio=CABLE Output (VB-Audio Virtual Cable)',
        '-ac', str(CHANNELS),
        '-ar', str(RATE),
        '-f', 's16le',
        '-loglevel', 'quiet',
        '-'
    ]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

    print("📤 Sending audio from VB-Cable...")
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


# === ENTRY POINT ===
def main():
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
    else:
        print("❌ Invalid audio_mode in config.")

if __name__ == "__main__":
    main()
