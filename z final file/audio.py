# audio.py
import os
import platform
import socket
import subprocess
import sys
import pyaudio
from config import app_config

PORT = 50009
CHUNK_SIZE = 4096
RATE = 44100
CHANNELS = 1

def run_server():

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    s = socket.socket()
    s.bind(('0.0.0.0', PORT))
    s.listen(1)
    print("Server waiting for connection...")

    conn, addr = s.accept()
    print("Connected by", addr)

    try:
        while True:
            data = conn.recv(CHUNK_SIZE * 2)
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


def run_client_windows():

    VIRTUAL_CABLE_DEVICE = "CABLE Output"
    p = pyaudio.PyAudio()

    device_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if VIRTUAL_CABLE_DEVICE in info.get('name', ''):
            device_index = i
            break

    if device_index is None:
        raise RuntimeError(f"Device '{VIRTUAL_CABLE_DEVICE}' not found.")

    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK_SIZE)

    s = socket.socket()
    s.connect((app_config.server_ip, PORT))
    print("Connected to server.")

    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            if not data:
                break
            s.sendall(data)
    except KeyboardInterrupt:
        print("Client stopped.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        s.close()


def run_client_linux():
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

    s = socket.socket()
    s.connect((app_config.server_ip, PORT))
    print("Connected to server.")

    parec_cmd = ["parec", "--format=s16le", "--rate=44100", "--channels=1", "-d", monitor_source]
    proc = subprocess.Popen(parec_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = proc.stdout.read(CHUNK_SIZE)
            if not data:
                break
            s.sendall(data)
    except KeyboardInterrupt:
        print("Client stopped.")
    finally:
        proc.terminate()
        unmute_output()
        s.close()


def main():
    os_type = platform.system().lower()
    
    if app_config.audio_direction == "server_to_client":
        if app_config.mode == "server":
            run_server()
        elif app_config.mode == "client":
            if "windows" in os_type:
                run_client_windows()
            else:
                run_client_linux()
    else:
        if app_config.mode == "client":
            run_server()
        elif app_config.mode == "server":
            if "windows" in os_type:
                run_client_windows()
            else:
                run_client_linux()

if __name__ == "__main__":
    main()
