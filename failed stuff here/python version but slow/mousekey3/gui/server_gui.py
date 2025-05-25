import tkinter as tk
from tkinter import ttk, messagebox
import threading
import socket
import platform
import pyautogui
from common import get_screen_size, clamp

CLIENT_POSITIONS = ['left', 'right', 'top', 'bottom']

class ServerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Barrier Prototype - Server")
        self.geometry("400x250")
        self.resizable(False, False)

        self.server_thread = None
        self.client_socket = None
        self.conn_lock = threading.Lock()
        self.control_with_client = False
        self.running = False

        self.local_x, self.local_y = pyautogui.position()
        self.screen_width, self.screen_height = get_screen_size()

        self.client_position = tk.StringVar(value='right')
        self.status_text = tk.StringVar(value="Server stopped")

        self.create_widgets()

    def create_widgets(self):
        ttk.Label(self, text="Select Client Position relative to Server:").pack(pady=8)

        pos_frame = ttk.Frame(self)
        pos_frame.pack()
        for pos in CLIENT_POSITIONS:
            rb = ttk.Radiobutton(pos_frame, text=pos.capitalize(), variable=self.client_position, value=pos)
            rb.pack(side=tk.LEFT, padx=10)

        self.status_label = ttk.Label(self, textvariable=self.status_text)
        self.status_label.pack(pady=10)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        self.start_btn = ttk.Button(btn_frame, text="Start Server", command=self.start_server)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = ttk.Button(btn_frame, text="Stop Server", command=self.stop_server, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)

    def start_server(self):
        if self.running:
            return
        self.running = True
        self.status_text.set("Starting server...")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        self.server_thread = threading.Thread(target=self.server_main, daemon=True)
        self.server_thread.start()

    def stop_server(self):
        self.running = False
        self.status_text.set("Server stopped")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        # Close client connection if any
        with self.conn_lock:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
                self.client_socket = None

    def send_deltas(self, dx, dy):
        with self.conn_lock:
            if self.client_socket:
                try:
                    data = f"{dx},{dy}\n".encode()
                    self.client_socket.sendall(data)
                except Exception as e:
                    self.status_text.set(f"Send error: {e}")
                    self.client_socket = None

    def handle_client(self, client_sock, addr):
        self.client_socket = client_sock
        self.status_text.set(f"Client connected: {addr}")
        try:
            while self.running:
                data = client_sock.recv(1024)
                if not data:
                    break
                msg = data.decode().strip()
                if msg == "release":
                    self.control_with_client = False
                    self.status_text.set("Control returned to server")
        except Exception as e:
            self.status_text.set(f"Client error: {e}")
        finally:
            self.client_socket = None
            self.status_text.set("Client disconnected")

    def server_main(self):
        HOST = '0.0.0.0'
        PORT = 65432
        self.control_with_client = False
        self.local_x, self.local_y = pyautogui.position()

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.settimeout(1.0)
        server_socket.bind((HOST, PORT))
        server_socket.listen(1)
        self.status_text.set(f"Server listening on {HOST}:{PORT}")

        client_sock = None
        while self.running:
            try:
                client_sock, addr = server_socket.accept()
                self.status_text.set(f"Client connected: {addr}")
                client_thread = threading.Thread(target=self.handle_client, args=(client_sock, addr), daemon=True)
                client_thread.start()
                break
            except socket.timeout:
                continue

        # Mouse tracking loop (simple implementation with pynput)
        from pynput import mouse

        def on_move(x, y):
            if not self.running:
                return False  # Stop listener

            dx = x - self.local_x
            dy = y - self.local_y
            self.local_x, self.local_y = x, y

            if not self.control_with_client:
                # Check edge based on client position
                at_edge = False
                if self.client_position.get() == 'right' and x >= self.screen_width - 1 and dx > 0:
                    at_edge = True
                elif self.client_position.get() == 'left' and x <= 0 and dx < 0:
                    at_edge = True
                elif self.client_position.get() == 'top' and y <= 0 and dy < 0:
                    at_edge = True
                elif self.client_position.get() == 'bottom' and y >= self.screen_height - 1 and dy > 0:
                    at_edge = True

                if at_edge:
                    self.control_with_client = True
                    self.status_text.set("Control moved to client")
                    self.send_deltas(dx, dy)
                else:
                    pass  # Local cursor already moved by pynput
            else:
                self.send_deltas(dx, dy)

        with mouse.Listener(on_move=on_move) as listener:
            while self.running:
                listener.join(0.1)

        server_socket.close()
        self.status_text.set("Server stopped")

if __name__ == "__main__":
    app = ServerApp()
    app.mainloop()
