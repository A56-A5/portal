import socket
import subprocess
import re

RECEIVER_IP = '192.168.1.71'  # 👈 Replace with receiver's IP
PORT = 50007

def get_monitor_source():
    # Run pactl and grab the first monitor source
    result = subprocess.run(['pactl', 'list', 'short', 'sources'], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    for line in lines:
        if '.monitor' in line:
            return line.split('\t')[1]  # Get the name field
    raise RuntimeError("No monitor source found.")

monitor_source = get_monitor_source()
print(f"🎧 Using monitor source: {monitor_source}")

# FFmpeg command to capture screen audio silently
ffmpeg_cmd = [
    'ffmpeg',
    '-f', 'pulse',
    '-i', monitor_source,
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
