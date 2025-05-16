import socket
import threading
import sys
import time
import platform
import pyautogui
from barrier.mousekey3.gui.common import get_screen_size, clamp

# Server config
HOST = '0.0.0.0'
PORT = 65432

# Client position relative to server screen edge
# Options: 'left', 'right', 'top', 'bottom'
CLIENT_POSITION = 'right'

# Communication
conn = None
conn_lock = threading.Lock()

# Screen size
screen_width, screen_height = get_screen_size()

# Local cursor position cache
local_x, local_y = pyautogui.position()

# Control state
control_with_client = False

def send_deltas(dx, dy):
    global conn
    data = f"{dx},{dy}\n".encode()
    with conn_lock:
        if conn:
            try:
                conn.sendall(data)
            except Exception as e:
                print(f"Send error: {e}")
                conn = None

# Cross-platform raw mouse listener
if platform.system() == 'Windows':
    # Import Windows raw input listener
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    WM_INPUT = 0x00FF
    RIDEV_INPUTSINK = 0x00000100
    RID_INPUT = 0x10000003
    RIM_TYPEMOUSE = 0

    class RAWINPUTDEVICE(ctypes.Structure):
        _fields_ = [
            ("usUsagePage", ctypes.c_ushort),
            ("usUsage", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("hwndTarget", ctypes.wintypes.HWND),
        ]

    class RAWINPUTHEADER(ctypes.Structure):
        _fields_ = [
            ("dwType", ctypes.c_ulong),
            ("dwSize", ctypes.c_ulong),
            ("hDevice", ctypes.wintypes.HANDLE),
            ("wParam", ctypes.wintypes.WPARAM),
        ]

    class RAWMOUSE(ctypes.Structure):
        _fields_ = [
            ("usFlags", ctypes.c_ushort),
            ("ulButtons", ctypes.c_ulong),
            ("usButtonFlags", ctypes.c_ushort),
            ("usButtonData", ctypes.c_ushort),
            ("ulRawButtons", ctypes.c_ulong),
            ("lLastX", ctypes.c_long),
            ("lLastY", ctypes.c_long),
            ("ulExtraInformation", ctypes.c_ulong),
        ]

    class RAWINPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mouse", RAWMOUSE)]
        _fields_ = [
            ("header", RAWINPUTHEADER),
            ("data", _U),
        ]

    def register_raw_input(hwnd):
        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01
        rid.usUsage = 0x02
        rid.dwFlags = RIDEV_INPUTSINK
        rid.hwndTarget = hwnd

        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
            raise ctypes.WinError()

    def get_raw_input_data(lparam):
        dwSize = ctypes.wintypes.UINT()
        user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER))
        buffer = ctypes.create_string_buffer(dwSize.value)
        user32.GetRawInputData(lparam, RID_INPUT, buffer, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER))
        raw = RAWINPUT.from_buffer_copy(buffer)
        return raw

    def wndproc(hwnd, msg, wparam, lparam):
        global local_x, local_y, control_with_client

        if msg == WM_INPUT:
            raw = get_raw_input_data(lparam)
            if raw.header.dwType == RIM_TYPEMOUSE:
                dx = raw.data.mouse.lLastX
                dy = raw.data.mouse.lLastY

                if dx != 0 or dy != 0:
                    if not control_with_client:
                        # Check if cursor at edge based on CLIENT_POSITION
                        at_edge = False
                        if CLIENT_POSITION == 'right' and local_x >= screen_width - 1 and dx > 0:
                            at_edge = True
                        elif CLIENT_POSITION == 'left' and local_x <= 0 and dx < 0:
                            at_edge = True
                        elif CLIENT_POSITION == 'top' and local_y <= 0 and dy < 0:
                            at_edge = True
                        elif CLIENT_POSITION == 'bottom' and local_y >= screen_height -1 and dy > 0:
                            at_edge = True

                        if at_edge:
                            control_with_client = True
                            print("Control moved to client")
                            send_deltas(dx, dy)
                        else:
                            # Move local cursor
                            local_x = clamp(local_x + dx, 0, screen_width -1)
                            local_y = clamp(local_y + dy, 0, screen_height -1)
                            pyautogui.moveTo(local_x, local_y)
                    else:
                        # We are controlling client now, send deltas
                        send_deltas(dx, dy)

            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    import threading

    def create_window_and_listen():
        WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)

        hInstance = user32.GetModuleHandleW(None)
        className = "RawInputWindow"

        wndClass = ctypes.wintypes.WNDCLASS()
        wndClass.lpfnWndProc = WNDPROCTYPE(wndproc)
        wndClass.lpszClassName = className
        wndClass.hInstance = hInstance

        atom = user32.RegisterClassW(ctypes.byref(wndClass))
        if not atom:
            raise ctypes.WinError()

        hwnd = user32.CreateWindowExW(0, className, "Raw Input", 0, 0, 0, 0, 0, 0, 0, hInstance, None)
        if not hwnd:
            raise ctypes.WinError()

        register_raw_input(hwnd)

        msg = ctypes.wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

else:
    # Linux (or other) fallback: use pynput relative movement
    from pynput import mouse

    def on_move(x, y):
        # Calculate relative movement compared to cached local pos
        global local_x, local_y, control_with_client

        dx = x - local_x
        dy = y - local_y

        if dx == 0 and dy == 0:
            return

        screen_width, screen_height = get_screen_size()

        if not control_with_client:
            at_edge = False
            if CLIENT_POSITION == 'right' and local_x >= screen_width - 1 and dx > 0:
                at_edge = True
            elif CLIENT_POSITION == 'left' and local_x <= 0 and dx < 0:
                at_edge = True
            elif CLIENT_POSITION == 'top' and local_y <= 0 and dy < 0:
                at_edge = True
            elif CLIENT_POSITION == 'bottom' and local_y >= screen_height - 1 and dy > 0:
                at_edge = True

            if at_edge:
                control_with_client = True
                print("Control moved to client")
                send_deltas(dx, dy)
            else:
                local_x = clamp(x, 0, screen_width - 1)
                local_y = clamp(y, 0, screen_height - 1)
        else:
            send_deltas(dx, dy)

    listener = mouse.Listener(on_move=on_move)

def handle_client(client_socket):
    global conn
    conn = client_socket
    print(f"Client connected from {client_socket.getpeername()}")

    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                print("Client disconnected")
                break

            # Expect client to send "release" message when it wants control back
            msg = data.decode().strip()
            if msg == "release":
                global control_with_client
                control_with_client = False
                print("Control returned to server")
    except Exception as e:
        print(f"Client connection error: {e}")
    finally:
        with conn_lock:
            conn = None
        client_socket.close()

def server_main():
    global local_x, local_y

    local_x, local_y = pyautogui.position()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    print(f"Server listening on {HOST}:{PORT}")

    client_socket, addr = server_socket.accept()
    client_thread = threading.Thread(target=handle_client, args=(client_socket,), daemon=True)
    client_thread.start()

    if platform.system() == 'Windows':
        create_window_and_listen()
    else:
        listener.start()
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            listener.stop()

if __name__ == "__main__":
    server_main()
