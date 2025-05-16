import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess
import platform
import os
import sys

# Import server run function directly for threading
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server import server as server_module

class BarrierApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Barrier-like Hybrid Mouse Control")
        self.geometry("350x180")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.mode = tk.StringVar(value="server")
        self.client_ip = tk.StringVar()
        self.thread = None
        self.running = False

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(expand=True, fill='both')

        ttk.Label(frame, text="Select Mode:").pack(anchor="w")
        modes = [("Server (control client)", "server"), ("Client (be controlled)", "client")]
        for text, val in modes:
            ttk.Radiobutton(frame, text=text, variable=self.mode, value=val, command=self.toggle_ip_entry).pack(anchor="w")

        self.ip_label = ttk.Label(frame, text="Client IP:")
        self.ip_label.pack(anchor="w", pady=(10, 0))

        self.ip_entry = ttk.Entry(frame, textvariable=self.client_ip)
        self.ip_entry.pack(fill="x")

        self.start_btn = ttk.Button(frame, text="Start", command=self.start)
        self.start_btn.pack(pady=10)

        self.stop_btn = ttk.Button(frame, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack()

        self.toggle_ip_entry()

    def toggle_ip_entry(self):
        if self.mode.get() == "server":
            self.ip_label.config(state="normal")
            self.ip_entry.config(state="normal")
        else:
            self.ip_label.config(state="disabled")
            self.ip_entry.config(state="disabled")

    def start(self):
        if self.running:
            return

        mode = self.mode.get()
        if mode == "server":
            ip = self.client_ip.get().strip()
            if not ip:
                messagebox.showerror("Error", "Please enter the client IP address.")
                return
            self.thread = threading.Thread(target=self.run_server, args=(ip,), daemon=True)
        else:
            self.thread = threading.Thread(target=self.run_client, daemon=True)

        self.thread.start()
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def stop(self):
        # Currently just exits app; improving to gracefully stop would need flags/signals
        self.running = False
        self.destroy()

    def run_server(self, ip):
        try:
            server_module.run_server(ip)
        except Exception as e:
            messagebox.showerror("Server Error", str(e))

    def run_client(self):
        try:
            # Running client.py as a subprocess so it uses correct environment & paths
            client_script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'client', 'client.py'))
            subprocess.run([sys.executable, client_script])
        except Exception as e:
            messagebox.showerror("Client Error", str(e))

    def on_close(self):
        if self.running:
            self.stop()
        else:
            self.destroy()


if __name__ == "__main__":
    app = BarrierApp()
    app.mainloop()
