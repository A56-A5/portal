# sender.py (Windows - screen audio via VB-Cable)

import socket
import subprocess

RECEIVER_IP = '192.168.1.75'  # 👈 Replace with receiver's IP
PORT = 50007

# Use VB-Audio Virtual Cable or similar (this captures system audio silently)
ffmpeg_cmd = [
    'ffmpeg',
    '-f', 'dshow',
    '-i', 'audio=CABLE Output (VB-Audio Virtual Cable)',
    '-ac', '1',
    '-ar', '48000',
    '-f', 's16le',
    '-loglevel', 'quiet',
    '-'
]

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((RECEIVER_IP, PORT))
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

    print("📤 Streaming screen audio...")
    try:
        while True:
            data = process.stdout.read(4096)
            if not data:
                break
            s.sendall(data)
    except KeyboardInterrupt:
        print("❌ Stopped.")
    finally:
        process.terminate()
