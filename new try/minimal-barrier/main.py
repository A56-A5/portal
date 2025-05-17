import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
import pyautogui
import time
from pynput import mouse

class BarrierApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Barrier Clone")
        self.root.geometry("400x300")
        
        # Variables
        self.is_server = tk.BooleanVar(value=False)
        self.server_ip = tk.StringVar(value="127.0.0.1")
        self.port = 5000  # Fixed port
        self.is_running = False
        self.server_socket = None
        self.client_socket = None
        self.mouse_thread = None
        
        self.setup_gui()
        
    def setup_gui(self):
        # Mode selection
        mode_frame = ttk.LabelFrame(self.root, text="Mode", padding=10)
        mode_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Radiobutton(mode_frame, text="Server", variable=self.is_server, 
                       value=True, command=self.update_mode).pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="Client", variable=self.is_server, 
                       value=False, command=self.update_mode).pack(side="left", padx=5)
        
        # Connection settings
        conn_frame = ttk.LabelFrame(self.root, text="Connection Settings", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(conn_frame, text="Server IP:").grid(row=0, column=0, padx=5, pady=5)
        self.ip_entry = ttk.Entry(conn_frame, textvariable=self.server_ip)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Control buttons
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="Start", command=self.toggle_connection)
        self.start_button.pack(side="left", padx=5)
        
        # Status
        self.status_label = ttk.Label(self.root, text="Status: Disconnected")
        self.status_label.pack(pady=10)
        
        # Initialize mode
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
                print("Starting server...")
                self.start_server()
            else:
                print(f"Connecting to server at {self.server_ip.get()}...")
                self.start_client()
            self.is_running = True
            self.start_button.config(text="Stop")
            self.status_label.config(text="Status: Connected")
            print("Connection established successfully!")
        except Exception as e:
            print(f"Connection failed: {str(e)}")
            messagebox.showerror("Error", f"Failed to start: {str(e)}")
            
    def stop_connection(self):
        print("Stopping connection...")
        self.is_running = False
        if self.server_socket:
            self.server_socket.close()
        if self.client_socket:
            self.client_socket.close()
        if self.mouse_thread:
            self.mouse_thread.join(timeout=1.0)
        self.start_button.config(text="Start")
        self.status_label.config(text="Status: Disconnected")
        print("Connection stopped")
        
    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(1)
        print(f"Server listening on port {self.port}")
        
        def server_thread():
            while self.is_running:
                try:
                    client, addr = self.server_socket.accept()
                    print(f"Client connected from: {addr}")
                    self.handle_client(client)
                except Exception as e:
                    if self.is_running:
                        print(f"Server error: {e}")
                    break
                    
        threading.Thread(target=server_thread, daemon=True).start()
        
    def start_client(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.server_ip.get(), self.port))
        print(f"Connected to server at {self.server_ip.get()}:{self.port}")
        
        def client_thread():
            while self.is_running:
                try:
                    data = self.client_socket.recv(1024)
                    if not data:
                        break
                    mouse_data = json.loads(data.decode())
                    self.update_mouse_position(mouse_data)
                except Exception as e:
                    if self.is_running:
                        print(f"Client error: {e}")
                    break
                    
        threading.Thread(target=client_thread, daemon=True).start()
        
    def handle_client(self, client_socket):
        def on_mouse_move(x, y):
            if self.is_running:
                try:
                    data = json.dumps({"x": x, "y": y})
                    client_socket.sendall(data.encode())
                except Exception as e:
                    print(f"Error sending mouse data: {e}")
                    
        with mouse.Listener(on_move=on_mouse_move) as listener:
            while self.is_running:
                time.sleep(0.01)
                
    def update_mouse_position(self, mouse_data):
        try:
            pyautogui.moveTo(mouse_data["x"], mouse_data["y"])
        except Exception as e:
            print(f"Error updating mouse position: {e}")
            
    def on_closing(self):
        self.stop_connection()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = BarrierApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop() 