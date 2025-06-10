import json
import platform

class AppConfig:
    def __init__(self):
        self.load()

    def load(self):
        try:
            with open("config.json", "r") as f:
                data = json.load(f)
                self.__dict__.update(data)
        except FileNotFoundError:
            self.set_defaults()

    def save(self):
        with open("config.json", "w") as f:
            json.dump(self.__dict__, f, indent=4)

    def set_defaults(self):
        self.mode = "server"
        self.server_direction = "Top"
        self.server_ip = "192.168.1.70"
        self.audio_enabled = False
        self.audio_direction = "client_to_server"
        self.stop_flag = True
        self.active_device = False
        self.is_running = False
        self.server_os = ""
        self.client_os = ""
        self.platform = platform.system().lower()

app_config = AppConfig()
