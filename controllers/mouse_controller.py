"""
Mouse Controller - Handles mouse input and position control
"""
import platform
import subprocess

class MouseController:
    def __init__(self):
        self.os_type = platform.system().lower()
        from pynput.mouse import Controller as PynputController
        self._controller = PynputController()
        
        # Import win32api only on Windows
        self._win32api = None
        self.use_xdotool = False
        if self.os_type == "windows":
            try:
                import win32api
                self._win32api = win32api
            except ImportError:
                pass
        elif self.os_type == "linux":
            try:
                res = subprocess.run(["which", "xdotool"], capture_output=True)
                self.use_xdotool = res.returncode == 0
            except Exception:
                self.use_xdotool = False
    
    @property
    def position(self):
        """Get current mouse position"""
        return self._controller.position
    
    @position.setter
    def position(self, pos):
        """Set mouse position"""
        if self.os_type == "windows" and self._win32api:
            try:
                self._win32api.SetCursorPos(pos)
            except Exception:
                self._controller.position = pos
        elif self.os_type == "linux" and self.use_xdotool:
            try:
                x, y = int(pos[0]), int(pos[1])
                subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=False)
            except Exception:
                self._controller.position = pos
        else:
            self._controller.position = pos
    
    def press(self, button):
        """Press mouse button"""
        self._controller.press(button)
    
    def release(self, button):
        """Release mouse button"""
        self._controller.release(button)
    
    def click(self, button):
        """Click mouse button"""
        self._controller.click(button)
    
    def scroll(self, dx, dy):
        """Scroll mouse"""
        self._controller.scroll(dx, dy)
