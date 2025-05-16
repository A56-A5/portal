import tkinter as tk
from tkinter import ttk, messagebox
import threading
import socket
import pyautogui
import time

class ClientApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Barrier Prototype - Client")
        self.geometry("350x180")
        self.resizable(False, False)

        self.sock = None
        self.running = False

        self.screen_width, self.screen_height = pyautogui.size()
        self.local_x, self.local_y = pyautogui.position()

        self.server_ip = tk.StringVar()
        self.status_text = tk.StringVar(value="Client stopped")

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(pady=20, padx=20)

        ttk.Label(frame, text="Server IP:").grid(row=0, column=0, sticky=tk.W)
        self.ip_entry = ttk.Entry(frame, textvariable=self.server_ip, width=25)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        self.start_btn = ttk.Button(btn_frame, text="Start Client", command=self.start_client)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = ttk.Button(btn_frame, text="Stop Client", command=self.stop_client, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        self.status_label = ttk.Label(self, textvariable=self.status_text)
        self.status_label.pack(pady=5)

    def start_client(self):
        if self.running:
            return
        ip = self.server_ip.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter server IP")
            return
        self.running = True
        self.status_text.set("Connecting...")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        threading.Thread(target=self.client_main, args=(ip,), daemon=True).start()

    def stop_client(self):
        self.running = False
        self.status_text.set("Client stopped")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    def clamp(self, val, minv, maxv):
        return max(minv, min(val, maxv))

    def receive_and_move(self, sock):
        buffer = ""
        while self.running:
            try:
                data = sock.recv(1024)
                if not data:
                    self.status_text.set("Server disconnected")
                    break
                buffer += data.decode()
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if "," in line:
                        try:
                            dx, dy = map(int, line.split(","))
                        except:
                            continue

                        self.local_x = self.clamp(self.local_x + dx, 0, self.screen_width - 1)
                        self.local_y = self.clamp(self.local_y + dy, 0, self.screen_height - 1)
                        pyautogui.moveTo(self.local_x, self.local_y)

                        # Release control back if at edge
                        if (self.local_x == 0 and dx < 0) or (self.local_x == self.screen_width - 1 and dx > 0) or \
                           (self.local_y == 0 and dy < 0) or (self.local_y == self.screen_height - 1 and dy > 0):
                            try:
                                sock.sendall(b"release\n")
                                self.status_text.set("Released control back to server")
                            except:
                                pass
            except Exception as e:
                self.status_text.set(f"Error: {e}")
                break

        self.running = False
        self.stop_client()

    def client_main(self, ip):
        PORT = 65432
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((ip, PORT))
            self.status_text.set(f"Connected to server {ip}:{PORT}")

            self.local_x, self.local_y = pyautogui.position()

            self.receive_and_move(self.sock)

        except Exception as e:
            self.status_text.set(f"Connection failed: {e}")
            self.running = False
            self.stop_client()

if __name__ == "__main__":
    app = ClientApp()
    app.mainloop()
