import socket
import pyautogui

HOST = '0.0.0.0'
PORT = 5000

def apply_movement(dx, dy):
    pyautogui.moveRel(dx, dy)

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(('SERVER_IP', PORT))  # Replace with the IP of the server
        print(f"[Client] Connected to server on port {PORT}")

        try:
            while True:
                data = s.recv(1024)
                if not data:
                    break
                try:
                    dx, dy = map(int, data.decode().split(','))
                    apply_movement(dx, dy)
                except ValueError:
                    print(f"[Client] Invalid data: {data}")
        except KeyboardInterrupt:
            print("\n[Client] Exiting.")

if __name__ == "__main__":
    main()
