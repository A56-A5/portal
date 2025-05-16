
### gui/client_gui.py

import tkinter as tk
from tkinter import ttk
import subprocess
import sys
import os

def start_client():
    ip = ip_entry.get()
    script_path = os.path.join(os.path.dirname(__file__), '../client/client_mouse.py')
    subprocess.Popen([sys.executable, script_path, ip])

def stop_client():
    os._exit(0)  # Quick and dirty stop

root = tk.Tk()
root.title("Barrier-like Client")

ttk.Label(root, text="Server IP:").pack(pady=5)
ip_entry = ttk.Entry(root)
ip_entry.pack(pady=5)

start_btn = ttk.Button(root, text="Start", command=start_client)
start_btn.pack(pady=5)

stop_btn = ttk.Button(root, text="Stop", command=stop_client)
stop_btn.pack(pady=5)

root.mainloop()