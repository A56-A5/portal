# log_viewer.py
import tkinter as tk
from tkinter import ttk
import threading
import time
import os,sys

LOG_FILE = "logs.log"

def read_log(text_widget):
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
    with open(LOG_FILE, "w") as f:
        f.truncate(0)
    text_widget.config(state='normal')
    text_widget.delete('1.0', tk.END)
    text_widget.config(state='disabled')

def main():
    root = tk.Tk()
    root.withdraw() 
    icon_path = "portal.ico"
    if hasattr(sys, "_MEIPASS"):  
        icon_path = os.path.join(sys._MEIPASS, icon_path)

    if sys.platform.startswith("win") and os.path.exists(icon_path):
        root.iconbitmap(icon_path)

    root.title("Portal Logs")
    root.geometry("600x500")
    root.deiconify() 

    text_area = tk.Text(root, state='disabled', wrap='none')
    text_area.pack(expand=True, fill='both', padx=10, pady=10)

    button_frame = ttk.Frame(root)
    button_frame.pack(pady=5)

    ttk.Button(button_frame, text="Clear Logs", command=lambda: clear_logs(text_area)).pack(side='left', padx=10)
    ttk.Button(button_frame, text="Close", command=root.destroy).pack(side='right', padx=10)

    threading.Thread(target=read_log, args=(text_area,), daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    main()
