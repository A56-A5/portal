import platform

if platform.system() == "Windows":
    import ctypes

    def apply_mouse_position(x, y):
        ctypes.windll.user32.SetCursorPos(x, y)
else:
    from Xlib import display

    def apply_mouse_position(x, y):
        d = display.Display()
        s = d.screen()
        root = s.root
        root.warp_pointer(x, y)
        d.sync()
