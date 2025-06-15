import json
import os

class AppConfig:
    def __init__(self):
        self.config_path = "config.json"
        self.set_defaults()
        self.load()

    def set_defaults(self):
        self.config = {
            # Shared config (common across client/server)
            "stop_flag": False,
            "is_running": False,
            "active_device": False,
            "audio_enabled": True,
            "audio_direction": "client_to_server",

            # Local config (specific to current instance)
            "mode": "server",  # or "client"
            "server_direction": "Right",  # screen edge
            "server_ip": "" ,

            #clipboard
            "clipboard" : "" 
        }

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                print(f"[Config] Failed to load config: {e}")

    def save(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"[Config] Failed to save config: {e}")

    def __getattr__(self, name):
        return self.config.get(name)

    def __setattr__(self, name, value):
        if name in ("config_path", "config"):
            super().__setattr__(name, value)
        else:
            self.config[name] = value

app_config = AppConfig()
