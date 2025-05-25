import socket
import threading
import pyautogui
import platform
import time

SERVER_IP = input("Enter server IP: ")
SERVER_PORT = 65432

# Screen size
screen_width, screen_height = pyautogui.size()

# Current cursor pos on client
local_x, local_y = pyautogui.position()

def clamp(value, minv, maxv):
    return max(minv, min(value, maxv))

def receive_and_move(sock):
    global local_x, local_y

    buffer = ""
    while True:
        data = sock.recv(1024)
        if not data:
            print("Server disconnected")
            break

        buffer += data.decode()
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if "," in line:
                try:
                    dx, dy = map(int, line.split(","))
                except:
                    continue

                # Move client cursor relative to current pos
                local_x = clamp(local_x + dx, 0, screen_width - 1)
                local_y = clamp(local_y + dy, 0, screen_height - 1)
                pyautogui.moveTo(local_x, local_y)

                # If cursor at edge, release control back to server
                if (local_x == 0 and dx < 0) or (local_x == screen_width - 1 and dx > 0) or \
                   (local_y == 0 and dy < 0) or (local_y == screen_height - 1 and dy > 0):
                    try:
                        sock.sendall(b"release\n")
                        print("Released control back to server")
                    except:
                        pass

def client_main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, SERVER_PORT))
    print(f"Connected to server at {SERVER_IP}:{SERVER_PORT}")

    recv_thread = threading.Thread(target=receive_and_move, args=(sock,), daemon=True)
    recv_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sock.close()

if __name__ == "__main__":
    client_main()
