# server_main.py
from common.protocol import decode_event
from screen.edge_detector import EdgeMonitor
from net.server import Server
from input.input_controller import handle_input_event
import pickle
import threading

server = Server(port=5051)
monitor = None
mouse_on_client = False
lock = threading.Lock()

def handle_client(conn):
    buffer = ""

    while True:
        try:
            data = conn.receive().decode('utf-8')
            if not data:
                break

            buffer += data
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if line.strip():
                    event = decode_event(line)
                    # Apply event from client
                    handle_input_event(event)

        except Exception as e:
            print(f"[Server] Error: {e}")
            break

    conn.close()
    print("[Server] Client disconnected")

def on_edge(direction):
    global mouse_on_client
    with lock:
        if not mouse_on_client:
            print(f"[Server] Edge detected: {direction}")
            server.broadcast(pickle.dumps({"type": "switch", "edge": direction}))
            mouse_on_client = True

def listen_for_return():
    """ Continuously check if mouse returns to this screen """
    import time
    from screen.edge_detector import get_mouse_position, get_screen_size

    while True:
        if mouse_on_client:
            x, y = get_mouse_position()
            screen_width, screen_height = get_screen_size()
            if 100 < x < screen_width - 100:  # Mouse is clearly inside screen
                with lock:
                    print("[Server] Mouse returned from client")
                    mouse_on_client = False
        time.sleep(0.1)

if __name__ == "__main__":
    monitor = EdgeMonitor(on_edge_callback=on_edge)
    monitor.start()

    threading.Thread(target=listen_for_return, daemon=True).start()

    server.start(handle_client)
    print("[Server] Running...")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("[Server] Stopping...")
