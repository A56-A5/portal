# input/input_controller.py
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController, Key

mouse = MouseController()
keyboard = KeyboardController()

def handle_input_event(event: dict):
    if event['type'] == 'mouse':
        handle_mouse_event(event['action'], event['data'])
    elif event['type'] == 'keyboard':
        handle_keyboard_event(event['action'], event['data'])

def handle_mouse_event(action, data):
    if action == 'move':
        mouse.position = (data['x'], data['y'])
    elif action == 'click':
        from pynput.mouse import Button
        button = Button.left if data.get('button') == 'left' else Button.right
        mouse.click(button, 1)

def handle_keyboard_event(action, data):
    if action == 'type':
        keyboard.type(data['text'])
    elif action == 'press':
        key = getattr(Key, data['key'], data['key'])
        keyboard.press(key)
    elif action == 'release':
        key = getattr(Key, data['key'], data['key'])
        keyboard.release(key)
