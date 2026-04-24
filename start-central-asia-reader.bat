@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo ==================================================
echo   Central Asia Reader - One-Click Startup
echo ==================================================
echo.

REM ----------------------------
REM 1) Ensure LibreTranslate is running (Docker)
REM ----------------------------
echo [1/5] Checking Docker...
docker version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker is not available. Start Docker Desktop first.
  goto :end
)

echo Checking LibreTranslate container...
docker inspect libretranslate >nul 2>&1
if errorlevel 1 (
  echo LibreTranslate container not found. Creating it...
  docker run -d --name libretranslate -p 5000:5000 libretranslate/libretranslate:v1.5.1 >nul
  if errorlevel 1 (
    echo ERROR: Failed to create LibreTranslate container.
    goto :end
  )
) else (
  for /f "tokens=*" %%s in ('docker inspect -f "{{.State.Running}}" libretranslate 2^>nul') do set LT_RUNNING=%%s
  if /i "!LT_RUNNING!" NEQ "true" (
    echo Starting existing LibreTranslate container...
    docker start libretranslate >nul
    if errorlevel 1 (
      echo ERROR: Failed to start LibreTranslate container.
      goto :end
    )
  ) else (
    echo LibreTranslate container already running.
  )
)

echo Waiting for LibreTranslate health...
set LT_READY=0
for /L %%i in (1,1,20) do (
  curl.exe -s http://127.0.0.1:5000/languages >nul 2>&1
  if not errorlevel 1 (
    set LT_READY=1
    goto :lt_ok
  )
  timeout /t 1 /nobreak >nul
)
:lt_ok
if "!LT_READY!" NEQ "1" (
  echo ERROR: LibreTranslate did not become ready at http://127.0.0.1:5000
  echo Run: docker logs libretranslate
  goto :end
)
echo LibreTranslate is ready.
echo.

REM ----------------------------
REM 2) Ensure Ollama is running
REM ----------------------------
echo [2/5] Checking Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
  echo ERROR: Ollama is not installed or not in PATH.
  goto :end
)

curl.exe -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo Ollama not responding. Starting ollama serve in new window...
  start "Central Asia Reader - Ollama" cmd /k "ollama serve"
  timeout /t 3 /nobreak >nul
)

curl.exe -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo ERROR: Ollama still not reachable at http://127.0.0.1:11434
  goto :end
)

echo Ensuring mistral model exists (this may take time on first run)...
ollama list | findstr /i "mistral" >nul
if errorlevel 1 (
  echo Pulling mistral model...
  ollama pull mistral
  if errorlevel 1 (
    echo ERROR: Failed to pull mistral model.
    goto :end
  )
)
echo Ollama is ready.
echo.

REM ----------------------------
REM 3) Start RSS proxy
REM ----------------------------
echo [3/5] Starting RSS proxy in new window...
start "Central Asia Reader - RSS Proxy" cmd /k "set LIBRETRANSLATE_URL=http://127.0.0.1:5000 && set OLLAMA_URL=http://127.0.0.1:11434 && set OLLAMA_MODEL=mistral && python rss_proxy.py"
timeout /t 2 /nobreak >nul

REM Optional readiness check
curl.exe -s http://127.0.0.1:8787/health >nul 2>&1
if errorlevel 1 (
  echo WARNING: RSS proxy health endpoint not ready yet. It may still be starting.
) else (
  echo RSS proxy health check OK.
)
echo.

REM ----------------------------
REM 4) Start static web server
REM ----------------------------
echo [4/5] Starting static web server in new window...
start "Central Asia Reader - Web Server" cmd /k "python -m http.server 8080"
timeout /t 1 /nobreak >nul
echo.

REM ----------------------------
REM 5) Open app
REM ----------------------------
echo [5/5] Opening app in browser...
start "" "http://localhost:8080/central-asia-reader-free_1.html"

echo.
echo Launch complete. Keep opened terminal windows running while using the app.
echo.

:end
endlocal