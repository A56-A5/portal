#  Portal - Cross-Device Input and Audio Sharing App

**Portal** is a cross-platform Python application for sharing your mouse, keyboard, clipboard, and audio across multiple devices on the same network. It supports both Linux and Windows.

##  Inspiration

Portal was inspired by tools like [Barrier](https://github.com/debauchee/barrier) and [Synergy](https://symless.com/synergy), which pioneered cross-device input sharing.  
This project aims to provide a simpler, Python-based alternative with audio sharing and a customizable GUI.

![Platform Support](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-blue)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-green)
![GUI Framework](https://img.shields.io/badge/GUI-Tkinter%20%7C%20PyQt5-orange)
![Audio Tool](https://img.shields.io/badge/Audio-FFmpeg-red)

## 🛠 Features

- **Seamless Input Sharing**: Mouse & keyboard transition across screens
- **Full Keyboard Support**: Works in all contexts including password fields and lock screens
- **Bidirectional Clipboard**: Text and images sync automatically when switching controls
- **Audio Streaming**: Share or receive audio between devices
- **Log Viewer**: GUI-based log viewer for debugging
- **Cross-Platform**: Works on Windows and Linux

> **Linux note:** Portal supports both **X11** and **Wayland** sessions. On Wayland, ensure `xdotool` and `wl-clipboard` (or `xclip`) are installed for seamless input sharing and clipboard sync.

## Open Source

**Portal** is fully open-source and community-driven.  
You’re welcome to explore, modify, and enhance the codebase — whether you want to improve performance, add features, or port it to more platforms.

License: [MIT License](LICENSE)

## 🤝 Contributing

We’d love your help to make Portal even better!  
Here’s how you can contribute:

1. **Fork** the repository  
2. **Create a branch** for your feature or bugfix  
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Commit** your changes with clear messages
    ```bash
    git commit -m "Add amazing feature"
    ```
4. **Push** to your branch
    ```bash
    git push origin feature/amazing-feature``
    ```
5. Open a **Pull Request** — we’ll review it together!

If you find a bug, open an **issue** describing:
- Your OS (Windows/Linux)
- Steps to reproduce the problem
- Any console/log output


##  Requirements

  -  Note: ffmpeg is used internally for capturing and streaming audio across systems. Make sure it's installed and available in your system PATH.

## Install

### Linux (one-liner)

```bash
curl -fsSL https://raw.githubusercontent.com/A56-A5/portal/main/install.sh | bash
```

Installs system dependencies (ffmpeg, xdotool, clipboard tools, etc.) then the
`portal` command via [pipx](https://pypa.github.io/pipx/) (falls back to
`pip install --user`).

### Windows (one-liner)

```powershell
irm https://raw.githubusercontent.com/A56-A5/portal/main/install.ps1 | iex
```

Run in PowerShell. Installs Python / Git / ffmpeg via `winget` if needed, then
the `portal` command via pipx. Needs `winget` (Windows 11 / modern Windows 10;
install **App Installer** from the Microsoft Store if missing).

Both installers are safe to re-run (upgrade in place).

### Launch & uninstall

```bash
portal              # start Portal (GUI)
portal uninstall    # remove Portal from this machine
portal --help
```

On Windows, use the same commands in PowerShell or Command Prompt after install.

### From source (any platform)

```bash
git clone https://github.com/A56-A5/portal.git
cd portal
pip install -r requirements.txt
pip install .
portal
```

Windows also needs: `pip install pywin32`  
Linux extras (if not using install.sh): `ffmpeg`, `xdotool`, `xclip` or `wl-clipboard`, and on Hyprland optionally `gtk-layer-shell` + `ydotool`.

### Release builds (maintainers)

```bash
# Linux one-file binary
chmod +x build.sh && ./build.sh
# → dist/Portal

# Windows one-file binary
build.bat
# → dist\Portal.exe
```

Tag a release on GitHub after merging to `main`. Users install with the
one-liners above (they track `main` or set `PORTAL_REF=vX.Y.Z`).

```bash
# install a specific tag
PORTAL_REF=v1.2.0 curl -fsSL https://raw.githubusercontent.com/A56-A5/portal/main/install.sh | bash
```

##  Project Structure

```
portal/
├── main.py                 # Main entry point
├── pyproject.toml          # Packaging config (`pip install .` -> `portal` command)
├── portal.spec             # PyInstaller spec (used by build.sh/build.bat)
├── config.json             # Configuration file
├── requirements.txt        # Python dependencies
├── install.sh              # One-line Linux installer (curl | bash)
├── install.ps1             # One-line Windows installer (irm | iex)
├── build.bat              # Windows build script
├── build.sh               # Linux build script
├── portal.ico             # Application icon
├── portal.png             # Application icon (Linux)
├── README.md              # This file
│
├── controllers/           # Input/output device controllers
│   ├── __init__.py
│   ├── keyboard_controller.py
│   ├── mouse_controller.py
│   ├── clipboard_controller.py
│   └── audio_controller.py
│
├── network/              # Network communication modules
│   ├── __init__.py
│   ├── share_manager.py      # Main input sharing manager
│   └── audio_manager.py      # Audio streaming manager
│
├── gui/                  # User interface components
│   ├── __init__.py
│   ├── main_window.py       # Main GUI window
│   └── log_viewer.py         # Log viewer window
│
└── utils/                # Utility functions
    ├── __init__.py
    ├── config.py           # Configuration management
    └── theme.py            # Light/dark theme detection
```

##  Clean Shutdown

Use the GUI **Stop** button to gracefully stop the app. All subprocesses, sockets, and overlays are properly cleaned up.

# Debugging Stuck Sockets (Windows & Linux)
If the app crashes or is killed without cleanup, you might encounter errors like:

```bash
[Errno 98] Address already in use          # Linux
[WinError 10048] Only one usage of each socket address is normally permitted  # Windows
```

# Windows: Kill socket process manually
 Find process using all ports (50007,50008,50009)

```bash
netstat -aon | findstr :<PORT>   #replace <PORT>

  TCP    0.0.0.0:<PORT>        0.0.0.0:0              LISTENING       <PID>

taskkill /PID <PID> /F     #replace <PID> 
```

# Linux: Kill socket process manually
 Find process using all ports (50007,50008,50009)

```bash
sudo lsof -i :<PORT>    #replace <PORT>

  python3  <PID> user   3u  IPv4  ...  TCP *:<PORT> (LISTEN)

kill -9 <PID>    #replace <PID> 
```