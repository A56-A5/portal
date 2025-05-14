import tkinter as tk
from tkinter import messagebox
import platform
import subprocess
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_script(role, ip=None):
    os_type = platform.system().lower()
    
    if role == "client":
        if not ip:
            messagebox.showerror("Error", "Please enter an IP address to connect to.")
            return
        script_name = f"client_{'windows' if 'windows' in os_type else 'linux'}.py"
        Pathway = "python" if 'windows' in os_type else 'python3' 
        script_path = os.path.join(BASE_DIR, "client", script_name)
        subprocess.Popen([Pathway, script_path], env={**os.environ, "SERVER_IP": ip})
    
    elif role == "server":
        script_name = f"server_{'windows' if 'windows' in os_type else 'linux'}.py"
        Pathway = "python" if 'windows' in os_type else 'python3' 
        script_path = os.path.join(BASE_DIR, "server", script_name)
        subprocess.Popen([Pathway, script_path])  
    else:
        messagebox.showerror("Error", "Unknown role selected.")

def main():
    root = tk.Tk()
    root.title("Audio Streamer")

    tk.Label(root, text="Select Mode:").pack(pady=5)

    mode_var = tk.StringVar(value="client")

    tk.Radiobutton(root, text="Client", variable=mode_var, value="client").pack()
    tk.Radiobutton(root, text="Server", variable=mode_var, value="server").pack()

    tk.Label(root, text="Server IP (Client Only):").pack(pady=5)
    ip_entry = tk.Entry(root)
    ip_entry.pack()

    def on_start():
        run_script(mode_var.get(), ip_entry.get())

    tk.Button(root, text="Start", command=on_start).pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()
