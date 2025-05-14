# client.py (Linux)
import socket
import pyaudio

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
SERVER_IP = 'YOUR_WINDOWS_IP'  # Change this
PORT = 50007

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

s = socket.socket()
s.connect((SERVER_IP, PORT))
print("Connected to server.")

try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        s.sendall(data)
except KeyboardInterrupt:
    print("Interrupted")

stream.stop_stream()
stream.close()
p.terminate()
s.close()
