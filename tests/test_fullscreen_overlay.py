import sys
import os
import time
import glob
import fcntl
import struct
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPalette

os.environ["QT_QPA_PLATFORM"] = "xcb"

EVIOCGRAB = 0x40044590
EVIOCGBIT_0 = 0x80204520
EV_KEY = 0x01


def find_evdev_keyboards():
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


def grab_evdev_keyboards():
    fds = []
    for path in find_evdev_keyboards():
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            fcntl.ioctl(fd, EVIOCGRAB, struct.pack("i", 1))
            fds.append(fd)
        except Exception as e:
            try:
                os.close(fd)
            except Exception:
                pass
    return fds


def release_evdev_keyboards(fds):
    for fd in fds:
        try:
            fcntl.ioctl(fd, EVIOCGRAB, struct.pack("i", 0))
            os.close(fd)
        except Exception:
            pass


def apply_wm_rules():
    """Apply Hyprland rules including opacity 0.0 override for 100% transparency."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        rules = [
            "float 1, match:title portal-overlay-test",
            "fullscreen 1, match:title portal-overlay-test",
            "pin 1, match:title portal-overlay-test",
            "opacity 0.0 override 0.0 override, match:title portal-overlay-test",
        ]
        for rule in rules:
            res = subprocess.run(
                ["hyprctl", "keyword", "windowrule", rule],
                capture_output=True,
                text=True,
            )
            print(f"[HYPRCTL RULE] {rule} -> {res.stdout.strip() or res.stderr.strip()}")


class FullscreenOverlayTest(QWidget):
    def __init__(self, screen_geom):
        super().__init__()
        self.setWindowTitle("portal-overlay-test")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")
        
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0, 0))
        self.setPalette(palette)
        
        self.setCursor(Qt.BlankCursor)
        self.setGeometry(0, 0, screen_geom.width(), screen_geom.height())
        self.setMouseTracking(True)
        self.move_count = 0

    def keyPressEvent(self, event):
        print(f"[TEST MOUSE/KEY] Key press intercepted: key={event.key()}, text={event.text()!r}")
        event.accept()

    def keyReleaseEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        self.move_count += 1
        event.accept()

    def mousePressEvent(self, event):
        print(f"[TEST MOUSE] Click press intercepted: button={event.button()}")
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()


def main():
    app = QApplication(sys.argv)
    primary = app.primaryScreen()
    screen_geom = primary.geometry()

    print("=== Fullscreen Overlay Transparency Test Starting ===")
    print(f"Primary Screen Geometry: {screen_geom.x()},{screen_geom.y()} {screen_geom.width()}x{screen_geom.height()}")

    apply_wm_rules()
    evdev_fds = grab_evdev_keyboards()
    print(f"[EVDEV] Grabbed {len(evdev_fds)} keyboard device(s)")

    overlay = FullscreenOverlayTest(screen_geom)
    overlay.showFullScreen()
    overlay.raise_()
    overlay.activateWindow()

    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    actual_geom = overlay.geometry()
    mouse_grabber = QWidget.mouseGrabber()
    keyboard_grabber = QWidget.keyboardGrabber()

    print("\n--- Diagnostics ---")
    print(f"Actual Window Geometry: {actual_geom.x()},{actual_geom.y()} {actual_geom.width()}x{actual_geom.height()}")
    print(f"Mouse Grabber: {mouse_grabber == overlay}")
    print(f"Keyboard Grabber: {keyboard_grabber == overlay}")
    print("Hyprland opacity rule set to 0.0 override.")
    print("-------------------\n")

    def cleanup_and_exit():
        print("10s timer expired. Exiting test...")
        release_evdev_keyboards(evdev_fds)
        overlay.close()
        app.quit()

    QTimer.singleShot(10000, cleanup_and_exit)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
