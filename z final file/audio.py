import socket
import subprocess
import platform
import time
import logging
import threading
import pyaudio
from config import app_config

PORT = 50009
CHUNK_SIZE = 1024
RATE = 44100
CHANNELS = 1

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
        if unmute:
            if platform.system().lower() == 'linux':
                subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '0'])
            elif platform.system().lower() == 'windows':
                try:
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                    from ctypes import cast, POINTER
                    from comtypes import CLSCTX_ALL
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume = cast(interface, POINTER(IAudioEndpointVolume))
                    volume.SetMute(0, None)
                except Exception:
                    pass
        logging.info("Cleaned up audio resources.")

def receive_audio():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0', PORT))
    print(f"🎧 UDP Audio Receiver listening on port {PORT}")
    logging.info("UDP Receiver started")

    try:
        while True:
            data, _ = s.recvfrom(CHUNK_SIZE * 2)
            if not data:
                continue
            stream.write(data)
    except KeyboardInterrupt:
        print("Server interrupted.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        s.close()

def send_audio_linux():
    def get_monitor_source():
        result = subprocess.run(['pactl', 'list', 'short', 'sources'], capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if '.monitor' in line:
                return line.split('\t')[1]
        raise RuntimeError("❌ No monitor source found.")

    def mute_output():
        subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '1'])

    monitor = get_monitor_source()

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

    for _ in range(5):
        try:
            sock.connect((app_config.audio_ip, PORT))
            mute_output()
            break
        except Exception:
            time.sleep(3)
    else:
        print("[Audio] ❌ Unable to connect to receiver.")
        return

    print(f"📤 Sending audio from {monitor} (muted locally)")
    logging.info("Sending audio from monitor (muted locally)")

    try:
        while True:
            data = process.stdout.read(CHUNK_SIZE * 2)
            if not data:
                break
            sock.sendto(data, (app_config.audio_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
        logging.info("Sender stopped.")
    finally:
        cleanup(sock=sock, process=process, unmute=True)

def send_audio_windows():
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL

    def mute_output_windows():
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(1, None)
        except Exception as e:
            print(f"⚠️ Error muting output: {e}")

    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'dshow',
        '-i', 'audio=CABLE Output (VB-Audio Virtual Cable)',
        '-ac', str(CHANNELS),
        '-ar', str(RATE),
        '-f', 's16le',
        '-hide_banner',
        '-loglevel', 'error',
        '-'
    ]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

    for _ in range(5):
        try:
            sock.connect((app_config.audio_ip, PORT))
            mute_output_windows()
            break
        except Exception:
            time.sleep(3)
    else:
        print("❌ Failed to connect to receiver.")
        return

    print("📤 Sending audio from VB-Cable... (muted locally)")
    logging.info("Sending audio from VB-Cable...")

    try:
        while True:
            data = process.stdout.read(CHUNK_SIZE * 2)
            if not data:
                continue
            sock.sendto(data, (app_config.audio_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
        logging.info("Sender stopped.")
    finally:
        cleanup(sock=sock, process=process, unmute=True)

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
