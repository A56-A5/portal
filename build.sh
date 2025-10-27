#!/bin/bash
echo "🔧 Building Portal for Linux..."

# Build main portal GUI as single file
pyinstaller main.py --onefile --windowed --icon=portal.ico \
--name Portal-v1.0 \
--add-data "portal.ico:." \
--add-data "config.json:." \
--hidden-import=controllers \
--hidden-import=network \
--hidden-import=gui \
--hidden-import=utils \
--hidden-import=pynput.keyboard \
--hidden-import=pynput.mouse

# Make sure it is executable
chmod +x dist/Portal-v1.0

echo "✅ Build complete. Check dist/Portal-v1.0"
