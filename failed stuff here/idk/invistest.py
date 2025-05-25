import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QCursor, QGuiApplication

class TransparentMouseTracker(QWidget):
    def __init__(self):
        super().__init__()

        # Fullscreen and transparent
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.0)
        self.showFullScreen()

        # Hide the mouse cursor
        self.setCursor(Qt.BlankCursor)

        # Timer to continuously check mouse position
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.print_mouse_position)
        self.timer.start(100)  # every 100 ms

    def print_mouse_position(self):
        pos = QCursor.pos()
        print(f"Mouse position: ({pos.x()}, {pos.y()})")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tracker = TransparentMouseTracker()
    sys.exit(app.exec_())