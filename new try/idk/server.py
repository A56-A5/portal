import socket
import time

HOST = '192.168.1.74'  # Replace with the IP of the client
PORT = 5000

def send_movement(sock, dx, dy):
    message = f"{dx},{dy}".encode()
    sock.sendall(message)

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', PORT))
        s.listen(1)
        print(f"[Server] Waiting for connection on port {PORT}...")
        conn, addr = s.accept()
        print(f"[Server] Connected to {addr}")

        try:
            while True:
                # Example pattern: move mouse in a square
                for dx, dy in [(10, 0), (0, 10), (-10, 0), (0, -10)]:
                    send_movement(conn, dx, dy)
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[Server] Exiting.")
        finally:
            conn.close()

if __name__ == "__main__":
    main()
