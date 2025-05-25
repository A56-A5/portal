import tkinter as tk
from tkinter import messagebox
from barrier_audio import start_audio_client, start_audio_server

def run_script(role, ip=None):
    import platform
    os_type = platform.system().lower()

    if role == "client":
        if not ip:
            messagebox.showerror("Error", "Please enter an IP address to connect to.")
            return
        start_audio_client(ip)

    elif role == "server":
        start_audio_server()

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

    audio_var = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="Enable Audio Sharing", variable=audio_var).pack()

    def on_start():
        if audio_var.get():
            run_script(mode_var.get(), ip_entry.get())
        else:
            messagebox.showinfo("Info", "Audio sharing is disabled.")

    tk.Button(root, text="Start", command=on_start).pack(pady=10)
    root.mainloop()

if __name__ == "__main__":
    main()
