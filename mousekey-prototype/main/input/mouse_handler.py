import pyautogui

def send_mouse_position(x, y):
    return {"type": "mouse", "x": x, "y": y}

def apply_mouse_position(x, y):
    pyautogui.moveTo(x, y)
