@echo off
REM ==========================================================================
REM  AI Readiness - share the running website on the internet (free)
REM  Uses a Cloudflare Quick Tunnel: no account, no router setup.
REM    1) run start.bat first and wait until the website opens
REM    2) double-click this file -> it prints a https://....trycloudflare.com link
REM  The link works while BOTH windows stay open. A new link is made every time.
REM ==========================================================================
setlocal
set "ROOT=%~dp0"
set "PORT=8000"
set "CF=%ROOT%tools\cloudflared.exe"
set "LOG=%ROOT%tools\tunnel.log"

REM ---- 1. refuse to go public with default passwords ----
set "BAD="
if not exist "%ROOT%backend\.env" set "BAD=backend\.env not found"
if exist "%ROOT%backend\.env" for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%ROOT%backend\.env") do (
  if /i "%%a"=="AUTH_ENABLED" if /i "%%b"=="false" set "BAD=AUTH_ENABLED=false"
  if /i "%%a"=="ADMIN_PASSWORD" if /i "%%b"=="change-me" set "BAD=ADMIN_PASSWORD is still change-me"
  if /i "%%a"=="ADMIN_PASSWORD" if "%%b"=="" set "BAD=ADMIN_PASSWORD is empty"
  if /i "%%a"=="JWT_SECRET" if "%%b"=="" set "BAD=JWT_SECRET is empty"
  if /i "%%a"=="JWT_SECRET" if /i "%%b"=="replace-with-a-long-random-string" set "BAD=JWT_SECRET is still the example value"
)
findstr /b /i "ADMIN_PASSWORD=" "%ROOT%backend\.env" >nul 2>&1 || set "BAD=ADMIN_PASSWORD is not set in backend\.env"
findstr /b /i "JWT_SECRET=" "%ROOT%backend\.env" >nul 2>&1 || set "BAD=JWT_SECRET is not set in backend\.env"
if defined BAD (
  echo.
  echo [STOP] %BAD%
  echo        Anyone on the internet could log in as admin and start crawls.
  echo        Set a strong ADMIN_PASSWORD and a long random JWT_SECRET in backend\.env,
  echo        restart start.bat, then run this file again.
  pause & exit /b 1
)

REM ---- 2. the website must already be running ----
curl.exe -s -o nul -m 5 http://127.0.0.1:%PORT%/api/v1/health || (
  echo.
  echo [STOP] The website is not running on port %PORT%.
  echo        Start start.bat first, wait until the page opens, then run this file again.
  pause & exit /b 1
)

REM ---- 3. get cloudflared once (official Cloudflare release) ----
if not exist "%CF%" (
  echo Downloading cloudflared ^(once, about 50 MB^) ...
  if not exist "%ROOT%tools" mkdir "%ROOT%tools"
  curl.exe -L --fail -o "%CF%" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe || (
    echo [ERROR] download failed. Get cloudflared-windows-amd64.exe from
    echo         https://github.com/cloudflare/cloudflared/releases and save it as tools\cloudflared.exe
    del "%CF%" 2>nul
    pause & exit /b 1
  )
)

REM ---- 4. open the tunnel and show the public link ----
if exist "%LOG%" del "%LOG%"
echo Opening the tunnel ...
start "" /b "%CF%" tunnel --no-autoupdate --url http://127.0.0.1:%PORT% --logfile "%LOG%" --loglevel info >nul 2>&1

powershell -NoProfile -Command ^
  "$u=$null; for($i=0;$i -lt 60 -and -not $u;$i++){ Start-Sleep 1; if(Test-Path '%LOG%'){ $m=Select-String -Path '%LOG%' -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1; if($m){ $u=$m.Matches[0].Value } } };" ^
  "if(-not $u){ Write-Host '[ERROR] no link after 60 s - see tools\tunnel.log'; exit 1 };" ^
  "Set-Clipboard $u; Write-Host ''; Write-Host '  Public link (copied to clipboard):' ; Write-Host ('  ' + $u) -ForegroundColor Green; Write-Host '';" ^
  "Write-Host '  Send this link to others. Keep this window and start.bat open.'; Write-Host '  Close this window to stop sharing.'"
if errorlevel 1 (taskkill /im cloudflared.exe /f >nul 2>&1 & pause & exit /b 1)

REM keep the window (and the tunnel) alive until it is closed
:wait
timeout /t 3600 /nobreak >nul
goto wait
