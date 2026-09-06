@echo off
echo ==============================================
echo       Starting Custom Backtest Engine
echo ==============================================
echo.
echo Activating Virtual Environment...
call venv\Scripts\activate.bat

echo Running Backtest...
python backtest/custom_engine.py

echo.
echo Backtest Completed.
pause
