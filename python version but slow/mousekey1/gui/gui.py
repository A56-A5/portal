import tkinter as tk
from tkinter import messagebox
import subprocess
import platform
import os

# Platform check
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Auto-detect script
SCRIPT_PATHS = {
    "server": {
        "Windows": "main/server_main.py",
        "Linux": "main/server_main.py"
    },
    "client": {
        "Windows": "main/client_main.py",
        "Linux": "main/client_main.py"
    }
}

def run_script(mode, ip=None):
    script = SCRIPT_PATHS[mode][platform.system()]
    env = os.environ.copy()

    # Pass server IP for client
    if mode == "client" and ip:
        command = ["python", script, ip]
    else:
        command = ["python", script]

    try:
        subprocess.Popen(command, env=env)
    except Exception as e:
        messagebox.showerror("Error", f"Could not start {mode} script:\n{e}")

def on_start():
    mode = mode_var.get()
    ip = ip_entry.get().strip()

    if mode == "client" and not ip:
        messagebox.showwarning("Missing IP", "Please enter the server IP for client mode.")
        return

    run_script(mode, ip)

def on_exit():
    root.destroy()

# GUI Setup
root = tk.Tk()
root.title("Python Barrier Prototype")
root.geometry("350x250")
root.resizable(False, False)

frame = tk.Frame(root, padx=20, pady=20)
frame.pack(expand=True)

mode_var = tk.StringVar(value="server")

# Mode Selector
tk.Label(frame, text="Select Mode:").pack(anchor="w")
tk.Radiobutton(frame, text="Server (share input)", variable=mode_var, value="server").pack(anchor="w")
tk.Radiobutton(frame, text="Client (receive input)", variable=mode_var, value="client").pack(anchor="w")

# Server IP Input
tk.Label(frame, text="Server IP (Client only):").pack(anchor="w", pady=(10, 0))
ip_entry = tk.Entry(frame, width=30)
ip_entry.pack(anchor="w")

# Start Button
tk.Button(frame, text="Start", width=20, command=on_start).pack(pady=(20, 5))

# Exit Button
tk.Button(frame, text="Exit", width=20, command=on_exit).pack()

root.mainloop()
