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
    logging.info("[Audio] Listening...")

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
    def get_default_monitor():
        result = subprocess.run(["pactl", "get-default-sink"], stdout=subprocess.PIPE, text=True)
        default_sink = result.stdout.strip()
        if not default_sink:
            raise RuntimeError("Could not determine default audio sink.")
        return f"{default_sink}.monitor"

    def mute_output():
        subprocess.run(["pactl", "set-sink-mute", "0", "1"])

    def unmute_output():
        subprocess.run(["pactl", "set-sink-mute", "0", "0"])

    monitor_source = get_default_monitor()
    mute_output()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    for _ in range(5,0,-1):
        try:
            s.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            time.sleep(1)
    else:
        logging.info(f"[Audio] Failed to connect: {e}")
        print(f"[Audio] Failed to connect: {e}")
        return 
    
    print("Audio Connected to server.")
    logging.info("[Audio] Streaming audio...")

    parec_cmd = ["parec", "--format=s16le", "--rate=44100", "--channels=1", "-d", monitor_source]
    proc = subprocess.Popen(parec_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = proc.stdout.read(CHUNK_SIZE)
            if not data:
                break
            s.sendall(data)
    except KeyboardInterrupt:
        print("Audio stopped.")
        logging.info("[Audio] Streaming stopped.")
    finally:
        proc.terminate()
        unmute_output()
        s.close()

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

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    connected = False
    for _ in range(5):
        try:
            sock.connect((app_config.audio_ip, PORT))
            mute_output_windows()
            connected = True
            break
        except Exception:
            time.sleep(3)

    if not connected:
        print("[Audio] ❌ Failed to connect to receiver.")
        logging.info("Sender failed to connect.")
        return

    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK_SIZE)

    print("[Audio] 🎙️ Streaming from Virtual Cable (muted locally)...")
    logging.info("Streaming from Virtual Cable...")

    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            if not data:
                break
            sock.send(data)
    except KeyboardInterrupt:
        print("[Audio] Audio streaming interrupted.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        sock.close()
        logging.info("Sender stopped.")

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
