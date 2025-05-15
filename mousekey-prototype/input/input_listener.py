# input/input_listener.py
from pynput import mouse, keyboard
from common.protocol import encode_event

class InputListener:
    def __init__(self, send_callback):
        self.send_callback = send_callback

    def start(self):
        mouse_listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click)
        keyboard_listener = keyboard.Listener(on_press=self.on_press)

        mouse_listener.start()
        keyboard_listener.start()

    def on_move(self, x, y):
        event = {
            "type": "mouse",
            "action": "move",
            "data": {"x": x, "y": y}
        }
        self.send_callback(encode_event(event))

    def on_click(self, x, y, button, pressed):
        if pressed:
            event = {
                "type": "mouse",
                "action": "click",
                "data": {"x": x, "y": y, "button": str(button)}
            }
            self.send_callback(encode_event(event))

    def on_press(self, key):
        try:
            event = {
                "type": "keyboard",
                "action": "type",
                "data": {"text": key.char}
            }
        except AttributeError:
            event = {
                "type": "keyboard",
                "action": "press",
                "data": {"key": str(key).replace("Key.", "")}
            }
        self.send_callback(encode_event(event))
