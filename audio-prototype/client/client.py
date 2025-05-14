import socket
import subprocess
import re

SERVER_IP = '192.168.1.70'  # Replace this
PORT = 50007
CHUNK_SIZE = 4096

def get_default_monitor():
    # Get the default sink
    result = subprocess.run(["pactl", "get-default-sink"], stdout=subprocess.PIPE, text=True)
    default_sink = result.stdout.strip()
    if not default_sink:
        raise RuntimeError("Could not determine default audio sink.")

    # Monitor source is typically sink + ".monitor"
    return f"{default_sink}.monitor"

def main():
    monitor_source = get_default_monitor()
    print(f"Using monitor source: {monitor_source}")

    parec_cmd = ["parec", "--format=s16le", "--rate=44100", "--channels=1", "-d", monitor_source]

    s = socket.socket()
    s.connect((SERVER_IP, PORT))
    print("Connected to server.")

    proc = subprocess.Popen(parec_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = proc.stdout.read(CHUNK_SIZE)
            if not data:
                break
            s.sendall(data)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        proc.terminate()
        s.close()

if __name__ == "__main__":
    main()
