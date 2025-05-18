# restore.py
import ctypes
import os
import subprocess

def restore_registry():
    reg_file = os.path.abspath("original_cursors.reg")
    if not os.path.exists(reg_file):
        print("Missing original_cursors.reg!")
        return False
    subprocess.run(["reg", "import", reg_file], shell=True)
    ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)  # Apply restored cursors
    return True

if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("Please run this script as administrator.")
    elif restore_registry():
        print("Original cursors restored successfully.")
    else:
        print("Cursor restore failed.")
