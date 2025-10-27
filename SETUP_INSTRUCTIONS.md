# Portal - Setup Instructions

## Installation

### Python Dependencies
```bash
pip install -r requirements.txt
```

### System Dependencies (Linux)

For keyboard input to work in secure contexts (lockscreen, password fields), install xdotool:

```bash
# Ubuntu/Debian
sudo apt install xdotool

# Fedora/RHEL
sudo yum install xdotool

# Arch Linux
sudo pacman -S xdotool
```

### Audio Dependencies

For audio streaming, install FFmpeg:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Fedora/RHEL
sudo yum install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

For Linux audio capture (sharing):
```bash
# Ubuntu/Debian
sudo apt install pulseaudio-utils

# Configure PulseAudio for audio capture
```

### Clipboard (Linux)

Ensure xclip is installed for clipboard functionality:

```bash
sudo apt install xclip
```

## Features

### Keyboard Input
- **Windows**: Uses win32api for system-level keyboard input
- **Linux**: Uses xdotool for secure contexts (lockscreen, password fields)
- Works in: App search, password fields, lockscreen, terminal, all applications

### Clipboard
- Supports text and images
- Base64 encoded for safe transmission
- Saves received images to `clipboard/` folder
- Windows: Handles DIB format images
- Linux: Handles PNG format images

### Mouse Control
- Cross-screen transitions
- Click, scroll, move
- Smooth edge detection

### Audio Streaming
- Share system audio
- Receive audio on client
- Low latency UDP streaming

## Usage

1. **Start Portal**:
   ```bash
   python portal.py  # Original
   # OR
   python main.py    # Organized structure
   ```

2. **Configure**:
   - Select mode (Server or Client)
   - Enter client IP if in client mode
   - Choose server direction (Top/Left/Right/Bottom)
   - Enable audio if needed

3. **Start Connection**:
   - Click "Start" button
   - Move mouse to screen edge to transition
   - Use keyboard and mouse on remote device

## Troubleshooting

### Keyboard not working in lockscreen/password fields (Linux)
**Solution**: Install xdotool
```bash
sudo apt install xdotool
```

### Audio not working (Linux)
**Solution**: Install FFmpeg and configure PulseAudio
```bash
sudo apt install ffmpeg pulseaudio-utils
```

### Clipboard images not saving
**Solution**: Ensure `clipboard/` folder exists with write permissions

### Connection fails
**Solution**: Check firewall allows ports 50007, 50008, 50009

## Files

- `portal.py` - Original main entry
- `main.py` - New organized entry
- `share.py` - Mouse/keyboard/clipboard sync
- `audio.py` - Audio streaming
- `config.py` - Configuration management
- `controllers/` - Input/output controllers
- `network/` - Network communication
- `gui/` - User interface
- `utils/` - Utilities

## Platform Support

- ✅ Windows 10/11
- ✅ Linux (Ubuntu, Debian, Fedora, Arch)
- ⚠️ macOS (limited - uses pynput fallback)

