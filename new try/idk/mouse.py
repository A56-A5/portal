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
        
        # Get screen dimensions using temporary root (more reliable)
        temp_root = tk.Tk()
        temp_root.withdraw()
        self.screen_width = temp_root.winfo_screenwidth()
        self.screen_height = temp_root.winfo_screenheight()
        temp_root.destroy()
        print(f"[System] Screen dimensions: {self.screen_width}x{self.screen_height}")
        print(f"[System] Screen edges: Left=0, Right={self.screen_width}, Top=0, Bottom={self.screen_height}")
        
        # Variables
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
        # Mode selection
        mode_frame = ttk.LabelFrame(self.root, text="Mode", padding=10)
        mode_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Radiobutton(mode_frame, text="Server", variable=self.is_server, 
                       value=True, command=self.update_mode).pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="Client", variable=self.is_server, 
                       value=False, command=self.update_mode).pack(side="left", padx=5)
        
        # Server IP input
        ip_frame = ttk.LabelFrame(self.root, text="Server IP", padding=10)
        ip_frame.pack(fill="x", padx=10, pady=5)
        
        self.ip_entry = ttk.Entry(ip_frame, textvariable=self.server_ip)
        self.ip_entry.pack(fill="x", padx=5, pady=5)
        
        # Screen info label
        screen_frame = ttk.LabelFrame(self.root, text="Screen Info", padding=10)
        screen_frame.pack(fill="x", padx=10, pady=5)
        
        self.screen_label = ttk.Label(screen_frame, 
            text=f"Screen: {self.screen_width}x{self.screen_height}")
        self.screen_label.pack(fill="x", padx=5, pady=5)
        
        # Control button
        self.start_button = ttk.Button(self.root, text="Start", command=self.toggle_connection)
        self.start_button.pack(pady=10)
        
        # Status label
        self.status_label = ttk.Label(self.root, text="Status: Disconnected")
        self.status_label.pack(pady=5)
        
        # Initialize mode
        self.update_mode()
        
    def update_mode(self):
        if self.is_server.get():
            self.ip_entry.config(state="disabled")
            print("[Mode] Switched to Server mode")
        else:
            self.ip_entry.config(state="normal")
            print("[Mode] Switched to Client mode")
            
    def toggle_connection(self):
        if not self.is_running:
            self.start_connection()
        else:
            self.stop_connection()
            
    def start_connection(self):
        try:
            if self.is_server.get():
                print("[Server] Starting server...")
                self.start_server()
            else:
                print(f"[Client] Connecting to server at {self.server_ip.get()}...")
                self.start_client()
            self.is_running = True
            self.start_button.config(text="Stop")
            self.status_label.config(text="Status: Connected")
        except Exception as e:
            print(f"[Error] Connection failed: {str(e)}")
            messagebox.showerror("Error", f"Failed to start: {str(e)}")
            
    def stop_connection(self):
        print("[System] Stopping connection...")
        self.is_running = False
        
        # Close overlay if open
        if self.overlay:
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
            print("[Server] Server socket closed")
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None
            print("[Client] Client socket closed")
        self.start_button.config(text="Start")
        self.status_label.config(text="Status: Disconnected")
        print("[System] Connection stopped")
        
    def create_overlay(self):
        print("[Overlay] Creating full-screen transparent overlay")

        # Use a new root window to get accurate screen size
        screen_root = tk.Tk()
        screen_root.withdraw()
        screen_width = screen_root.winfo_screenwidth()
        screen_height = screen_root.winfo_screenheight()
        screen_root.destroy()
        print(f"[Overlay] Detected screen size: {screen_width}x{screen_height}")

        self.overlay = tk.Toplevel()
        self.overlay.overrideredirect(True)
        self.overlay.geometry(f"{screen_width}x{screen_height}+0+0")
        self.overlay.configure(bg='black')

        # Make almost fully transparent but allow mouse events to go through
        self.overlay.attributes("-alpha", 0.01)
        self.overlay.attributes("-topmost", True)

        # Hide cursor on overlay
        self.overlay.config(cursor="none")

        # Bring overlay on top
        self.overlay.lift()
        self.overlay.update_idletasks()
        self.overlay.focus_force()
        print("[Overlay] Overlay is now active and covering full screen")
        
    def handle_client(self, client_socket):
        print("[Server] Starting mouse tracking...")
        self.create_overlay()

        def track_mouse_position():
            last_position = None
            controller = mouse.Controller()
            try:
                while self.is_running:
                    x, y = controller.position

                    # Edge logging (optional)
                    if x <= 0:
                        print(f"[Server] Mouse at LEFT edge: X={x}")
                    elif x >= self.screen_width - 1:
                        print(f"[Server] Mouse at RIGHT edge: X={x}")
                    if y <= 0:
                        print(f"[Server] Mouse at TOP edge: Y={y}")
                    elif y >= self.screen_height - 1:
                        print(f"[Server] Mouse at BOTTOM edge: Y={y}")

                    # Only send if position changed
                    if last_position != (x, y):
                        data = json.dumps({"x": x, "y": y}) + '\n'
                        client_socket.sendall(data.encode())
                        last_position = (x, y)

                    time.sleep(0.01)
            except Exception as e:
                print(f"[Server] Error sending mouse data: {e}")
                self.stop_connection()

        threading.Thread(target=track_mouse_position, daemon=True).start()
        
    def start_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(1)
            print(f"[Server] Listening on port {self.port}")
            
            def server_thread():
                try:
                    print("[Server] Waiting for client connection...")
                    client, addr = self.server_socket.accept()
                    print(f"[Server] Client connected from: {addr}")
                    # Send initial connection acknowledgment
                    client.sendall(b'CONNECTED\n')
                    print("[Server] Sent connection acknowledgment")
                    self.handle_client(client)
                except Exception as e:
                    if self.is_running:
                        print(f"[Server] Error: {e}")
                    self.stop_connection()
                        
            threading.Thread(target=server_thread, daemon=True).start()
            
        except Exception as e:
            print(f"[Server] Failed to start: {e}")
            raise
            
    def start_client(self):
        try:
            print(f"[Client] Attempting to connect to {self.server_ip.get()}:{self.port}")
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_ip.get(), self.port))
            print(f"[Client] Connected to server at {self.server_ip.get()}:{self.port}")
            
            # Wait for server acknowledgment
            data = self.client_socket.recv(1024)
            if data == b'CONNECTED\n':
                print("[Client] Received connection acknowledgment from server")
            else:
                print("[Client] Did not receive proper connection acknowledgment")
                raise Exception("Connection failed - no server acknowledgment")
            
            def client_thread():
                print("[Client] Starting mouse tracking...")
                buffer = ""
                last_position = None
                while self.is_running:
                    try:
                        # Receive data in chunks
                        data = self.client_socket.recv(1024).decode()
                        if not data:
                            print("[Client] Server disconnected")
                            break
                            
                        # Add received data to buffer
                        buffer += data
                        
                        # Process complete JSON messages
                        while '\n' in buffer:
                            message, buffer = buffer.split('\n', 1)
                            try:
                                mouse_data = json.loads(message)
                                x, y = mouse_data["x"], mouse_data["y"]
                                
                                # Edge logging (optional)
                                if x <= 0:
                                    print(f"[Client] Mouse at LEFT edge: X={x}")
                                elif x >= self.screen_width - 1:
                                    print(f"[Client] Mouse at RIGHT edge: X={x}")
                                if y <= 0:
                                    print(f"[Client] Mouse at TOP edge: Y={y}")
                                elif y >= self.screen_height - 1:
                                    print(f"[Client] Mouse at BOTTOM edge: Y={y}")
                                
                                # Only move if position changed
                                if last_position != (x, y):
                                    print(f"[Client] Moving mouse to: X={x}, Y={y}")
                                    self.mouse_controller.position = (x, y)
                                    last_position = (x, y)
                            except json.JSONDecodeError as e:
                                print(f"[Client] Error decoding mouse data: {e}")
                            except Exception as e:
                                print(f"[Client] Error moving mouse: {e}")
                                
                    except Exception as e:
                        if self.is_running:
                            print(f"[Client] Error: {e}")
                        break
                        
            threading.Thread(target=client_thread, daemon=True).start()
            
        except Exception as e:
            print(f"[Client] Connection error: {e}")
            raise
            
    def on_closing(self):
        print("[System] Application closing...")
        self.stop_connection()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseSyncApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
