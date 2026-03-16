@echo off
echo 🔧 Building Portal...

REM Build using the spec file
pyinstaller --noconfirm Portal-v1.0.spec

echo ✅ Build complete. Check dist\Portal-v1.0.exe
pause
