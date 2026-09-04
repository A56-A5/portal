#!/bin/bash
set -e
echo "🔧 Building Portal for Linux..."

# Simple one-file build (no portal.spec is shipped in the repo).
# If you later add a portal.spec you can switch back to:
#   pyinstaller --noconfirm portal.spec
pyinstaller --noconfirm \
    --onefile \
    --windowed \
    --name Portal \
    --icon portal.ico \
    --add-data "portal.png:." \
    --add-data "portal.ico:." \
    main.py

# Make sure it is executable
chmod +x dist/Portal

echo "✅ Build complete. Check dist/Portal"
