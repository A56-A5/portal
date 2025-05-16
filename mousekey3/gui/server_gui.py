### gui/server_gui.py

import tkinter as tk
from tkinter import ttk
import subprocess
import sys
import os

def start_server():
    position = position_var.get()
    script_path = os.path.join(os.path.dirname(__file__), '../server/server_mouse.py')
    subprocess.Popen([sys.executable, script_path, position])

root = tk.Tk()
root.title("Barrier-like Server")

position_var = tk.StringVar(value="right")

ttk.Label(root, text="Client Position:").pack(pady=5)
for pos in ["left", "right", "top", "bottom"]:
    ttk.Radiobutton(root, text=pos.capitalize(), variable=position_var, value=pos).pack(anchor=tk.W)

ttku = ttk.Button(root, text="Start Server", command=start_server)
ttku.pack(pady=10)

root.mainloop()