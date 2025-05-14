import socket
import pyaudio
import os

SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")  # fallback to localhost
PORT = 50007
CHUNK_SIZE = 4096
VIRTUAL_CABLE_DEVICE = "CABLE Output" # Exact match needed!

# Setup PyAudio
p = pyaudio.PyAudio()

#  use this code to find a device with more than 0 input channels and replace the VIRTUAL_CABLE_DEVICE variable with the name of that device
"""
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"{i}: {info['name']} - {info['maxInputChannels']} input channels")
"""

# Find virtual cable device
device_index = None
for i in range(p.get_device_count()):
    device_info = p.get_device_info_by_index(i)
    if VIRTUAL_CABLE_DEVICE in device_info.get('name'):
        device_index = i
        break

if device_index is None:
    raise RuntimeError(f"Could not find device: {VIRTUAL_CABLE_DEVICE}")

device_info = p.get_device_info_by_index(device_index)
max_input_channels = device_info['maxInputChannels']
print(f"Device {device_index} supports {max_input_channels} input channels")

if max_input_channels < 1:
    raise RuntimeError(f"Device '{VIRTUAL_CABLE_DEVICE}' does not support input channels.")
channels = 1

# Open stream
stream = p.open(format=pyaudio.paInt16,
                channels=channels,
                rate=44100,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE)

# Connect to server
s = socket.socket()
s.connect((SERVER_IP, PORT))
print("Connected to server.")

# Stream audio
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
