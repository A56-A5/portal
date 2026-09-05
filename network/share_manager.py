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
        
        # StreamHandler added alongside the file handler so any
        # logging.info/warning/error call in this process also shows in
        # the terminal, not just logs.log — same reasoning as the fix in
        # controllers/audio_controller.py.
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("logs.log", mode="a"),
                logging.StreamHandler(),
            ],
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
            self.overlay_width = self.screen_width
            self.overlay_height = self.screen_height
        elif self.os_type == "linux":
            if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
                os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
            from PyQt5.QtWidgets import QApplication, QWidget
            from PyQt5.QtCore import Qt
            self.Qt = Qt
            self.QWidget = QWidget
            self.gui_app = QApplication(sys.argv)

            # Edge detection must use the same coordinate space as cursorpos
            # (logical under Hyprland fractional scale). Overlay window must
            # use Qt/X11 size so it actually covers the full display.
            primary = self.gui_app.primaryScreen()
            geom = primary.geometry()
            self.overlay_width = geom.width()
            self.overlay_height = geom.height()

            matched = self.mouse_controller.get_display_size_matching_position()
            if matched:
                self.screen_width, self.screen_height = matched
                print(f"[Screen] Edge coords (cursor space): {self.screen_width}x{self.screen_height}")
            else:
                self.screen_width = self.overlay_width
                self.screen_height = self.overlay_height
                print(f"[Screen] Edge coords (Qt fallback): {self.screen_width}x{self.screen_height}")
            print(f"[Screen] Overlay window size (Qt): {self.overlay_width}x{self.overlay_height}")

            self._wayland = self._detect_wayland()
            self._compositor_available = self._detect_compositor()
            self._compositor_warned = False

            if self._wayland:
                msg = ("Wayland session detected - running with X11 compatibility layer for overlay & input sharing.")
                logging.info(f"[Remote Status] {msg}")
                print(f"[Session] {msg}")
            print(f"[Config] server_direction={app_config.server_direction!r}  mode={app_config.mode!r}")

            # Thread-safe overlay control: worker threads emit, Qt main thread applies
            from PyQt5.QtCore import QObject, pyqtSignal
            class _OverlayBridge(QObject):
                request = pyqtSignal(bool)
            self._overlay_bridge = _OverlayBridge()
            self._overlay_bridge.request.connect(self._on_overlay_request)
            print("[Overlay] Qt signal bridge ready")

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
        try:
            self._stop_hypr_mouse_poller()
        except Exception:
            pass
        try:
            self._stop_evdev_reader()
        except Exception:
            pass
        try:
            self._set_waybar_visible(True)
        except Exception:
            pass
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
        root cause of the old GTK-overlay-in-a-background-thread crashes.

        Overlay is ONLY created when transitioning TO active_device=True
        (input is being sent to the client). It must be destroyed when
        returning control to the server. Never leave it up permanently.
        """
        # Always tear down any existing overlay first so we never stack them
        # and never leave a stale one visible.
        if self.overlay is not None:
            self.destroy_overlay()

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
            # Fully transparent overlay (user is invisible).
            # Do NOT grabMouse under Wayland/XWayland — that freezes hyprctl
            # cursorpos and kills relative mouse sharing.
            overlay.setAttribute(self.Qt.WA_TranslucentBackground, True)
            overlay.setAttribute(self.Qt.WA_NoSystemBackground, True)
            from PyQt5.QtGui import QColor, QPalette
            palette = overlay.palette()
            palette.setColor(QPalette.Window, QColor(0, 0, 0, 0))
            overlay.setPalette(palette)
            overlay.setStyleSheet("background: transparent;")

            overlay.setCursor(self.Qt.BlankCursor)
            ow = getattr(self, 'overlay_width', None) or self.screen_width
            oh = getattr(self, 'overlay_height', None) or self.screen_height
            if ow and oh:
                overlay.setGeometry(0, 0, ow, oh)
            overlay.setMouseTracking(True)
            overlay.setFocusPolicy(self.Qt.StrongFocus)

            # Capture mouse/keyboard on the overlay itself (critical on Wayland
            # where pynput global hooks do not receive events).
            self._wire_overlay_input(overlay)

            # Configure WM rules (Hyprland, Sway, i3) before mapping
            self._configure_wm_rules_sync()

            # i3: showFullScreen maps to i3 fullscreen which hides other
            # windows (wallpaper-only view). Use a normal top-level show.
            if os.environ.get("I3SOCK"):
                overlay.show()
            else:
                overlay.showFullScreen()
            overlay.raise_()
            overlay.activateWindow()
            overlay.setFocus()
            # Re-apply i3 geometry after map (timing)
            if os.environ.get("I3SOCK"):
                try:
                    self._configure_wm_rules_sync()
                except Exception:
                    pass
            # No grabMouse/grabKeyboard — breaks hyprctl position on Wayland
            if self.gui_app:
                self.gui_app.processEvents()

            self.overlay = overlay
            print(f"[Overlay] CREATED transparent {ow}x{oh} (i3={bool(os.environ.get('I3SOCK'))})")


    def _wire_overlay_input(self, overlay):
        """Forward Qt mouse/key events from the overlay to the client.

        On Wayland/Hyprland global pynput hooks often see nothing. The
        fullscreen overlay is the reliable event source for clicks and
        can also supply moves if the compositor delivers them to the window.
        """
        from PyQt5.QtCore import Qt as QtCore

        last = [None]  # last local pos for relative deltas

        def send_move(x, y):
            if not self._mouse_send_json or not app_config.active_device:
                return
            # Map overlay (physical/Qt) coords into edge/logical space for deltas
            # Prefer relative deltas from last point in overlay space.
            if last[0] is None:
                last[0] = (x, y)
                return
            dx = int(x - last[0][0])
            dy = int(y - last[0][1])
            last[0] = (x, y)
            if dx or dy:
                # Scale overlay pixels -> logical if sizes differ
                ow = getattr(self, 'overlay_width', None) or self.screen_width or 1
                oh = getattr(self, 'overlay_height', None) or self.screen_height or 1
                sx = self.screen_width / float(ow)
                sy = self.screen_height / float(oh)
                self._mouse_send_json({
                    "type": "move",
                    "dx": int(round(dx * sx)),
                    "dy": int(round(dy * sy)),
                })

        def on_move(event):
            if not app_config.active_device:
                return
            send_move(event.x(), event.y())
            event.accept()

        def btn_name(button):
            if button == QtCore.LeftButton:
                return "left"
            if button == QtCore.RightButton:
                return "right"
            if button == QtCore.MiddleButton:
                return "middle"
            return "left"

        def on_press(event):
            if not app_config.active_device or not self._mouse_send_json:
                return
            self._mouse_send_json({
                "type": "click",
                "button": btn_name(event.button()),
                "pressed": True,
            })
            print(f"[Overlay] click press {btn_name(event.button())}")
            event.accept()

        def on_release(event):
            if not app_config.active_device or not self._mouse_send_json:
                return
            self._mouse_send_json({
                "type": "click",
                "button": btn_name(event.button()),
                "pressed": False,
            })
            event.accept()

        def on_wheel(event):
            if not app_config.active_device or not self._mouse_send_json:
                return
            delta = event.angleDelta()
            dy = 1 if delta.y() > 0 else (-1 if delta.y() < 0 else 0)
            dx = 1 if delta.x() > 0 else (-1 if delta.x() < 0 else 0)
            if dx or dy:
                self._mouse_send_json({"type": "scroll", "dx": dx, "dy": dy})
            event.accept()

        def qt_key_to_wire(event):
            from PyQt5.QtCore import Qt as QtC
            qt_map = {
                QtC.Key_Backspace: "Key.backspace",
                QtC.Key_Return: "Key.enter",
                QtC.Key_Enter: "Key.enter",
                QtC.Key_Tab: "Key.tab",
                QtC.Key_Escape: "Key.esc",
                QtC.Key_Space: "Key.space",
                QtC.Key_Delete: "Key.delete",
                QtC.Key_Left: "Key.left",
                QtC.Key_Right: "Key.right",
                QtC.Key_Up: "Key.up",
                QtC.Key_Down: "Key.down",
                QtC.Key_Home: "Key.home",
                QtC.Key_End: "Key.end",
                QtC.Key_PageUp: "Key.page_up",
                QtC.Key_PageDown: "Key.page_down",
                QtC.Key_Shift: "Key.shift",
                QtC.Key_Control: "Key.ctrl",
                QtC.Key_Alt: "Key.alt",
                QtC.Key_Meta: "Key.cmd",
                QtC.Key_Super_L: "Key.cmd",
                QtC.Key_Super_R: "Key.cmd_r",
            }
            k = event.key()
            if k in qt_map:
                return qt_map[k]
            t = event.text()
            if t and len(t) == 1 and t.isprintable():
                return t
            return f"Key.qt_{int(k)}"

        def on_key_press(event):
            if not app_config.active_device or not self.keyboard_socket:
                return
            try:
                val = qt_key_to_wire(event)
                msg = json.dumps({"type": "key_press", "key": val}) + "\n"
                self.keyboard_socket.sendall(msg.encode())
            except Exception:
                pass
            event.accept()

        def on_key_release(event):
            if not app_config.active_device or not self.keyboard_socket:
                return
            try:
                val = qt_key_to_wire(event)
                msg = json.dumps({"type": "key_release", "key": val}) + "\n"
                self.keyboard_socket.sendall(msg.encode())
            except Exception:
                pass
            event.accept()

        overlay.mouseMoveEvent = on_move
        overlay.mousePressEvent = on_press
        overlay.mouseReleaseEvent = on_release
        overlay.wheelEvent = on_wheel
        overlay.keyPressEvent = on_key_press
        overlay.keyReleaseEvent = on_key_release

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
            # NEVER use i3 "fullscreen enable" — i3 fullscreen unmaps every
            # other window, so a transparent overlay only shows the wallpaper.
            # Use floating + sticky + borderless covering the full geometry.
            if os.environ.get("I3SOCK"):
                ow = getattr(self, "overlay_width", None) or self.screen_width or 1920
                oh = getattr(self, "overlay_height", None) or self.screen_height or 1080
                subprocess.run(
                    ["i3-msg",
                     '[title="portal-overlay"] floating enable, '
                     'sticky enable, border none, '
                     f'move position 0 0, resize set {int(ow)} {int(oh)}'],
                    check=False, timeout=2,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass

    def destroy_overlay(self):
        """Destroy overlay window (must be called from the GUI main thread).

        This is the only place that should clear the fullscreen grab window.
        Called on every transition back to the server (active_device=False)
        and on cleanup / disconnect.
        """
        if self.overlay is None:
            return
        try:
            if self.os_type == "windows":
                try:
                    self.overlay.destroy()
                except Exception:
                    pass
            elif self.os_type == "linux":
                try:
                    try:
                        self.overlay.releaseMouse()
                        self.overlay.releaseKeyboard()
                    except Exception:
                        pass
                    self.overlay.hide()
                    self.overlay.close()
                    if hasattr(self.overlay, 'deleteLater'):
                        self.overlay.deleteLater()
                    if self.gui_app:
                        self.gui_app.processEvents()
                except Exception as e:
                    print(f"[Overlay] Error destroying Qt overlay: {e}")
        finally:
            self.overlay = None
            print("[Overlay] DESTROYED")

    def _schedule_overlay(self, to_active):
        """Schedule overlay creation/destruction on the GUI toolkit's own
        thread. QTimer.singleShot from a worker thread is NOT delivered on
        Qt — that is why the overlay never appeared. Use a queued signal
        (or Tk after_idle) so the real main thread runs create/destroy.
        """
        if not self.gui_app:
            return
        if self.os_type == "windows":
            self.gui_app.after_idle(lambda: self.create_overlay() if to_active else self.destroy_overlay())
        elif self.os_type == "linux":
            bridge = getattr(self, '_overlay_bridge', None)
            if bridge is None:
                print("[Overlay] ERROR: bridge not initialized")
                return
            bridge.request.emit(bool(to_active))

    def _on_overlay_request(self, to_active):
        """Runs on the Qt main thread only."""
        try:
            if to_active:
                self.create_overlay()
            else:
                self.destroy_overlay()
        except Exception as e:
            print(f"[Overlay] apply failed: {e}")

    def _force_release_on_disconnect(self):
        """Idempotently force input release, transition out of active_device,
        destroy overlay, and stop application loop when disconnect occurs."""
        if getattr(self, '_releasing_disconnect', False):
            return
        self._releasing_disconnect = True
        print("[System] Client disconnected, forcing input release and cleanup...")
        logging.info("[System] Client disconnected, forcing input release and cleanup...")
        logging.warning("[Remote Status] Disconnected")

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

            try:
                self._stop_hypr_mouse_poller()
            except Exception:
                pass

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
        margin = 5
        last_debug = 0.0
        
        while app_config.is_running:
            # If input sharing is disabled, ensure inactive and skip transitions
            if not getattr(app_config, 'input_sharing_enabled', True):
                if app_config.active_device:
                    self.transition(False, self.mouse_controller.position)
                time.sleep(0.05)
                continue
            x, y = self.mouse_controller.position
            warp_buffer = 40
            grace_period = 0.35  # longer to stop bounce after warp
            
            # Throttled debug
            now = time.time()
            if now - last_debug > 2.0:
                last_debug = now
                direction = getattr(app_config, 'server_direction', 'Right')
                print(f"[Edge] pos=({x},{y}) size={self.screen_width}x{self.screen_height} "
                      f"dir={direction!r} active={app_config.active_device} cooldown={self.edge_transition_cooldown}")
            
            # Skip if we just transitioned (hard bounce protection)
            if now - self.last_transition_time < grace_period:
                time.sleep(0.01)
                continue

            if not app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x >= self.screen_width - margin:
                    print(f"[Edge] RIGHT edge hit at x={x} -> activating client")
                    self.transition(True, (margin + warp_buffer, y))
                    continue
                elif app_config.server_direction == "Left" and x <= margin:
                    print(f"[Edge] LEFT edge hit at x={x} -> activating client")
                    self.transition(True, (self.screen_width - margin - warp_buffer, y))
                    continue
                elif app_config.server_direction == "Top" and y <= margin:
                    print(f"[Edge] TOP edge hit at y={y} -> activating client")
                    self.transition(True, (x, self.screen_height - margin - warp_buffer))
                    continue
                elif app_config.server_direction == "Bottom" and y >= self.screen_height - margin:
                    print(f"[Edge] BOTTOM edge hit at y={y} -> activating client")
                    self.transition(True, (x, margin + warp_buffer))
                    continue
            
            # While active: no server-side return-edge (client sends edge_return).
            # Physical cursor must move freely so hyprctl poller can emit deltas.
            elif app_config.active_device:
                pass
            
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

            # Stop any previous hyprctl poller before flipping state
            self._stop_hypr_mouse_poller()

            # Set active state FIRST so any poller/listener that checks
            # app_config.active_device sees the correct value immediately.
            app_config.active_device = to_active
            app_config.save()

            use_hypr = getattr(self.mouse_controller, 'use_hyprctl', False)

            if to_active:
                from pynput import keyboard
                # On pure Wayland, suppress=True often fails or freezes input.
                # Use suppress only when NOT on Hyprland; on Hyprland rely on
                # overlay + hypr poller + non-suppress listeners.
                kb_suppress = not use_hypr
                with self.keyboard_listener_lock:
                    self.keyboard_listener = keyboard.Listener(
                        on_press=self._on_press,
                        on_release=self._on_release,
                        suppress=kb_suppress
                    )
                    self.keyboard_listener.start()
                    print(f"[Input] Keyboard listener started (suppress={kb_suppress})")

                if self._mouse_send_json is not None:
                    if use_hypr:
                        # Hyprland: absolute cursorpos freezes under the overlay.
                        # Use evdev relative mouse deltas instead (same path as kb).
                        print("[Input] Hyprland mouse via evdev relative (not hyprctl)")
                    else:
                        with self.mouse_listener_lock:
                            self.mouse_listener = self._make_mouse_listener(suppress=True)
                            self.mouse_listener.start()
                            print("[Input] Mouse listener started (suppress=True)")

                # Exclusive grab keyboards + mice; reader forwards keys and
                # relative mouse motion / buttons / wheel to the client.
                try:
                    self._evdev_grab()
                    self._start_evdev_reader()
                except Exception as e:
                    print(f"[Input] evdev grab failed (need 'input' group?): {e}")

                # Hide waybar while sharing so overlay covers full screen
                self._set_waybar_visible(False)

            else:
                # CRITICAL order: stop reader thread first (so it is not in
                # select/read), THEN ungrab+close FDs. Otherwise the mouse
                # device can stay exclusively grabbed and the server cursor
                # never moves again.
                try:
                    self._stop_evdev_reader()
                except Exception as e:
                    print(f"[Input] stop evdev reader: {e}")
                try:
                    self._evdev_release()
                except Exception as e:
                    print(f"[Input] evdev release: {e}")
                self._set_waybar_visible(True)
                # new_position comes from edge_return / transition caller
                # (entry edge). Do not force center — that felt wrong.

            self._schedule_overlay(to_active)
            try:
                self.mouse_controller.position = new_position
            except Exception as e:
                print(f"[Transition] warp failed: {e}")
            print(f"[Transition] active={to_active} warped to {new_position}")

            # Preserve the exact crossing point across the boundary, like a
            # real side-by-side monitor, instead of always re-centering on
            # the client (the old behaviour). Sent as a 0.0-1.0 FRACTION of
            # this machine's own axis dimension at the moment of crossing -
            # not a raw pixel value - so it still lines up correctly even
            # when the two machines have different resolutions or Hyprland's
            # fractional scaling is involved. Only meaningful when
            # activating (to_active=True); the direction determines which
            # axis of new_position is the "along the edge" coordinate.
            axis_fraction = None
            if to_active:
                direction = getattr(app_config, 'server_direction', 'Right')
                try:
                    if direction in ("Right", "Left"):
                        axis_fraction = new_position[1] / float(self.screen_height or 1)
                    else:
                        axis_fraction = new_position[0] / float(self.screen_width or 1)
                    axis_fraction = min(1.0, max(0.0, axis_fraction))
                except Exception:
                    axis_fraction = None

            def send_active_state():
                if hasattr(self, 'secondary_server') and self.secondary_server:
                    try:
                        active_msg = {
                            "type": "active_device",
                            "value": to_active,
                            "server_direction": getattr(app_config, 'server_direction', 'Right')
                        }
                        if axis_fraction is not None:
                            active_msg["axis_fraction"] = axis_fraction
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
            time.sleep(0.35)
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
    

    def _start_hypr_mouse_poller(self):
        """Poll hyprctl cursorpos while active and send relative deltas.

        Loop is controlled by a local Event reference so _stop can clear
        self._hypr_poller_stop without crashing the running thread.
        First sample after start is used only as baseline (no huge jump
        from pre-warp position).
        """
        stop_event = threading.Event()
        self._hypr_poller_stop = stop_event

        def poll_loop(stop=stop_event):
            last = None
            moves_sent = 0
            print("[Input] Hyprland mouse poller started")
            while not stop.is_set() and app_config.is_running:
                try:
                    pos = self.mouse_controller.position
                    if last is not None and self._mouse_send_json is not None:
                        dx = int(pos[0] - last[0])
                        dy = int(pos[1] - last[1])
                        # Ignore absurd jumps (warp / monitor switch)
                        if abs(dx) > 400 or abs(dy) > 400:
                            last = pos
                            continue
                        if dx or dy:
                            self._mouse_send_json({"type": "move", "dx": dx, "dy": dy})
                            moves_sent += 1
                            if moves_sent <= 3 or moves_sent % 50 == 0:
                                print(f"[Input] sent move dx={dx} dy={dy} (#{moves_sent})")
                    last = pos
                except Exception as e:
                    print(f"[Input] hypr poller error: {e}")
                time.sleep(0.008)  # ~125 Hz
            print(f"[Input] Hyprland mouse poller stopped (sent {moves_sent} moves)")

        self._hypr_poller_thread = threading.Thread(target=poll_loop, daemon=True)
        self._hypr_poller_thread.start()

    def _stop_hypr_mouse_poller(self):
        stop = getattr(self, '_hypr_poller_stop', None)
        if stop is not None:
            try:
                stop.set()
            except Exception:
                pass
        t = getattr(self, '_hypr_poller_thread', None)
        if t is not None and t.is_alive():
            t.join(timeout=0.6)
        # Clear refs only after thread has exited (or timed out)
        self._hypr_poller_stop = None
        self._hypr_poller_thread = None

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

            # Return-edge is client-driven only (edge_return message). Do not
            # abort sharing when the physical server cursor crosses a margin.

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
    
    def _serialize_key(self, key):
        """Canonical key wire format: 'Key.backspace', 'Key.enter', or a single char."""
        from pynput.keyboard import Key, KeyCode
        if isinstance(key, Key):
            return f"Key.{key.name}"
        if isinstance(key, KeyCode):
            if key.char is not None and isinstance(key.char, str) and len(key.char) == 1:
                o = ord(key.char)
                if o == 8:
                    return "Key.backspace"
                if o == 9:
                    return "Key.tab"
                if o == 13:
                    return "Key.enter"
                if o == 27:
                    return "Key.esc"
                if o >= 32 and key.char.isprintable():
                    return key.char
            vk_map = {8: "Key.backspace", 9: "Key.tab", 13: "Key.enter", 27: "Key.esc", 32: "Key.space", 46: "Key.delete"}
            if getattr(key, "vk", None) in vk_map:
                return vk_map[key.vk]
        s = str(key)
        if s.startswith("Key."):
            return s
        # Bare name already
        if s.lower() in ("backspace", "enter", "tab", "esc", "space", "delete"):
            return f"Key.{s.lower()}"
        return s

    def _on_press(self, key):
        if not app_config.active_device or not self.keyboard_socket:
            return
        try:
            val = self._serialize_key(key)
            msg = json.dumps({"type": "key_press", "key": val}) + "\n"
            self.keyboard_socket.sendall(msg.encode())
        except Exception:
            self._force_release_on_disconnect()

    def _on_release(self, key):
        if not app_config.active_device or not self.keyboard_socket:
            return
        try:
            val = self._serialize_key(key)
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
        print(f"[Server] Starting edge monitor  direction={app_config.server_direction!r}  "
              f"screen={self.screen_width}x{self.screen_height}")
        threading.Thread(target=self.monitor_mouse_edges, daemon=True).start()
        self._setup_mouse_sender(client)  # register send callback; listener started by transition()
        threading.Thread(target=self._disconnect_watchdog, args=(client,), daemon=True).start()
    
    # ------------------------------------------------------------------ #
    #  evdev kernel-level keyboard grab                                    #
    #  Grabs /dev/input/event* devices exclusively so ALL key events      #
    #  (including Super+key Wayland compositor shortcuts) are consumed     #
    #  before the compositor sees them.  Requires user in 'input' group.  #
    # ------------------------------------------------------------------ #


    def _set_waybar_visible(self, visible):
        """Toggle waybar (SIGUSR1) so the overlay can cover the bar area."""
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return
        try:
            # waybar toggles visibility on SIGUSR1
            import signal
            # Only toggle when state actually changes
            currently = getattr(self, '_waybar_hidden', False)
            want_hidden = not visible
            if want_hidden and not currently:
                subprocess.run(["pkill", "-USR1", "waybar"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._waybar_hidden = True
                print("[Overlay] waybar hidden (SIGUSR1)")
            elif visible and currently:
                subprocess.run(["pkill", "-USR1", "waybar"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._waybar_hidden = False
                print("[Overlay] waybar restored (SIGUSR1)")
        except Exception as e:
            print(f"[Overlay] waybar toggle failed: {e}")

    def _start_evdev_reader(self):
        """Read exclusive-grabbed keyboard FDs and forward keys to client."""
        self._evdev_reader_stop = threading.Event()
        stop = self._evdev_reader_stop

        # Linux KEY_* code -> wire name
        KEYMAP = {
            1: "Key.esc", 14: "Key.backspace", 15: "Key.tab", 28: "Key.enter",
            29: "Key.ctrl", 42: "Key.shift", 54: "Key.shift_r", 56: "Key.alt",
            97: "Key.ctrl_r", 100: "Key.alt_r", 125: "Key.cmd", 126: "Key.cmd_r",
            57: "Key.space", 111: "Key.delete",
            103: "Key.up", 108: "Key.down", 105: "Key.left", 106: "Key.right",
            102: "Key.home", 107: "Key.end", 104: "Key.page_up", 109: "Key.page_down",
        }
        # printable: keycode 2-13 digits, 16-25 qwerty row, etc. Use a simple US map
        US = {
            2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
            12: "-", 13: "=", 16: "q", 17: "w", 18: "e", 19: "r", 20: "t", 21: "y", 22: "u",
            23: "i", 24: "o", 25: "p", 26: chr(91), 27: chr(93), 30: "a", 31: "s", 32: "d", 33: "f",
            34: "g", 35: "h", 36: "j", 37: "k", 38: "l", 39: ";", 40: chr(39), 41: "`",
            43: chr(92), 44: "z", 45: "x", 46: "c", 47: "v", 48: "b", 49: "n", 50: "m",
            51: ",", 52: ".", 53: "/",
        }

        def reader_loop(stop_ev=stop):
            import struct, select
            EVENT_FORMAT = "llHHi"
            EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
            EV_KEY, EV_REL, EV_SYN = 1, 2, 0
            REL_X, REL_Y, REL_WHEEL, REL_HWHEEL = 0, 1, 8, 6
            BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
            pending_dx = 0
            pending_dy = 0
            moves = 0
            print("[Input] evdev keyboard+mouse reader started")
            while not stop_ev.is_set() and app_config.is_running:
                fds = list(getattr(self, "_evdev_grab_fds", []) or [])
                if not fds:
                    time.sleep(0.05)
                    continue
                try:
                    r, _, _ = select.select(fds, [], [], 0.05)
                except Exception:
                    time.sleep(0.05)
                    continue
                for fd in r:
                    try:
                        # Drain all pending events on this fd
                        while True:
                            data = os.read(fd, EVENT_SIZE)
                            if len(data) < EVENT_SIZE:
                                break
                            _sec, _usec, etype, code, value = struct.unpack(EVENT_FORMAT, data)
                            if etype == EV_REL:
                                if code == REL_X:
                                    pending_dx += int(value)
                                elif code == REL_Y:
                                    pending_dy += int(value)
                                elif code == REL_WHEEL and self._mouse_send_json and app_config.active_device:
                                    self._mouse_send_json({"type": "scroll", "dx": 0, "dy": int(value)})
                                elif code == REL_HWHEEL and self._mouse_send_json and app_config.active_device:
                                    self._mouse_send_json({"type": "scroll", "dx": int(value), "dy": 0})
                            elif etype == EV_KEY and value != 2:
                                # Mouse buttons
                                if code in (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE) and self._mouse_send_json and app_config.active_device:
                                    btn = {BTN_LEFT: "left", BTN_RIGHT: "right", BTN_MIDDLE: "middle"}[code]
                                    self._mouse_send_json({"type": "click", "button": btn, "pressed": value == 1})
                                    if moves < 5:
                                        print(f"[Input] evdev click {btn} pressed={value==1}")
                                else:
                                    # Keyboard keys
                                    name = KEYMAP.get(code) or US.get(code)
                                    if name and self.keyboard_socket and app_config.active_device:
                                        typ = "key_press" if value == 1 else "key_release"
                                        msg = json.dumps({"type": typ, "key": name}) + "\n"
                                        try:
                                            self.keyboard_socket.sendall(msg.encode())
                                        except Exception:
                                            pass
                            elif etype == EV_SYN:
                                # Sync: flush accumulated relative motion
                                if (pending_dx or pending_dy) and self._mouse_send_json and app_config.active_device:
                                    self._mouse_send_json({"type": "move", "dx": pending_dx, "dy": pending_dy})
                                    moves += 1
                                    if moves <= 5 or moves % 100 == 0:
                                        print(f"[Input] evdev move dx={pending_dx} dy={pending_dy} (#{moves})")
                                    pending_dx = 0
                                    pending_dy = 0
                    except BlockingIOError:
                        pass
                    except Exception:
                        pass
                # Flush any pending motion even without SYN (some devices)
                if (pending_dx or pending_dy) and self._mouse_send_json and app_config.active_device:
                    self._mouse_send_json({"type": "move", "dx": pending_dx, "dy": pending_dy})
                    moves += 1
                    pending_dx = 0
                    pending_dy = 0
            print(f"[Input] evdev keyboard+mouse reader stopped (moves={moves})")

        self._evdev_reader_thread = threading.Thread(target=reader_loop, daemon=True)
        self._evdev_reader_thread.start()

    def _stop_evdev_reader(self):
        stop = getattr(self, "_evdev_reader_stop", None)
        if stop is not None:
            try:
                stop.set()
            except Exception:
                pass
        t = getattr(self, "_evdev_reader_thread", None)
        if t is not None and t.is_alive():
            t.join(timeout=1.0)
        self._evdev_reader_stop = None
        self._evdev_reader_thread = None

    def _evdev_find_keyboards(self):
        """Return /dev/input/event* paths that report EV_KEY (keyboards)."""
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

    def _evdev_find_mice(self):
        """Return /dev/input/event* paths that report EV_REL (mice / trackpads)."""
        import glob
        import fcntl
        EV_REL = 0x02
        EVIOCGBIT_0 = 0x80204520
        devices = []
        for path in sorted(glob.glob("/dev/input/event*")):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                buf = bytearray(32)
                fcntl.ioctl(fd, EVIOCGBIT_0, buf)
                os.close(fd)
                if buf[EV_REL // 8] & (1 << (EV_REL % 8)):
                    devices.append(path)
            except Exception:
                pass
        return devices

    def _evdev_grab(self):
        """Open keyboard + mouse devices and EVIOCGRAB for exclusive ownership."""
        import fcntl
        import struct
        EVIOCGRAB = 0x40044590
        paths = list(dict.fromkeys(self._evdev_find_keyboards() + self._evdev_find_mice()))
        new_fds = []
        for path in paths:
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
            print(f"[evdev] Grabbed {len(new_fds)} input device(s) (kbd+mouse)")
            logging.info(f"[evdev] Grabbed {len(new_fds)} input device(s)")

    def _evdev_release(self):
        """Release exclusive grabs on all input devices (kbd + mouse)."""
        import fcntl
        import struct
        EVIOCGRAB = 0x40044590
        n = 0
        with self._evdev_grab_lock:
            fds = list(self._evdev_grab_fds)
            self._evdev_grab_fds = []
            for fd in fds:
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, struct.pack('i', 0))
                except Exception:
                    pass
                try:
                    os.close(fd)
                except Exception:
                    pass
                n += 1
        print(f"[evdev] Released {n} input device(s) — local mouse/keyboard restored")
        logging.info(f"[evdev] Released {n} input device(s)")

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
        """Accept tertiary connection (large data / clipboard images / files)"""
        print("[Server] Waiting for tertiary (large-data) connection on port", self.tertiary_port)
        ter_socket, ter_addr = self.tertiary_server_socket.accept()
        ter_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ter_socket.settimeout(1.0) # Prevent transition hangs
        print(f"[Server] Tertiary connection from: {ter_addr}")
        logging.info(f"[Connection] Tertiary connection from: {ter_addr}")
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
                    # Prefer the resolution-independent fraction (0.0-1.0) if
                    # the peer sent one; fall back to the old raw-pixel value
                    # (interpreted in OUR OWN screen space, which is wrong if
                    # the two machines differ in resolution, but matches the
                    # previous behaviour) only for compatibility with an
                    # older, unpatched client that doesn't send axis_fraction.
                    frac = evt.get("axis_fraction")
                    if frac is not None:
                        try:
                            frac = min(1.0, max(0.0, float(frac)))
                        except (TypeError, ValueError):
                            frac = None
                    if direction == "Right":
                        along = int(frac * self.screen_height) if frac is not None else evt.get("y", self.screen_height // 2)
                        return_pos = (self.screen_width - margin - warp_buffer, along)
                    elif direction == "Left":
                        along = int(frac * self.screen_height) if frac is not None else evt.get("y", self.screen_height // 2)
                        return_pos = (margin + warp_buffer, along)
                    elif direction == "Top":
                        along = int(frac * self.screen_width) if frac is not None else evt.get("x", self.screen_width // 2)
                        return_pos = (along, self.screen_height - margin - warp_buffer)
                    elif direction == "Bottom":
                        along = int(frac * self.screen_width) if frac is not None else evt.get("x", self.screen_width // 2)
                        return_pos = (along, margin + warp_buffer)
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
                        # Track a software cursor — do NOT read back hardware
                        # position (fails/stuck on Wayland). Apply relative
                        # deltas to our own running coordinates.
                        if not hasattr(self, "_client_cursor") or self._client_cursor is None:
                            self._client_cursor = [
                                max(0, (self.screen_width or 1920) // 2),
                                max(0, (self.screen_height or 1080) // 2),
                            ]
                        try:
                            dx = int(evt.get("dx", 0))
                            dy = int(evt.get("dy", 0))
                        except (TypeError, ValueError):
                            continue
                        # Clamp insane packets (unsigned-overflow leftovers etc.)
                        if abs(dx) > 300:
                            dx = 0
                        if abs(dy) > 300:
                            dy = 0
                        w = max(1, self.screen_width or 1920)
                        h = max(1, self.screen_height or 1080)
                        self._client_cursor[0] = max(0, min(w - 1, self._client_cursor[0] + dx))
                        self._client_cursor[1] = max(0, min(h - 1, self._client_cursor[1] + dy))
                        nx, ny = self._client_cursor[0], self._client_cursor[1]
                        try:
                            self.mouse_controller.position = (nx, ny)
                        except Exception as e:
                            print(f"[Client] mouse set failed: {e}")
                        if not hasattr(self, "_client_move_log"):
                            self._client_move_log = 0
                        self._client_move_log += 1
                        if self._client_move_log <= 5 or self._client_move_log % 200 == 0:
                            print(f"[Client] apply move dx={dx} dy={dy} -> ({nx},{ny}) #{self._client_move_log}")

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
                                        # Send the crossing point as a 0.0-1.0
                                        # FRACTION of this (client) machine's
                                        # own axis dimension, not a raw pixel
                                        # value - the server has a different
                                        # resolution/scale, so a raw pixel
                                        # coordinate from here doesn't mean
                                        # the same point over there. See the
                                        # matching fix on the server->client
                                        # direction in transition().
                                        if direction in ("Right", "Left"):
                                            axis_fraction = ny / float(h)
                                        else:
                                            axis_fraction = nx / float(w)
                                        axis_fraction = min(1.0, max(0.0, axis_fraction))
                                        msg = json.dumps({
                                            "type": "edge_return",
                                            "x": nx, "y": ny,  # kept for older-peer compatibility
                                            "axis_fraction": axis_fraction,
                                        }) + "\n"
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
            from pynput.keyboard import Key
            if not isinstance(key_str, str):
                return key_str
            # Canonical "Key.backspace" form
            if key_str.startswith("Key."):
                key_name = key_str.split(".", 1)[1].lower()
                # Aliases
                aliases = {"return": "enter", "escape": "esc", "super": "cmd", "meta": "cmd",
                           "control": "ctrl", "command": "cmd", "pageup": "page_up", "pagedown": "page_down"}
                key_name = aliases.get(key_name, key_name)
                try:
                    return getattr(Key, key_name)
                except AttributeError:
                    return key_name  # KeyboardController will map
            # Bare special names
            bare = key_str.lower()
            if bare in ("backspace", "enter", "tab", "esc", "space", "delete", "shift", "ctrl", "alt", "cmd",
                        "up", "down", "left", "right", "home", "end", "page_up", "page_down"):
                try:
                    return getattr(Key, bare)
                except AttributeError:
                    return bare
            # Single character
            if len(key_str) == 1:
                return key_str
            return key_str.lower()
        
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
                        # Place cursor on the entry edge when control arrives
                        if evt["value"]:
                            w = max(1, self.screen_width or 1920)
                            h = max(1, self.screen_height or 1080)
                            direction = getattr(app_config, "server_direction", "Right")
                            # Preserve the exact point the cursor crossed on
                            # the server, like a real side-by-side monitor,
                            # instead of always snapping to the center of the
                            # edge (the old behaviour). axis_fraction is a
                            # 0.0-1.0 fraction of the SERVER's own axis
                            # dimension at the moment of crossing, so we
                            # scale it by OUR OWN dimension here rather than
                            # using it as a raw pixel value - that's what
                            # keeps this correct across differing
                            # resolutions/scaling between the two machines.
                            frac = evt.get("axis_fraction")
                            try:
                                frac = min(1.0, max(0.0, float(frac))) if frac is not None else None
                            except (TypeError, ValueError):
                                frac = None
                            if direction == "Right":
                                along = int(frac * h) if frac is not None else h // 2
                                self._client_cursor = [30, along]
                            elif direction == "Left":
                                along = int(frac * h) if frac is not None else h // 2
                                self._client_cursor = [w - 30, along]
                            elif direction == "Top":
                                along = int(frac * w) if frac is not None else w // 2
                                self._client_cursor = [along, h - 30]
                            else:
                                along = int(frac * w) if frac is not None else w // 2
                                self._client_cursor = [along, 30]
                            try:
                                self.mouse_controller.position = tuple(self._client_cursor)
                            except Exception:
                                pass
                            print(f"[Client] cursor placed at entry {self._client_cursor}")
                        else:
                            self._client_cursor = None
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

