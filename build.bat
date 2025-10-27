@echo off
echo 🔧 Building Portal...

REM Build main portal GUI
pyinstaller main.py --noconsole --icon=portal.ico ^
--name Portal-v1.0 ^
--add-data "portal.ico;." ^
--add-data "config.json;." ^
--hidden-import=controllers ^
--hidden-import=network ^
--hidden-import=gui ^
--hidden-import=utils

echo ✅ Build complete. Check dist\Portal-v1.0\
pause
