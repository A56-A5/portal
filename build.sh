#!/bin/bash
echo "🔧 Building Portal for Linux..."

# Build main portal GUI as single file
pyinstaller main.py --onefile --windowed --icon=portal.ico \
--name Portal-v1.0 \
--add-data "portal.ico:." \
--add-data "portal.png:." \
--add-data "config.json:." \
--hidden-import=controllers \
--hidden-import=controllers.keyboard_controller \
--hidden-import=controllers.mouse_controller \
--hidden-import=controllers.clipboard_controller \
--hidden-import=controllers.audio_controller \
--hidden-import=network \
--hidden-import=network.share_manager \
--hidden-import=network.audio_manager \
--hidden-import=network.connection_handler \
--hidden-import=network.input_handler \
--hidden-import=gui \
--hidden-import=gui.main_window \
--hidden-import=gui.log_viewer \
--hidden-import=utils \
--hidden-import=utils.config \
--hidden-import=pynput.keyboard \
--hidden-import=pynput.mouse \
--hidden-import=sounddevice \
--hidden-import=numpy

# Make sure it is executable
chmod +x dist/Portal-v1.0

echo "✅ Build complete. Check dist/Portal-v1.0"
