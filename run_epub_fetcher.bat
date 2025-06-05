@echo off
REM Drag and drop an epub file onto this script to process it

REM Set the directory where main.py is located
REM If this script is not in the same directory as main.py, adjust the path accordingly
REM Example: set SCRIPT_DIR=C:\Users\Documents\LCP
set SCRIPT_DIR=%~dp0

REM Run the Python script with the dropped file as argument
python "%SCRIPT_DIR%\main.py" "%~1"

pause