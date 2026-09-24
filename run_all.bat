@echo off
title Gladiators - run everything
cd /d "%~dp0"

echo ============================================
echo   GLADIATORS - starting everything
echo ============================================
echo.
echo [1/4] Installing packages (first time: 5-10 minutes)...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Package install failed. Check the internet connection and that Python is installed.
  pause
  exit /b 1
)

echo.
echo [2/4] Starting backend  ^(http://127.0.0.1:8000^)
start "Gladiators BACKEND - close to stop" /D "%~dp0backend" cmd /k python -m uvicorn main:app --port 8000

echo [3/4] Starting dashboard ^(http://localhost:8501^)
start "Gladiators DASHBOARD - close to stop" /D "%~dp0dashboard" cmd /k python -m streamlit run app.py --server.port 8501 --server.headless true

echo [4/4] Running optimizer on sample data...
pushd "%~dp0optimizer"
python optimizer.py --csv ..\data\sample_detections_synthetic.csv --budget 500000
popd

echo.
echo Waiting for the servers to start...
timeout /t 10 /nobreak >nul

start "" "http://127.0.0.1:8000"
start "" "http://localhost:8501"
start "" "%~dp0website\index.html"

echo.
echo ============================================
echo  Opened in your browser:
echo   - Backend website : http://127.0.0.1:8000
echo   - API test page   : http://127.0.0.1:8000/docs
echo   - Dashboard       : http://localhost:8501
echo   - Website         : website\index.html
echo   - Optimizer output: optimizer\repair_plan.csv, budget_curve.png, map.html
echo.
echo  To stop: close the BACKEND and DASHBOARD windows.
echo ============================================
pause
