import json
import threading
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                             QLineEdit, QPushButton, QLabel, QGroupBox, 
                             QRadioButton, QHBoxLayout, QMessageBox)
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController
import pyperclip
import platform
import ctypes
import socket
import sys

class Communicate(QObject):
    status_signal = pyqtSignal(str, str)

class InputSharingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cross-Platform Input Sharing")
        self.setGeometry(100, 100, 400, 300)
        
        # Network settings
        self.server_ip = ""
        self.server_port = 5555
        self.client_socket = None
        self.server_socket = None
        self.running = False
        self.role = "server"
        self.connection_active = False
        self.last_message_time = time.time()
        
        # Screen edge configuration
        self.client_side = "right"
        
        # Input controllers
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.remote_control_active = False
        
        # Comm signal
        self.comm = Communicate()
        self.comm.status_signal.connect(self.show_status)
        
        # UI
        self.init_ui()
        
        # Clipboard monitor
        self.last_clipboard_content = ""
        self.clipboard_monitor_thread = None
        self.clipboard_monitor_active = False
        
        # Screen size
        self.screen_width, self.screen_height = self.get_screen_size()
        
    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # Role selection
        role_group = QGroupBox("Device Role")
        role_layout = QHBoxLayout()
        self.server_radio = QRadioButton("Server")
        self.client_radio = QRadioButton("Client")
        self.server_radio.setChecked(True)
        role_layout.addWidget(self.server_radio)
        role_layout.addWidget(self.client_radio)
        role_group.setLayout(role_layout)
        
        # IP input
        self.ip_label = QLabel("Server IP:")
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("Enter server IP address")
        
        # Side config
        side_group = QGroupBox("Client Screen Position (Server Only)")
        side_layout = QHBoxLayout()
        self.left_radio = QRadioButton("Left")
        self.right_radio = QRadioButton("Right")
        self.top_radio = QRadioButton("Top")
        self.bottom_radio = QRadioButton("Bottom")
        self.right_radio.setChecked(True)
        side_layout.addWidget(self.left_radio)
        side_layout.addWidget(self.right_radio)
        side_layout.addWidget(self.top_radio)
        side_layout.addWidget(self.bottom_radio)
        side_group.setLayout(side_layout)
        
        # Buttons
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        
        # Layout assemble
        layout.addWidget(role_group)
        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_input)
        layout.addWidget(side_group)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        
        self.server_radio.toggled.connect(self.update_role)
        self.start_btn.clicked.connect(self.start_sharing)
        self.stop_btn.clicked.connect(self.stop_sharing)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
    def update_role(self, checked):
        if checked:
            self.role = "server"
            self.ip_label.setText("Server IP:")
        else:
            self.role = "client"
            self.ip_label.setText("Server IP to connect:")
            
    def start_sharing(self):
        self.server_ip = self.ip_input.text().strip()
        if self.role == "client" and not self.server_ip:
            self.show_status("Error", "Please enter server IP address")
            return
        
        # side
        if self.left_radio.isChecked(): self.client_side="left"
        elif self.right_radio.isChecked(): self.client_side="right"
        elif self.top_radio.isChecked(): self.client_side="top"
        else: self.client_side="bottom"
        
        self.running = True
        if self.role=="server":
            threading.Thread(target=self.start_server,daemon=True).start()
        else:
            threading.Thread(target=self.connect_to_server,daemon=True).start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # clipboard
        self.last_clipboard_content = pyperclip.paste()
        if not self.clipboard_monitor_active:
            self.clipboard_monitor_thread=threading.Thread(target=self.monitor_clipboard,daemon=True)
            self.clipboard_monitor_thread.start()
            self.clipboard_monitor_active=True
        
        self.show_status("Status",f"Input sharing started as {self.role}")
        
    def stop_sharing(self):
        self.running=False
        self.connection_active=False
        if self.client_socket:
            try: self.client_socket.close()
            except: pass
            self.client_socket=None
        if self.server_socket:
            try: self.server_socket.close()
            except: pass
            self.server_socket=None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.show_status("Status","Input sharing stopped")
        
    def show_status(self,title,message):
        print(f"[{title}] {message}")
        if title=="Error":
            QMessageBox.critical(self,title,message)
            
    # == Server handlers ==
    def start_server(self):
        self.server_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:
            self.server_socket.bind(('0.0.0.0',self.server_port))
            self.server_socket.listen(1)
            self.show_status("Server",f"Listening on port {self.server_port}...")
            while self.running:
                try:
                    conn,addr=self.server_socket.accept()
                    conn.settimeout(0.1)
                    self.connection_active=True
                    self.client_socket=conn
                    self.show_status("Server",f"Connected to {addr}")
                    threading.Thread(target=self.send_heartbeat,daemon=True).start()
                    # listeners
                    mouse.Listener(on_move=self.on_server_mouse_move,
                                   on_click=self.on_server_mouse_click,
                                   on_scroll=self.on_server_mouse_scroll).start()
                    keyboard.Listener(on_press=self.on_server_key_press,
                                      on_release=self.on_server_key_release).start()
                    self.handle_connection(conn)
                except socket.timeout:
                    continue
        except Exception as e:
            if self.running: self.comm.status_signal.emit("Server Error",str(e))
        finally:
            if self.server_socket: self.server_socket.close()
            self.connection_active=False
            
    def send_heartbeat(self):
        while self.running and self.connection_active:
            try:
                self.send_message("heartbeat")
                time.sleep(1)
            except: break
            
    def handle_connection(self,conn):
        try:
            while self.running and self.connection_active:
                data=conn.recv(4096)
                if not data: break
                for msg in data.decode().split('\n'):
                    if not msg.strip(): continue
                    m=json.loads(msg)
                    if m["type"]=="heartbeat": continue
                    if self.role=="server": self.handle_client_message(m)
                    else: self.handle_server_message(m)
        except Exception:
            pass
        finally:
            conn.close(); self.connection_active=False
            self.comm.status_signal.emit("Server","Client disconnected")
            
    # server-side event forwards
    def on_server_mouse_move(self,x,y):
        if not self.connection_active: return
        # detect edge
        if time.time()-self.last_message_time>5:
            self.screen_width,self.screen_height=self.get_screen_size()
        thr=5
        if ((self.client_side=="left" and x<=thr) or
            (self.client_side=="right" and x>=self.screen_width-thr) or
            (self.client_side=="top" and y<=thr) or
            (self.client_side=="bottom" and y>=self.screen_height-thr)):
            if not self.remote_control_active:
                self.remote_control_active=True
                # normalize
                cx,cy=(0,y) if self.client_side=="right" else                       (self.screen_width-1,y) if self.client_side=="left" else                       (x,0) if self.client_side=="bottom" else                       (x,self.screen_height-1)
                self.send_message("mouse_move",{"x":cx,"y":cy,
                                               "screen_width":self.screen_width,
                                               "screen_height":self.screen_height})
    def on_server_mouse_click(self,x,y,button,pressed):
        self.send_message("mouse_click",{"x":x,"y":y,
                                         "button":str(button),
                                         "pressed":pressed})
    def on_server_mouse_scroll(self,x,y,dx,dy):
        self.send_message("mouse_scroll",{"x":x,"y":y,"dx":dx,"dy":dy})
    def on_server_key_press(self,key):
        try:self.send_message("key_press",{"key":str(key)})
        except:pass
    def on_server_key_release(self,key):
        try:self.send_message("key_release",{"key":str(key)})
        except:pass

    # == Client side ==
    def connect_to_server(self):
        self.client_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.client_socket.settimeout(5)
        try:
            self.client_socket.connect((self.server_ip,self.server_port))
            self.connection_active=True
            self.show_status("Client",f"Connected to {self.server_ip}")
            threading.Thread(target=self.send_heartbeat,daemon=True).start()
            mouse.Listener(on_move=self.on_client_mouse_move,
                           on_click=self.on_client_mouse_click,
                           on_scroll=self.on_client_mouse_scroll).start()
            keyboard.Listener(on_press=self.on_client_key_press,
                              on_release=self.on_client_key_release).start()
            self.handle_connection(self.client_socket)
        except Exception as e:
            self.comm.status_signal.emit("Error",str(e))

    def on_client_mouse_move(self,x,y):
        if not self.connection_active:return
        if time.time()-self.last_message_time>5:
            self.screen_width,self.screen_height=self.get_screen_size()
        thr=5
        if ((self.client_side=="left" and x<=thr) or
            (self.client_side=="right" and x>=self.screen_width-thr) or
            (self.client_side=="top" and y<=thr) or
            (self.client_side=="bottom" and y>=self.screen_height-thr)):
            if self.remote_control_active:
                self.remote_control_active=False
                self.send_message("mouse_move",{"x":x,"y":y,
                                               "screen_width":self.screen_width,
                                               "screen_height":self.screen_height})
    def on_client_mouse_click(self,x,y,button,pressed):
        self.send_message("mouse_click",{"x":x,"y":y,
                                         "button":str(button),
                                         "pressed":pressed})
    def on_client_mouse_scroll(self,x,y,dx,dy):
        self.send_message("mouse_scroll",{"x":x,"y":y,"dx":dx,"dy":dy})
    def on_client_key_press(self,key):
        try:self.send_message("key_press",{"key":str(key)})
        except:pass
    def on_client_key_release(self,key):
        try:self.send_message("key_release",{"key":str(key)})
        except:pass

    # == Message handlers ==
    def handle_client_message(self,message):
        t=message["type"];d=message.get("data",{})
        if t=="mouse_move":
            if "screen_width" in d:
                self.screen_width,self.screen_height=d["screen_width"],d["screen_height"]
            self.remote_control_active=True
            self.mouse_controller.position=(d["x"],d["y"])
        elif t=="mouse_click":
            b=mouse.Button[d["button"].split(".")[-1]]
            (self.mouse_controller.press if d["pressed"] else self.mouse_controller.release)(b)
        elif t=="mouse_scroll":
            self.mouse_controller.scroll(d["dx"],d["dy"])
        elif t=="key_press":
            k=self.parse_key(d["key"])
            if k:self.keyboard_controller.press(k)
        elif t=="key_release":
            k=self.parse_key(d["key"])
            if k:self.keyboard_controller.release(k)
        elif t=="clipboard_update":
            c=d["content"]
            if c!=pyperclip.paste():pyperclip.copy(c)

    def handle_server_message(self,message):
        t=message["type"];d=message.get("data",{})
        if t=="mouse_move":
            if "screen_width" in d:
                self.screen_width,self.screen_height=d["screen_width"],d["screen_height"]
            self.remote_control_active=False
            # adjust pos
            if self.client_side=="left": new_x,new_y=self.screen_width-1,d["y"]
            elif self.client_side=="right": new_x,new_y=0,d["y"]
            elif self.client_side=="top": new_x,new_y=d["x"],self.screen_height-1
            else: new_x,new_y=d["x"],0
            self.mouse_controller.position=(new_x,new_y)
        elif t=="mouse_click":
            b=mouse.Button[d["button"].split(".")[-1]]
            (self.mouse_controller.press if d["pressed"] else self.mouse_controller.release)(b)
        elif t=="mouse_scroll":
            self.mouse_controller.scroll(d["dx"],d["dy"])
        elif t=="key_press":
            k=self.parse_key(d["key"]); 
            if k:self.keyboard_controller.press(k)
        elif t=="key_release":
            k=self.parse_key(d["key"]);
            if k:self.keyboard_controller.release(k)
        elif t=="clipboard_update":
            c=d["content"]
            if c!=pyperclip.paste():pyperclip.copy(c)

    def parse_key(self,key_str):
        try:
            if "Key." in key_str: return getattr(keyboard.Key,key_str.split(".")[-1])
            if key_str.startswith("'") and key_str.endswith("'"): return key_str.strip("'")
            return None
        except: return None

    def monitor_clipboard(self):
        while self.running:
            try:
                c=pyperclip.paste()
                if c!=self.last_clipboard_content:
                    self.last_clipboard_content=c
                    self.send_message("clipboard_update",{"content":c})
                time.sleep(0.5)
            except: time.sleep(1)

    def get_screen_size(self):
        if platform.system()=="Windows":
            u=ctypes.windll.user32
            return (u.GetSystemMetrics(0),u.GetSystemMetrics(1))
        elif platform.system()=="Linux":
            try:
                from Xlib import display
                d=display.Display();s=d.screen()
                return (s.width_in_pixels,s.height_in_pixels)
            except:
                return (1920,1080)
        return (1920,1080)

    def closeEvent(self,event):
        self.stop_sharing(); event.accept()

if __name__=="__main__":
    app=QApplication(sys.argv)
    w=InputSharingApp(); w.show(); sys.exit(app.exec_())
