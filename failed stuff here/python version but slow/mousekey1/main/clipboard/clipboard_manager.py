# clipboard/clipboard_manager.py
import pyperclip
import time
import threading

def watch_clipboard(send_callback, poll_interval=1.0):
    """Continuously watch for clipboard changes and send updates."""
    last_text = pyperclip.paste()

    def loop():
        nonlocal last_text
        while True:
            try:
                current = pyperclip.paste()
                if current != last_text:
                    last_text = current
                    event = {
                        "type": "clipboard",
                        "action": "copy",
                        "data": {"text": current}
                    }
                    send_callback(event)
                time.sleep(poll_interval)
            except KeyboardInterrupt:
                break

    threading.Thread(target=loop, daemon=True).start()

def apply_clipboard(data):
    """Set clipboard content on server."""
    text = data.get("text", "")
    pyperclip.copy(text)
