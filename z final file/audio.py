import socket
import subprocess
import platform
import pyaudio
import logging
from config import app_config

PORT = 50009
CHUNK_SIZE = 1024
RATE = 44100
CHANNELS = 1
stream =  p = sock = process = None
unmute=False

logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a", format="[Audio] - %(message)s")

def cleanup(stream=None, p=None, sock=None, process=None, unmute=False):
    try:
        if stream:
            try:
                stream.stop_stream()
                stream.close()
                logging.info("✅ Audio stream closed.")
            except Exception as e:
                logging.error(f"⚠️ Error closing audio stream: {e}")
        if p:
            try:
                p.terminate()
                logging.info("✅ PyAudio terminated.")
            except Exception as e:
                logging.error(f"⚠️ Error terminating PyAudio: {e}")
        if sock:
            try:
                sock.close()
                logging.info("✅ Socket closed.")
            except Exception as e:
                logging.error(f"⚠️ Error closing socket: {e}")
        if process:
            try:
                process.terminate()
                process.wait(timeout=2)
                logging.info("✅ FFmpeg process terminated.")
            except Exception as e:
                logging.error(f"⚠️ Error terminating process: {e}")
    finally:
        logging.info("🧹 Cleaned up audio resources.")

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
    logging.info("🔊 Receiving audio...")
    try:
        while True:
            data, _ = sock.recvfrom(CHUNK_SIZE)
            stream.write(data)
    except KeyboardInterrupt:
        print("❌ Receiver stopped.")
        logging.info("❌ Receiver stopped.")
    finally:
        cleanup(stream=stream, p=p, sock=sock)

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
    logging.info(f"📤 Sending audio from {monitor} (muted locally)")
    try:
        while True:
            data = process.stdout.read(CHUNK_SIZE)
            if not data:
                break
            sock.sendto(data, (app_config.audio_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
        logging.info("❌ Sender stopped.")
    finally:
        cleanup(sock=sock, process=process, unmute=True)
        unmute_output()

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
            print("🔇 Windows output muted.")
        except Exception as e:
            print(f"⚠️ Error muting output: {e}")

    def unmute_output_windows():
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(0, None)
            print("🔊 Windows output unmuted.")
        except Exception as e:
            print(f"⚠️ Error unmuting output: {e}")

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
    mute_output_windows()
    logging.info("📤 Sending audio from VB-Cable...")
    try:
        while True:
            data = process.stdout.read(CHUNK_SIZE)
            if not data:
                break
            sock.sendto(data, (app_config.audio_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
        logging.info("❌ Sender stopped.")
    finally:
        cleanup(sock=sock, process=process)
        unmute_output_windows()

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
            logging.info(f"❌ Unsupported OS: {os_type}")
    else:
        print("❌ Invalid audio_mode in config.")
        logging.info("❌ Invalid audio_mode in config.")

if __name__ == "__main__":
    main()
