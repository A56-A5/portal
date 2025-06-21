import socket
import subprocess
import platform
import re
import pyaudio
import time
from config import app_config

sock = None
process = None
stream = None
p = None


# === CLEANUP FUNCTION ===
def cleanup():
    global sock, process, stream, p
    print("🧹 Cleaning up...")
    try:
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()
        if sock:
            sock.close()
        if process:
            process.terminate()
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")


# === RECEIVER ===
def receive_audio():
    global sock, stream, p

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=app_config.channels,
                    rate=app_config.rate,
                    output=True,
                    frames_per_buffer=app_config.chunk)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', app_config.port))

    print("🔊 Receiving audio...")
    try:
        while True:
            data, _ = sock.recvfrom(app_config.chunk)
            stream.write(data)
    except KeyboardInterrupt:
        print("❌ Receiver stopped.")
    finally:
        cleanup()


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
    global sock, process
    monitor = get_monitor_source()
    mute_output()

    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'pulse',
        '-i', monitor,
        '-ac', str(app_config.channels),
        '-ar', str(app_config.rate),
        '-f', 's16le',
        '-loglevel', 'quiet',
        '-'
    ]

    for attempt in range(5):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(f"🔌 Socket created (attempt {attempt+1}/5)")
            break
        except Exception as e:
            print(f"⚠️ Socket creation failed: {e}")
            time.sleep(1)
    else:
        print("❌ Failed to create socket after 5 attempts.")
        return

    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
    print(f"📤 Sending audio from {monitor} (muted locally)")

    try:
        while True:
            data = process.stdout.read(app_config.chunk)
            if not data:
                break
            sock.sendto(data, (app_config.receiver_ip, app_config.port))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
    finally:
        unmute_output()
        cleanup()


# === SENDER WINDOWS ===
def send_audio_windows():
    global sock, process
    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'dshow',
        '-i', 'audio=CABLE Output (VB-Audio Virtual Cable)',
        '-ac', str(app_config.channels),
        '-ar', str(app_config.rate),
        '-f', 's16le',
        '-loglevel', 'quiet',
        '-'
    ]

    for attempt in range(5):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(f"🔌 Socket created (attempt {attempt+1}/5)")
            break
        except Exception as e:
            print(f"⚠️ Socket creation failed: {e}")
            time.sleep(1)
    else:
        print("❌ Failed to create socket after 5 attempts.")
        return

    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
    print("📤 Sending audio from VB-Cable...")

    try:
        while True:
            data = process.stdout.read(app_config.chunk)
            if not data:
                break
            sock.sendto(data, (app_config.receiver_ip, app_config.port))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
    finally:
        cleanup()


# === ENTRY POINT ===
def main():
    try:
        if app_config.audio_mode == "Receive_Audio":
            receive_audio()
        elif app_config.audio_mode == "Send_Audio":
            if app_config.os_type == "linux":
                send_audio_linux()
            elif app_config.os_type == "windows":
                send_audio_windows()
            else:
                print(f"❌ Unsupported OS: {app_config.os_type}")
        else:
            print("❌ Invalid audio_mode in config.")
    except Exception as e:
        print(f"🔥 Critical error: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
