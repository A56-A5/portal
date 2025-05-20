import sys
import threading
import tkinter as tk
from tkinter import messagebox
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
import ctypes

class MouseSyncGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mouse Sync")

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.server_ip = tk.StringVar()
        self.client_position = tk.StringVar(value="right")
        self.mode = tk.StringVar(value="server")
        self.overlay = None
        self.qt_app = QApplication(sys.argv) if sys.platform.startswith("linux") else None

        self.build_gui()

    def build_gui(self):
        tk.Label(self.root, text="Mode:").pack(pady=5)
        tk.Radiobutton(self.root, text="Server", variable=self.mode, value="server", command=self.update_mode).pack()
        tk.Radiobutton(self.root, text="Client", variable=self.mode, value="client", command=self.update_mode).pack()

        self.client_frame = tk.Frame(self.root)
        tk.Label(self.client_frame, text="Server IP:").pack(pady=5)
        tk.Entry(self.client_frame, textvariable=self.server_ip).pack()

        self.server_frame = tk.Frame(self.root)
        tk.Label(self.server_frame, text="Client Position:").pack(pady=5)
        for pos in ["left", "right", "top", "bottom"]:
            tk.Radiobutton(self.server_frame, text=pos.capitalize(), variable=self.client_position, value=pos).pack()

        self.control_button = tk.Button(self.root, text="Start", command=self.toggle_connection)
        self.control_button.pack(pady=10)

        self.update_mode()

    def update_mode(self):
        if self.mode.get() == "client":
            self.server_frame.pack_forget()
            self.client_frame.pack()
        else:
            self.client_frame.pack_forget()
            self.server_frame.pack()

    def toggle_connection(self):
        if self.control_button["text"] == "Start":
            self.start_connection()
        else:
            self.stop_connection()

    def start_connection(self):
        print("[INFO] Starting connection...")
        self.create_overlay()
        self.control_button["text"] = "Stop"
        # Start networking logic here...

    def stop_connection(self):
        print("[INFO] Stopping connection...")
        if self.overlay:
            if sys.platform.startswith("win"):
                self.overlay.destroy()
            elif sys.platform.startswith("linux"):
                self.qt_app.quit()
            self.overlay = None
        self.control_button["text"] = "Start"
        # Stop networking logic here...

    def create_overlay(self):
        if sys.platform.startswith("win"):
            print("[Overlay] Creating full-screen transparent overlay (Windows)")
            self.overlay = tk.Toplevel(self.root)
            self.overlay.attributes("-fullscreen", True)
            self.overlay.attributes("-topmost", True)
            self.overlay.attributes("-transparentcolor", "white")
            self.overlay.configure(bg="white", cursor="none")

            hwnd = ctypes.windll.user32.GetParent(self.overlay.winfo_id())
            extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, extended_style | 0x80000 | 0x20)  # WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0x00FFFFFF, 0, 0x1)

        elif sys.platform.startswith("linux"):
            print("[Overlay] Creating PyQt5 full-screen transparent overlay (Linux)")

            def run_overlay():
                self.overlay = QWidget()
                self.overlay.setWindowFlags(
                    Qt.FramelessWindowHint |
                    Qt.WindowStaysOnTopHint |
                    Qt.Tool
                )
                self.overlay.setAttribute(Qt.WA_TranslucentBackground)
                self.overlay.setCursor(Qt.BlankCursor)
                self.overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
                self.overlay.setWindowOpacity(0.0)
                self.overlay.show()
                self.overlay.raise_()
                print("[Overlay] PyQt5 overlay running event loop")
                self.qt_app.exec_()

            threading.Thread(target=run_overlay, daemon=True).start()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MouseSyncGUI()
    app.run()
