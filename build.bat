@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Checking Python...
python --version
if errorlevel 1 goto :error

echo [2/3] Installing build requirements...
python -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

echo [3/3] Building MacroRecorder.exe...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name MacroRecorder main.py
if errorlevel 1 goto :error

if not exist "dist\script" mkdir "dist\script"
echo.
echo Build completed successfully:
echo %~dp0dist\MacroRecorder.exe
echo Saved macros will be stored in:
echo %~dp0dist\script
pause
exit /b 0

:error
echo.
echo Build failed. Review the error messages above.
pause
exit /b 1
