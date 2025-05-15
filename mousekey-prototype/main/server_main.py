from common.protocol import decode_event
from screen.edge_detector import EdgeMonitor
from net.server import Server
import pickle

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
                    # Do something with the event, like:
                    print("[Server] Received:", event)

        except Exception as e:
            print(f"[Server] Error: {e}")
            break

    conn.close()
    print("[Server] Client disconnected")

def on_edge(direction):
    print(f"[Server] Edge detected: {direction}")
    # Send dummy mouse switch event
    server.broadcast(pickle.dumps({"type": "switch", "edge": direction}))

if __name__ == "__main__":
    server = Server(port=5051)
    monitor = EdgeMonitor(on_edge_callback=on_edge)
    monitor.start()
    server.start(handle_client)

    print("[Server] Running...")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("[Server] Stopping...")
