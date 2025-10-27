#!/bin/bash
echo "🔧 Building Portal for Linux..."

# Build main portal GUI
pyinstaller main.py --noconsole --icon=portal.ico \
--name Portal-v1.0 \
--add-data "portal.ico:." \
--add-data "config.json:." \
--hidden-import=controllers \
--hidden-import=network \
--hidden-import=gui \
--hidden-import=utils

# Make sure it is executable
chmod +x dist/Portal-v1.0/Portal-v1.0

echo "✅ Build complete. Check dist/Portal-v1.0"
