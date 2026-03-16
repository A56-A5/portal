#!/bin/bash
echo "🔧 Building Portal for Linux..."

# Build using the spec file
pyinstaller --noconfirm Portal-v1.0.spec

# Make sure it is executable
chmod +x dist/Portal-v1.0

echo "✅ Build complete. Check dist/Portal-v1.0"
