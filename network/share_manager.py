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
        self.mouse_listener = None          # suppress=True listener, started on activate
        self.mouse_listener_lock = threading.Lock()  # shared with keyboard_listener_lock logic
        self.keyboard_listener_lock = threading.Lock()
        self.keyboard_socket = None
        self._mouse_send_json = None        # set by _setup_mouse_sender()
        
        self._evdev_grab_fds = []
        self._evdev_grab_lock = threading.Lock()
        
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
        
        # Stop input listeners first
        with self.keyboard_listener_lock:
            if self.keyboard_listener:
                try: self.keyboard_listener.stop()
                except Exception: pass
                self.keyboard_listener = None
        with self.mouse_listener_lock:
            if self.mouse_listener:
                try: self.mouse_listener.stop()
                except Exception: pass
                self.mouse_listener = None

        if self.os_type == "linux":
            try:
                self._evdev_release()
            except Exception:
                pass

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
            overlay.setWindowTitle("portal-overlay")

            overlay.setWindowFlags(
                self.Qt.FramelessWindowHint
                | self.Qt.WindowStaysOnTopHint
                | self.Qt.Tool
            )
            overlay.setAttribute(self.Qt.WA_TranslucentBackground, True)
            overlay.setAttribute(self.Qt.WA_NoSystemBackground, True)
            overlay.setStyleSheet("background: transparent;")
            
            from PyQt5.QtGui import QColor, QPalette
            palette = overlay.palette()
            palette.setColor(QPalette.Window, QColor(0, 0, 0, 0))
            overlay.setPalette(palette)

            overlay.setCursor(self.Qt.BlankCursor)
            if self.screen_width and self.screen_height:
                overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
            overlay.setMouseTracking(True)

            # Configure WM rules (Hyprland, Sway, i3) before mapping
            self._configure_wm_rules_sync()

            overlay.showFullScreen()
            overlay.raise_()
            overlay.activateWindow()

            self.overlay = overlay

    def _configure_wm_rules_sync(self):
        """Synchronously register WM-specific float+fullscreen+pin rules for the
        overlay window (matched by title 'portal-overlay') before it maps."""
        try:
            # ── Hyprland ──────────────────────────────────────────────────
            if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
                rules = [
                    "float 1, match:title portal-overlay",
                    "fullscreen 1, match:title portal-overlay",
                    "pin 1, match:title portal-overlay",
                    "opacity 0.0 override 0.0 override, match:title portal-overlay",
                    "float 1, match:title portal-overlay-test",
                    "fullscreen 1, match:title portal-overlay-test",
                    "pin 1, match:title portal-overlay-test",
                    "opacity 0.0 override 0.0 override, match:title portal-overlay-test",
                ]
                for rule in rules:
                    subprocess.run(
                        ["hyprctl", "keyword", "windowrule", rule],
                        check=False, timeout=2,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

                rules_v2 = [
                    "float, title:^(portal-overlay.*)$",
                    "fullscreen, title:^(portal-overlay.*)$",
                    "pin, title:^(portal-overlay.*)$",
                    "opacity 0.0 override 0.0 override, title:^(portal-overlay.*)$",
                ]
                for rule in rules_v2:
                    subprocess.run(
                        ["hyprctl", "keyword", "windowrulev2", rule],
                        check=False, timeout=2,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                return

            # ── Sway / wlroots ────────────────────────────────────────────
            if os.environ.get("SWAYSOCK"):
                subprocess.run(
                    ["swaymsg",
                     'for_window [title="portal-overlay"] '
                     'floating enable, sticky enable, fullscreen enable'],
                    check=False, timeout=2,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return

            # ── i3 ────────────────────────────────────────────────────────
            if os.environ.get("I3SOCK"):
                subprocess.run(
                    ["i3-msg",
                     '[title="portal-overlay"] floating enable; '
                     '[title="portal-overlay"] sticky enable; '
                     '[title="portal-overlay"] fullscreen enable'],
                    check=False, timeout=2,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass

    def destroy_overlay(self):
        """Destroy overlay window (must be called from the GUI main thread)."""
        if self.overlay:
            if self.os_type == "windows":
                try:
                    self.overlay.destroy()
                except Exception:
                    pass
            elif self.os_type == "linux":
                try:
                    self.overlay.hide()
                    self.overlay.close()
                    if hasattr(self.overlay, 'deleteLater'):
                        self.overlay.deleteLater()
                except Exception as e:
                    print(f"[Overlay] Error destroying Qt overlay: {e}")
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

    def _force_release_on_disconnect(self):
        """Idempotently force input release, transition out of active_device,
        destroy overlay, and stop application loop when disconnect occurs."""
        if getattr(self, '_releasing_disconnect', False):
            return
        self._releasing_disconnect = True
        print("[System] Client disconnected, forcing input release and cleanup...")
        logging.info("[System] Client disconnected, forcing input release and cleanup...")

        def _do_release():
            try:
                if app_config.active_device:
                    self.transition(False, self.mouse_controller.position)
            except Exception as e:
                print(f"[Disconnect Cleanup] Transition error: {e}")

            with self.keyboard_listener_lock:
                if self.keyboard_listener:
                    try: self.keyboard_listener.stop()
                    except Exception: pass
                    self.keyboard_listener = None

            with self.mouse_listener_lock:
                if self.mouse_listener:
                    try: self.mouse_listener.stop()
                    except Exception: pass
                    self.mouse_listener = None

            if self.os_type == "linux":
                try: self._evdev_release()
                except Exception: pass

            self._schedule_overlay(False)
            app_config.is_running = False
            app_config.save()

        threading.Thread(target=_do_release, daemon=True).start()

    def _disconnect_watchdog(self, sock):
        """Poll primary socket with select() + MSG_PEEK to detect EOF or socket disconnect."""
        import select
        while app_config.is_running:
            try:
                rlist, _, _ = select.select([sock], [], [], 1.0)
                if rlist:
                    peek = sock.recv(1, socket.MSG_PEEK)
                    if not peek:
                        print("[Watchdog] Primary connection EOF detected")
                        self._force_release_on_disconnect()
                        break
            except Exception as e:
                print(f"[Watchdog] Socket error: {e}")
                self._force_release_on_disconnect()
                break
    
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

            # PRIORITY 1: Instant Input Suppression — keyboard AND mouse.
            # Both listeners are stopped first (releasing any existing X11
            # grab), then restarted with suppress=True when activating.
            # The sleep gives X11 a moment to process the ungrab before
            # we issue a new grab, preventing "already grabbed" errors.
            with self.keyboard_listener_lock:
                if self.keyboard_listener:
                    try: self.keyboard_listener.stop()
                    except: pass
                    self.keyboard_listener = None

            with self.mouse_listener_lock:
                if self.mouse_listener:
                    try: self.mouse_listener.stop()
                    except: pass
                    self.mouse_listener = None

            time.sleep(0.05)  # Give X11 a moment to release grabs

            if to_active:
                from pynput import keyboard
                with self.keyboard_listener_lock:
                    self.keyboard_listener = keyboard.Listener(
                        on_press=self._on_press,
                        on_release=self._on_release,
                        suppress=True
                    )
                    self.keyboard_listener.start()

                # Mouse: suppress=True issues XGrabPointer so local apps
                # never see clicks or scrolls while input is being shared.
                # Only needed on the server side (where _mouse_send_json is set).
                if self._mouse_send_json is not None:
                    with self.mouse_listener_lock:
                        self.mouse_listener = self._make_mouse_listener(suppress=True)
                        self.mouse_listener.start()

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
                        active_msg = {
                            "type": "active_device",
                            "value": to_active,
                            "server_direction": getattr(app_config, 'server_direction', 'Right')
                        }
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
    
    def _setup_mouse_sender(self, sock):
        """Store the send callback for mouse events.

        The mouse listener itself is managed by transition(): started with
        suppress=True when the device activates and stopped on deactivate.
        This avoids having a permanently running non-suppress listener that
        lets clicks/scrolls pass through to local apps while sharing.
        """
        def send_json(data):
            try:
                sock.sendall((json.dumps(data) + "\n").encode())
            except Exception as e:
                print(f"[Server] Mouse send failed: {e}")
                self._force_release_on_disconnect()
        self._mouse_send_json = send_json

    def _make_mouse_listener(self, suppress=False):
        """Build a mouse.Listener that sends relative deltas.

        suppress=True issues XGrabPointer so local apps never see the
        events (clicks, scrolls, movement) while input is shared.

        Rate is capped at 125 Hz: at high DPI a fast sweep generates
        1000+ events/second which floods the TCP channel and causes the
        client receive loop to fall behind (perceived as lag). 8 ms
        batching is imperceptible to humans but keeps the pipe clear.
        """
        last_pos    = [None]   # (x, y) of previous move sample
        last_t      = [0.0]   # monotonic timestamp of last sent move
        MIN_INTERVAL = 1.0 / 125  # 125 Hz cap

        def on_move(x, y):
            if not app_config.active_device:
                last_pos[0] = None  # reset so next activation starts clean
                return

            # Check if physical mouse on Server hit the return edge
            if app_config.active_device and not self.edge_transition_cooldown:
                margin = 5
                warp_buffer = 50
                direction = getattr(app_config, 'server_direction', 'Right')
                return_triggered = False
                return_pos = None

                if direction == "Right" and x <= margin:
                    return_pos = (self.screen_width - margin - warp_buffer, y)
                    return_triggered = True
                elif direction == "Left" and x >= self.screen_width - margin:
                    return_pos = (margin + warp_buffer, y)
                    return_triggered = True
                elif direction == "Top" and y >= self.screen_height - margin:
                    return_pos = (x, margin + warp_buffer)
                    return_triggered = True
                elif direction == "Bottom" and y <= margin:
                    return_pos = (x, self.screen_height - margin - warp_buffer)
                    return_triggered = True

                if return_triggered and return_pos:
                    print(f"[Server] Physical mouse hit return edge -> returning input to server at {return_pos}")
                    logging.info(f"[Server] Physical mouse hit return edge -> returning input to server at {return_pos}")
                    threading.Thread(target=lambda: self.transition(False, return_pos), daemon=True).start()
                    return

            if last_pos[0] is None:
                last_pos[0] = (x, y)
                return
            now = time.monotonic()
            if now - last_t[0] < MIN_INTERVAL:
                # Still accumulate position so the next sent delta is correct
                last_pos[0] = (x, y)
                return
            dx = x - last_pos[0][0]
            dy = y - last_pos[0][1]
            last_pos[0] = (x, y)
            last_t[0]   = now
            if (dx or dy) and hasattr(self, '_mouse_send_json'):
                self._mouse_send_json({"type": "move", "dx": dx, "dy": dy})

        def on_click(x, y, button, pressed):
            if not app_config.active_device:
                return
            btn_name = button.name if hasattr(button, 'name') else str(button)
            if hasattr(self, '_mouse_send_json'):
                self._mouse_send_json({"type": "click", "button": btn_name, "pressed": pressed})

        def on_scroll(x, y, dx, dy):
            if not app_config.active_device:
                return
            if hasattr(self, '_mouse_send_json'):
                self._mouse_send_json({"type": "scroll", "dx": dx, "dy": dy})

        return mouse.Listener(
            on_move=on_move,
            on_click=on_click,
            on_scroll=on_scroll,
            suppress=suppress,
        )

    def send_keyboard_events(self, socket):
        """Save socket for the instant handlers"""
        self.keyboard_socket = socket
    
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
        except Exception:
            self._force_release_on_disconnect()

    def _on_release(self, key):
        if not app_config.active_device or not self.keyboard_socket:
            return
        try:
            val = key.char if hasattr(key, 'char') and key.char else str(key)
            msg = json.dumps({"type": "key_release", "key": val}) + "\n"
            self.keyboard_socket.sendall(msg.encode())
        except Exception:
            self._force_release_on_disconnect()

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
        client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            try: client.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 3)
            except Exception: pass
        elif hasattr(socket, "TCP_KEEPALIVE"):
            try: client.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 3)
            except Exception: pass
        if hasattr(socket, "TCP_KEEPINTVL"):
            try: client.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 2)
            except Exception: pass
        if hasattr(socket, "TCP_KEEPCNT"):
            try: client.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            except Exception: pass

        print(f"[Server] Primary connection from: {addr}")
        logging.info(f"[Connection] Primary connection from: {addr}")
        client.sendall(b'CONNECTED\n')
        print("[Server] Primary handshake sent")
        logging.info("[Connection] Primary handshake sent")
        threading.Thread(target=self.monitor_mouse_edges, daemon=True).start()
        self._setup_mouse_sender(client)  # register send callback; listener started by transition()
        threading.Thread(target=self._disconnect_watchdog, args=(client,), daemon=True).start()
    
    # ------------------------------------------------------------------ #
    #  evdev kernel-level keyboard grab                                    #
    #  Grabs /dev/input/event* devices exclusively so ALL key events      #
    #  (including Super+key Wayland compositor shortcuts) are consumed     #
    #  before the compositor sees them.  Requires user in 'input' group.  #
    # ------------------------------------------------------------------ #

    def _evdev_find_keyboards(self):
        """Return a list of /dev/input/event* paths that have EV_KEY."""
        import glob
        import fcntl
        EV_KEY = 0x01
        EVIOCGBIT_0 = 0x80204520
        devices = []
        for path in sorted(glob.glob("/dev/input/event*")):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                buf = bytearray(32)
                fcntl.ioctl(fd, EVIOCGBIT_0, buf)
                os.close(fd)
                if buf[EV_KEY // 8] & (1 << (EV_KEY % 8)):
                    devices.append(path)
            except Exception:
                pass
        return devices

    def _evdev_grab(self):
        """Open keyboard devices and issue EVIOCGRAB to take exclusive ownership."""
        import fcntl
        import struct
        EVIOCGRAB = 0x40044590
        new_fds = []
        for path in self._evdev_find_keyboards():
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                fcntl.ioctl(fd, EVIOCGRAB, struct.pack('i', 1))
                new_fds.append(fd)
            except Exception:
                try:
                    os.close(fd)
                except Exception:
                    pass
        with self._evdev_grab_lock:
            for fd in self._evdev_grab_fds:
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, struct.pack('i', 0))
                    os.close(fd)
                except Exception:
                    pass
            self._evdev_grab_fds = new_fds
        if new_fds:
            logging.info(f"[evdev] Grabbed {len(new_fds)} keyboard device(s)")

    def _evdev_release(self):
        """Release all evdev keyboard grabs so normal input routing resumes."""
        import fcntl
        import struct
        EVIOCGRAB = 0x40044590
        with self._evdev_grab_lock:
            for fd in self._evdev_grab_fds:
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, struct.pack('i', 0))
                    os.close(fd)
                except Exception:
                    pass
            self._evdev_grab_fds = []
        logging.info("[evdev] Released keyboard grabs")

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
            elif evt["type"] == "edge_return":
                if app_config.active_device:
                    margin = 2
                    warp_buffer = 50
                    direction = getattr(app_config, 'server_direction', 'Right')
                    if direction == "Right":
                        return_pos = (self.screen_width - margin - warp_buffer, evt.get("y", self.screen_height // 2))
                    elif direction == "Left":
                        return_pos = (margin + warp_buffer, evt.get("y", self.screen_height // 2))
                    elif direction == "Top":
                        return_pos = (evt.get("x", self.screen_width // 2), self.screen_height - margin - warp_buffer)
                    elif direction == "Bottom":
                        return_pos = (evt.get("x", self.screen_width // 2), margin + warp_buffer)
                    else:
                        return_pos = self.mouse_controller.position

                    print(f"[Server] Client edge return received -> returning input to server at {return_pos}")
                    logging.info(f"[Server] Client edge return received -> returning input to server at {return_pos}")
                    threading.Thread(target=lambda: self.transition(False, return_pos), daemon=True).start()
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

                        # Client edge detection: if cursor hits opposite edge on Client, send edge_return to Server
                        if app_config.active_device and not getattr(self, 'client_edge_cooldown', False):
                            margin = 5
                            direction = getattr(app_config, 'server_direction', 'Right')
                            return_triggered = False

                            if direction == "Right" and nx <= margin:
                                return_triggered = True
                            elif direction == "Left" and nx >= self.screen_width - 1 - margin:
                                return_triggered = True
                            elif direction == "Top" and ny >= self.screen_height - 1 - margin:
                                return_triggered = True
                            elif direction == "Bottom" and ny <= margin:
                                return_triggered = True

                            if return_triggered:
                                self.client_edge_cooldown = True
                                target_socket = getattr(self, 'secondary_client_socket', None) or getattr(self, 'client_socket', None)
                                if target_socket:
                                    try:
                                        msg = json.dumps({"type": "edge_return", "x": nx, "y": ny}) + "\n"
                                        target_socket.sendall(msg.encode())
                                        print(f"[Client] Hit return edge ({direction}), sending edge_return to server")
                                        logging.info(f"[Client] Hit return edge ({direction}), sending edge_return to server")
                                    except Exception as e:
                                        print(f"[Client] Failed to send edge_return: {e}")

                        # Cooldown reset when cursor moves into central screen area
                        if getattr(self, 'client_edge_cooldown', False):
                            margin = 20
                            direction = getattr(app_config, 'server_direction', 'Right')
                            if direction in ("Right", "Left"):
                                if margin < nx < self.screen_width - margin:
                                    self.client_edge_cooldown = False
                            else:
                                if margin < ny < self.screen_height - margin:
                                    self.client_edge_cooldown = False
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
                        if "server_direction" in evt:
                            app_config.server_direction = evt["server_direction"]
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

