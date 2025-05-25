# barrier_audio.py
import socket
import threading
import platform

# --------- CLIENT SIDE --------- #

def stream_audio_linux(server_ip, port=50007, chunk_size=4096):
    import subprocess

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

    parec_cmd = ["parec", "--format=s16le", "--rate=44100", "--channels=1", "-d", monitor_source]
    s = socket.socket()
    s.connect((server_ip, port))
    proc = subprocess.Popen(parec_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = proc.stdout.read(chunk_size)
            if not data:
                break
            s.sendall(data)
    except Exception as e:
        print("Audio stream stopped:", e)
    finally:
        proc.terminate()
        unmute_output()
        s.close()


def stream_audio_windows(server_ip, port=50007, chunk_size=4096, device_name="CABLE Output"):
    import pyaudio

    p = pyaudio.PyAudio()

    device_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if device_name in info.get("name", ""):
            device_index = i
            break

    if device_index is None:
        raise RuntimeError(f"Could not find device: {device_name}")

    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=chunk_size)

    s = socket.socket()
    s.connect((server_ip, port))

    try:
        while True:
            data = stream.read(chunk_size, exception_on_overflow=False)
            if not data:
                break
            s.sendall(data)
    except Exception as e:
        print("Audio stream stopped:", e)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        s.close()


def start_audio_client(server_ip):
    os_type = platform.system().lower()
    if "windows" in os_type:
        threading.Thread(target=stream_audio_windows, args=(server_ip,), daemon=True).start()
    else:
        threading.Thread(target=stream_audio_linux, args=(server_ip,), daemon=True).start()


# --------- SERVER SIDE --------- #

def start_audio_server_linux(port=50007, chunk=1024):
    import pyaudio

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    output=True,
                    frames_per_buffer=chunk)

    s = socket.socket()
    s.bind(('0.0.0.0', port))
    s.listen(1)
    print("[Server] Waiting for audio client...")

    conn, addr = s.accept()
    print("[Server] Connected by", addr)

    try:
        while True:
            data = conn.recv(chunk * 2)
            if not data:
                break
            stream.write(data)
    except Exception as e:
        print("Audio server stopped:", e)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        conn.close()
        s.close()


def start_audio_server_windows(port=50007, chunk=1024):
    # identical to Linux
    start_audio_server_linux(port, chunk)


def start_audio_server():
    os_type = platform.system().lower()
    if "windows" in os_type:
        threading.Thread(target=start_audio_server_windows, daemon=True).start()
    else:
        threading.Thread(target=start_audio_server_linux, daemon=True).start()
