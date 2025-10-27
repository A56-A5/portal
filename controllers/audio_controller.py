"""
Audio Controller - Handles audio capture and playback across platforms
"""
import socket
import subprocess
import platform
import logging
import threading
import time
import sounddevice as sd
import numpy as np

class AudioController:
    def __init__(self):
        self.os_type = platform.system().lower()
        self.CHANNELS = 2
        self.RATE = 44100
        self.FORMAT = 's16le'
        self.CHUNK_SIZE = 1024
        
        # Windows-specific input device
        self.INPUT = 'audio=Stereo Mix (Realtek(R) Audio)'
        
        logging.basicConfig(
            level=logging.INFO, 
            filename="logs.log", 
            filemode="a", 
            format="[Audio] - %(message)s"
        )
    
    def cleanup(self, sock=None, process=None):
        """Clean up audio resources"""
        try:
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except Exception as e:
                    logging.error(f"Error terminating process: {e}")
            if sock:
                try:
                    sock.close()
                except Exception as e:
                    logging.error(f"Error closing socket: {e}")
        finally:
            logging.info("Cleaned up audio resources.")
    
    def get_monitor_source(self):
        """Get monitor source for Linux"""
        if self.os_type != "linux":
            raise RuntimeError("Method only available on Linux")
        
        result = subprocess.run(
            ['pactl', 'list', 'short', 'sources'], 
            capture_output=True, 
            text=True
        )
        for line in result.stdout.strip().split('\n'):
            if '.monitor' in line:
                return line.split('\t')[1]
        raise RuntimeError("❌ No monitor source found.")
    
    def mute_output(self):
        """Mute output (Linux only)"""
        if self.os_type == "linux":
            subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '1'])
    
    def unmute_output(self):
        """Unmute output (Linux only)"""
        if self.os_type == "linux":
            subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', '0'])
    
    def send_audio_linux(self, target_ip: str, port: int):
        """Send audio on Linux using PulseAudio"""
        monitor = self.get_monitor_source()
        self.mute_output()
        
        print(f"Sending audio to {target_ip}:{port}")
        logging.info(f"Sending audio {target_ip}:{port}")
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'pulse',
            '-i', monitor,
            '-ac', str(self.CHANNELS),
            '-ar', str(self.RATE),
            '-f', 's16le',
            '-loglevel', 'info',
            '-'
        ]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
        
        print(f"📤 Sending audio from {monitor} (muted locally)")
        
        try:
            while True:
                data = process.stdout.read(self.CHUNK_SIZE)
                if not data:
                    break
                sock.sendto(data, (target_ip, port))
        except KeyboardInterrupt:
            print("❌ Sender stopped.")
        finally:
            self.unmute_output()
            self.cleanup(sock, process)
    
    def send_audio_windows(self, target_ip: str, port: int):
        """Send audio on Windows using DirectShow"""
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'dshow',
            '-i', str(self.INPUT),
            '-ar', str(self.RATE),
            '-ac', str(self.CHANNELS),
            '-f', 's16le',
            '-loglevel', 'info',
            '-'
        ]
        
        print(f"Sending audio to {target_ip}:{port}")
        logging.info(f"Sending audio {target_ip}:{port}")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
        
        try:
            while True:
                data = process.stdout.read(self.CHUNK_SIZE)
                if not data:
                    break
                sock.sendto(data, (target_ip, port))
        except KeyboardInterrupt:
            print("❌ Audio sending stopped.")
        finally:
            self.cleanup(sock, process)
    
    def receive_audio(self, port: int):
        """Receive audio using sounddevice"""
        print(f"Playing Audio...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        
        stream = sd.OutputStream(
            samplerate=self.RATE,
            channels=self.CHANNELS,
            dtype='int16',
            blocksize=self.CHUNK_SIZE
        )
        
        try:
            with stream:
                while True:
                    data, _ = sock.recvfrom(self.CHUNK_SIZE * self.CHANNELS * 2)
                    audio_array = np.frombuffer(data, dtype='int16').reshape(-1, self.CHANNELS)
                    stream.write(audio_array)
        except KeyboardInterrupt:
            print("❌ Receiver stopped.")
        finally:
            self.cleanup(sock)
    
    def receive_audio_ffplay(self, port: int):
        """Receive audio using ffplay"""
        print(f"🎧 Receiving audio via ffplay on port {port}...")
        
        cmd = [
            'ffplay',
            '-f', self.FORMAT,
            '-ac', str(self.CHANNELS),
            '-ar', str(self.RATE),
            '-i', f'udp://0.0.0.0:{port}',
            '-autoexit'
        ]
        
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("❌ Receiver stopped.")

