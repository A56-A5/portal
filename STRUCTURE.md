# Portal - Organized Structure

## Overview
The Portal application has been reorganized into a clean, modular structure for better maintainability and separation of concerns.

## Directory Structure

```
portal/
├── controllers/          # Input/output controllers
│   ├── __init__.py
│   ├── mouse_controller.py      # Mouse input/output handling
│   ├── keyboard_controller.py   # Keyboard input/output handling
│   ├── clipboard_controller.py  # Clipboard operations across OS
│   └── audio_controller.py      # Audio capture/playback
│
├── network/              # Network communication
│   ├── __init__.py
│   ├── connection_handler.py    # Connection management
│   └── input_handler.py         # Input event handling
│
├── gui/                  # Graphical user interface
│   ├── __init__.py
│   ├── main_window.py           # Main portal window
│   └── log_viewer.py            # Log viewer window
│
├── utils/                # Utility functions
│   ├── __init__.py
│   └── config.py                # Configuration management
│
├── main.py               # Main entry point (NEW)
├── portal.py             # Original main entry (kept for compatibility)
├── share.py              # Original share module
├── audio.py              # Original audio module
├── log_viewer.py         # Original log viewer
└── config.py             # Original config (kept for compatibility)
```

## Module Responsibilities

### Controllers (`controllers/`)
Handle all input/output operations for different devices:

- **MouseController**: Controls mouse position, clicks, and scrolling
  - Cross-platform mouse control using pynput
  - Uses win32api on Windows for better performance

- **KeyboardController**: Controls keyboard input
  - Parses key strings and simulates key presses/releases
  - Handles special keys (Ctrl, Alt, etc.)

- **ClipboardController**: Manages clipboard operations
  - Windows: Uses win32clipboard
  - Linux: Uses xclip
  - Cross-platform fallback with pyperclip

- **AudioController**: Handles audio streaming
  - Captures audio from system (Stereo Mix on Windows, PulseAudio on Linux)
  - Receives and plays audio streams
  - Cross-platform audio handling

### Network (`network/`)
Manages all network communication:

- **ConnectionHandler**: Main connection manager
  - Establishes TCP sockets for primary and secondary connections
  - Handles device state transitions (active/inactive)
  - Manages overlay window creation/destruction
  - Coordinates edge transitions between devices

- **InputHandler**: Processes input events
  - Mouse event sender/receiver
  - Keyboard event sender/receiver
  - Event parsing and routing

### GUI (`gui/`)
User interface components:

- **MainWindow**: Primary portal interface
  - Mode selection (Server/Client)
  - Audio settings
  - Start/Stop/Reload controls
  - Status display

- **LogViewer**: Log file viewer
  - Real-time log display
  - Clear logs functionality

### Utils (`utils/`)
Utility functions and configuration:

- **config.py**: Application configuration
  - JSON-based configuration storage
  - Settings for ports, modes, audio, etc.
  - Configuration loading and saving

## Usage

### Original Usage (Backward Compatible)
```bash
python portal.py
```

### New Organized Usage
```bash
python main.py
```

The new structure maintains backward compatibility with the original files while providing a clean, organized codebase.

## Migration Notes

1. **Imports**: Update imports from old structure:
   ```python
   # Old
   from config import app_config
   
   # New
   from utils.config import app_config
   ```

2. **Controllers**: Use dedicated controller classes:
   ```python
   # Old
   from pynput.mouse import Controller
   mouse_ctrl = Controller()
   
   # New
   from controllers.mouse_controller import MouseController
   mouse_ctrl = MouseController()
   ```

3. **Configuration**: Configuration management remains the same, just in a new location.

## Benefits of New Structure

1. **Separation of Concerns**: Each module has a single responsibility
2. **Reusability**: Controllers can be used independently
3. **Testability**: Individual components can be tested in isolation
4. **Maintainability**: Easier to locate and modify specific functionality
5. **Scalability**: Easy to add new controllers or features

## Future Improvements

- Add unit tests for each controller
- Implement event-driven architecture
- Add configuration validation
- Create plugin system for additional input/output devices
- Add network encryption for security

