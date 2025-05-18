import platform
import socket
import threading
import pyautogui

# === Configuration ===
IS_SERVER = True  # Change to False on the client
TARGET_IP = "CLIENT_OR_SERVER_IP"
PORT = 5000

# === Client Code (same for all OS) ===
def start_client():
    pyautogui.FAILSAFE = False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", PORT))
        s.listen(1)
        print("[Client] Waiting for connection...")
        conn, addr = s.accept()
        print(f"[Client] Connected to {addr}")

        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                try:
                    dx, dy = map(int, data.decode().split(','))
                    pyautogui.moveRel(dx, dy)
                except Exception as e:
                    print(f"[Client] Parse error: {e}")
        except KeyboardInterrupt:
            print("[Client] Stopped.")


# === Linux Server: Use evdev ===
def linux_server():
    from evdev import InputDevice, categorize, ecodes, list_devices

    def find_mouse():
        for path in list_devices():
            dev = InputDevice(path)
            if "mouse" in dev.name.lower() or "pointer" in dev.name.lower():
                print(f"[Linux] Using device: {dev.name} at {path}")
                return dev
        raise Exception("Mouse device not found.")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((TARGET_IP, PORT))
        print("[Linux Server] Connected to client.")
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


# === Windows Server: Use Raw Input Hook ===
def windows_server():
    import ctypes
    import ctypes.wintypes as wt
    import threading

    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

    class RawMouseHook:
        def __init__(self):
            self.last_pos = self.get_pos()
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((TARGET_IP, PORT))
            print("[Windows Server] Connected to client.")

        def get_pos(self):
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y

        def poll_loop(self):
            print("[Windows Server] Polling mouse deltas...")
            while True:
                x, y = self.get_pos()
                dx = x - self.last_pos[0]
                dy = y - self.last_pos[1]
                if dx != 0 or dy != 0:
                    self.sock.sendall(f"{dx},{dy}".encode())
                self.last_pos = (x, y)

    RawMouseHook().poll_loop()


# === Entrypoint ===
def main():
    os_name = platform.system().lower()
    if IS_SERVER:
        print(f"[Mode] Server | OS Detected: {os_name}")
        if os_name == "linux":
            linux_server()
        elif os_name == "windows":
            windows_server()
        else:
            print("[Error] Unsupported server OS")
    else:
        print("[Mode] Client")
        start_client()

if __name__ == "__main__":
    main()
