import tkinter as tk
import threading
import pyautogui
import random
import keyboard
import ctypes
import platform
import time

# OS-specific mouse lock (just moves it back to a position repeatedly)
def lock_real_mouse(x, y):
    def lock_loop():
        while not stop_flag[0]:
            pyautogui.moveTo(x, y)
            time.sleep(0.01)
    t = threading.Thread(target=lock_loop, daemon=True)
    t.start()

# Virtual mouse movement loop
def move_virtual_mouse(dot, screen_w, screen_h):
    x, y = 100, 100
    dx, dy = 5, 3

    while not stop_flag[0]:
        x += dx
        y += dy

        # Bounce off edges
        if x <= 0 or x >= screen_w:
            dx *= -1
        if y <= 0 or y >= screen_h:
            dy *= -1

        dot.place(x=x, y=y)
        time.sleep(0.01)

# Main GUI App
def run_virtual_mouse():
    screen_w, screen_h = pyautogui.size()

    root = tk.Tk()
    root.title("Virtual Mouse Overlay")
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", "white")  # Makes white color transparent
    root.configure(bg='white')  # Full transparent background

    # Create red dot as virtual mouse
    dot = tk.Label(root, bg="red", width=2, height=1)
    dot.place(x=100, y=100)

    # Lock real mouse to center
    center_x, center_y = screen_w // 2, screen_h // 2
    pyautogui.moveTo(center_x, center_y)
    lock_real_mouse(center_x, center_y)

    # Start virtual mouse thread
    threading.Thread(target=move_virtual_mouse, args=(dot, screen_w, screen_h), daemon=True).start()

    # Listen for ESC key to exit
    def check_exit():
        if keyboard.is_pressed('esc'):
            stop_flag[0] = True
            root.destroy()
        else:
            root.after(100, check_exit)

    root.after(100, check_exit)
    root.mainloop()

# Global flag to stop threads
stop_flag = [False]

if __name__ == "__main__":
    run_virtual_mouse()
