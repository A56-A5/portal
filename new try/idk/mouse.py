
import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
from pynput import mouse
import time

class MouseSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mouse Sync")
        self.root.geometry("300x200")

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.is_server = tk.BooleanVar(value=False)
        self.server_ip = tk.StringVar(value="127.0.0.1")
        self.port = 50007
        self.is_running = False
        self.server_socket = None
        self.client_socket = None
        self.mouse_controller = mouse.Controller()
        self.overlay = None

        self.setup_gui()

    def setup_gui(self):
        mode_frame = ttk.LabelFrame(self.root, text="Mode", padding=10)
        mode_frame.pack(fill="x", padx=10, pady=5)

        ttk.Radiobutton(mode_frame, text="Server", variable=self.is_server, 
                        value=True, command=self.update_mode).pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="Client", variable=self.is_server, 
                        value=False, command=self.update_mode).pack(side="left", padx=5)

        ip_frame = ttk.LabelFrame(self.root, text="Server IP", padding=10)
        ip_frame.pack(fill="x", padx=10, pady=5)

        self.ip_entry = ttk.Entry(ip_frame, textvariable=self.server_ip)
        self.ip_entry.pack(fill="x", padx=5, pady=5)

        screen_frame = ttk.LabelFrame(self.root, text="Screen Info", padding=10)
        screen_frame.pack(fill="x", padx=10, pady=5)

        self.screen_label = ttk.Label(screen_frame, 
            text=f"Screen: {self.screen_width}x{self.screen_height}")
        self.screen_label.pack(fill="x", padx=5, pady=5)

        self.start_button = ttk.Button(self.root, text="Start", command=self.toggle_connection)
        self.start_button.pack(pady=10)

        self.status_label = ttk.Label(self.root, text="Status: Disconnected")
        self.status_label.pack(pady=5)

        self.update_mode()

    def update_mode(self):
        if self.is_server.get():
            self.ip_entry.config(state="disabled")
        else:
            self.ip_entry.config(state="normal")

    def toggle_connection(self):
        if not self.is_running:
            self.start_connection()
        else:
            self.stop_connection()

    def start_connection(self):
        try:
            if self.is_server.get():
                self.start_server()
            else:
                self.start_client()
            self.is_running = True
            self.start_button.config(text="Stop")
            self.status_label.config(text="Status: Connected")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start: {str(e)}")

    def stop_connection(self):
        self.is_running = False
        if self.server_socket:
            self.server_socket.close()
        if self.client_socket:
            self.client_socket.close()
        if self.overlay:
            self.overlay.destroy()
            self.overlay = None
        self.start_button.config(text="Start")
        self.status_label.config(text="Status: Disconnected")

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(1)

        def server_thread():
            client, addr = self.server_socket.accept()
            client.sendall(b'CONNECTED\n')
            self.create_invisible_overlay()
            self.handle_client(client)

        threading.Thread(target=server_thread, daemon=True).start()

    def create_invisible_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
        self.overlay.attributes("-alpha", 0.01)
        self.overlay.attributes("-topmost", True)
        self.overlay.configure(cursor="none")
        self.overlay.update_idletasks()
        self.overlay.lift()
        self.overlay.focus_force()

    def handle_client(self, client_socket):
        last_position = None
        def on_mouse_move(x, y):
            nonlocal last_position
            if self.is_running and last_position != (x, y):
                data = json.dumps({"x": x, "y": y}) + '\n'
                try:
                    client_socket.sendall(data.encode())
                    last_position = (x, y)
                except:
                    self.stop_connection()

        with mouse.Listener(on_move=on_mouse_move) as listener:
            while self.is_running:
                time.sleep(0.01)

    def start_client(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.server_ip.get(), self.port))
        ack = self.client_socket.recv(1024)
        if ack != b'CONNECTED\n':
            raise Exception("No ack from server")

        def client_thread():
            buffer = ""
            while self.is_running:
                try:
                    data = self.client_socket.recv(1024).decode()
                    if not data:
                        break
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        payload = json.loads(line)
                        x, y = payload["x"], payload["y"]
                        self.mouse_controller.position = (x, y)
                except:
                    self.stop_connection()
                    break

        threading.Thread(target=client_thread, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseSyncApp(root)
    root.mainloop()
