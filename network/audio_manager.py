"""
Audio Manager - Handles audio streaming across the network using AudioController
"""
import platform
import time
import threading
import logging
from utils.config import app_config
from controllers.audio_controller import AudioController


class AudioManager:
    def __init__(self):
        self.audio_controller = AudioController()
        self.os_type = platform.system().lower()
        
        logging.basicConfig(
            level=logging.INFO,
            filename="logs.log",
            filemode="a",
            format="%(levelname)s - %(message)s"
        )
        
        app_config.load()
    
    def run(self):
        """Run the audio manager"""
        app_config.is_running = True
        logging.info(
            f"[Audio] mode={app_config.audio_mode} ip={app_config.audio_ip or '(none)'} "
            f"port={app_config.audio_port}"
        )
        
        # Run audio in a separate thread to allow monitoring
        def audio_thread():
            try:
                if app_config.audio_mode == "Receive_Audio":
                    if self.os_type == "linux":
                        # ffmpeg → Pulse/PipeWire is more reliable than PortAudio
                        # for continuous UDP receive on Linux.
                        self.audio_controller.receive_audio_pulse(app_config.audio_port)
                    else:
                        self.audio_controller.receive_audio(app_config.audio_port)
                elif app_config.audio_mode == "Share_Audio":
                    if self.os_type == "linux":
                        self.audio_controller.send_audio_linux(app_config.audio_ip, app_config.audio_port)
                    elif self.os_type == "windows":
                        self.audio_controller.send_audio_windows(app_config.audio_ip, app_config.audio_port)
                    else:
                        logging.error(f"❌ Unsupported OS: {self.os_type}")
                else:
                    logging.error("❌ Invalid audio_mode in config.")
            except Exception as e:
                logging.error(f"Audio error: {e}")
        
        # Start audio thread
        audio_th = threading.Thread(target=audio_thread, daemon=True)
        audio_th.start()
        
        # Monitor stop flag. Same reasoning as ShareManager.monitor_stop:
        # this process never reloads the full config after startup, so we
        # refresh just the one flag we need to see the GUI's Stop request.
        while app_config.is_running:
            app_config.refresh_control_flags()
            if app_config.stop_flag:
                break
            time.sleep(0.5)
        
        app_config.is_running = False
        audio_th.join(timeout=3)


if __name__ == "__main__":
    AudioManager().run()

