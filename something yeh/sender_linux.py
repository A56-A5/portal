import socket
import subprocess
import re

RECEIVER_IP = '192.168.1.42'
PORT = 50007

def get_monitor_source():
    result = subprocess.run(['pactl', 'list', 'short', 'sources'], capture_output=True, text=True)
    for line in result.stdout.strip().split('\n'):
        if '.monitor' in line:
            return line.split('\t')[1]
    raise RuntimeError("No monitor source found.")

def mute_output():
    subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '1'])

def unmute_output():
    subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '0'])

monitor_source = get_monitor_source()
mute_output()  # Mute local playback

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

    print(f"🎧 Streaming from: {monitor_source} (local muted)")
    try:
        while True:
            data = process.stdout.read(4096)
            if not data:
                break
            s.sendall(data)
    except KeyboardInterrupt:
        print("❌ Stopped.")
    finally:
        unmute_output()  # Unmute after exit
        process.terminate()
