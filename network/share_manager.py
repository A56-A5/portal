"""
Share Manager - Complete mouse, keyboard, clipboard sync using organized controllers
"""
import sys
import socket
import threading
import json
import time
import platform
import subprocess
import logging
import os
from datetime import datetime
from pynput import mouse, keyboard
from pynput.mouse import Button

from utils.config import app_config
from controllers.mouse_controller import MouseController
from controllers.keyboard_controller import KeyboardController
from controllers.clipboard_controller import ClipboardController


class ShareManager:
    def __init__(self):
        self.edge_transition_cooldown = False
        self.primary_port = app_config.server_primary_port
        self.secondary_port = app_config.server_secondary_port
        
        # Controllers
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.clipboard_controller = ClipboardController()
        
        # Network sockets
        self.server_socket = None
        self.client_socket = None
        self.secondary_server_socket = None
        self.secondary_client_socket = None
        self.secondary_server = None
        
        # Overlay
        self.overlay = None
        self.screen_width = None
        self.screen_height = None
        self.gui_app = None
        self.last_send = None
        
        # Keyboard listener
        self.keyboard_listener = None
        self.keyboard_listener_lock = threading.Lock()
        
        self.os_type = platform.system().lower()
        
        logging.basicConfig(
            level=logging.INFO,
            filename="logs.log",
            filemode="a",
            format="%(levelname)s - %(message)s"
        )
        
        app_config.load()
        app_config.active_device = False
        app_config.save()
        
        self.setup_screen()
        self.start_hotkey_listener()
    
    def setup_screen(self):
        """Setup GUI app and get screen dimensions"""
        if self.os_type == "windows":
            import tkinter as tk
            self.tk = tk
            self.gui_app = self.tk.Tk()
            self.gui_app.withdraw()
            self.screen_width = self.gui_app.winfo_screenwidth()
            self.screen_height = self.gui_app.winfo_screenheight()
        elif self.os_type == "linux":
            from PyQt5.QtWidgets import QApplication, QWidget
            from PyQt5.QtCore import Qt
            self.Qt = Qt
            self.QWidget = QWidget
            self.gui_app = QApplication(sys.argv)
            screen = self.gui_app.primaryScreen().size()
            self.screen_width = screen.width()
            self.screen_height = screen.height()
    
    def cleanup(self):
        """Clean up all resources"""
        print("[System] Cleaning up sockets and resources...")
        
        try:
            if self.client_socket:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
            if self.secondary_client_socket:
                self.secondary_client_socket.shutdown(socket.SHUT_RDWR)
                self.secondary_client_socket.close()
        except Exception as e:
            print(f"[Client] Error closing socket: {e}")
        
        try:
            if self.server_socket:
                self.server_socket.close()
            if self.secondary_server_socket:
                self.secondary_server_socket.close()
        except Exception as e:
            print(f"[Server] Error closing socket: {e}")
        
        if self.overlay:
            self.destroy_overlay()
        
        app_config.is_running = False
        app_config.save()
    
    def create_overlay(self):
        """Create invisible overlay window"""
        if not app_config.active_device:
            return
        
        if self.os_type == "windows":
            overlay = self.tk.Toplevel(self.gui_app)
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            overlay.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
            overlay.attributes("-alpha", 0.01)
            overlay.configure(bg="black")
            overlay.config(cursor="none")
            overlay.lift()
            overlay.focus_force()
            overlay.update_idletasks()
            self.overlay = overlay
        elif self.os_type == "linux":
            overlay = self.QWidget()
            overlay.setWindowFlags(self.Qt.FramelessWindowHint | self.Qt.WindowStaysOnTopHint | self.Qt.Tool)
            overlay.setAttribute(self.Qt.WA_TranslucentBackground)
            overlay.setCursor(self.Qt.BlankCursor)
            overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
            overlay.setWindowOpacity(0.0)
            overlay.show()
            overlay.raise_()
            self.overlay = overlay
    
    def destroy_overlay(self):
        """Destroy overlay window"""
        if self.overlay:
            if self.os_type == "windows":
                self.overlay.destroy()
            elif self.os_type == "linux":
                self.overlay.close()
            self.overlay = None
    
    def monitor_mouse_edges(self):
        """Monitor mouse edges for transitions"""
        margin = 2
        
        while app_config.is_running:
            # If input sharing is disabled, ensure inactive and skip transitions
            if not getattr(app_config, 'input_sharing_enabled', True):
                if app_config.active_device:
                    self.transition(False, self.mouse_controller.position)
                time.sleep(0.05)
                continue
            x, y = self.mouse_controller.position
            
            if not app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x >= self.screen_width - margin:
                    self.transition(True, (margin, y))
                elif app_config.server_direction == "Left" and x <= margin:
                    self.transition(True, (self.screen_width - margin, y))
                elif app_config.server_direction == "Top" and y <= margin:
                    self.transition(True, (x, self.screen_height - margin))
                elif app_config.server_direction == "Bottom" and y >= self.screen_height - margin:
                    self.transition(True, (x, margin))
            
            elif app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x <= margin:
                    self.transition(False, (self.screen_width - margin, y))
                elif app_config.server_direction == "Left" and x >= self.screen_width - margin:
                    self.transition(False, (margin, y))
                elif app_config.server_direction == "Top" and y >= self.screen_height - margin:
                    self.transition(False, (x, margin))
                elif app_config.server_direction == "Bottom" and y <= margin:
                    self.transition(False, (x, self.screen_height - margin))
            
            # Cooldown reset
            if margin < x < self.screen_width - margin and margin < y < self.screen_height - margin:
                self.edge_transition_cooldown = False
            
            time.sleep(0.01)
    
    def transition(self, to_active, new_position):
        """Handle device transition"""
        app_config.load()
        if to_active and not getattr(app_config, 'input_sharing_enabled', True):
            return
        app_config.active_device = to_active
        self.edge_transition_cooldown = True
        
        if self.os_type == "windows":
            self.gui_app.after_idle(self.create_overlay if to_active else self.destroy_overlay)
            self.mouse_controller.position = new_position
        else:
            if to_active:
                self.create_overlay()
            else:
                self.destroy_overlay()
            self.mouse_controller.position = new_position
        
        # Notify client of transition
        if hasattr(self, 'secondary_server') and self.secondary_server:
            try:
                active_msg = {"type": "active_device", "value": to_active}
                self.secondary_server.sendall((json.dumps(active_msg) + "\n").encode())
            except Exception as e:
                print(f"[Transition] Failed to send active_device state: {e}")
        
        # Send clipboard on transition to active (server to client)
        if to_active:
            current_clip = self.clipboard_controller.get_clipboard()
            if self.last_send != current_clip:
                self.last_send = current_clip
                if hasattr(self, 'secondary_server') and self.secondary_server:
                    self.clipboard_sender(self.secondary_server)
        
        # Also send clipboard when transitioning FROM active to inactive (bidirectional sync)
        if not to_active and app_config.mode == "server":
            current_clip = self.clipboard_controller.get_clipboard()
            if self.last_send != current_clip:
                self.last_send = current_clip
                if hasattr(self, 'secondary_server') and self.secondary_server:
                    self.clipboard_sender(self.secondary_server)
        
        print(f"[System] Device {'Activated' if to_active else 'Deactivated'} at {new_position}")
        logging.info(f"[System] Device {'Activated' if to_active else 'Deactivated'} at {new_position}")
        app_config.save()
        time.sleep(0.2)

    def start_hotkey_listener(self):
        """Start a global listener for the user-defined sharing hotkey.
        The hotkey toggles app_config.input_sharing_enabled instantly."""
        from pynput import keyboard as kb

        pressed_mods = set()
        last_key = [None]

        def parse_config_hotkey():
            app_config.load()
            hot = getattr(app_config, 'sharing_hotkey', '') or ''
            parts = [p.strip() for p in hot.split('+') if p.strip()]
            mods = set()
            key = None
            for p in parts:
                up = p.upper()
                if up in ("CTRL", "CONTROL"):
                    mods.add('control')
                elif up in ("ALT", "OPTION"):
                    mods.add('alt')
                elif up in ("SHIFT",):
                    mods.add('shift')
                elif up in ("SUPER", "WIN", "META"):
                    mods.add('super')
                else:
                    key = p.lower()
            return mods, key

        def current_matches(target_mods, target_key):
            if not target_mods and not target_key:
                return False
            if not target_key:
                return False
            if last_key[0] is None:
                return False
            return (target_mods.issubset(pressed_mods) and str(last_key[0]).lower() == target_key)

        def toggle_input_sharing():
            """Instant toggle and immediate transition reset"""
            enabled = getattr(app_config, 'input_sharing_enabled', True)
            app_config.input_sharing_enabled = not enabled
            app_config.save()

            # Force immediate deactivation if turning off
            if not app_config.input_sharing_enabled and app_config.active_device:
                self.transition(False, self.mouse_controller.position)

            # Reset cooldown and edge detection so it works instantly when toggled back on
            self.edge_transition_cooldown = False

            print(f"[Hotkey] Input sharing toggled → {app_config.input_sharing_enabled}")
            logging.info(f"[Hotkey] Input sharing toggled : {app_config.input_sharing_enabled}")

        def on_press(key):
            try:
                if isinstance(key, kb.Key):
                    name = str(key).lower()
                    if "shift" in name:
                        pressed_mods.add('shift')
                    elif "ctrl" in name:
                        pressed_mods.add('control')
                    elif "alt" in name:
                        pressed_mods.add('alt')
                    elif "cmd" in name or "win" in name or "super" in name:
                        pressed_mods.add('super')
                else:
                    last_key[0] = getattr(key, 'char', None) or str(key).replace('Key.', '')
        
                # Check for match instantly
                target_mods, target_key = parse_config_hotkey()
                if current_matches(target_mods, target_key):
                    toggle_input_sharing()
        
            except Exception as e:
                print(f"[Hotkey ERROR] {e}")
        

        def on_release(key):
            try:
                if isinstance(key, kb.Key):
                    if key in (kb.Key.shift, kb.Key.shift_l, kb.Key.shift_r):
                        pressed_mods.discard('shift')
                    elif key in (kb.Key.ctrl, kb.Key.ctrl_l, kb.Key.ctrl_r):
                        pressed_mods.discard('control')
                    elif key in (kb.Key.alt, kb.Key.alt_l, kb.Key.alt_r):
                        pressed_mods.discard('alt')
                    elif key in (kb.Key.cmd, kb.Key.cmd_l, kb.Key.cmd_r, kb.Key.windows):
                        pressed_mods.discard('super')
                else:
                    last_key[0] = None
            except Exception:
                pass

        listener = kb.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()

    def clipboard_sender(self, socket):
        """Send clipboard data"""
        current_clip = self.clipboard_controller.get_clipboard()
        try:
            data = {"type": "clipboard", "content": current_clip}
            socket.sendall((json.dumps(data) + "\n").encode())
            print("[Clipboard] Sent clipboard data")
            logging.info("[Clipboard] Sent clipboard data")
        except Exception as e:
            print(f"[Clipboard] Error: {e}")
            logging.info(f"[Clipboard] Error: {e}")
    
    def send_mouse_events(self, socket):
        """Send mouse events from server"""
        def send_json(data):
            try:
                socket.sendall((json.dumps(data) + "\n").encode())
            except Exception as e:
                app_config.is_running = False
                app_config.save()
                print(f"[Server] Send failed: {e}")
        
        def on_move(x, y):
            if not app_config.active_device:
                return
            norm_x = x / self.screen_width
            norm_y = y / self.screen_height
            send_json({"type": "move", "x": norm_x, "y": norm_y})
        
        def on_click(x, y, button, pressed):
            if not app_config.active_device:
                return
            send_json({"type": "click", "button": button.name, "pressed": pressed})
        
        def on_scroll(x, y, dx, dy):
            if not app_config.active_device:
                return
            send_json({"type": "scroll", "dx": dx, "dy": dy})
        
        mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll).start()
    
    def send_keyboard_events(self, socket):
        """Send keyboard events from server"""
        def send_json(data):
            try:
                socket.sendall((json.dumps(data) + "\n").encode())
            except Exception as e:
                app_config.is_running = False
                app_config.save()
                print(f"[Server] Send failed: {e}")
        
        def on_press(key):
            if not app_config.active_device:
                return
            try:
                # Always try to get the character representation
                if hasattr(key, 'char') and key.char is not None:
                    key_char = key.char
                    # Send character directly
                    send_json({"type": "key_press", "key": key_char})
                elif hasattr(key, 'name'):
                    # For special keys without char attribute
                    send_json({"type": "key_press", "key": str(key)})
                else:
                    send_json({"type": "key_press", "key": str(key)})
            except Exception as e:
                print(f"[Keyboard] Error sending key press: {e}")
                send_json({"type": "key_press", "key": str(key)})
        
        def on_release(key):
            if not app_config.active_device:
                return
            try:
                send_json({"type": "key_release", "key": key.char})
            except AttributeError:
                send_json({"type": "key_release", "key": str(key)})
        
        def keyboard_listener_watcher():
            while app_config.is_running:
                with self.keyboard_listener_lock:
                    if app_config.active_device and self.keyboard_listener is None:
                        self.keyboard_listener = keyboard.Listener(
                            on_press=on_press, on_release=on_release, suppress=True
                        )
                        self.keyboard_listener.start()
                    elif not app_config.active_device and self.keyboard_listener is not None:
                        self.keyboard_listener.stop()
                        self.keyboard_listener = None
                time.sleep(0.5)
        
        threading.Thread(target=keyboard_listener_watcher, daemon=True).start()
    
    # Server functions
    def start_server(self):
        """Start server mode"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.primary_port))
        self.server_socket.listen(1)
        
        self.secondary_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.secondary_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.secondary_server_socket.bind(("0.0.0.0", self.secondary_port))
        self.secondary_server_socket.listen(1)
        
        print("[Server] Waiting for Client to connect")
        logging.info("[Server] Waiting for Client to connect")
        
        threading.Thread(target=self.accept_primary, daemon=True).start()
        threading.Thread(target=self.accept_secondary, daemon=True).start()
    
    def accept_primary(self):
        """Accept primary connection (mouse)"""
        client, addr = self.server_socket.accept()
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"[Server] Primary connection from: {addr}")
        logging.info(f"[Connection] Primary connection from: {addr}")
        client.sendall(b'CONNECTED\n')
        print("[Server] Primary handshake sent")
        logging.info("[Connection] Primary handshake sent")
        threading.Thread(target=self.monitor_mouse_edges, daemon=True).start()
        threading.Thread(target=lambda: self.send_mouse_events(client), daemon=True).start()
    
    def accept_secondary(self):
        """Accept secondary connection (keyboard, clipboard)"""
        sec_socket, sec_addr = self.secondary_server_socket.accept()
        sec_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"[Server] Secondary connection from: {sec_addr}")
        logging.info(f"[Connection] Secondary connection from: {sec_addr}")
        self.secondary_server = sec_socket
        threading.Thread(target=lambda: self.send_keyboard_events(sec_socket), daemon=True).start()
        print("[Server] Secondary ready for keyboard/clipboard")
        logging.info("[Connection] Secondary ready for keyboard/clipboard")
        
        # Read clipboard from client
        def read_clipboard():
            buffer = ""
            while app_config.is_running:
                try:
                    data = self.secondary_server.recv(1024).decode()
                    if not data:
                        break
                    
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        try:
                            evt = json.loads(line)
                            if evt["type"] == "clipboard":
                                local_clip = self.clipboard_controller.get_clipboard()
                                if evt["content"] != local_clip:
                                    self.clipboard_controller.set_clipboard(evt["content"])
                                    self.last_send = evt["content"]
                        except json.JSONDecodeError:
                            pass
                except Exception as e:
                    print(f"[Clipboard] Error: {e}")
                    break
        
        threading.Thread(target=read_clipboard, daemon=True).start()
    
    # Client functions
    def start_client(self):
        """Start client mode"""
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        self.secondary_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.secondary_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        # Connect primary
        for i in range(10, -1, -1):
            try:
                self.client_socket.connect((app_config.server_ip, self.primary_port))
                if self.client_socket.recv(1024) != b'CONNECTED\n':
                    raise Exception("Handshake failed")
                break
            except Exception as e:
                print(f"Retrying connection (primary) Attempt: {i}")
                if i == 0:
                    print(f"[Client] Connection failed: {e}")
                    app_config.is_running = False
                    self.cleanup()
                    return
                time.sleep(1)
        
        print("[Client] Primary Connected")
        logging.info("[Connection] Primary Connected")
        
        # Connect secondary
        for i in range(10, -1, -1):
            try:
                self.secondary_client_socket.connect((app_config.server_ip, self.secondary_port))
                break
            except Exception as e:
                if i == 0:
                    print(f"[Client] Connection failed: {e}")
                    app_config.is_running = False
                    self.cleanup()
                    return
                time.sleep(1)
        
        print("[Client] Secondary Connected")
        logging.info("[Connection] Secondary Connected")
        
        threading.Thread(target=self.receive_primary, daemon=True).start()
        threading.Thread(target=self.receive_secondary, daemon=True).start()
    
    def receive_primary(self):
        """Receive mouse events"""
        buffer = ""
        while app_config.is_running:
            try:
                data = self.client_socket.recv(1024).decode()
            except Exception:
                break
            
            if not data:
                break
            
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                try:
                    evt = json.loads(line)
                    if evt["type"] == "move":
                        x = int(evt["x"] * self.screen_width)
                        y = int(evt["y"] * self.screen_height)
                        self.mouse_controller.position = (x, y)
                    elif evt["type"] == "click":
                        btn = getattr(Button, evt['button'])
                        if evt['pressed']:
                            self.mouse_controller.press(btn)
                        else:
                            self.mouse_controller.release(btn)
                    elif evt["type"] == "scroll":
                        self.mouse_controller.scroll(evt['dx'], evt['dy'])
                except Exception as e:
                    print(f"[Client] Parse error: {e}")
                    logging.info(f"[Client] Parse error: {e}")
                    logging.info(f"[Client] Parse error: {e}")
    
    def receive_secondary(self):
        """Receive keyboard events and clipboard"""
        def parse_key(key_str):
            if key_str.startswith("Key."):
                from pynput.keyboard import Key
                try:
                    return getattr(Key, key_str.split(".", 1)[1])
                except AttributeError:
                    return None
            return key_str
        
        buffer = ""
        while app_config.is_running:
            try:
                data = self.secondary_client_socket.recv(1024).decode()
            except Exception:
                break
            
            if not data:
                break
            
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                try:
                    evt = json.loads(line)
                    if evt["type"] == "key_press":
                        key_str = evt["key"]
                        if isinstance(key_str, str):
                            if key_str.startswith("Key."):
                                # Special key like Key.enter, Key.shift, etc.
                                key = parse_key(key_str)
                                if key:
                                    self.keyboard_controller.press(key)
                            else:
                                # Regular character - use tap for better compatibility in secure contexts
                                self.keyboard_controller.tap(key_str)
                        else:
                            self.keyboard_controller.press(key_str)
                    elif evt["type"] == "key_release":
                        key_str = evt["key"]
                        if isinstance(key_str, str):
                            if key_str.startswith("Key."):
                                # Special key
                                key = parse_key(key_str)
                                if key:
                                    self.keyboard_controller.release(key)
                            # Regular characters don't need explicit release when using tap
                        else:
                            self.keyboard_controller.release(key_str)
                    elif evt["type"] == "active_device":
                        app_config.active_device = evt["value"]
                        app_config.save()
                        if not app_config.active_device:
                            current_clip = self.clipboard_controller.get_clipboard()
                            if self.last_send != current_clip:
                                self.last_send = current_clip
                                self.clipboard_sender(self.secondary_client_socket)
                    elif evt["type"] == "clipboard":
                        current_clip = self.clipboard_controller.get_clipboard()
                        if current_clip != evt["content"]:
                            self.clipboard_controller.set_clipboard(evt["content"])
                            self.last_send = evt["content"]
                            print("[Clipboard] Updated")
                except Exception as e:
                    print(f"[Client] Parse error: {e}")
    
    def run(self):
        """Run the share manager"""
        app_config.is_running = True
        
        if app_config.mode == "server":
            self.start_server()
        else:
            self.start_client()
        
        def monitor_stop():
            while app_config.is_running and not app_config.stop_flag:
                time.sleep(0.5)
            self.cleanup()
            if self.gui_app:
                if self.os_type == "windows":
                    self.gui_app.quit()
                else:
                    self.gui_app.quit()
        
        threading.Thread(target=monitor_stop, daemon=True).start()
        
        if self.os_type == "windows":
            self.gui_app.mainloop()
        else:
            self.gui_app.exec_()


if __name__ == "__main__":
    ShareManager().run()

