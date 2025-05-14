import socket
import pyaudio

SERVER_IP = 'YOUR_LINUX_SERVER_IP'  # Replace with actual Linux server IP
PORT = 50007
CHUNK_SIZE = 4096
VIRTUAL_CABLE_DEVICE = "Cable Output (VB-Audio Virtual Cable)"  # Replace with your virtual cable device

# Setup PyAudio to capture from the virtual cable
p = pyaudio.PyAudio()

# Find the device index for the virtual cable (system audio output)
device_index = None
for i in range(p.get_device_count()):
    if VIRTUAL_CABLE_DEVICE in p.get_device_info_by_index(i).get('name'):
        device_index = i
        break

if device_index is None:
    raise RuntimeError(f"Could not find device: {VIRTUAL_CABLE_DEVICE}")

stream = p.open(format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE)

s = socket.socket()
s.connect((SERVER_IP, PORT))
print("Connected to server.")

try:
    while True:
        data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        if not data:
            break
        s.sendall(data)
except KeyboardInterrupt:
    print("Stopped.")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    s.close()
