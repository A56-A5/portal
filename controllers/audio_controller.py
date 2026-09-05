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


def _detached_kwargs():
    """Popen kwargs that put ffmpeg/ffplay in their own process group.

    Without this, if this (audio) process is ever hard-killed - e.g. the
    graceful-shutdown fallback in main.py, or the OS killing us directly -
    the ffmpeg/ffplay grandchild can be orphaned and keep running (and on
    Linux, keep the system muted since unmute_output() in cleanup() never
    gets to run). Putting it in its own group lets a tree-kill reach it
    even when it can't be joined normally.
    """
    if platform.system() == "Windows":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}

class AudioController:
    def __init__(self):
        self.os_type = platform.system().lower()
        self.CHANNELS = 2
        self.RATE = 44100
        self.FORMAT = 's16le'
        self.CHUNK_SIZE = 1024
        
        # Windows-specific input device
        self.INPUT = 'audio=Stereo Mix (Realtek(R) Audio)'
        
        # NOTE: this is the FIRST logging.basicConfig() call in the audio
        # subprocess (AudioController is constructed before AudioManager
        # calls its own basicConfig), so this is the config that actually
        # sticks for the whole process — later basicConfig() calls
        # elsewhere are no-ops. Previously this only attached a file
        # handler, so anything logged via logging.warning/error (like the
        # ffmpeg exit-code diagnostics) went to logs.log ONLY and never
        # appeared in the terminal, which is exactly what hid the
        # "listen=1" ffmpeg bug. Adding a StreamHandler here means every
        # existing logging.* call in this file (and anything else in this
        # process) now shows in both places automatically.
        logging.basicConfig(
            level=logging.INFO,
            format="[Audio] - %(message)s",
            handlers=[
                logging.FileHandler("logs.log", mode="a"),
                logging.StreamHandler(),
            ],
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
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 256)
        except Exception:
            pass
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            **_detached_kwargs(),
        )

        sent = 0
        read_size = max(self.CHUNK_SIZE, 4096)
        try:
            logging.info(f"[Audio] Send linux start -> {target_ip}:{port}")
            if not target_ip:
                logging.error("[Audio] audio_ip is empty — set the receiver IP in the UI")
            while app_config.is_running and not app_config.stop_flag:
                data = process.stdout.read(read_size)
                if not data:
                    if process.poll() is not None:
                        logging.warning("[Audio] ffmpeg capture exited")
                        break
                    continue
                try:
                    sock.sendto(data, (target_ip, int(port)))
                except Exception as e:
                    logging.warning(f"[Audio] sendto failed: {e}")
                    time.sleep(0.05)
                    continue
                sent += 1
                if sent == 1:
                    logging.info(f"[Audio] first packet sent ({len(data)} bytes)")
                elif sent % 500 == 0:
                    logging.info(f"[Audio] sending… {sent} packets")
        except (KeyboardInterrupt, Exception) as e:
            logging.info(f"[Audio] send interrupted: {e}")
        finally:
            logging.info(f"[Audio] Send linux stop {target_ip}:{port} (sent={sent})")
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
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, **_detached_kwargs())
        
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
        """Receive s16le stereo UDP and play via PortAudio (sounddevice)."""
        from utils.config import app_config

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 256)
        except Exception:
            pass
        sock.bind(("0.0.0.0", port))
        sock.settimeout(1.0)

        # bytes per UDP packet from sender
        pkt = max(self.CHUNK_SIZE, 4096)
        frames = max(256, self.CHUNK_SIZE)

        stream = sd.OutputStream(
            samplerate=self.RATE,
            channels=self.CHANNELS,
            dtype="int16",
            blocksize=0,
            latency="low",
        )

        packets = 0
        try:
            logging.info(f"[Audio] sounddevice receive start {port}")
            with stream:
                while app_config.is_running and not app_config.stop_flag:
                    try:
                        data, addr = sock.recvfrom(pkt)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        logging.warning(f"[Audio] recv error: {e}")
                        continue
                    if not data:
                        continue
                    # pad/trim to whole frames
                    frame_bytes = self.CHANNELS * 2  # int16
                    n = len(data) - (len(data) % frame_bytes)
                    if n <= 0:
                        continue
                    audio_array = np.frombuffer(data[:n], dtype="int16").reshape(-1, self.CHANNELS)
                    try:
                        stream.write(audio_array)
                    except Exception as e:
                        logging.warning(f"[Audio] playback write failed: {e}")
                        continue
                    packets += 1
                    if packets == 1:
                        logging.info(f"[Audio] first packet from {addr} ({len(data)} bytes)")
                    elif packets % 500 == 0:
                        logging.info(f"[Audio] receiving… {packets} packets")
        except (KeyboardInterrupt, Exception) as e:
            logging.info(f"[Audio] receive interrupted: {e}")
        finally:
            logging.info(f"[Audio] Receive stop {port} (packets={packets})")
            self.cleanup(sock)
    

    def receive_audio_pulse(self, port: int):
        """Linux: UDP s16le → ffmpeg → PulseAudio/PipeWire default sink.

        sounddevice often opens a device but produces silence under PipeWire;
        ffmpeg -f pulse default is the path that actually plays.
        """
        from utils.config import app_config

        port = int(port)
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-f", self.FORMAT,
            "-ar", str(self.RATE),
            "-ac", str(self.CHANNELS),
            # NOTE: "listen=1" is a TCP-only ffmpeg URL option; UDP has no
            # connection handshake, so it isn't valid here and made ffmpeg
            # fail to parse the URL, dying immediately after spawn (only
            # visible via logging.warning in logs.log, never printed to
            # the terminal).
            "-i", f"udp://0.0.0.0:{port}?fifo_size=1048576&overrun_nonfatal=1",
            "-f", "pulse",
            "-device", "default",
            "portal-audio",
        ]

        process = None
        try:
            logging.info(f"[Audio] pulse receive start (ffmpeg) port={port}")
            print(f"[Audio] pulse receive start port={port}")
            while app_config.is_running and not app_config.stop_flag:
                try:
                    process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        **_detached_kwargs(),
                    )
                except FileNotFoundError:
                    logging.error("[Audio] ffmpeg missing — falling back to sounddevice")
                    self.receive_audio(port)
                    return
                except Exception as e:
                    logging.error(f"[Audio] ffmpeg spawn failed: {e}")
                    time.sleep(1)
                    continue

                while app_config.is_running and not app_config.stop_flag:
                    code = process.poll()
                    if code is not None:
                        err = b""
                        try:
                            err = process.stderr.read() if process.stderr else b""
                        except Exception:
                            pass
                        logging.warning(
                            f"[Audio] ffmpeg exited code={code} err={err[:300]!r} — restart"
                        )
                        break
                    time.sleep(0.5)

                if process and process.poll() is None:
                    break
                if app_config.is_running and not app_config.stop_flag:
                    time.sleep(0.3)
        except (KeyboardInterrupt, Exception) as e:
            logging.info(f"[Audio] pulse receive interrupted: {e}")
        finally:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
            logging.info(f"[Audio] pulse receive stop port={port}")

    def receive_audio_ffplay(self, port: int):
        """Receive raw s16le UDP audio on Linux.

        Some ffplay builds reject -ac ("Option not found"). Prefer ffmpeg
        decoding into PulseAudio; fall back to the sounddevice path.
        """
        from utils.config import app_config

        # ffmpeg: input options MUST come before -i
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", self.FORMAT,
            "-ar", str(self.RATE),
            "-ac", str(self.CHANNELS),
            "-i", f"udp://0.0.0.0:{port}",
            "-f", "pulse",
            "default",
        ]

        process = None
        use_ffmpeg = True
        try:
            # Probe ffmpeg once
            try:
                subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    timeout=3,
                    check=False,
                )
            except FileNotFoundError:
                use_ffmpeg = False
                logging.warning("[Audio] ffmpeg not found — using sounddevice receive")

            if not use_ffmpeg:
                self.receive_audio(port)
                return

            logging.info(f"[Audio] ffmpeg pulse receive start {port}")
            while app_config.is_running and not app_config.stop_flag:
                try:
                    process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        **_detached_kwargs(),
                    )
                except Exception as e:
                    logging.error(f"[Audio] ffmpeg spawn failed: {e} — falling back to sounddevice")
                    self.receive_audio(port)
                    return

                while app_config.is_running and not app_config.stop_flag:
                    code = process.poll()
                    if code is not None:
                        err = b""
                        try:
                            err = process.stderr.read() if process.stderr else b""
                        except Exception:
                            pass
                        logging.warning(
                            f"[Audio] ffmpeg exited code={code}"
                            + (f" err={err[:300]!r}" if err else "")
                            + " — restarting"
                        )
                        break
                    time.sleep(0.4)

                if process and process.poll() is None:
                    break
                if app_config.is_running and not app_config.stop_flag:
                    time.sleep(0.5)
        except (KeyboardInterrupt, Exception) as e:
            logging.info(f"[Audio] receive interrupted: {e}")
        finally:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
            logging.info(f"[Audio] ffmpeg pulse receive stop {port}")

