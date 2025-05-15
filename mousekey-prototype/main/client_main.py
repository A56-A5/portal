# main/client_main.py
from net.client import Client
from clipboard.clipboard_manager import watch_clipboard
from input.input_listener import InputListener
from common.protocol import encode_event
from input.mouse_handler import apply_mouse_position
import sys
import pickle
import platform
import threading

# Platform-specific screen width getter
if platform.system() == "Windows":
    import ctypes

    def get_screen_width():
        return ctypes.windll.user32.GetSystemMetrics(0)
else:
    from Xlib import display

    def get_screen_width():
        d = display.Display()
        screen = d.screen()
        return screen.width_in_pixels

# Thread function to receive events from the server
def receive_events(client):
    while True:
        data = client.receive()
        if not data:
            continue
        try:
            event = pickle.loads(data)
            if event.get("type") == "switch":
                print(f"[Client] Mouse switched from: {event['edge']}")
                if event['edge'] == "right":
                    apply_mouse_position(0, 100)
                elif event['edge'] == "left":
                    screen_width = get_screen_width()
                    apply_mouse_position(screen_width - 1, 100)
        except Exception as e:
            print(f"[Client] Error processing data: {e}")

# Main program
if __name__ == "__main__":
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    client = Client(server_ip=server_ip)
    client.connect()

    print("[Client] Starting input and clipboard listeners...")

    # Start receiving events in a background thread
    threading.Thread(target=receive_events, args=(client,), daemon=True).start()

    # Start mouse/keyboard listener
    listener = InputListener(send_callback=client.send)
    listener.start()

    # Start clipboard watcher
    watch_clipboard(lambda event: client.send(encode_event(event)))

    print("[Client] Sending input & clipboard events...")
    try:
        while True:
            pass  # Keeps the main thread alive
    except KeyboardInterrupt:
        client.close()
