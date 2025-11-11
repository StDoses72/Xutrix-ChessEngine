@echo off
cd /d "%~dp0"

echo [INFO] Creating virtual environment (Python 3.12 required)...
python -3.12 -m venv venv312

echo [INFO] Installing dependencies...
call venv312\Scripts\activate.bat
pip install -r requirements.txt

echo [DONE] Environment ready. You can now run:
echo     run_venv312.bat
pause