# config.py
import json
import platform
import os

class AppConfig:
    def __init__(self):
        self.config_path = "config.json"
        self.set_defaults()
        self.load()

    def set_defaults(self):
        self.mode = "server"
        self.server_direction = "Top"
        self.server_ip = "127.0.0.1"
        self.client_ip = ""
        self.audio_enabled = True
        self.stop_flag = False
        self.active_device = False
        self.audio_direction = "client_to_server"
        self.is_running = False
        self.server_os = ""
        self.client_os = ""
        self.platform = platform.system().lower()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    self.__dict__.update(data)
            except Exception as e:
                print(f"[Config] Failed to load: {e}")

    def save(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.__dict__, f, indent=4)
        except Exception as e:
            print(f"[Config] Failed to save: {e}")

app_config = AppConfig()
