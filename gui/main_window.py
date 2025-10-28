"""
Main Window - Primary UI for Portal application
"""
import tkinter as tk
from tkinter import PhotoImage, ttk
import sys
import os
import threading
import subprocess
import time
import logging
import platform
import socket

from utils.config import app_config
from gui.log_viewer import open_log_viewer


def get_executable(name):
    """Return command to launch a module using current interpreter.

    Always invokes as `python -m package.module` so it works both when
    running from source and inside a single-file PyInstaller bundle.
    """
    module_map = {
        "log_viewer": "gui.log_viewer",
    }
    module = module_map.get(name, name)
    return [sys.executable, "-m", module]


class MainWindow:
    def __init__(self, root, on_start_stop):
        self.root = root
        self.os_type = platform.system().lower()
        self.on_start_stop = on_start_stop
        
        self.root.title("Portal")
        self.root.withdraw()
        self.setup_icon()
        self.root.geometry("350x550")
        self.root.deiconify()
        
        self.mode = tk.StringVar(value=app_config.mode)
        self.audio_enabled = tk.BooleanVar(value=app_config.audio_enabled)
        self.running = False
        self.invis_process = None
        self.audio_process = None
        
        # Create tabs
        self.tab_control = ttk.Notebook(root)
        self.portal_tab = ttk.Frame(self.tab_control)
        self.logs_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.portal_tab, text='Portal')
        self.tab_control.add(self.logs_tab, text='View Logs')
        self.tab_control.pack(expand=1, fill='both')
        
        # Initialize logging
        with open("logs.log", "w") as f:
            print("")
        logging.basicConfig(
            level=logging.INFO,
            filename="logs.log",
            filemode="a",
            format="%(levelname)s - %(message)s"
        )
        
        self.tab_control.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.create_portal_tab()
        
        threading.Thread(target=self.check_status, daemon=True).start()
    
    def setup_icon(self):
        """Setup application icon"""
        icon_path = "portal.ico"
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, icon_path)
        
        if sys.platform.startswith("win") and os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
        else:
            try:
                img = PhotoImage(file="portal.png")
                self.root.iconphoto(False, img)
            except Exception as e:
                print("Failed to set icon:", e)
    
    def on_tab_changed(self, event):
        selected_tab = event.widget.tab(event.widget.index("current"))["text"]
        if selected_tab == "View Logs":
            try:
                open_log_viewer(self.root)
                self.tab_control.select(self.portal_tab)
            except Exception as e:
                pass
    
    def create_portal_tab(self):
        mode_frame = ttk.LabelFrame(self.portal_tab, text="Mode")
        mode_frame.pack(pady=10, padx=10, fill='x')

        server_row = ttk.Frame(mode_frame)
        server_row.pack(anchor='w', padx=10, pady=2, fill='x')

        bold_font = ('TkDefaultFont', 10, 'bold')
        style = ttk.Style()
        style.configure("Bold.TRadiobutton", font=bold_font)

        server_rb = ttk.Radiobutton(server_row, text="Server", variable=self.mode, value="server", command=self.toggle_mode, style="Bold.TRadiobutton")
        server_rb.pack(side='left')

        def get_local_ip():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            except Exception:
                ip = "127.0.0.1"
            finally:
                s.close()
            return ip
        device_ip = get_local_ip()
        ip_label = ttk.Label(server_row, text=f"-  ({device_ip})", font=bold_font)
        ip_label.pack(side='left', padx=10)

        self.server_direction = tk.StringVar(value=app_config.server_direction)
        self.server_location_label = tk.Label(mode_frame, text="Choose where the client device is located:", fg='black')
        self.server_location_label.pack(anchor='w', padx=30, pady=(5, 0))

        self.server_top_rb = ttk.Radiobutton(mode_frame, text="Top", variable=self.server_direction, value="Top")
        self.server_left_rb = ttk.Radiobutton(mode_frame, text="Left", variable=self.server_direction, value="Left")
        self.server_right_rb = ttk.Radiobutton(mode_frame, text="Right", variable=self.server_direction, value="Right")
        self.server_bottom_rb = ttk.Radiobutton(mode_frame, text="Bottom", variable=self.server_direction, value="Bottom")

        for rb in [self.server_top_rb, self.server_left_rb, self.server_right_rb, self.server_bottom_rb]:
            rb.pack(anchor='w', padx=30)

        client_rb = ttk.Radiobutton(mode_frame, text="Client", variable=self.mode, value="client", command=self.toggle_mode, style="Bold.TRadiobutton")
        client_rb.pack(anchor='w', padx=10, pady=10)

        self.client_ip_entry = ttk.Entry(mode_frame, width=35, foreground='grey')
        self.client_ip_entry.pack(anchor='w', padx=30)
        if app_config.server_ip == "":
            self.client_ip_entry.insert(0, "Enter Server IP")
        else:
            self.client_ip_entry.insert(0, app_config.server_ip)
            
        self.client_ip_entry.bind("<FocusIn>", self.clear_placeholder)
        self.client_ip_entry.bind("<FocusOut>", self.restore_placeholder)

        # Audio radios (no section label)
        self.audio_mode = tk.StringVar(value=app_config.audio_mode)
        self.audio_mode.trace_add("write", self.on_audio_mode_change)

        self.audio_enabled_cb = ttk.Checkbutton(self.portal_tab, text="Enable Audio ", variable=self.audio_enabled, command=self.toggle_audio)
        self.audio_enabled_cb.pack(anchor='w', padx=10, pady=(0, 5))
        self.audio_share_rb = ttk.Radiobutton(self.portal_tab, text="Share Audio", variable=self.audio_mode, value="Share_Audio")
        self.audio_receive_rb = ttk.Radiobutton(self.portal_tab, text="Receive Audio", variable=self.audio_mode, value="Receive_Audio")

        self.audio_share_rb.pack(anchor='w', padx=40, pady=2)
        self.audio_receive_rb.pack(anchor='w', padx=40, pady=2)

        control_frame = ttk.Frame(self.portal_tab)
        control_frame.pack(pady=20)

        self.status_label = ttk.Label(control_frame, text="Portal is not running", foreground="red")
        self.status_label.grid(row=0, column=0, columnspan=2, pady=5)

        self.reload_button = ttk.Button(control_frame, text="Reload", command=lambda: self.on_start_stop("reload"))
        self.reload_button.grid(row=1, column=0, padx=5)

        self.start_stop_button = ttk.Button(control_frame, text="Start", command=lambda: self.on_start_stop("start"))
        self.start_stop_button.grid(row=1, column=1, padx=5)

        self.toggle_mode()
        self.toggle_audio()

    def clear_placeholder(self, event):
        if self.client_ip_entry.get() == "Enter Server IP":
            self.client_ip_entry.delete(0, 'end')
            self.client_ip_entry.config(foreground='black')

    def restore_placeholder(self, event):
        if not self.client_ip_entry.get():
            if app_config.server_ip == "":
                self.client_ip_entry.insert(0, "Enter Server IP")
            else:
                self.client_ip_entry.insert(0, app_config.server_ip)
            self.client_ip_entry.config(foreground='grey')

    def toggle_mode(self):
        last_mode = app_config.mode
        current_mode = self.mode.get()
        is_server = current_mode == "server"
        state = 'normal' if is_server else 'disabled'

        if is_server:
            self.client_ip_entry.config(state='disabled')
            self.client_ip_entry.delete(0, 'end')
            self.client_ip_entry.insert(0, "Enter Server IP")
            self.client_ip_entry.config(foreground='grey')
        else:
            self.client_ip_entry.config(state='normal')
            self.client_ip_entry.delete(0, 'end')
            if app_config.server_ip:
                self.client_ip_entry.insert(0, app_config.server_ip)
                self.client_ip_entry.config(foreground='black')
            else:
                self.client_ip_entry.insert(0, "Enter Server IP")
                self.client_ip_entry.config(foreground='grey')

        for rb in [self.server_top_rb, self.server_left_rb, self.server_right_rb, self.server_bottom_rb]:
            rb.config(state=state)

        self.server_location_label.config(fg='black' if is_server else 'grey')

        app_config.mode = current_mode
        app_config.save()

    def on_audio_mode_change(self, *args):
        if self.audio_mode.get() == "Share_Audio" and self.audio_enabled.get():
            self.prompt_audio_ip()

    def prompt_audio_ip(self):
        def save_ip():
            entered_ip = ip_entry.get().strip()
            if entered_ip:
                app_config.audio_ip = entered_ip
                app_config.save()
                popup.destroy()

        popup = tk.Toplevel(self.root)
        popup.title("IP")
        popup.geometry("300x120")
        tk.Label(popup, text="Enter IP of Audio Receiver:").pack(pady=10)
        ip_entry = tk.Entry(popup, width=30)
        ip_entry.insert(0, app_config.audio_ip if app_config.audio_ip else "")
        ip_entry.pack(pady=5)
        tk.Button(popup, text="Save", command=save_ip).pack(pady=5)

    def toggle_audio(self):
        state = 'normal' if self.audio_enabled.get() else 'disabled'
        self.audio_share_rb.config(state=state)
        self.audio_receive_rb.config(state=state)
        app_config.audio_enabled = self.audio_enabled.get()
        app_config.audio_mode = self.audio_mode.get()
    
    def check_status(self):
        while app_config.is_running and not app_config.stop_flag:
            time.sleep(0.5)
        
        self.status_label.config(text="Portal is not running", foreground="red")
        self.start_stop_button.config(text="Start")

