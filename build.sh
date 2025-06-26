#!/bin/bash
echo "🔧 Building Portal for Linux..."

pyinstaller portal.py --noconsole --icon=portal.ico \
--name Portal-v1.0 \
--add-data "portal.ico:." \
--add-data "share.py:." \
--add-data "audio.py:." \
--add-data "log_viewer.py:." \
--add-data "config.py:." \
--add-data "config.json:." \
--hidden-import=PyQt5.sip

echo "✅ Build complete. Check dist// for your executable."
