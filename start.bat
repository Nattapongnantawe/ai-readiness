@echo off
REM ==========================================================================
REM  AI Readiness - start the whole system (API + website + scheduler)
REM  Double-click this file, then open http://localhost:8000
REM  Close this window (or press Ctrl+C) to stop.
REM ==========================================================================
setlocal
set "ROOT=%~dp0"
REM Python of the pipeline venv (has torch, bge-m3, uvicorn ...). Change if yours is elsewhere.
set "PY=C:\projeb\pipeline\venv\Scripts\python.exe"
set "PORT=8000"

if not exist "%PY%" (
  echo [ERROR] Python not found: %PY%
  echo         Edit the PY line at the top of start.bat
  pause & exit /b 1
)

if not exist "%ROOT%frontend\dist\index.html" (
  echo Website is not built yet - building it once ...
  call "%ROOT%build-frontend.bat" nopause || (pause & exit /b 1)
)

echo.
echo  AI Readiness is starting ... (loading the bge-m3 model takes about 20-60 s)
echo  Website : http://localhost:%PORT%
echo  API docs: http://localhost:%PORT%/docs
echo  Keep this window open. Scheduled crawls only run while it is open.
echo.

REM open the browser after the model has loaded
start "" /min cmd /c "timeout /t 40 /nobreak >nul & start http://localhost:%PORT%"

cd /d "%ROOT%backend"
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
echo.
echo  Server stopped.
pause
