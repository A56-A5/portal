import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
import pyautogui
import time
from pynput import mouse
import platform
import os

class BarrierApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Barrier Clone")
        self.root.geometry("400x300")
        
        # Variables
        self.is_server = tk.BooleanVar(value=False)
        self.server_ip = tk.StringVar(value="127.0.0.1")
        self.port = 5000
        self.is_running = False
        self.server_socket = None
        self.client_socket = None
        self.mouse_thread = None
        self.mouse_controller = mouse.Controller()
        self.pointer_on_server = True
        self.pointer_on_client = False
        
        self.setup_gui()
        
    def get_screen_size(self):
        try:
            return pyautogui.size()
        except:
            if platform.system() == 'Windows':
                from ctypes import windll
                return windll.user32.GetSystemMetrics(0), windll.user32.GetSystemMetrics(1)
            else:
                return 1920, 1080  # fallback
                
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
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(1)
            print(f"Server listening on port {self.port}")
            print("Server is ready to accept connections...")
            
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
            
        except Exception as e:
            print(f"Failed to start server: {e}")
            raise
            
    def start_client(self):
        try:
            server_ip = self.server_ip.get()
            print(f"Attempting to connect to {server_ip}:{self.port}")
            
            # Test if we can resolve the hostname
            try:
                socket.gethostbyname(server_ip)
            except socket.gaierror:
                print(f"Cannot resolve hostname: {server_ip}")
                raise
                
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)  # 5 second timeout
            self.client_socket.connect((server_ip, self.port))
            print(f"Successfully connected to server at {server_ip}:{self.port}")
            
            def client_thread():
                width, height = self.get_screen_size()
                while self.is_running:
                    try:
                        data = self.client_socket.recv(1024)
                        if not data:
                            print("Server disconnected")
                            break
                        lines = data.decode().splitlines()
                        for line in lines:
                            if not line:
                                continue
                            mouse_data = json.loads(line)
                            if mouse_data["type"] == "move":
                                x, y = mouse_data["x"], mouse_data["y"]
                                # Check if mouse is at screen edge
                                if x <= 0 or x >= width - 1 or y <= 0 or y >= height - 1:
                                    self.client_socket.sendall(b'RETURN\n')
                                    self.pointer_on_client = False
                                    print("Mouse returned to server")
                                else:
                                    self.mouse_controller.position = (x, y)
                            elif mouse_data["type"] == "click":
                                button = getattr(mouse.Button, mouse_data["button"].split('.')[-1], mouse.Button.left)
                                if mouse_data["pressed"]:
                                    self.mouse_controller.press(button)
                                else:
                                    self.mouse_controller.release(button)
                            elif mouse_data["type"] == "scroll":
                                self.mouse_controller.scroll(mouse_data["dx"], mouse_data["dy"])
                    except Exception as e:
                        if self.is_running:
                            print(f"Client error: {e}")
                        break
                        
            threading.Thread(target=client_thread, daemon=True).start()
            
        except socket.timeout:
            print("Connection timed out. Please check if the server is running and the IP is correct.")
            raise
        except ConnectionRefusedError:
            print("Connection refused. Please check if the server is running and the port is correct.")
            raise
        except socket.gaierror:
            print("Invalid IP address. Please check the server IP address.")
            raise
        except Exception as e:
            print(f"Failed to connect: {e}")
            raise
            
    def handle_client(self, client_socket):
        width, height = self.get_screen_size()
        
        def on_mouse_move(x, y):
            if not self.is_running:
                return True
                
            if not self.pointer_on_server:
                return True
                
            # Check if mouse is at screen edge
            if x <= 0 or x >= width - 1 or y <= 0 or y >= height - 1:
                self.pointer_on_server = False
                self.pointer_on_client = True
                try:
                    client_socket.sendall(f'ENTER:{x},{y}\n'.encode())
                    print("Mouse entered client")
                except Exception as e:
                    print(f"Error sending ENTER: {e}")
                return True
                
            try:
                data = json.dumps({"type": "move", "x": x, "y": y})
                client_socket.sendall(data.encode() + b'\n')
            except Exception as e:
                print(f"Error sending mouse data: {e}")
            return True
                    
        def on_mouse_click(x, y, button, pressed):
            if not self.is_running or not self.pointer_on_server:
                return
            try:
                data = json.dumps({
                    "type": "click",
                    "button": str(button),
                    "pressed": pressed
                })
                client_socket.sendall(data.encode() + b'\n')
            except Exception as e:
                print(f"Error sending click data: {e}")
                    
        def on_mouse_scroll(x, y, dx, dy):
            if not self.is_running or not self.pointer_on_server:
                return
            try:
                data = json.dumps({
                    "type": "scroll",
                    "dx": dx,
                    "dy": dy
                })
                client_socket.sendall(data.encode() + b'\n')
            except Exception as e:
                print(f"Error sending scroll data: {e}")
                    
        with mouse.Listener(
            on_move=on_mouse_move,
            on_click=on_mouse_click,
            on_scroll=on_mouse_scroll
        ) as listener:
            while self.is_running:
                try:
                    data = client_socket.recv(1024)
                    if not data:
                        print("Client disconnected")
                        break
                    if b'RETURN' in data:
                        self.pointer_on_server = True
                        self.pointer_on_client = False
                        print("Mouse returned to server")
                except Exception as e:
                    if self.is_running:
                        print(f"Server error: {e}")
                    break
                time.sleep(0.01)
            
    def on_closing(self):
        self.stop_connection()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = BarrierApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop() 