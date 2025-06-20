import tkinter as tk
from tkinter import ttk
from config import app_config
import threading
import subprocess
import time
import logging 
import platform
import sys
import socket 

class PortalUI:
    def __init__(self, root):
        self.root = root
        self.os_type = platform.system().lower()
        self.root.title("Portal")
        root.iconbitmap("portal.ico")
        self.root.geometry("350x550")
        self.mode = tk.StringVar(value=app_config.mode)
        self.audio_enabled = tk.BooleanVar(value=app_config.audio_enabled)
        self.running = False
        self.invis_process = None
        self.audio_process = None

        self.tab_control = ttk.Notebook(root)
        self.portal_tab = ttk.Frame(self.tab_control)
        self.logs_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.portal_tab, text='Portal')
        self.tab_control.add(self.logs_tab, text='View Logs')
        self.tab_control.pack(expand=1, fill='both')

        logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="w", format="%(levelname)s - %(message)s")

        self.tab_control.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.create_portal_tab()

    def on_tab_changed(self, event):
        selected_tab = event.widget.tab(event.widget.index("current"))["text"]
        if selected_tab == "View Logs":
            try:
                subprocess.Popen([sys.executable, "log_viewer.py"])
                self.tab_control.select(self.portal_tab)
            except Exception as e:
                logging.info(f"Failed to open log viewer: {e}")

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

        self.server_direction = tk.StringVar(value="Top")
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

        self.audio_disabled_rb = ttk.Checkbutton(self.portal_tab, text="Enable Audio ", variable=self.audio_enabled, command=self.toggle_audio, style="Bold.TRadiobutton")
        self.audio_disabled_rb.pack(anchor='w', padx=10, pady=(0, 5))
        self.audio_share_rb = ttk.Radiobutton(self.portal_tab, text="Share Audio", variable=self.audio_mode, value="Share_Audio")
        self.audio_receive_rb = ttk.Radiobutton(self.portal_tab, text="Receive Audio", variable=self.audio_mode, value="Receive_Audio")

        for rb in [self.audio_disabled_rb, self.audio_share_rb, self.audio_receive_rb]:
            rb.pack(anchor='w', padx=20, pady=2 )
        self.audio_share_rb.pack(padx=40)
        self.audio_receive_rb.pack(padx=40)

        control_frame = ttk.Frame(self.portal_tab)
        control_frame.pack(pady=20)

        self.status_label = ttk.Label(control_frame, text="Portal is not running", foreground="red")
        self.status_label.grid(row=0, column=0, columnspan=2, pady=5)

        self.reload_button = ttk.Button(control_frame, text="Reload", command=lambda: self.toggle_portal("reload"))
        self.reload_button.grid(row=1, column=0, padx=5)

        self.start_stop_button = ttk.Button(control_frame, text="Start", command=lambda: self.toggle_portal("start"))
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
        if last_mode != current_mode:
            logging.info(f"[System] Mode set to {current_mode}")

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

    def toggle_portal(self, mode):
        if mode == "start" and not self.running:
            if getattr(self, 'portal_thread', None) and self.portal_thread.is_alive():
                print("Portal is already running")
                logging.info("Portal is already running.")
                return

            app_config.stop_flag = False
            self.running = True
            app_config.is_running = True
            self.status_label.config(text="Portal is running", foreground="green")
            self.start_stop_button.config(text="Stop")
            logging.info("Portal started")

            app_config.server_direction = self.server_direction.get()
            if self.client_ip_entry.get() != "Enter Server IP":
                app_config.server_ip = self.client_ip_entry.get()

            app_config.mode = self.mode.get()
            app_config.audio_enabled = self.audio_enabled.get()
            app_config.audio_mode = self.audio_mode.get()
            app_config.save()  

            
            try:
                self.invis_process = subprocess.Popen([sys.executable, "share.py"])
            except Exception as e:
                logging.info(f"Failed to launch share.py: {e}")

            if app_config.audio_enabled: 
                try:
                    self.audio_process = subprocess.Popen([sys.executable,"audio.py"])
                except Exception as e:
                    logging.info(f"Failed to launch audio.py")
            

        elif self.running and mode != "reload":
            logging.info("Stopping portal...")
            app_config.stop_flag = True
            self.running = False
            app_config.is_running = False
            self.status_label.config(text="Portal is not running", foreground="red")
            self.start_stop_button.config(text="Start")
            try:
                if self.invis_process:
                    self.invis_process.terminate()
                self.invis_process = None
            except Exception as e:
                print(f"Failed to terminate invis.py: {e}")
            try:
                if self.audio_process:
                    self.audio_process.terminate()
                self.audio_process = None
            except Exception as e:
                print(f"Failed to terminate audio.py: {e}")
            logging.info("Portal stopped.")

        elif self.running and mode == "reload":
            logging.info("Reloading portal...")
            self.toggle_portal("stop")
            time.sleep(0.5)
            self.toggle_portal("start")

        else:
            logging.info(f"Unknown command: {mode}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PortalUI(root)
    root.mainloop()
