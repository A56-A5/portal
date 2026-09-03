@echo off
echo 🔧 Building Portal...

REM Build using the tracked spec file (see portal.spec - this used to
REM reference a gitignored, never-committed "Portal-v1.0.spec" and would
REM fail immediately on a fresh clone)
pyinstaller --noconfirm portal.spec

echo ✅ Build complete. Check dist\Portal.exe
pause
