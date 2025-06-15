from pynput import keyboard

def on_press(key):
    try:
        print(f"Key pressed: {key.char}")
    except AttributeError:
        print(f"Special key pressed: {key}")

    # Suppress Alt+F4
    if key == keyboard.Key.f4 and current_keys.get(keyboard.Key.alt_l, False):
        print("Alt+F4 detected and suppressed!")
        return False  # Return False here won't stop the listener, but to actually suppress, we do nothing
    current_keys[key] = True

def on_release(key):
    if key in current_keys:
        current_keys[key] = False

# Dictionary to track current pressed keys
current_keys = {}

# Start keyboard listener
with keyboard.Listener(on_press=on_press, on_release=on_release, suppress=True) as listener:
    listener.join()
