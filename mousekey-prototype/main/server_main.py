# main/server_main.py
from net.server import Server
from common.protocol import decode_event
from clipboard.clipboard_manager import apply_clipboard
from input.input_controller import handle_input_event

def handle_client(conn):
    while True:
        data = conn.receive()
        if not data:
            break
        event = decode_event(data)

        if event["type"] == "clipboard":
            apply_clipboard(event["data"])
        else:
            handle_input_event(event)

if __name__ == "__main__":
    Server().start(handle_client)
    print("[Server] Ready to receive input events.")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("[Server] Exiting.")
