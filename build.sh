#!/bin/bash
echo "🔧 Building Portal and subprocess components for Linux..."

# Build main portal GUI
pyinstaller portal.py --noconsole --icon=portal.ico \
--name Portal-v1.0 \
--add-data "portal.ico:." \
--add-data "config.py:." \
--add-data "config.json:."

# Build subprocess workers
pyinstaller audio.py --noconsole --name audio
pyinstaller share.py --noconsole --name share
pyinstaller log_viewer.py --noconsole --name log_viewer

# Copy worker executables into Portal directory
echo "📁 Copying worker executables into Portal directory..."
cp dist/audio/audio dist/Portal-v1.0/
cp dist/share/share dist/Portal-v1.0/
cp dist/log_viewer/log_viewer dist/Portal-v1.0/

# Make sure they are executable
chmod +x dist/Portal-v1.0/audio
chmod +x dist/Portal-v1.0/share
chmod +x dist/Portal-v1.0/log_viewer
chmod +x dist/Portal-v1.0/Portal-v1.0

echo "✅ All executables ready inside dist/Portal-v1.0"
echo "✅ Build complete."
