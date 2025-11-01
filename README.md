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

Install Python 3.8+ and then:

```bash
pip install -r requirements.txt
```

### Windows-only dependencies:

```bash
pip install pywin32
```

### Linux-only packages:

```bash
sudo apt install ffmpeg xclip pactl
# For better keyboard support in secure contexts:
sudo apt install xdotool
```

##  Running the App

```bash
python main.py
```

##  Configuration

Update `config.json` or use the GUI to:
- Set Server / Client mode  
- Set audio to Share / Receive  
- Define client direction (Top / Left / Right / Bottom)  
- Enter audio receiver IP

##  Building Executables

###  Windows

Run `build.bat`:

- Output: `dist/Portal-v1.0.exe` (single file)

###  Linux

Run `build.sh`:

Make it executable and run:

```bash
chmod +x build.sh
./build.sh
```

- Output: `dist/Portal-v1.0` (single file)

##  Project Structure

```
portal/
├── main.py                 # Main entry point
├── config.json             # Configuration file
├── requirements.txt        # Python dependencies
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
│   ├── audio_manager.py      # Audio streaming manager
│   ├── connection_handler.py # Connection management
│   └── input_handler.py      # Input event handling
│
├── gui/                  # User interface components
│   ├── __init__.py
│   ├── main_window.py       # Main GUI window
│   └── log_viewer.py         # Log viewer window
│
└── utils/                # Utility functions
    ├── __init__.py
    └── config.py           # Configuration management
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