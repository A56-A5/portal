# config.py

class AppConfig:
    def __init__(self):
        # Mode: "server" or "client"
        self.mode = "server"

        # Server direction (for server mode): "Top", "Left", "Right", "Bottom"
        self.server_direction = "Top"

        # IP address to connect to (for client mode)
        self.server_ip = "192.168.1.70"
        self.client_ip = ""

        # Audio sharing enabled or not
        self.audio_enabled = True

        # Stop flag to control server/client shutdown
        self.stop_flag = True

        self.server_os = "windows"
        self.client_os = "linux"

        # Flag to check active device 
        self.active_device = False 
        
        # Audio direction: "client_to_server" or "server_to_client"
        self.audio_direction = "client_to_server"

        # Internal status flag to track if the portal is currently running
        self.is_running = False

        # Optional: detect platform (used if you want OS-specific modules)
        import platform
        self.platform = platform.system().lower()  # 'windows', 'linux', etc.

# Global shared config instance
app_config = AppConfig()
