@echo off
REM ==========================================================================
REM  AI Readiness - prepare the GitHub repository + the SQL dump to submit
REM
REM  Output:
REM    C:\ai-readiness-github\            folder for GitHub (all 4 modules, no secrets).
REM                                       Run again any time: it is updated in place and
REM                                       its .git folder (GitHub Desktop) is kept.
REM    C:\ai-readiness\_release\jobmarket.sql.gz
REM                                       SQL dump: jobs + skills + vectors (pgvector),
REM                                       contact info removed (PDPA) -> attach to a GitHub Release
REM  Also: backup\jobmarket_full_<date>.dump = FULL private backup (keep, never share)
REM
REM  Never copied into repo\: .env (DB password, Gemini key), venv, node_modules,
REM  dist, logs, scraper output, *.json / *.jsonl data, *.dump, CurrStructRPT*.pdf
REM  The script scans repo\ for API keys / passwords and stops if it finds any.
REM
REM  Close start.bat first (the dump is taken while nothing writes to the DB).
REM ==========================================================================
setlocal
set "ROOT=%~dp0"
set "PGBIN=C:\Program Files\PostgreSQL\18\bin"
set "PGHOST=localhost"
set "PGPORT=5432"
set "PGUSER=postgres"
set "DB=jobmarket"
set "SHARE=jobmarket_share"
set "PY=C:\projeb\pipeline\venv\Scripts\python.exe"
set "PIPELINE_DIR=C:\projeb\pipeline"
set "JOBTHAI_DIR="
set "JOBBKK_DIR="
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM folder paths: same values the Crawler page uses (backend\.env)
if exist "%ROOT%backend\.env" for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%ROOT%backend\.env") do (
  if /i "%%a"=="PIPELINE_DIR" set "PIPELINE_DIR=%%b"
  if /i "%%a"=="JOBTHAI_DIR" set "JOBTHAI_DIR=%%b"
  if /i "%%a"=="JOBBKK_DIR" set "JOBBKK_DIR=%%b"
)
if not exist "%PGBIN%\pg_dump.exe" (echo [ERROR] pg_dump not found in %PGBIN% - edit PGBIN at the top & pause & exit /b 1)
if not exist "%PY%" (echo [ERROR] Python not found: %PY% - edit PY at the top & pause & exit /b 1)

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "STAMP=%%d"
set "OUT=%ROOT%_release"
for %%r in ("%ROOT%..\ai-readiness-github") do set "REPO=%%~fr"
set "BACKUP=%ROOT%backup"

echo.
echo  PostgreSQL password for user %PGUSER% (typing is hidden):
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$s=Read-Host -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"`) do set "PGPASSWORD=%%p"
"%PGBIN%\psql.exe" -d %DB% -Atc "select 1" >nul 2>&1 || (echo [ERROR] cannot connect to %DB% - wrong password? & pause & exit /b 1)

if not exist "%OUT%" mkdir "%OUT%"
if exist "%OUT%\jobmarket.sql.gz" del "%OUT%\jobmarket.sql.gz"
if not exist "%REPO%" mkdir "%REPO%"
if not exist "%BACKUP%" mkdir "%BACKUP%"

echo.
echo [1/5] Full private backup of %DB% ...
"%PGBIN%\pg_dump.exe" -Fc -f "%BACKUP%\jobmarket_full_%STAMP%.dump" %DB% || goto :fail
echo       backup\jobmarket_full_%STAMP%.dump  (keep it, do not share)

echo [2/5] Copy of the database without contact info (PDPA) ...
"%PGBIN%\dropdb.exe" --if-exists %SHARE% || goto :fail
"%PGBIN%\createdb.exe" %SHARE% || goto :fail
"%PGBIN%\pg_restore.exe" --no-owner --exit-on-error -d %SHARE% "%BACKUP%\jobmarket_full_%STAMP%.dump" || goto :fail
pushd "%ROOT%backend"
"%PY%" scripts\pdpa_clean.py "postgresql://%PGUSER%@%PGHOST%:%PGPORT%/%SHARE%"
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" goto :fail
REM (counts go through a small file: parentheses inside "for /f" break cmd)
"%PGBIN%\psql.exe" -d %SHARE% -Atc "select count(*) from jobs" > "%OUT%\count.txt"
set /p NJOBS=<"%OUT%\count.txt"
"%PGBIN%\psql.exe" -d %SHARE% -Atc "select count(*) from jobs where embedding is not null" > "%OUT%\count.txt"
set /p NVEC=<"%OUT%\count.txt"
del "%OUT%\count.txt"
echo       jobs %NJOBS% (with vector %NVEC%)

echo [3/5] SQL dump (plain SQL, gzip) ...
"%PGBIN%\pg_dump.exe" -Fp -Z 9 --no-owner --no-privileges ^
  --exclude-table-data=raw_jobs --exclude-table-data=m4_crawl_runs --exclude-table-data=m4_apscheduler_jobs ^
  --exclude-table-data=m4_job_changes -f "%OUT%\jobmarket.sql.gz" %SHARE% || goto :fail
"%PGBIN%\dropdb.exe" %SHARE%
for %%f in ("%OUT%\jobmarket.sql.gz") do echo       _release\jobmarket.sql.gz  [%%~zf bytes]

echo [4/5] Copying source code ...
set "XD=venv .venv node_modules dist logs output output_backup_before_electronics __pycache__ .git .pytest_cache _release backup .vscode .idea"
set "XF=.env .env.local *.dump *.sql.gz *.log *.pyc *.jsonl CurrStructRPT*.pdf listing_dates.json cloudflared.exe"
REM /MIR = make it an exact copy (deleted files disappear too); .git and the module folders are left alone
robocopy "%ROOT%." "%REPO%" /MIR /NFL /NDL /NJH /NJS /NP /XD %XD% pipeline scrapers /XF %XF% >nul
if errorlevel 8 goto :fail
REM pipeline + scrapers: also leave out *.json data files (they hold scraped jobs with contact info)
call :copy "%PIPELINE_DIR%" "pipeline" || goto :fail
call :copy "%JOBTHAI_DIR%" "scrapers\jobthai" || goto :fail
call :copy "%JOBBKK_DIR%" "scrapers\jobbkk" || goto :fail

echo [5/5] Checking for secrets ...
powershell -NoProfile -Command ^
  "$hits = Get-ChildItem -LiteralPath '%REPO%' -Recurse -File | Where-Object { $_.Length -lt 5MB } | Select-String -Pattern 'AIza[0-9A-Za-z_\-]{30,}','postgres(ql)?(\+\w+)?://[^:/\s]+:[\x21-\x3f\x41-\x7e]+@','GEMINI_API_KEY\s*=\s*[A-Za-z0-9_\-]{20,}' | Where-Object { $_.Line -notmatch 'YOUR_PASSWORD|u:p@|user:pass@|Select-String|:\$\{|:<' };" ^
  "if ($hits) { $hits | ForEach-Object { Write-Host ('  ' + $_.Path.Replace('%REPO%\','') + ':' + $_.LineNumber) -ForegroundColor Red }; exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo.
  echo [STOP] The files above contain a key or a password. Move it into .env,
  echo        then run make-repo.bat again. Nothing was uploaded.
  pause & exit /b 1
)
echo       no keys or passwords found

echo.
echo  Done.
echo    %REPO%   ^<- push this folder to GitHub
echo    %OUT%\jobmarket.sql.gz   ^<- attach to a GitHub Release (too big for git)
echo    jobs in the dump: %NJOBS%  (with vector: %NVEC%)
pause
exit /b 0

:copy
REM %1 source folder  %2 destination inside repo\  (+ requirements-lock.txt from its venv)
if "%~1"=="" (echo [ERROR] folder for %~2 is not set in backend\.env & exit /b 1)
if not exist "%~1" (echo [ERROR] folder not found: %~1 & exit /b 1)
robocopy "%~1" "%REPO%\%~2" /MIR /NFL /NDL /NJH /NJS /NP /XD %XD% eval_results /XF %XF% *.json >nul
if errorlevel 8 (echo [ERROR] copy failed: %~1 & exit /b 1)
if exist "%~1\venv\Scripts\python.exe" "%~1\venv\Scripts\python.exe" -m pip freeze > "%REPO%\%~2\requirements-lock.txt" 2>nul
echo       %~2
REM show the .json files left out, so you can check none of them is needed to run the code
powershell -NoProfile -Command "Get-ChildItem -LiteralPath '%~1' -Recurse -File -Filter *.json | Where-Object { $_.FullName -notmatch '\\(venv|output[^\\]*|node_modules|__pycache__)\\' } | ForEach-Object { Write-Host ('         not copied (data): ' + $_.FullName.Substring('%~1'.Length + 1)) -ForegroundColor DarkGray }"
exit /b 0

:fail
echo.
echo [ERROR] stopped - see the message above.
"%PGBIN%\dropdb.exe" --if-exists %SHARE% >nul 2>&1
pause
exit /b 1
