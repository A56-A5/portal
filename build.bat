@echo off
echo 🔧 Building Portal and subprocess components...

REM Build main portal GUI
pyinstaller portal.py --noconsole --icon=portal.ico ^
--name Portal-v1.0 ^
--add-data "portal.ico;." ^
--add-data "config.py;." ^
--add-data "config.json;."

REM Build background subprocesses
pyinstaller audio.py --noconsole --name audio
pyinstaller share.py --noconsole --name share
pyinstaller log_viewer.py --noconsole --name log_viewer

echo 📁 Copying worker EXEs into Portal directory...

copy dist\audio\audio.exe dist\Portal-v1.0\
copy dist\share\share.exe dist\Portal-v1.0\
copy dist\log_viewer\log_viewer.exe dist\Portal-v1.0\

echo ✅ All executables ready inside dist\Portal-v1.0\
pause

echo ✅ Build complete. Check dist\ for executables.
pause
