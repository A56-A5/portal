# server.py (Windows)
import socket
import pyaudio

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
PORT = 50007

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK)

s = socket.socket()
s.bind(('0.0.0.0', PORT))
s.listen(1)
print("Waiting for connection...")

conn, addr = s.accept()
print("Connected by", addr)

try:
    while True:
        data = conn.recv(CHUNK * 2)
        if not data:
            break
        stream.write(data)
except KeyboardInterrupt:
    print("Interrupted")

stream.stop_stream()
stream.close()
p.terminate()
conn.close()
s.close()
