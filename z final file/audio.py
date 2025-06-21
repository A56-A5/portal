# audio.py
import logging
import platform
import socket
import subprocess
import time 
import pyaudio 
import threading
from config import app_config

PORT = 50009
CHUNK_SIZE = 128
RATE = 44100
CHANNELS = 1
s = None
tries = 10 
VIRTUAL_CABLE_DEVICE = "CABLE Output" 

def cleanup():
    global s
    try:
        s.shutdown(socket.SHUT_RDWR)
        s.close()
    except:
        print("yesh")
    logging.info(f"[Audio] Stopped")

def run_audio_receiver():
    global s 
    import pyaudio
    import av

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True, frames_per_buffer=CHUNK_SIZE)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", PORT))
    print("Audio waiting (UDP)...")

    decoder = av.CodecContext.create("opus", "r")
    packet_buffer = b""

    try:
        while True:
            data, _ = s.recvfrom(CHUNK_SIZE * 4)
            if not data:
                break
            packet_buffer += data
            try:
                pkt = av.packet.Packet(packet_buffer)
                for frame in decoder.decode(pkt):
                    stream.write(frame.planes[0].to_bytes())
                packet_buffer = b""
            except av.AVError:
                continue
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        s.close()

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', PORT))
    print("Audio waiting (UDP)...")

    try:
        while True:
            data, addr = s.recvfrom(CHUNK_SIZE * 2)  
            if not data:
                break
            stream.write(data)
    except KeyboardInterrupt:
        print("Audio Receiver interrupted.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        s.close()


def run_audio_sender_windows():
    global s
    ffmpeg_cmd = [
        "ffmpeg", "-f", "dshow", "-i", f"audio={VIRTUAL_CABLE_DEVICE}",
        "-acodec", "libopus", "-f", "ogg", "-"
    ]

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for c in range(tries, 0, -1):
        try:
            s.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            print(f"[Audio] Connection Attempt: {c}")
            time.sleep(1)
            if c == 1:
                print(f"[Audio] Failed to connect: {e}")
                return

    proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
    try:
        while True:
            data = proc.stdout.read(CHUNK_SIZE)
            if not data:
                break
            s.send(data)
    finally:
        proc.terminate()
        s.close()

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
    
    
    
    # Connect to receiver
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    c = tries
    while c != 0:
        try:
            s.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            logging.info(f"[Audio] Connection Attempt: {c}")
            print(f"[Audio] Connection Attempt: {c}")
            time.sleep(1)
            c -= 1
            if c == 0:
                logging.info(f"[Audio] Failed to connect: {e}")
                print(f"[Audio] Failed to connect: {e}")
                return

    # Open PyAudio stream
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK_SIZE)

    print("[Audio] Streaming from Virtual Cable...")
    logging.info("[Audio] Streaming from Virtual Cable...")

    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            if not data:
                break
            s.send(data)
    except KeyboardInterrupt:
        print("[Audio] Audio streaming interrupted.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        s.close()

def run_audio_sender_linux():
    global s
    def get_monitor():
        out = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True)
        return f"{out.stdout.strip()}.monitor"

    monitor = get_monitor()
    ffmpeg_cmd = [
        "ffmpeg", "-f", "pulse", "-i", monitor,
        "-acodec", "libopus", "-f", "ogg", "-"
    ]

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for c in range(tries, 0, -1):
        try:
            s.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            print(f"[Audio] Connection Attempt: {c}")
            time.sleep(1)
            if c == 1:
                print(f"[Audio] Failed to connect: {e}")
                return

    proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
    try:
        while True:
            data = proc.stdout.read(CHUNK_SIZE)
            if not data:
                break
            s.send(data)
    finally:
        proc.terminate()
        s.close()

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
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    c = tries
    while c!=0:
        try:
            s.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            logging.info(f"[Audio] Connection Attempt: {c}")
            print(f"[Audio] Connection Attempt: {c}")
            time.sleep(1)
            c-=1
            if c == 0:
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
            s.send(data)
    except KeyboardInterrupt:
        print("Audio stopped.")
        logging.info("[Audio] Streaming stopped.")
    finally:
        proc.terminate()
        unmute_output() 
        s.close()

def main():
    os_type = platform.system().lower()

    def monitor_stop():
            while app_config.is_running and not app_config.stop_flag:
                time.sleep(0.5)
            cleanup()
    threading.Thread(target=monitor_stop, daemon=True).start()
    
    if app_config.audio_mode == "Share_Audio":
        if "windows" in os_type:
            run_audio_sender_windows()
        elif "linux" in os_type:
            run_audio_sender_linux()
    elif app_config.audio_mode == "Receive_Audio":
        run_audio_receiver()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a",format ="%(levelname)s - %(message)s")
    main()
