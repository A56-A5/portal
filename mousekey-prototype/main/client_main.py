# main/client_main.py
from net.client import Client
from clipboard.clipboard_manager import watch_clipboard
from input.input_listener import InputListener
from common.protocol import encode_event

if __name__ == "__main__":
    client = Client(server_ip='127.0.0.1')  # Change this dynamically via GUI or env
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
