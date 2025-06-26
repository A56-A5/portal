# 🎯 Portal - Cross-Device Input and Audio Sharing App

**Portal** is a cross-platform Python application for sharing your mouse, keyboard, clipboard, and audio across multiple devices on the same network. It supports both Linux and Windows.

## 🙏 Inspiration

Portal was inspired by tools like [Barrier](https://github.com/debauchee/barrier) and [Synergy](https://symless.com/synergy), which pioneered cross-device input sharing.  
This project aims to provide a simpler, Python-based alternative with audio sharing and a customizable GUI.

## 🛠 Features

- Seamless mouse & keyboard transition across screens  
- Clipboard synchronization  
- Audio streaming (Share or Receive)  
- Visual overlay during transitions  
- Log viewer GUI  
- GUI-based configuration with `portal_ui.py`

## 📦 Requirements

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
```

## 🚀 Running the App

```bash
python portal.py
```

## ⚙️ Configuration

Update `config.json` or use the GUI to:
- Set Server / Client mode  
- Set audio to Share / Receive  
- Define client direction (Top / Left / Right / Bottom)  
- Enter audio receiver IP

## 🧱 Building Executables

### 🪟 Windows

Run `build.bat`:

- Output: `dist/portal.exe`

### 🐧 Linux

Run `build.sh`:

Make it executable and run:

```bash
chmod +x build.sh
./build.sh
```

- Output: `dist/main`

## 📁 Project Structure

```
portal/
├── portal.py
├── share.py
├── audio.py
├── log_viewer.py
├── config.py
├── config.json
├── portal.ico
├── requirements.txt
├── build.bat
├── build.sh
└── README.md
```

## 🧹 Clean Shutdown

Use the GUI **Stop** button to gracefully stop the app. All subprocesses, sockets, and overlays are properly cleaned up.
