import os
import platform
import subprocess

def build():
    os.makedirs("build", exist_ok=True)
    system = platform.system()

    if system == "Windows":
        subprocess.run([
            "gcc", "-shared", "-o", "build/win_mouse.dll", "win_mouse.c"
        ])
        print("✅ Built Windows DLL")
    elif system == "Linux":
        subprocess.run([
            "gcc", "-shared", "-fPIC", "-o", "build/linux_mouse.so", "linux_mouse.c", "-lX11", "-lXtst"
        ])
        print("✅ Built Linux SO")
    else:
        print("Unsupported platform")

if __name__ == "__main__":
    build()
