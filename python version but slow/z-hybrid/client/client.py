import platform
import ctypes
import os
from common import protocol

if platform.system() == "Windows":
    lib = ctypes.CDLL(os.path.abspath("client/inject/build/win_mouse.dll"))
elif platform.system() == "Linux":
    lib = ctypes.CDLL(os.path.abspath("client/inject/build/linux_mouse.so"))
else:
    raise RuntimeError("Unsupported platform")

lib.move_mouse_by.argtypes = [ctypes.c_int, ctypes.c_int]

sock = protocol.create_receiver()
print("🟢 Client receiving mouse movement...")

while True:
    data, _ = sock.recvfrom(8)
    dx, dy = struct.unpack("!ii", data)
    lib.move_mouse_by(dx, dy)
