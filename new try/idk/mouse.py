import platform
import socket
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
import pyautogui

pyautogui.FAILSAFE = False

PORT = 5000

# === Client code ===
def start_client(server_ip, status_label):
    def client_thread():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((server_ip, PORT))
            except Exception as e:
                status_label.config(text=f"Connection failed: {e}")
                return
            status_label.config(text=f"Connected to server: {server_ip}")

            try:
                while True:
                    data = s.recv(1024)
                    if not data:
                        break
                    try:
                        dx, dy = map(int, data.decode().split(","))
                        pyautogui.moveRel(dx, dy)
                    except Exception as e:
                        print(f"Parse error: {e}")
            except Exception as e:
                print(f"Client stopped: {e}")

            status_label.config(text="Disconnected from server")

    threading.Thread(target=client_thread, daemon=True).start()


# === Linux Server ===
def linux_server(client_ip, status_label):
    try:
        from evdev import InputDevice, list_devices, ecodes
    except ImportError:
        messagebox.showerror("Missing dependency", "Please install evdev: sudo pip3 install evdev")
        return

    def find_mouse():
        for path in list_devices():
            dev = InputDevice(path)
            if "mouse" in dev.name.lower() or "pointer" in dev.name.lower():
                return dev
        raise Exception("Mouse device not found")

    def server_thread():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((client_ip, PORT))
                status_label.config(text=f"Connected to client: {client_ip}")

                dev = find_mouse()
                dx, dy = 0, 0

                for event in dev.read_loop():
                    if event.type == ecodes.EV_REL:
                        if event.code == ecodes.REL_X:
                            dx = event.value
                        elif event.code == ecodes.REL_Y:
                            dy = event.value
                        if dx != 0 or dy != 0:
                            s.sendall(f"{dx},{dy}".encode())
                            dx, dy = 0, 0

        except Exception as e:
            status_label.config(text=f"Error: {e}")

    threading.Thread(target=server_thread, daemon=True).start()


# === Windows Server (polling cursor pos, no real raw input) ===
def windows_server(client_ip, status_label):
    import ctypes
    import ctypes.wintypes as wt
    import time

    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

    def get_cursor_pos():
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def server_thread():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((client_ip, PORT))
                status_label.config(text=f"Connected to client: {client_ip}")

                last_x, last_y = get_cursor_pos()
                while True:
                    x, y = get_cursor_pos()
                    dx, dy = x - last_x, y - last_y
                    if dx != 0 or dy != 0:
                        s.sendall(f"{dx},{dy}".encode())
                    last_x, last_y = x, y
                    time.sleep(0.01)
        except Exception as e:
            status_label.config(text=f"Error: {e}")

    threading.Thread(target=server_thread, daemon=True).start()


# === GUI ===
def main_gui():
    root = tk.Tk()
    root.title("Raw Mouse Streamer")

    tk.Label(root, text="Select Mode:").pack(pady=5)

    mode_var = tk.StringVar(value="client")

    tk.Radiobutton(root, text="Client", variable=mode_var, value="client").pack()
    tk.Radiobutton(root, text="Server", variable=mode_var, value="server").pack()

    status_label = tk.Label(root, text="Idle", fg="blue")
    status_label.pack(pady=10)

    def start():
        mode = mode_var.get()
        if mode == "client":
            server_ip = simpledialog.askstring("Server IP", "Enter Server IP:")
            if not server_ip:
                messagebox.showwarning("Input required", "Server IP is required")
                return
            status_label.config(text="Connecting to server...")
            start_client(server_ip, status_label)

        else:  # server
            client_ip = simpledialog.askstring("Client IP", "Enter Client IP:")
            if not client_ip:
                messagebox.showwarning("Input required", "Client IP is required")
                return
            status_label.config(text="Starting server...")

            os_name = platform.system().lower()
            if os_name == "linux":
                # Must run with sudo on linux to read evdev
                linux_server(client_ip, status_label)
            elif os_name == "windows":
                windows_server(client_ip, status_label)
            else:
                messagebox.showerror("Unsupported OS", f"OS {os_name} not supported")

    tk.Button(root, text="Start", command=start).pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main_gui()
