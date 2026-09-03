#!/bin/bash
set -e
echo "🔧 Building Portal for Linux..."

# Build using the tracked spec file (see portal.spec - this used to
# reference a gitignored, never-committed "Portal-v1.0.spec" and would
# fail immediately on a fresh clone)
pyinstaller --noconfirm portal.spec

# Make sure it is executable
chmod +x dist/Portal

echo "✅ Build complete. Check dist/Portal"
