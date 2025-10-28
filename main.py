"""
Main entry point for Portal application
"""
import tkinter as tk
from gui.main_window import MainWindow
from utils.config import app_config
import threading
import subprocess
import time
import sys
import os
import platform
import logging


def get_executable(name):
    """Return command to launch a child role within the same executable.

    Use a flag understood by this program to dispatch into specific roles
    inside a single-file bundle without reopening the main UI.
    """
    if getattr(sys, 'frozen', False):
        return [sys.executable, f"--child={name}"]
    else:
        script_path = os.path.abspath(__file__)
        return [sys.executable, script_path, f"--child={name}"]


def run_child_role(name):
    """Dispatch execution to a child role by name and exit when done."""
    if name == "share_manager":
        from network.share_manager import ShareManager
        ShareManager().run()
    elif name == "audio":
        from network.audio_manager import AudioManager
        AudioManager().run()
    elif name == "log_viewer":
        from gui.log_viewer import main as log_main
        log_main()
    else:
        print(f"Unknown child role: {name}")


class PortalApp:
    """Main Portal application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.running = False
        self.invis_process = None
        self.audio_process = None
        
        # Create main window
        self.main_window = MainWindow(self.root, self.on_start_stop)
    
    def on_start_stop(self, mode):
        """Handle start/stop/reload button"""
        
        if mode == "start" and not self.running:
            if getattr(self.main_window, 'portal_thread', None) and self.main_window.portal_thread.is_alive():
                print("Portal is already running")
                return
            
            app_config.stop_flag = False
            self.running = True
            app_config.is_running = True
            self.main_window.status_label.config(text="Portal is running", foreground="green")
            self.main_window.start_stop_button.config(text="Stop")
            
            # Update configuration from UI
            app_config.server_direction = self.main_window.server_direction.get()
            if self.main_window.client_ip_entry.get() != "Enter Server IP":
                app_config.server_ip = self.main_window.client_ip_entry.get()
            
            app_config.mode = self.main_window.mode.get()
            app_config.audio_enabled = self.main_window.audio_enabled.get()
            app_config.audio_mode = self.main_window.audio_mode.get()
            app_config.save()
            
            # Start share process
            try:
                self.invis_process = subprocess.Popen(get_executable("share_manager"))
            except Exception as e:
                print(f"Failed to launch share_manager: {e}")
            
            # Start audio process if enabled
            if app_config.audio_enabled:
                try:
                    self.audio_process = subprocess.Popen(get_executable("audio"))
                except Exception as e:
                    print(f"Failed to launch audio: {e}")
        
        elif self.running and mode != "reload":
            app_config.stop_flag = True
            self.running = False
            app_config.is_running = False
            self.main_window.status_label.config(text="Portal is not running", foreground="red")
            self.main_window.start_stop_button.config(text="Start")
            
            # Terminate processes
            if self.invis_process:
                try:
                    self.invis_process.terminate()
                    self.invis_process.wait()
                except Exception as e:
                    print(f"Failed to terminate share_manager: {e}")
            
            if self.audio_process:
                try:
                    self.audio_process.terminate()
                    self.audio_process.wait()
                except Exception as e:
                    print(f"Failed to terminate audio: {e}")
        
        elif self.running and mode == "reload":
            self.on_start_stop("stop")
            time.sleep(0.5)
            self.on_start_stop("start")
    
    def run(self):
        """Run the application"""
        self.root.mainloop()


if __name__ == "__main__":
    # Configure logging early and consistently for both parent and child roles
    try:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        log_path = os.path.join(base_dir, "logs.log")
        logging.basicConfig(
            level=logging.INFO,
            filename=log_path,
            filemode="a",
            format="%(levelname)s - %(message)s",
            force=True,
        )
    except Exception:
        pass

    # Support child role dispatch for single-file builds
    for arg in sys.argv[1:]:
        if arg.startswith("--child="):
            role = arg.split("=", 1)[1]
            run_child_role(role)
            sys.exit(0)

    app = PortalApp()
    app.run()

