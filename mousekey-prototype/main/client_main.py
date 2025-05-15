# main/client_main.py
from net.client import Client
from clipboard.clipboard_manager import watch_clipboard
from input.input_listener import InputListener
from common.protocol import encode_event
import sys

if __name__ == "__main__":
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    client = Client(server_ip=server_ip)
    client.connect()

    listener = InputListener(send_callback=client.send)
    listener.start()

    watch_clipboard(lambda event: client.send(encode_event(event)))

    print("[Client] Sending input & clipboard events...")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        client.close()
