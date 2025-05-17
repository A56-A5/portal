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

# Platform-specific imports and structures
if platform.system() == "Windows":
    try:
        import win32api
        import win32con
        import win32gui
        from ctypes import windll, Structure, c_long, byref
        
        class POINT(Structure):
            _fields_ = [("x", c_long), ("y", c_long)]
            
        # Windows API constants
        CURSOR_SHOWING = 0x00000001
        SPI_SETMOUSECLICKLOCK = 0x101F
        SPI_SETMOUSESONAR = 0x101D
        SPI_SETMOUSEVANISH = 0x1021
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDCHANGE = 0x02
        
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
        self.system = platform.system()
        self.cursor_hidden = False
        self.cursor_locked = False
        
        self.setup_gui()
        
    def lock_cursor(self):
        """Lock cursor at screen edge and hide it"""
        if self.cursor_locked:
            return
            
        try:
            if self.system == "Windows":
                # Move cursor to edge of screen
                win32api.SetCursorPos((0, 0))
                
                # Hide cursor globally
                for _ in range(50):
                    win32api.ShowCursor(False)
                
                # Create a tiny rectangle at screen edge to confine cursor
                rect = ctypes.c_long * 4
                rect = rect(0, 0, 1, 1)  # 1x1 pixel at (0,0)
                ctypes.windll.user32.ClipCursor(ctypes.byref(rect))
                
            elif self.system == "Linux":
                try:
                    d = display.Display()
                    root = d.screen().root
                    # Move cursor to edge
                    root.warp_pointer(0, 0)
                    # Hide cursor
                    os.system('xsetroot -cursor_name none')
                    os.system('unclutter -idle 0.1 -root &')
                except:
                    print("[Server] Failed to lock cursor on Linux")
            
            self.cursor_locked = True
            print("[Server] Cursor locked at edge")
            
        except Exception as e:
            print(f"[Server] Error locking cursor: {e}")
            
    def unlock_cursor(self):
        """Show cursor globally"""
        if not self.cursor_locked:
            return
            
        try:
            if self.system == "Windows":
                # Show cursor globally
                for _ in range(50):  # Multiple attempts to ensure it's shown
                    win32api.ShowCursor(True)
                
                # Restore system-wide cursor visibility
                try:
                    ctypes.windll.user32.SystemParametersInfoW(0x101F, 1, None, 0x01 | 0x02)  # SPI_SETMOUSECLICKLOCK
                    ctypes.windll.user32.SystemParametersInfoW(0x101D, 1, None, 0x01 | 0x02)  # SPI_SETMOUSESONAR
                    ctypes.windll.user32.SystemParametersInfoW(0x1021, 1, None, 0x01 | 0x02)  # SPI_SETMOUSEVANISH
                except:
                    print("[Server] Could not restore system-wide cursor visibility")
                
            elif self.system == "Linux":
                try:
                    # Show cursor globally
                    os.system('xsetroot -cursor_name left_ptr')
                    os.system('pkill unclutter')
                    # Restore pointer
                    os.system('xinput set-prop "Virtual core pointer" "Device Enabled" 1')
                except:
                    print("[Server] Failed to show cursor on Linux")
            
            self.cursor_locked = False
            print("[Server] Global cursor shown")
            
        except Exception as e:
            print(f"[Server] Error showing cursor: {e}")
            
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
            
    def handle_client(self, client_socket):
        print("[Server] Starting mouse tracking...")
        last_position = None
        last_physical_pos = None
        
        def on_mouse_move(x, y):
            nonlocal last_position, last_physical_pos
            if self.is_running:
                try:
                    # Get the physical mouse position
                    if self.system == "Windows":
                        pt = POINT()
                        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                        physical_x, physical_y = pt.x, pt.y
                    else:
                        # For Linux, use the raw coordinates
                        physical_x, physical_y = x, y
                    
                    # Only send if physical position has changed
                    if last_physical_pos != (physical_x, physical_y):
                        # Send the physical mouse position
                        data = json.dumps({"x": physical_x, "y": physical_y}) + '\n'
                        client_socket.sendall(data.encode())
                        print(f"[Server] Physical mouse position: X={physical_x}, Y={physical_y}")
                        last_physical_pos = (physical_x, physical_y)
                        
                        # Keep cursor locked at edge
                        if self.system == "Windows":
                            win32api.SetCursorPos((0, 0))
                        elif self.system == "Linux":
                            try:
                                d = display.Display()
                                root = d.screen().root
                                root.warp_pointer(0, 0)
                            except:
                                pass
                                
                except Exception as e:
                    print(f"[Server] Error sending mouse data: {e}")
                    self.stop_connection()
                    
        # Lock cursor at edge before starting mouse tracking
        self.lock_cursor()
        
        with mouse.Listener(on_move=on_mouse_move) as listener:
            print("[Server] Mouse listener started")
            try:
                while self.is_running:
                    time.sleep(0.01)
            except Exception as e:
                print(f"[Server] Mouse tracking error: {e}")
                self.stop_connection()
            finally:
                # Show cursor when done
                self.unlock_cursor()
        
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
                                
                                # Move client cursor to match server's physical mouse position
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
            
    def stop_connection(self):
        print("[System] Stopping connection...")
        self.is_running = False
        if self.server_socket:
            self.server_socket.close()
            print("[Server] Server socket closed")
            # Unlock cursor when server stops
            self.unlock_cursor()
        if self.client_socket:
            self.client_socket.close()
            print("[Client] Client socket closed")
        self.start_button.config(text="Start")
        self.status_label.config(text="Status: Disconnected")
        print("[System] Connection stopped")
        
    def on_closing(self):
        """Ensure cursor is unlocked when closing"""
        print("[System] Application closing...")
        self.unlock_cursor()
        self.stop_connection()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseSyncApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop() 