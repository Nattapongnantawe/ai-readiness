@echo off
REM ==========================================================================
REM  Build the website into frontend\dist (run again after changing frontend code)
REM ==========================================================================
setlocal
cd /d "%~dp0frontend"
where npm >nul 2>nul || (echo [ERROR] Node.js / npm not found. Install Node.js 18+ first. & exit /b 1)
if not exist node_modules (
  echo Installing packages ...
  call npm install || exit /b 1
)
echo Building website ...
call npx vite build || exit /b 1
echo.
echo  Done: %~dp0frontend\dist
if /i not "%~1"=="nopause" pause
