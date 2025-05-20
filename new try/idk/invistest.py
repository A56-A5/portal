# transparent_overlay.py
import sys
from PyQt5 import QtWidgets, QtCore, QtGui

class TransparentOverlay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Set window to full screen, transparent, and frameless
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.X11BypassWindowManagerHint  # Important for true transparency
        )

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)  # Makes it click-through

        # Optional: Full screen on all monitors
        screen_geometry = QtWidgets.QApplication.desktop().screenGeometry()
        self.setGeometry(screen_geometry)

    def paintEvent(self, event):
        # Optional: draw semi-transparent overlay
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 100))  # RGBA (black with 100 alpha)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    overlay = TransparentOverlay()
    overlay.showFullScreen()
    sys.exit(app.exec_())

