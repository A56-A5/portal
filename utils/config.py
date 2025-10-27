import json
import os

class AppConfig:
    def __init__(self):
        self.config_path = "config.json"
        self.set_defaults()
        self.load()

    def set_defaults(self):
        self.config = {
            # Default configuration 
            "stop_flag": False,
            "is_running": False,
            "active_device": False,
            "audio_enabled": False,
            "audio_mode": "Share_Audio",

            # Local config (specific to current instance)
            "mode": "server",  # or "client"
            "server_direction": "Right",  # screen direcion related to client
            "server_ip": "" ,
            "audio_ip":"",

            #Ports
            "server_primary_port": 50007,
            "server_secondary_port": 50008,
            "audio_port": 50009, 

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

