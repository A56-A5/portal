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
                    pass
            if sock:
                try:
                    sock.close()
                except Exception as e:
                    pass
        finally:
            pass
    
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
        from utils.config import app_config
        
        monitor = self.get_monitor_source()
        self.mute_output()
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'pulse',
            '-i', monitor,
            '-ac', str(self.CHANNELS),
            '-ar', str(self.RATE),
            '-f', 's16le',
            '-loglevel', 'quiet',
            '-'
        ]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
        
        try:
            while app_config.is_running and not app_config.stop_flag:
                data = process.stdout.read(self.CHUNK_SIZE)
                if not data:
                    break
                sock.sendto(data, (target_ip, port))
        except (KeyboardInterrupt, Exception):
            pass
        finally:
            logging.info(f"[Audio] Send linux stop {target_ip}:{port}")
            self.unmute_output()
            self.cleanup(sock, process)
    
    def send_audio_windows(self, target_ip: str, port: int):
        """Send audio on Windows using DirectShow"""
        from utils.config import app_config
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'dshow',
            '-i', str(self.INPUT),
            '-ar', str(self.RATE),
            '-ac', str(self.CHANNELS),
            '-f', 's16le',
            '-loglevel', 'quiet',
            '-'
        ]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
        
        try:
            while app_config.is_running and not app_config.stop_flag:
                data = process.stdout.read(self.CHUNK_SIZE)
                if not data:
                    break
                sock.sendto(data, (target_ip, port))
        except (KeyboardInterrupt, Exception):
            pass
        finally:
            logging.info(f"[Audio] Send windows stop {target_ip}:{port}")
            self.cleanup(sock, process)
    
    def receive_audio(self, port: int):
        """Receive audio using sounddevice"""
        from utils.config import app_config
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        sock.settimeout(1.0)  # Timeout for checking stop flag
        
        stream = sd.OutputStream(
            samplerate=self.RATE,
            channels=self.CHANNELS,
            dtype='int16',
            blocksize=self.CHUNK_SIZE
        )
        
        try:
            with stream:
                while app_config.is_running and not app_config.stop_flag:
                    try:
                        data, _ = sock.recvfrom(self.CHUNK_SIZE * self.CHANNELS * 2)
                        audio_array = np.frombuffer(data, dtype='int16').reshape(-1, self.CHANNELS)
                        stream.write(audio_array)
                    except socket.timeout:
                        continue
        except (KeyboardInterrupt, Exception):
            pass
        finally:
            logging.info(f"[Audio] Receive stop {port}")
            self.cleanup(sock)
    
    def receive_audio_ffplay(self, port: int):
        """Receive audio using ffplay"""
        from utils.config import app_config
        
        cmd = [
            'ffplay',
            '-f', self.FORMAT,
            '-ac', str(self.CHANNELS),
            '-ar', str(self.RATE),
            '-i', f'udp://0.0.0.0:{port}',
            '-autoexit',
            '-loglevel', 'quiet'
        ]
        
        process = None
        try:
            logging.info(f"[Audio] ffplay start {port}")
            process = subprocess.Popen(cmd)
            while app_config.is_running and not app_config.stop_flag:
                if process.poll() is not None:
                    break
                time.sleep(0.5)
        except (KeyboardInterrupt, Exception):
            pass
        finally:
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    pass
            logging.info(f"[Audio] ffplay stop {port}")

