# transparent_overlay.py
import sys
from PyQt5 import QtWidgets, QtCore, QtGui

class TransparentOverlay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Frameless, always-on-top, and bypass window manager
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.X11BypassWindowManagerHint
        )

        # Fully transparent background
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)

        # Hide mouse cursor
        self.setCursor(QtCore.Qt.BlankCursor)

        # Fullscreen geometry
        screen_geometry = QtWidgets.QApplication.desktop().screenGeometry()
        self.setGeometry(screen_geometry)

    def paintEvent(self, event):
        # No painting = fully transparent. You can draw here if needed.
        pass

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    overlay = TransparentOverlay()
    overlay.showFullScreen()
    sys.exit(app.exec_())
