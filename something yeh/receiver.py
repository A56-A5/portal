# receiver.py (cross-platform - plays incoming raw audio)

import socket
import pyaudio

PORT = 50007
CHUNK = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(('', PORT))
    s.listen(1)
    print("🔊 Waiting for sender to connect...")
    conn, addr = s.accept()
    print(f"✅ Connected by {addr}")

    try:
        while True:
            data = conn.recv(CHUNK)
            if not data:
                break
            stream.write(data)
    except KeyboardInterrupt:
        print("❌ Stopped.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
