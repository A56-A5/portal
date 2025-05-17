import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
from pynput import mouse
import time
import platform
import ctypes
import os

# Platform-specific imports
if platform.system() == "Windows":
    try:
        import win32api
        import win32con
        import win32gui
        from ctypes import windll, Structure, c_long, byref
        
        class POINT(Structure):
            _fields_ = [("x", c_long), ("y", c_long)]
    except ImportError:
        print("[System] win32api not available, using ctypes fallback")
elif platform.system() == "Linux":
    try:
        from Xlib import display, X
        from Xlib.ext import record
        from Xlib.protocol import rq
    except ImportError:
        print("[System] Xlib not available, using Tkinter fallback")

class MouseSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mouse Sync")
        self.root.geometry("300x200")
        
        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
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
        self.original_cursor_visibility = True
        self.system = platform.system()
        self.cursor_hidden = False
        self.last_mouse_pos = None
        
        self.setup_gui()
        
    def get_mouse_position(self):
        """Get current mouse position using platform-specific methods"""
        if self.system == "Windows":
            try:
                pt = POINT()
                windll.user32.GetCursorPos(byref(pt))
                return pt.x, pt.y
            except:
                return 0, 0
        elif self.system == "Linux":
            try:
                d = display.Display()
                root = d.screen().root
                root.query_pointer()
                return root.query_pointer().root_x, root.query_pointer().root_y
            except:
                return 0, 0
        return 0, 0
        
    def hide_cursor(self):
        """Hide the global cursor using platform-specific methods"""
        if self.cursor_hidden:
            return
            
        try:
            if self.system == "Windows":
                # Windows implementation - hide cursor globally
                # First try to hide cursor multiple times to ensure it's hidden
                for _ in range(20):  # Try multiple times to ensure it's hidden
                    win32api.ShowCursor(False)
                
                # Move cursor to center of screen before hiding
                win32api.SetCursorPos((self.screen_width//2, self.screen_height//2))
            elif self.system == "Linux":
                # Linux implementation using Xlib
                try:
                    d = display.Display()
                    root = d.screen().root
                    # Move cursor to center before hiding
                    root.warp_pointer(self.screen_width//2, self.screen_height//2)
                    # Hide cursor
                    os.system('xsetroot -cursor_name none')
                except (NameError, ImportError):
                    print("[Server] Xlib not available, using fallback method")
                    os.system('xsetroot -cursor_name none')
            
            self.cursor_hidden = True
            print("[Server] Global cursor hidden")
        except Exception as e:
            print(f"[Server] Error hiding cursor: {e}")
            
    def show_cursor(self):
        """Show the global cursor using platform-specific methods"""
        if not self.cursor_hidden:
            return
            
        try:
            if self.system == "Windows":
                # Windows implementation - show cursor globally
                # Show cursor multiple times to ensure it's visible
                for _ in range(20):  # Try multiple times to ensure it's shown
                    win32api.ShowCursor(True)
                # Move cursor to center of screen
                win32api.SetCursorPos((self.screen_width//2, self.screen_height//2))
            elif self.system == "Linux":
                # Linux implementation
                try:
                    d = display.Display()
                    root = d.screen().root
                    # Show cursor
                    root.warp_pointer(self.screen_width//2, self.screen_height//2)
                    # Restore default cursor
                    os.system('xsetroot -cursor_name left_ptr')
                except (NameError, ImportError):
                    print("[Server] Xlib not available, using fallback method")
                    os.system('xsetroot -cursor_name left_ptr')
            
            self.cursor_hidden = False
            print("[Server] Global cursor shown")
        except Exception as e:
            print(f"[Server] Error showing cursor: {e}")
            
    def handle_client(self, client_socket):
        print("[Server] Starting mouse tracking...")
        last_position = None
        
        def track_mouse():
            """Track mouse movement using platform-specific methods"""
            while self.is_running:
                try:
                    x, y = self.get_mouse_position()
                    if last_position != (x, y):
                        # Clamp coordinates
                        x = max(0, min(x, self.screen_width - 1))
                        y = max(0, min(y, self.screen_height - 1))
                        
                        # Send position to client
                        data = json.dumps({"x": x, "y": y}) + '\n'
                        client_socket.sendall(data.encode())
                        print(f"[Server] Mouse position: X={x}, Y={y}")
                        last_position = (x, y)
                except Exception as e:
                    print(f"[Server] Error tracking mouse: {e}")
                    break
                time.sleep(0.01)  # Small delay to prevent high CPU usage
        
        # Start mouse tracking in a separate thread
        tracking_thread = threading.Thread(target=track_mouse, daemon=True)
        tracking_thread.start()
        
        try:
            while self.is_running:
                time.sleep(0.1)
        except Exception as e:
            print(f"[Server] Mouse tracking error: {e}")
            self.stop_connection()
        
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
        if self.server_socket:
            self.server_socket.close()
            print("[Server] Server socket closed")
            # Show cursor when server stops
            self.show_cursor()
        if self.client_socket:
            self.client_socket.close()
            print("[Client] Client socket closed")
        self.start_button.config(text="Start")
        self.status_label.config(text="Status: Disconnected")
        print("[System] Connection stopped")
        
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
                    # Hide cursor after connection is established
                    self.hide_cursor()
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
                                
                                # Check if mouse is at screen edges
                                if x <= 0:
                                    print(f"[Client] Mouse at LEFT edge: X={x}")
                                elif x >= self.screen_width - 1:
                                    print(f"[Client] Mouse at RIGHT edge: X={x}")
                                if y <= 0:
                                    print(f"[Client] Mouse at TOP edge: Y={y}")
                                elif y >= self.screen_height - 1:
                                    print(f"[Client] Mouse at BOTTOM edge: Y={y}")
                                
                                # Only move if position has changed
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
        """Ensure cursor is shown when closing the application"""
        print("[System] Application closing...")
        try:
            self.show_cursor()  # Make sure cursor is shown
        except:
            pass  # Ignore any errors during cleanup
        self.stop_connection()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseSyncApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop() 