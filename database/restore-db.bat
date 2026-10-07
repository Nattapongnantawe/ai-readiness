@echo off
REM Restore jobmarket.sql.gz into a new local database "jobmarket" (PostgreSQL 18 + pgvector on Windows)
setlocal
set "HERE=%~dp0"
set "PGBIN=C:\Program Files\PostgreSQL\18\bin"
set "PGUSER=postgres"
set "DB=jobmarket"
if not exist "%PGBIN%\psql.exe" (echo [ERROR] psql not found in %PGBIN% - edit PGBIN & pause & exit /b 1)
if not exist "%HERE%jobmarket.sql.gz" (echo [ERROR] put jobmarket.sql.gz from GitHub Releases next to this file & pause & exit /b 1)
where python >nul 2>&1 || (echo [ERROR] Python is needed to unzip the dump & pause & exit /b 1)

echo PostgreSQL password for %PGUSER% (typing is hidden):
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$s=Read-Host -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"`) do set "PGPASSWORD=%%p"

"%PGBIN%\psql.exe" -d postgres -Atc "select 1 from pg_database where datname='%DB%'" | findstr 1 >nul && (
  echo [STOP] database %DB% already exists - drop it or change DB at the top first
  pause & exit /b 1
)
"%PGBIN%\createdb.exe" %DB% || (pause & exit /b 1)
"%PGBIN%\psql.exe" -d %DB% -c "CREATE EXTENSION IF NOT EXISTS vector" || (
  echo [ERROR] pgvector is not installed in this PostgreSQL - see https://github.com/pgvector/pgvector#windows
  pause & exit /b 1
)
echo Restoring ... (a few minutes)
python -c "import gzip,shutil,sys; shutil.copyfileobj(gzip.open(sys.argv[1],'rb'), sys.stdout.buffer, 1<<20)" "%HERE%jobmarket.sql.gz" | "%PGBIN%\psql.exe" -q -v ON_ERROR_STOP=1 -d %DB% >nul || (echo [ERROR] restore failed & pause & exit /b 1)
"%PGBIN%\psql.exe" -d %DB% -c "select count(*) as jobs, count(embedding) as with_vector from jobs"
echo Done.
pause
