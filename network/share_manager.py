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
            if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
                os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
            from PyQt5.QtWidgets import QApplication, QWidget
            from PyQt5.QtCore import Qt
            self.Qt = Qt
            self.QWidget = QWidget
            self.gui_app = QApplication(sys.argv)
            # Use primary screen only — the full virtual desktop spans all
            # monitors combined, which makes normalization wrong when server
            # and client have different multi-monitor layouts.
            primary = self.gui_app.primaryScreen()
            geom = primary.geometry()
            self.screen_width = geom.width()
            self.screen_height = geom.height()

            self._wayland = self._detect_wayland()
            self._compositor_available = self._detect_compositor()
            self._compositor_warned = False

            if self._wayland:
                msg = ("Wayland session detected - running with X11 compatibility layer for overlay & input sharing.")
                logging.info(f"[Remote Status] {msg}")
                print(f"[Session] {msg}")

    def _detect_wayland(self):
        return (
            os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
            or bool(os.environ.get("WAYLAND_DISPLAY"))
        )

    def _detect_compositor(self):
        """Best-effort check for a running X11 compositing manager.

        The overlay's "invisible but still blocks clicks" trick needs a
        compositor to actually blend a near-zero-alpha window with what's
        behind it; without one, X11 just renders it opaque, i.e. the
        screen appears to go solid black instead of invisible. That's not
        a crash, but it looks like one to a user - detecting it lets us
        pick an intentional, documented fallback color instead of an
        unpredictable one, and warn once instead of confusing anyone.
        Defaults to True (assume a compositor is present) on any failure
        to detect, since that's the common case and we'd rather try the
        normal path than degrade unnecessarily.
        """
        try:
            from PyQt5.QtX11Extras import QX11Info
            return QX11Info.isCompositingManagerRunning()
        except Exception:
            return True
    
    def cleanup(self):
        """Clean up all resources"""
        print("[System] Cleaning up sockets and resources...")
        
        try:
            if getattr(self, 'client_socket', None):
                try: self.client_socket.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                self.client_socket.close()
            if getattr(self, 'secondary_client_socket', None):
                try: self.secondary_client_socket.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                self.secondary_client_socket.close()
            if getattr(self, 'tertiary_client_socket', None):
                try: self.tertiary_client_socket.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                self.tertiary_client_socket.close()
        except Exception as e:
            print(f"[Client] Error closing socket: {e}")
        
        try:
            if getattr(self, 'server_socket', None):
                self.server_socket.close()
            if getattr(self, 'secondary_server_socket', None):
                self.secondary_server_socket.close()
            if getattr(self, 'tertiary_server_socket', None):
                self.tertiary_server_socket.close()
        except Exception as e:
            print(f"[Server] Error closing socket: {e}")
        
        if getattr(self, 'overlay', None):
            self.destroy_overlay()
        
        app_config.is_running = False
        app_config.save()
    
    def create_overlay(self):
        """Create invisible overlay window. Call via _schedule_overlay only
        - it must run on the GUI toolkit's own thread (Tk's mainloop
        thread on Windows, Qt's main thread on Linux). Building a Qt/Tk
        widget from any other thread is undefined behaviour and was the
        root cause of the old GTK-overlay-in-a-background-thread crashes."""
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
            # X11BypassWindowManagerHint: skip the WM entirely so the overlay
            # is guaranteed to stay on top and actually intercept input.
            # WindowStaysOnTopHint alone is a hint the WM can ignore.
            overlay.setWindowFlags(
                self.Qt.FramelessWindowHint
                | self.Qt.WindowStaysOnTopHint
                | self.Qt.X11BypassWindowManagerHint
            )
            # Solid opaque black — Qt stylesheet rgba() alpha is 0-255.
            # The old value rgba(0,0,0,1) had alpha=1/255 ≈ transparent,
            # which meant the overlay showed nothing and captured no clicks.
            overlay.setStyleSheet("background-color: rgba(0, 0, 0, 255);")
            overlay.setCursor(self.Qt.BlankCursor)
            overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
            overlay.show()
            overlay.raise_()
            overlay.activateWindow()
            # grabMouse ensures all mouse events go to this widget even if
            # the cursor briefly leaves it during fast movements.
            overlay.grabMouse()
            self.overlay = overlay
    
    def destroy_overlay(self):
        """Destroy overlay window (must be called from the GUI main thread)."""
        if self.overlay:
            if self.os_type == "windows":
                self.overlay.destroy()
            elif self.os_type == "linux":
                try:
                    self.overlay.releaseMouse()
                except Exception:
                    pass
                self.overlay.close()
            self.overlay = None

    def _schedule_overlay(self, to_active):
        """Schedule overlay creation/destruction on the GUI toolkit's own
        thread. Both Tk and Qt widgets must only ever be touched from the
        thread that owns their event loop - this is what makes that safe
        to call from monitor_mouse_edges()'s background thread."""
        if not self.gui_app:
            return
        if self.os_type == "windows":
            self.gui_app.after_idle(lambda: self.create_overlay() if to_active else self.destroy_overlay())
        elif self.os_type == "linux":
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.create_overlay() if to_active else self.destroy_overlay())
    
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
        """Send mouse events from server using relative deltas.

        Absolute normalized coordinates (x/screen_width) were unreliable:
        - Multi-monitor virtual desktop makes screen_width wrong
        - Server and client with different resolutions cause cursor drift
        Relative deltas are screen-agnostic and feel 1:1.
        """
        def send_json(data):
            try:
                socket.sendall((json.dumps(data) + "\n").encode())
            except Exception as e:
                app_config.is_running = False
                app_config.save()
                print(f"[Server] Send failed: {e}")
        
        last_pos = [None]  # [x, y] of previous event, or None on first

        def on_move(x, y):
            if not app_config.active_device:
                last_pos[0] = None  # reset so next activation starts clean
                return
            if last_pos[0] is None:
                last_pos[0] = (x, y)
                return
            dx = x - last_pos[0][0]
            dy = y - last_pos[0][1]
            last_pos[0] = (x, y)
            if dx != 0 or dy != 0:
                send_json({"type": "move", "dx": dx, "dy": dy})
        
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
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try: self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception: pass
            self.server_socket.bind(("0.0.0.0", self.primary_port))
            self.server_socket.listen(1)
            
            self.secondary_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.secondary_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try: self.secondary_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception: pass
            self.secondary_server_socket.bind(("0.0.0.0", self.secondary_port))
            self.secondary_server_socket.listen(1)

            self.tertiary_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tertiary_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try: self.tertiary_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception: pass
            self.tertiary_server_socket.bind(("0.0.0.0", self.tertiary_port))
            self.tertiary_server_socket.listen(1)
        except OSError as e:
            if getattr(e, 'errno', 0) in (98, 48) or "address already in use" in str(e).lower():
                msg = f"Port conflict: Server ports ({self.primary_port}/{self.secondary_port}/{self.tertiary_port}) are already in use. Please close any running Portal instance."
            else:
                msg = f"Failed to start Server: {e}"
            print(f"[Server] {msg}")
            logging.warning(f"[Remote Status] {msg}")
            app_config.is_running = False
            self.cleanup()
            return
        
        msg = "Server running - Waiting for Client to connect..."
        print(f"[Server] {msg}")
        logging.info(f"[Remote Status] {msg}")
        
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
                except socket.timeout:
                    # settimeout(1.0) is intentional to prevent blocking
                    # forever on transition — just keep looping.
                    continue
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
        server_ip = (app_config.server_ip or "").strip()
        if not server_ip or server_ip == "Enter Server IP":
            msg = "Invalid Server IP. Please enter a valid Server IP address in Client mode."
            print(f"[Client] {msg}")
            logging.warning(f"[Remote Status] {msg}")
            app_config.is_running = False
            self.cleanup()
            return

        msg = f"Connecting to Server at {server_ip}..."
        print(f"[Client] {msg}")
        logging.info(f"[Remote Status] {msg}")

        # Connect primary
        # NOTE: We create a fresh socket on every retry attempt.
        # Once connect() is called on a socket — even if it times out — the OS
        # marks it as "connection in progress". Re-calling connect() on the same
        # socket then raises errno 114 (EINPROGRESS / Operation already in progress).
        primary_connected = False
        last_error = None
        for i in range(10):
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.client_socket.settimeout(3.0)
                self.client_socket.connect((server_ip, self.primary_port))
                handshake = self.client_socket.recv(1024)
                if handshake != b'CONNECTED\n':
                    raise Exception("Handshake failed")
                self.client_socket.settimeout(None)
                primary_connected = True
                break
            except Exception as e:
                last_error = e
                print(f"[Client] Primary connection attempt {i+1}/10 failed: {e}")
                try:
                    self.client_socket.close()
                except Exception:
                    pass
                self.client_socket = None
                if i < 9:
                    logging.info(f"[Remote Status] Connecting to {server_ip}... (Attempt {i+2}/10)")
                    time.sleep(1)

        if not primary_connected:
            msg = f"Failed to connect to {server_ip}: {last_error}"
            print(f"[Client] {msg}")
            logging.warning(f"[Remote Status] {msg}")
            app_config.is_running = False
            self.cleanup()
            return

        print("[Client] Primary Connected")
        
        # Connect secondary (fresh socket on each retry to avoid errno 114)
        secondary_connected = False
        for i in range(5):
            try:
                self.secondary_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.secondary_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.secondary_client_socket.settimeout(3.0)
                self.secondary_client_socket.connect((server_ip, self.secondary_port))
                self.secondary_client_socket.settimeout(None)
                secondary_connected = True
                break
            except Exception as e:
                last_error = e
                try:
                    self.secondary_client_socket.close()
                except Exception:
                    pass
                self.secondary_client_socket = None
                time.sleep(1)

        if not secondary_connected:
            msg = f"Secondary connection failed: {last_error}"
            print(f"[Client] {msg}")
            logging.warning(f"[Remote Status] {msg}")
            app_config.is_running = False
            self.cleanup()
            return
        
        print("[Client] Secondary Connected")

        # Connect tertiary (optional / best-effort; fresh socket on each retry)
        for i in range(3):
            try:
                self.tertiary_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tertiary_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.tertiary_client_socket.settimeout(3.0)
                self.tertiary_client_socket.connect((server_ip, self.tertiary_port))
                self.tertiary_client_socket.settimeout(None)
                self.tertiary_connected = True
                print("[Client] Tertiary Connected")
                break
            except Exception:
                try:
                    self.tertiary_client_socket.close()
                except Exception:
                    pass
                self.tertiary_client_socket = None
                time.sleep(0.5)
        
        msg = f"Successfully connected to Server at {server_ip}!"
        print(f"[Client] {msg}")
        logging.info(f"[Remote Status] {msg}")

        threading.Thread(target=self.receive_primary, daemon=True).start()
        threading.Thread(target=self.receive_secondary, daemon=True).start()
        if self.tertiary_connected:
            threading.Thread(target=self.receive_tertiary, daemon=True).start()

    def receive_primary(self):
        """Receive mouse events (relative deltas from server)."""
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
                        # Server now sends relative deltas; apply them to
                        # wherever the cursor currently is on THIS screen.
                        cx, cy = self.mouse_controller.position
                        nx = max(0, min(self.screen_width - 1,  cx + int(evt["dx"])))
                        ny = max(0, min(self.screen_height - 1, cy + int(evt["dy"])))
                        self.mouse_controller.position = (nx, ny)
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
            except socket.timeout:
                continue
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
            # NOTE: app_config.stop_flag starts out stale here - this process
            # loaded config.json once at startup and never touches the full
            # config again (see comments in transition() / the hotkey
            # listener for why a full reload is unsafe). refresh_control_flags()
            # re-reads *only* stop_flag from disk each tick, which is what
            # lets the GUI process's "Stop" button actually reach this loop.
            while app_config.is_running:
                app_config.refresh_control_flags()
                if app_config.stop_flag:
                    break
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

