import json
import os

class AppConfig:
    def __init__(self):
        import sys
        if getattr(sys, 'frozen', False):
            # Bundled executable
            base_dir = os.path.dirname(sys.executable)
        else:
            # Source script
            base_dir = os.getcwd()
        self.config_path = os.path.join(base_dir, "config.json")
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

            # Input sharing master gate and hotkey
            "input_sharing_enabled": True,
            "sharing_hotkey": "",

            # Local config (specific to current instance)
            "mode": "server",  # or "client"
            "server_direction": "Right",  # screen direcion related to client
            "server_ip": "" ,
            "audio_ip":"",

            #Ports
            "server_primary_port": 50007,
            "server_secondary_port": 50008,
            "server_tertiary_port": 50010,
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
        # Always force active_device to False on startup/load
        self.config["active_device"] = False

    def refresh_control_flags(self):
        """Re-read ONLY the cross-process control flags from disk.

        A full load() overwrites the entire in-memory config, which is
        unsafe to call from a polling loop in a worker process: the GUI
        process and the worker each treat certain keys (active_device,
        server_direction, etc.) as owned by themselves, and clobbering
        them with whatever the other process last wrote mid-transition
        causes state corruption (see the comment in ShareManager.transition).

        This method exists so a worker can cheaply notice "the GUI asked
        me to stop" without that risk - it only ever touches stop_flag.
        Safe to call frequently (e.g. every 0.5s) from a monitor loop.
        """
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
            if "stop_flag" in data:
                self.config["stop_flag"] = data["stop_flag"]
        except Exception:
            # Don't let a transient read/parse race (the GUI process is
            # mid-write) take down the monitor loop.
            pass

    def save(self):
        try:
            save_data = dict(self.config)
            save_data["active_device"] = False
            with open(self.config_path, "w") as f:
                json.dump(save_data, f, indent=4)
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

