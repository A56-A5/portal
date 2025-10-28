
"""
Log Viewer - GUI component for viewing application logs
"""
import tkinter as tk
from tkinter import ttk
import threading
import time
import os
import sys

def _resolve_log_path():
    base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    return os.path.join(base_dir, "logs.log")

LOG_FILE = _resolve_log_path()

def read_log(text_widget):
    """Read log file and update text widget"""
    last_mod_time = 0
    while True: 
        try:
            if os.path.exists(LOG_FILE):
                mod_time = os.path.getmtime(LOG_FILE)
                if mod_time != last_mod_time:
                    last_mod_time = mod_time
                    with open(LOG_FILE, "r") as f:
                        content = f.read()
                    text_widget.config(state='normal')
                    text_widget.delete('1.0', tk.END)
                    text_widget.insert(tk.END, content)
                    text_widget.config(state='disabled')
                    text_widget.see('end')
        except Exception as e:
            print(f"Error reading log file: {e}")
        time.sleep(1)

def clear_logs(text_widget):
    """Clear log file and text widget"""
    with open(LOG_FILE, "w") as f:
        f.truncate(0)
    text_widget.config(state='normal')
    text_widget.delete('1.0', tk.END)
    text_widget.config(state='disabled')

def open_log_viewer(parent):
    """Open the log viewer as a child window of the given parent Tk root."""
    window = tk.Toplevel(parent)
    icon_path = "portal.ico"
    if hasattr(sys, "_MEIPASS"):
        icon_path = os.path.join(sys._MEIPASS, icon_path)

    if sys.platform.startswith("win") and os.path.exists(icon_path):
        try:
            window.iconbitmap(icon_path)
        except Exception:
            pass

    window.title("Portal Logs")
    window.geometry("600x500")

    text_area = tk.Text(window, state='disabled', wrap='none')
    text_area.pack(expand=True, fill='both', padx=10, pady=10)

    button_frame = ttk.Frame(window)
    button_frame.pack(pady=5)

    ttk.Button(button_frame, text="Clear Logs", command=lambda: clear_logs(text_area)).pack(side='left', padx=10)
    ttk.Button(button_frame, text="Close", command=window.destroy).pack(side='right', padx=10)

    threading.Thread(target=read_log, args=(text_area,), daemon=True).start()
    return window

def main():
    """Main entry point for running the log viewer standalone."""
    root = tk.Tk()
    open_log_viewer(root)
    root.mainloop()

if __name__ == "__main__":
    main()
