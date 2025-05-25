import keyboard

def on_key_event(event):
    action = "DOWN" if event.event_type == "down" else "UP"
    print(f"Key {action}: {event.name}")
    return False  # Return False to suppress the key

# Hook all keyboard events, suppress them, but log them
keyboard.hook(on_key_event, suppress=True)

print("[INFO] Keyboard is blocked (presses will be shown here).")


