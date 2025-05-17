# Minimal Python Barrier App with Audio Sharing

This is a minimal cross-platform Barrier-like app written in Python, featuring:
- Mouse sharing
- Keyboard sharing
- Clipboard sharing
- Audio sharing (integrated from the audio prototype)

## Features
- Simple GUI inspired by Barrier
- Server and client modes
- Audio sharing via the audio prototype

## How to Run
1. Install requirements: `pip install -r requirements.txt`
2. Run: `python main.py`

## Linux: 'Failed to create compose table' Warning
If you see a warning like:

    Failed to create compose table

on the Linux client, this is a harmless X11 warning from the input system. It does **not** affect mouse sharing. To suppress or fix it:
- Run the app as a normal user (not with sudo).
- Make sure your locale is set (e.g., `export LANG=en_US.UTF-8`).
- Install `x11-xkb-utils` and `xkb-data`:
  sudo apt update
  sudo apt install x11-xkb-utils xkb-data
- If using Wayland, try logging in with an Xorg session.

You can safely ignore this warning if mouse sharing works.

---

This is a minimal, educational implementation. For full features, use the official Barrier app. 