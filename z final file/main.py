import subprocess
import time
import sys
from config import app_config

# Map config keys to script filenames
script_map = {
    "logs_viewer": "logs_viewer.py",
    "Share_input": "share.py",
    "Audio_input": "audio.py",
}

# Track running processes
processes = {
    "logs_viewer": None,
    "Share_input": None,
    "Audio_input": None,
}

# Start portal_ui.py
portal_process = subprocess.Popen([sys.executable, "portal_ui.py"])
print("Started portal_ui.py")

def start_process(key):
    if processes[key] is None or processes[key].poll() is not None:
        processes[key] = subprocess.Popen([sys.executable, script_map[key]])
        print(f"Started {script_map[key]}")

def stop_process(key):
    proc = processes[key]
    if proc is not None and proc.poll() is None:
        proc.terminate()
        print(f"Terminated {script_map[key]}")
        processes[key] = None

try:
    while True:
        # Exit if portal_ui.py dies
        if portal_process.poll() is not None:
            print("portal_ui.py exited. Terminating all other scripts.")
            for key in processes:
                stop_process(key)
            break

        # Dynamically reload config
        app_config.load()

        for key in processes:
            should_run = app_config.config.get(key, False)
            if should_run:
                start_process(key)
            else:
                stop_process(key)

        time.sleep(1)

except KeyboardInterrupt:
    print("Interrupted. Terminating all processes.")
    portal_process.terminate()
    for key in processes:
        stop_process(key)
