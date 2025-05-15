from common.protocol import decode_event
from net.server import Server

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

if __name__ == "__main__":
    server = Server(port=24800)
    server.start(handle_client)

    print("[Server] Running...")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("[Server] Stopping...")
