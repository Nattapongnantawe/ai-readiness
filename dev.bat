@echo off
REM ==========================================================================
REM  Development mode: API with auto-reload (:8000) + Vite dev server (:5173)
REM  Edit code and the page updates by itself. Do NOT use while a crawl is running
REM  (saving a backend file restarts the API and stops the run).
REM ==========================================================================
setlocal
set "ROOT=%~dp0"
set "PY=C:\projeb\pipeline\venv\Scripts\python.exe"
start "AI Readiness API (dev)" cmd /k "cd /d %ROOT%backend && "%PY%" -m uvicorn app.main:app --reload"
start "AI Readiness web (dev)" cmd /k "cd /d %ROOT%frontend && npm run dev"
start "" /min cmd /c "timeout /t 8 /nobreak >nul & start http://localhost:5173"
