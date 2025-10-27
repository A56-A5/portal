"""
Input Handler - Handles sending and receiving input events (mouse, keyboard)
"""
import json
import logging
import threading
import time
from pynput import mouse, keyboard
from pynput.mouse import Button
from utils.config import app_config


class InputHandler:
    def __init__(self, connection_handler):
        self.connection_handler = connection_handler
        self.keyboard_listener = None
        self.keyboard_listener_lock = threading.Lock()
        logging.basicConfig(
            level=logging.INFO,
            filename="logs.log",
            filemode="a",
            format="%(levelname)s - %(message)s"
        )
    
    def send_json(self, data, socket):
        """Send JSON data over socket"""
        try:
            socket.sendall((json.dumps(data) + "\n").encode())
        except Exception as e:
            app_config.is_running = False
            app_config.save()
            print(f"[Server] Send failed: {e}")
            logging.info(f"[Server] Send failed: {e}")
    
    def start_mouse_sender(self, client_socket):
        """Start sending mouse events"""
        def on_move(x, y):
            if not app_config.active_device and app_config.is_running:
                return
            norm_x = x / self.connection_handler.screen_width
            norm_y = y / self.connection_handler.screen_height
            self.send_json({"type": "move", "x": norm_x, "y": norm_y}, client_socket)
        
        def on_click(x, y, button, pressed):
            if not app_config.active_device:
                return
            self.send_json({"type": "click", "button": button.name, "pressed": pressed}, client_socket)
        
        def on_scroll(x, y, dx, dy):
            if not app_config.active_device:
                return
            self.send_json({"type": "scroll", "dx": dx, "dy": dy}, client_socket)
        
        mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll).start()
    
    def start_keyboard_sender(self, client_socket):
        """Start sending keyboard events"""
        def on_press(key):
            if not app_config.active_device:
                return
            try:
                self.send_json({"type": "key_press", "key": key.char}, client_socket)
            except AttributeError:
                self.send_json({"type": "key_press", "key": str(key)}, client_socket)
        
        def on_release(key):
            if not app_config.active_device:
                return
            try:
                self.send_json({"type": "key_release", "key": key.char}, client_socket)
            except AttributeError:
                self.send_json({"type": "key_release", "key": str(key)}, client_socket)
        
        # Keyboard listener handler thread
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
    
    def handle_primary_events(self, client_socket):
        """Handle primary connection events (mouse)"""
        threading.Thread(
            target=self.connection_handler.monitor_mouse_edges,
            args=(client_socket,),
            daemon=True
        ).start()
        threading.Thread(
            target=self.start_mouse_sender,
            args=(client_socket,),
            daemon=True
        ).start()
    
    def handle_secondary_events(self, client_socket):
        """Handle secondary connection events (keyboard)"""
        threading.Thread(
            target=self.start_keyboard_sender,
            args=(client_socket,),
            daemon=True
        ).start()
    
    def parse_and_execute_mouse_event(self, event, mouse_controller):
        """Parse and execute mouse event from client"""
        from pynput.mouse import Button
        import win32api
        
        event_type = event.get("type")
        
        if event_type == "move":
            x = int(event["x"] * self.connection_handler.screen_width)
            y = int(event["y"] * self.connection_handler.screen_height)
            new_position = (x, y)
            try:
                win32api.SetCursorPos(new_position)
            except (NameError, ImportError):
                mouse_controller.position = new_position
        
        elif event_type == "click":
            btn = getattr(Button, event['button'])
            if event['pressed']:
                mouse_controller.press(btn)
            else:
                mouse_controller.release(btn)
        
        elif event_type == "scroll":
            mouse_controller.scroll(event['dx'], event['dy'])
    
    def parse_and_execute_keyboard_event(self, event, keyboard_controller, secondary_socket, clipboard_controller):
        """Parse and execute keyboard event from client"""
        from pynput.keyboard import Key
        
        event_type = event.get("type")
        
        if event_type == "key_press":
            key = self.parse_key(event["key"])
            if key:
                keyboard_controller.press(key)
        
        elif event_type == "key_release":
            key = self.parse_key(event["key"])
            if key:
                keyboard_controller.release(key)
        
        elif event_type == "active_device":
            app_config.active_device = event["value"]
            app_config.save()
            if not app_config.active_device:
                current_clip = clipboard_controller.get_clipboard()
                if self.connection_handler.last_send != current_clip:
                    self.connection_handler.last_send = current_clip
                    self.connection_handler.clipboard_sender(secondary_socket, current_clip)
        
        elif event_type == "clipboard":
            current_clip = clipboard_controller.get_clipboard()
            if current_clip != event["content"]:
                app_config.clipboard = event["content"]
                clipboard_controller.set_clipboard(event["content"])
                self.connection_handler.last_send = event["content"]
                app_config.save()
                print("[Clipboard] Updated clipboard content")
                logging.info("[Clipboard] Updated.")
    
    def parse_key(self, key_str):
        """Parse key string to Key object"""
        from pynput.keyboard import Key
        
        if key_str.startswith("Key."):
            try:
                return getattr(Key, key_str.split(".", 1)[1])
            except AttributeError:
                print(f"[Parse] Unknown special key: {key_str}")
                return None
        return key_str

