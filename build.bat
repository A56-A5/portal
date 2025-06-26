@echo off
echo Building Portal...

pyinstaller portal.py --noconsole --icon=portal.ico ^
--name Portal-v1.0 ^
--add-data "portal.ico;." ^
--add-data "share.py;." ^
--add-data "audio.py;." ^
--add-data "log_viewer.py;." ^
--add-data "config.py;." ^
--add-data "config.json;." ^
--hidden-import=PyQt5.sip

echo Done. Check /dist/main/ folder for your executable.
pause
