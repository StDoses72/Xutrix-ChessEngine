@echo off
REM =====================================================
REM  Xustrix Chess Engine - Python 3.12 Virtual Environment Launcher
REM =====================================================

REM 获取脚本所在目录
cd /d "%~dp0"

echo [INFO] Activating Python 3.12 virtual environment...
echo.

REM 激活 venv312 环境
call venv312\Scripts\activate.bat

if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    echo Make sure venv312 exists under: %~dp0
    pause
    exit /b
)

echo [OK] Virtual environment activated.
echo Python version:
python --version
echo.

REM 如果你想直接启动引擎，请取消下面这一行的注释
REM python engine.py

echo.
echo [DONE] Virtual environment is ready.
echo Type 'deactivate' to exit.
cmd /k