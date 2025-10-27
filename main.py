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
    """Get executable path for subprocess"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
        ext = ".exe" if platform.system().lower() == "windows" else ""
        return os.path.join(base, name + ext)
    else:
        return [sys.executable, name + ".py"]


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
                logging.info("Portal is already running.")
                return
            
            app_config.stop_flag = False
            self.running = True
            app_config.is_running = True
            self.main_window.status_label.config(text="Portal is running", foreground="green")
            self.main_window.start_stop_button.config(text="Stop")
            logging.info("Portal started")
            
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
                self.invis_process = subprocess.Popen(get_executable("share"))
            except Exception as e:
                logging.info(f"Failed to launch share.py: {e}")
            
            # Start audio process if enabled
            if app_config.audio_enabled:
                try:
                    self.audio_process = subprocess.Popen(get_executable("audio"))
                except Exception as e:
                    logging.info(f"Failed to launch audio.py")
        
        elif self.running and mode != "reload":
            logging.info("Stopping portal...")
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
                    print(f"Failed to terminate share.py: {e}")
            
            if self.audio_process:
                try:
                    self.audio_process.terminate()
                    self.audio_process.wait()
                except Exception as e:
                    print(f"Failed to terminate audio.py: {e}")
            
            logging.info("Portal stopped.")
        
        elif self.running and mode == "reload":
            logging.info("Reloading portal...")
            self.on_start_stop("stop")
            time.sleep(0.5)
            self.on_start_stop("start")
    
    def run(self):
        """Run the application"""
        self.root.mainloop()


if __name__ == "__main__":
    app = PortalApp()
    app.run()

