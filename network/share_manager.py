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
import base64
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
        self.last_transition_time = 0
        self._transition_lock = threading.Lock()
        self.primary_port = app_config.server_primary_port
        self.secondary_port = app_config.server_secondary_port
        self.tertiary_port = app_config.server_tertiary_port
        
        # Controllers
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.clipboard_controller = ClipboardController()
        
        # Network sockets
        self.server_socket = None
        self.client_socket = None
        self.secondary_server_socket = None
        self.secondary_client_socket = None
        self.tertiary_server_socket = None
        self.tertiary_client_socket = None
        self.secondary_server = None
        self.tertiary_server = None
        self.tertiary_connected = False
        
        # Overlay
        self.overlay = None
        self.screen_width = None
        self.screen_height = None
        self.gui_app = None
        self.last_send = None
        
        # Listeners
        self.keyboard_listener = None
        self.keyboard_listener_lock = threading.Lock()
        self.gtk_overlay_thread = None
        self.keyboard_socket = None
        
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
            # Get full virtual desktop size (all monitors)
            desktop = self.gui_app.desktop()
            geom = desktop.geometry()
            self.screen_width = geom.width()
            self.screen_height = geom.height()
    
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
            if self.tertiary_client_socket:
                self.tertiary_client_socket.shutdown(socket.SHUT_RDWR)
                self.tertiary_client_socket.close()
        except Exception as e:
            print(f"[Client] Error closing socket: {e}")
        
        try:
            if self.server_socket:
                self.server_socket.close()
            if self.secondary_server_socket:
                self.secondary_server_socket.close()
            if self.tertiary_server_socket:
                self.tertiary_server_socket.close()
        except Exception as e:
            print(f"[Server] Error closing socket: {e}")
        
        if self.overlay:
            self.destroy_overlay()
        
        app_config.is_running = False
        app_config.save()
    
    def create_overlay(self):
        """Create invisible overlay window. Call via _schedule_overlay only."""
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
            # Standard Frameless + TopMost. Removed Qt.Tool as it can make windows click-through.
            overlay.setWindowFlags(self.Qt.FramelessWindowHint | self.Qt.WindowStaysOnTopHint)
            # Use stylesheet for transparency instead of WA_TranslucentBackground 
            # (which can be unreliable for input blocking)
            overlay.setStyleSheet("background-color: rgba(0, 0, 0, 1);") # Almost 0 alpha but solid to mouse
            overlay.setCursor(self.Qt.BlankCursor)
            overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
            overlay.show()
            overlay.raise_()
            overlay.activateWindow()
            self.overlay = overlay
    
    def destroy_overlay(self):
        """Destroy overlay window (must be called from the GUI main thread)."""
        if self.overlay:
            if self.os_type == "windows":
                self.overlay.destroy()
            elif self.os_type == "linux":
                self.overlay.close()
            self.overlay = None

    def _schedule_overlay(self, to_active):
        """Schedule overlay creation/destruction."""
        if self.os_type == "windows":
            if self.gui_app:
                self.gui_app.after_idle(lambda: self.create_overlay() if to_active else self.destroy_overlay())
        elif self.os_type == "linux":
            if to_active:
                # Start GTK overlay in a separate thread
                if self.gtk_overlay_thread is None or not self.gtk_overlay_thread.is_alive():
                    self.gtk_overlay_thread = threading.Thread(target=self.create_gtk_overlay, daemon=True)
                    self.gtk_overlay_thread.start()
            else:
                self.destroy_gtk_overlay()
    
    def create_gtk_overlay(self):
        """Native GTK3 Overlay for Linux (Ubuntu Native)"""
        try:
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk, Gdk
            import cairo

            # POPUP type bypasses window managers and grabs top-level priority
            self.overlay = Gtk.Window(type=Gtk.WindowType.POPUP)
            self.overlay.set_keep_above(True)
            self.overlay.set_accept_focus(False) # CRITICAL: Don't steal focus from pynput
            
            # Full screen coverage
            self.overlay.set_default_size(self.screen_width, self.screen_height)
            self.overlay.move(0, 0)

            # Transparency logic
            screen = self.overlay.get_screen()
            visual = screen.get_rgba_visual()
            if visual:
                self.overlay.set_visual(visual)
            
            self.overlay.set_app_paintable(True)
            def on_draw(w, cr):
                cr.set_source_rgba(0, 0, 0, 0.01) # Invisible but solid to clicks
                cr.set_operator(cairo.OPERATOR_SOURCE)
                cr.paint()
                return False
            self.overlay.connect("draw", on_draw)

            # Show and set blank cursor
            self.overlay.show_all()
            
            # Use X11/Wayland cursor hide
            win = self.overlay.get_window()
            if win:
                cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.BLANK_CURSOR)
                win.set_cursor(cursor)

            Gtk.main()
        except Exception as e:
            print(f"[GTK Overlay] Error: {e}")

    def destroy_gtk_overlay(self):
        """Stop GTK overlay"""
        try:
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            Gtk.main_quit()
            if self.overlay:
                self.overlay.destroy()
                self.overlay = None
        except: pass
    
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
            warp_buffer = 50 
            grace_period = 0.2 # Snappy but prevents velocity bounces
            
            # Skip if we just transitioned (hard bounce protection)
            if time.time() - self.last_transition_time < grace_period:
                time.sleep(0.01)
                continue

            if not app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x >= self.screen_width - margin:
                    self.transition(True, (margin + warp_buffer, y))
                    continue
                elif app_config.server_direction == "Left" and x <= margin:
                    self.transition(True, (self.screen_width - margin - warp_buffer, y))
                    continue
                elif app_config.server_direction == "Top" and y <= margin:
                    self.transition(True, (x, self.screen_height - margin - warp_buffer))
                    continue
                elif app_config.server_direction == "Bottom" and y >= self.screen_height - margin:
                    self.transition(True, (x, margin + warp_buffer))
                    continue
            
            elif app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x <= margin:
                    self.transition(False, (self.screen_width - margin - warp_buffer, y))
                    continue
                elif app_config.server_direction == "Left" and x >= self.screen_width - margin:
                    self.transition(False, (margin + warp_buffer, y))
                    continue
                elif app_config.server_direction == "Top" and y >= self.screen_height - margin:
                    self.transition(False, (x, margin + warp_buffer))
                    continue
                elif app_config.server_direction == "Bottom" and y <= margin:
                    self.transition(False, (x, self.screen_height - margin - warp_buffer))
                    continue
            
            # Cooldown reset — Clear when cursor moves away from the trigger axis.
            if not self._transition_lock.locked():
                reset_needed = False
                if app_config.server_direction in ("Right", "Left"):
                    # Only care about X axis for horizontal setups
                    if margin + 5 < x < self.screen_width - margin - 5:
                        reset_needed = True
                else:
                    # Only care about Y axis for vertical setups
                    if margin + 5 < y < self.screen_height - margin - 5:
                        reset_needed = True
                
                if reset_needed:
                    self.edge_transition_cooldown = False

            time.sleep(0.01)
    
    def transition(self, to_active, new_position):
        """Handle device transition.

        Guards against rapid back-and-forth triggering with a mutex so
        only one transition can run at a time.  The disk reload that used
        to sit at the top of this method has been removed: reading
        config.json here would overwrite in-memory state with whatever the
        client process last wrote, corrupting the server's view of
        active_device mid-transition.
        """
        # Block until any in-progress transition finishes, then run.
        # Using blocking=True so transitions queue up rather than being silently
        # dropped — dropping caused the server to get stuck in the wrong state.
        self._transition_lock.acquire(blocking=True)
        try:
            # Set cooldown and grace period IMMEDIATELY
            self.edge_transition_cooldown = True
            self.last_transition_time = time.time()

            # Re-check sharing gate
            if to_active and not getattr(app_config, 'input_sharing_enabled', True):
                return

            # PRIORITY 1: Instant Keyboard Suppression (Before anything else)
            with self.keyboard_listener_lock:
                if self.keyboard_listener:
                    try: self.keyboard_listener.stop()
                    except: pass
                    self.keyboard_listener = None
                    time.sleep(0.05) # Give X11 a moment to release the grab
                
                if to_active:
                    from pynput import keyboard
                    self.keyboard_listener = keyboard.Listener(
                        on_press=self._on_press,
                        on_release=self._on_release,
                        suppress=True
                    )
                    self.keyboard_listener.start()

            # Deduplicate
            if app_config.active_device == to_active:
                return

            app_config.active_device = to_active
            app_config.save()

            self._schedule_overlay(to_active)
            self.mouse_controller.position = new_position

            def send_active_state():
                if hasattr(self, 'secondary_server') and self.secondary_server:
                    try:
                        active_msg = {"type": "active_device", "value": to_active}
                        self.secondary_server.sendall((json.dumps(active_msg) + "\n").encode())
                    except Exception as e:
                        print(f"[Transition] Failed to send active_device state: {e}")
            
            # Run network send in background so the local mouse warp is instant and non-blocking
            threading.Thread(target=send_active_state, daemon=True).start()

            clip_socket = None
            if hasattr(self, 'tertiary_connected') and self.tertiary_connected:
                if app_config.mode == "server":
                    clip_socket = self.tertiary_server
                else:
                    clip_socket = self.tertiary_client_socket

            if not clip_socket:
                if app_config.mode == "server":
                    clip_socket = self.secondary_server
                else:
                    clip_socket = self.secondary_client_socket

            logging.info(f"[Clipboard] Using socket: {'Tertiary' if 'tertiary' in str(clip_socket) else 'Secondary'}")

            if clip_socket:
                current_clip = self.clipboard_controller.get_clipboard()
                if self.last_send != current_clip:
                    self.last_send = current_clip
                    self.clipboard_sender(clip_socket, current_clip)

            logging.info(f"[System] Device {'Activated' if to_active else 'Deactivated'} at {new_position}")
            app_config.save()
            time.sleep(0.2)
        finally:
            self._transition_lock.release()

    def start_hotkey_listener(self):
        """Start a global listener for the user-defined sharing hotkey.
        The hotkey toggles app_config.input_sharing_enabled instantly."""
        from pynput import keyboard as kb

        pressed_mods = set()
        last_key = [None]

        def parse_config_hotkey():
            # Do NOT call app_config.load() here — it runs on every keypress
            # and would overwrite active_device in memory with the stale disk
            # value, breaking transitions. The hotkey doesn't change at runtime.
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
                # Get the actual character or name
                if hasattr(key, 'char') and key.char:
                    k = key.char.lower()
                elif hasattr(key, 'name'):
                    k = key.name.lower()
                else:
                    k = str(key).lower()
                
                # Check modifiers
                if 'shift' in k:
                    pressed_mods.add('shift')
                elif 'ctrl' in k or 'control' in k:
                    pressed_mods.add('control')
                elif 'alt' in k or 'option' in k:
                    pressed_mods.add('alt')
                elif 'cmd' in k or 'win' in k or 'super' in k:
                    pressed_mods.add('super')
                else:
                    last_key[0] = k
                    
                target_mods, target_key = parse_config_hotkey()
                if current_matches(target_mods, target_key):
                    toggle_input_sharing()
                    # Clear last_key to prevent double trigger
                    last_key[0] = None
            except Exception as e:
                pass
        

        def on_release(key):
            try:
                if hasattr(key, 'char') and key.char:
                    k = key.char.lower()
                elif hasattr(key, 'name'):
                    k = key.name.lower()
                else:
                    k = str(key).lower()

                if 'shift' in k:
                    pressed_mods.discard('shift')
                elif 'ctrl' in k or 'control' in k:
                    pressed_mods.discard('control')
                elif 'alt' in k or 'option' in k:
                    pressed_mods.discard('alt')
                elif 'cmd' in k or 'win' in k or 'super' in k:
                    pressed_mods.discard('super')
                
                if k == last_key[0]:
                    last_key[0] = None
            except Exception:
                pass

        listener = kb.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()

    def clipboard_sender(self, socket, clip_data=None):
        """Send clipboard data, handling large files and status notifications"""
        current_clip = clip_data if clip_data else self.clipboard_controller.get_clipboard()
        if not current_clip:
            return
            
        def perform_send():
            try:
                # Check for files
                if current_clip.startswith("files:"):
                    # Notify start
                    socket.sendall((json.dumps({"type": "status", "msg": "File transfer starting..."}) + "\n").encode())
                    
                    import shutil
                    paths = base64.b64decode(current_clip.split(":", 1)[1]).decode('utf-8').splitlines()
                    all_files_data = []
                    for p in paths:
                        p = p.strip()
                        if not os.path.exists(p): continue

                        if os.path.isfile(p):
                            try:
                                with open(p, "rb") as f:
                                    content = f.read()
                                    name = os.path.basename(p)
                                    encoded_content = base64.b64encode(content).decode('utf-8')
                                    all_files_data.append({"name": name, "data": encoded_content})
                            except Exception as e:
                                print(f"[Clipboard] Failed to read file {p}: {e}")
                        elif os.path.isdir(p):
                            try:
                                # Zip directory to temporary file
                                zip_name = os.path.basename(p) + ".zip"
                                socket.sendall((json.dumps({"type": "status", "msg": f"Zipping {zip_name}..."}) + "\n").encode())
                                
                                temp_zip = os.path.join(os.path.expanduser("~"), "Portal", "temp_" + zip_name)
                                os.makedirs(os.path.dirname(temp_zip), exist_ok=True)
                                
                                # Create zip
                                shutil.make_archive(temp_zip.replace(".zip", ""), 'zip', p)
                                
                                with open(temp_zip, "rb") as f:
                                    content = f.read()
                                    encoded_content = base64.b64encode(content).decode('utf-8')
                                    all_files_data.append({"name": zip_name, "data": encoded_content})
                                
                                # Cleanup
                                if os.path.exists(temp_zip):
                                    os.remove(temp_zip)
                            except Exception as e:
                                print(f"[Clipboard] Failed to zip directory {p}: {e}")
                    
                    if all_files_data:
                        data = {"type": "file_transfer", "files": all_files_data}
                        # Large data send
                        payload = (json.dumps(data) + "\n").encode()
                        socket.sendall(payload)
                        socket.sendall((json.dumps({"type": "status", "msg": "Files synced!"}) + "\n").encode())
                    return

                # Regular clipboard
                is_large = len(current_clip) > 100000 # 100KB+
                if is_large:
                    try:
                        socket.sendall((json.dumps({"type": "status", "msg": "Syncing large clipboard..."}) + "\n").encode())
                    except: pass

                data = {"type": "clipboard", "content": current_clip}
                try:
                    socket.sendall((json.dumps(data) + "\n").encode())
                    if is_large:
                        socket.sendall((json.dumps({"type": "status", "msg": "Clipboard synced!"}) + "\n").encode())
                    logging.info("[Clipboard] Sent clipboard data successfully")
                except Exception as e:
                    logging.error(f"[Clipboard] Send failed: {e}")
            except Exception as e:
                print(f"[Clipboard Threaded Send] Error: {e}")

        # Always run in a separate thread to prevent blocking transition thread/GUI
        threading.Thread(target=perform_send, daemon=True).start()
    
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
            btn_name = button.name if hasattr(button, 'name') else str(button)
            send_json({"type": "click", "button": btn_name, "pressed": pressed})
        
        def on_scroll(x, y, dx, dy):
            if not app_config.active_device:
                return
            send_json({"type": "scroll", "dx": dx, "dy": dy})
        
        mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll).start()
    
    def _on_press(self, key):
        if not app_config.active_device or not self.keyboard_socket:
            return
        try:
            if hasattr(key, 'char') and key.char is not None:
                val = key.char
            else:
                val = str(key)
            msg = json.dumps({"type": "key_press", "key": val}) + "\n"
            self.keyboard_socket.sendall(msg.encode())
        except: pass

    def _on_release(self, key):
        if not app_config.active_device or not self.keyboard_socket:
            return
        try:
            val = key.char if hasattr(key, 'char') and key.char else str(key)
            msg = json.dumps({"type": "key_release", "key": val}) + "\n"
            self.keyboard_socket.sendall(msg.encode())
        except: pass

    def send_keyboard_events(self, socket):
        """Save socket for the instant handlers"""
        self.keyboard_socket = socket
    
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

        self.tertiary_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tertiary_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tertiary_server_socket.bind(("0.0.0.0", self.tertiary_port))
        self.tertiary_server_socket.listen(1)
        
        print("[Server] Waiting for Client to connect")
        logging.info("[Server] Waiting for Client to connect")
        
        threading.Thread(target=self.accept_primary, daemon=True).start()
        threading.Thread(target=self.accept_secondary, daemon=True).start()
        threading.Thread(target=self.accept_tertiary, daemon=True).start()
    
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
        sec_socket.settimeout(1.0) # Prevent transition hangs
        print(f"[Server] Secondary connection from: {sec_addr}")
        logging.info(f"[Connection] Secondary connection from: {sec_addr}")
        self.secondary_server = sec_socket
        threading.Thread(target=lambda: self.send_keyboard_events(sec_socket), daemon=True).start()
        print("[Server] Secondary ready for keyboard/clipboard")
        logging.info("[Connection] Secondary ready for keyboard/clipboard")
        
        # Read clipboard from client
        def read_clipboard():
            buffer = b""
            while app_config.is_running:
                try:
                    data = self.secondary_server.recv(4096)
                    if not data:
                        break
                    
                    buffer += data
                    while b"\n" in buffer:
                        line_bytes, buffer = buffer.split(b"\n", 1)
                        try:
                            line = line_bytes.decode('utf-8')
                            self.handle_incoming_large_event(line, self.secondary_server)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[Clipboard] Error: {e}")
                    break
        
        threading.Thread(target=read_clipboard, daemon=True).start()

    def accept_tertiary(self):
        """Accept tertiary connection (large data)"""
        ter_socket, ter_addr = self.tertiary_server_socket.accept()
        ter_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ter_socket.settimeout(1.0) # Prevent transition hangs
        print(f"[Server] Tertiary connection from: {ter_addr}")
        self.tertiary_server = ter_socket
        self.tertiary_connected = True
        
        def read_large_data():
            buffer = b""
            while app_config.is_running:
                try:
                    data = self.tertiary_server.recv(16384)
                    if not data: break
                    buffer += data
                    while b"\n" in buffer:
                        line_bytes, buffer = buffer.split(b"\n", 1)
                        try:
                            line = line_bytes.decode('utf-8')
                            self.handle_incoming_large_event(line, self.tertiary_server)
                        except UnicodeDecodeError:
                            pass
                except Exception as e:
                    print(f"[Tertiary] Error: {e}")
                    break
        threading.Thread(target=read_large_data, daemon=True).start()

    def handle_incoming_large_event(self, line, socket_to_reply):
        try:
            evt = json.loads(line)
            if evt["type"] == "clipboard":
                local_clip = self.clipboard_controller.get_clipboard()
                if evt["content"] != local_clip:
                    self.clipboard_controller.set_clipboard(evt["content"])
                    self.last_send = evt["content"]
            elif evt["type"] == "file_transfer":
                self.handle_file_transfer(evt["files"])
            elif evt["type"] == "status":
                print(f"[Status] {evt['msg']}")
                # Trigger a system notification if possible, or just log
                logging.info(f"[Remote Status] {evt['msg']}")
        except Exception as e:
            print(f"[Event Handler] Error: {e}")

    def handle_file_transfer(self, files_list):
        """Handle incoming files from a transfer"""
        try:
            download_path = os.path.join(os.path.expanduser("~"), "Portal", "Downloads")
            
            # Clear existing files in Downloads folder before each new transfer
            if os.path.exists(download_path):
                import shutil
                try:
                    for filename in os.listdir(download_path):
                        file_path = os.path.join(download_path, filename)
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            print(f"[Cleanup] Failed to delete {file_path}: {e}")
                except Exception as e:
                    print(f"[Cleanup] Error clearing directory: {e}")

            os.makedirs(download_path, exist_ok=True)
            
            saved_paths = []
            for f in files_list:
                name = f["name"]
                content = base64.b64decode(f["data"])
                target = os.path.join(download_path, name)
                
                # Handle duplicates
                base, ext = os.path.splitext(target)
                counter = 1
                while os.path.exists(target):
                    target = f"{base}_{counter}{ext}"
                    counter += 1
                
                with open(target, "wb") as out:
                    out.write(content)
                saved_paths.append(target)
            
            if saved_paths:
                # Set clipboard to the newly saved local paths
                encoded = base64.b64encode("\n".join(saved_paths).encode('utf-8')).decode('utf-8')
                self.clipboard_controller.set_clipboard(f"files:{encoded}")
                self.last_send = f"files:{encoded}"
                msg = f"Received {len(saved_paths)} files to Portal/Downloads"
                print(f"[Files] {msg}")
                logging.info(f"[Remote Status] {msg}")
                
                # Notify the sender that we got the files
                socket_to_notify = self.tertiary_server if app_config.mode == "server" else self.tertiary_client_socket
                if not socket_to_notify:
                    socket_to_notify = self.secondary_server if app_config.mode == "server" else self.secondary_client_socket
                
                if socket_to_notify:
                    try:
                        socket_to_notify.sendall((json.dumps({"type": "status", "msg": f"Success: Target got {len(saved_paths)} files!"}) + "\n").encode())
                    except: pass
        except Exception as e:
            print(f"[Files] Receipt failed: {e}")
    
    # Client functions
    def start_client(self):
        """Start client mode"""
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        self.secondary_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.secondary_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self.tertiary_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tertiary_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
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

        # Connect tertiary
        for i in range(10, -1, -1):
            try:
                self.tertiary_client_socket.connect((app_config.server_ip, self.tertiary_port))
                break
            except Exception as e:
                if i == 0:
                    print(f"[Client] Tertiary connection failed: {e}")
                time.sleep(1)
        
        print("[Client] Tertiary Connected")
        self.tertiary_connected = True
        
        threading.Thread(target=self.receive_primary, daemon=True).start()
        threading.Thread(target=self.receive_secondary, daemon=True).start()
        threading.Thread(target=self.receive_tertiary, daemon=True).start()
    
    def receive_primary(self):
        """Receive mouse events"""
        buffer = b""
        while app_config.is_running:
            try:
                data = self.client_socket.recv(4096)
            except Exception:
                break
            
            if not data:
                break
            
            buffer += data
            while b"\n" in buffer:
                line_bytes, buffer = buffer.split(b"\n", 1)
                try:
                    line = line_bytes.decode('utf-8')
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
                    pass # Noise
    
    def receive_secondary(self):
        """Receive keyboard events and clipboard"""
        def parse_key(key_str):
            if key_str.startswith("Key."):
                from pynput.keyboard import Key
                try:
                    # Extract key name and convert to lowercase (pynput Key attributes are lowercase)
                    key_name = key_str.split(".", 1)[1].lower()
                    return getattr(Key, key_name)
                except AttributeError:
                    # If direct lookup fails, return the normalized string and let KeyboardController handle it
                    return key_str.split(".", 1)[1].lower()
            # For regular characters, preserve case (single char) or normalize special strings
            if isinstance(key_str, str):
                if len(key_str) == 1:
                    return key_str  # Preserve case for single characters
                return key_str.lower()  # Normalize multi-character strings to lowercase
            return key_str
        
        buffer = b""
        while app_config.is_running:
            try:
                data = self.secondary_client_socket.recv(4096)
            except Exception:
                break
            
            if not data:
                break
            
            buffer += data
            while b"\n" in buffer:
                line_bytes, buffer = buffer.split(b"\n", 1)
                try:
                    line = line_bytes.decode('utf-8')
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
                        print(f"[Client] Active device state sync: {evt['value']}")
                        app_config.active_device = evt["value"]
                        app_config.save()
                        if not app_config.active_device:
                            current_clip = self.clipboard_controller.get_clipboard()
                            if self.last_send != current_clip:
                                self.last_send = current_clip
                                # Send large stuff over tertiary if available
                                target = self.tertiary_client_socket if self.tertiary_client_socket else self.secondary_client_socket
                                self.clipboard_sender(target, current_clip)
                    elif evt["type"] == "clipboard":
                        self.handle_incoming_large_event(line, self.secondary_client_socket)
                    elif evt["type"] == "status":
                        print(f"[Status] {evt['msg']}")
                        logging.info(f"[Remote Status] {evt['msg']}")
                    elif evt["type"] == "file_transfer":
                        self.handle_file_transfer(evt["files"])
                except Exception as e:
                    print(f"[Client] Parse error: {e}")

    def receive_tertiary(self):
        """Receive large data events (images, files)"""
        buffer = b""
        while app_config.is_running:
            try:
                data = self.tertiary_client_socket.recv(16384)
                if not data: break
                buffer += data
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    try:
                        line = line_bytes.decode('utf-8')
                        self.handle_incoming_large_event(line, self.tertiary_client_socket)
                    except UnicodeDecodeError:
                        pass
            except Exception:
                break
    
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

