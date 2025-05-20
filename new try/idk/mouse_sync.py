import platform
import subprocess
import sys
import os

def main():
    os_type = platform.system()
    
    if os_type == "Windows":
        target = "windows_invis.py"
    elif os_type == "Linux":
        target = "linux_invis.py"
    else:
        print(f"Unsupported OS: {os_type}")
        sys.exit(1)

    print(f"Running {target}...")
    subprocess.run([sys.executable, target])

if __name__ == "__main__":
    main()
