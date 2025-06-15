# config.py
import json
import os

class AppConfig:
    def __init__(self):
        self.shared_config_path = "shared_config.json"
        self.local_config_path = "local_config.json"
        self.set_defaults()
        self.load()

    def set_defaults(self):
        # Shared config (same for client & server)
        self.stop_flag = False
        self.is_running = False
        self.active_device = False
        self.audio_enabled = True
        self.audio_direction = "client_to_server"

        # Local/unique config (specific to client or server)
        self.mode = "server"
        self.server_direction = "Right"
        self.server_ip = ""

    def load(self):
        # Load shared config
        if os.path.exists(self.shared_config_path):
            try:
                with open(self.shared_config_path, "r") as f:
                    shared_data = json.load(f)
                    self.stop_flag = shared_data.get("stop_flag", self.stop_flag)
                    self.is_running = shared_data.get("is_running", self.is_running)
                    self.active_device = shared_data.get("active_device", self.active_device)
                    self.audio_enabled = shared_data.get("audio_enabled", self.audio_enabled)
                    self.audio_direction = shared_data.get("audio_direction", self.audio_direction)
            except Exception as e:
                print(f"[Config] Failed to load shared config: {e}")

        # Load local config
        if os.path.exists(self.local_config_path):
            try:
                with open(self.local_config_path, "r") as f:
                    local_data = json.load(f)
                    self.mode = local_data.get("mode", self.mode)
                    self.server_direction = local_data.get("server_direction", self.server_direction)
                    self.server_ip = local_data.get("server_ip", self.server_ip)
            except Exception as e:
                print(f"[Config] Failed to load local config: {e}")

    def save(self):
        # Save shared config
        try:
            with open(self.shared_config_path, "w") as f:
                shared_data = {
                    "stop_flag": self.stop_flag,
                    "is_running": self.is_running,
                    "active_device": self.active_device,
                    "audio_enabled": self.audio_enabled,
                    "audio_direction": self.audio_direction
                }
                json.dump(shared_data, f, indent=4)
        except Exception as e:
            print(f"[Config] Failed to save shared config: {e}")

        # Save local config
        try:
            with open(self.local_config_path, "w") as f:
                local_data = {
                    "mode": self.mode,
                    "server_direction": self.server_direction,
                    "server_ip": self.server_ip
                }
                json.dump(local_data, f, indent=4)
        except Exception as e:
            print(f"[Config] Failed to save local config: {e}")

app_config = AppConfig()
