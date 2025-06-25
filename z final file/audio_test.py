import subprocess
import socket
import sys
import pyaudio

target_ip = ""  # ⬅️ Replace with Linux IP
PORT = 50009
CHANNELS = 2
RATE = 44100 
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024

def get_monitor_source():
    result = subprocess.run(['pactl', 'list', 'short', 'sources'], capture_output=True, text=True)
    for line in result.stdout.strip().split('\n'):
        if '.monitor' in line:
            return line.split('\t')[1]
    raise RuntimeError("❌ No monitor source found.")
def mute_output():
    subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '1'])
def unmute_output():
    subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '0'])

def send_audio_linux():
    monitor = get_monitor_source()
    mute_output()
    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'pulse',
        '-i', monitor,
        '-ac', str(CHANNELS),
        '-ar', str(RATE),
        '-f', 's16le',
        '-loglevel', 'info',
        '-'
    ]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
    print(f"📤 Sending audio from {monitor} (muted locally)")
    try:
        while True:
            data = process.stdout.read(CHUNK_SIZE)
            if not data:
                break
            sock.sendto(data, (target_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
    finally:
        unmute_output()
        sock.close()
        process.terminate()

def send_audio_windows():
    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'dshow',
        '-i', 'audio=Stereo Mix (Realtek(R) Audio)',  # Match your input device
        '-ar', str(RATE),
        '-ac' , str(CHANNELS),
        '-f', 's16le',
        '-loglevel', 'info',
        '-'
    ]

    print(f"📤 Sending Windows audio from VB-Cable (raw PCM via FFmpeg) to {target_ip}:{PORT}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = process.stdout.read(CHUNK_SIZE*CHANNELS*2)
            if not data:
                break
            sock.sendto(data, (target_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Audio sending stopped.")
    finally:
        sock.close()
        process.terminate()

def receive_audio(PORT=50009):
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    print(f"🎧 Listening on UDP port {PORT} (PCM s16le)...")

    try:
        while True:
            data, _ = sock.recvfrom(CHUNK_SIZE*CHANNELS*2)  # buffer size slightly larger than chunk
            if data:
                stream.write(data)
    except KeyboardInterrupt:
        print("\n❌ Receiver stopped.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        sock.close()

def receive_audio_ffplay():
    print(f"🎧 Receiving audio via ffplay on port {PORT}...")
    cmd = [
        'ffplay',
        '-f', FORMAT,
        '-ac', str(CHANNELS),
        '-ar', str(RATE),
        '-i', f'udp://0.0.0.0:{PORT}',
        '-autoexit'  # remove this if you want it to stay open
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("❌ Receiver stopped.")

if __name__ == '__main__':
    if True:
        receive_audio_ffplay()
    elif sys.platform.startswith('linux'):
        send_audio_linux()
    elif sys.platform.startswith('win'):
        send_audio_windows()
