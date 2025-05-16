import platform
import pyautogui

def get_screen_size():
    return pyautogui.size()

def clamp(value, minv, maxv):
    return max(minv, min(value, maxv))
