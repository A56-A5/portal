@echo off
powershell -Command "Start-Process python -ArgumentList '%~dp0main.py' -Verb RunAs" 