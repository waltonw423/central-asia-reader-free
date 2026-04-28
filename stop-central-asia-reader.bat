@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo ==================================================
echo   Central Asia Reader - Shutdown
echo ==================================================
echo.

REM ----------------------------
REM 1) Close app terminals
REM ----------------------------
echo [1/3] Closing app terminal windows...
taskkill /FI "WINDOWTITLE eq Central Asia Reader - RSS Proxy*" /T /F >nul 2>&1
if errorlevel 1 (
  echo - RSS Proxy window not running.
) else (
  echo - Closed RSS Proxy window.
)

taskkill /FI "WINDOWTITLE eq Central Asia Reader - Web Server*" /T /F >nul 2>&1
if errorlevel 1 (
  echo - Web Server window not running.
) else (
  echo - Closed Web Server window.
)

taskkill /FI "WINDOWTITLE eq Central Asia Reader - Ollama*" /T /F >nul 2>&1
if errorlevel 1 (
  echo - Ollama window not running.
) else (
  echo - Closed Ollama window.
)
echo.

REM ----------------------------
REM 2) Stop LibreTranslate container
REM ----------------------------
echo [2/3] Stopping LibreTranslate container...
docker version >nul 2>&1
if errorlevel 1 (
  echo - Docker not available, skipping container shutdown.
) else (
  docker inspect libretranslate >nul 2>&1
  if errorlevel 1 (
    echo - libretranslate container not found.
  ) else (
    for /f "tokens=*" %%s in ('docker inspect -f "{{.State.Running}}" libretranslate 2^>nul') do set LT_RUNNING=%%s
    if /i "!LT_RUNNING!"=="true" (
      docker stop libretranslate >nul 2>&1
      if errorlevel 1 (
        echo - Failed to stop libretranslate container.
      ) else (
        echo - Stopped libretranslate container.
      )
    ) else (
      echo - libretranslate container already stopped.
    )
  )
)
echo.

REM ----------------------------
REM 3) Verify key ports are free
REM ----------------------------
echo [3/3] Checking local ports...
for %%P in (8787 8080 5000 11434) do (
  netstat -ano | findstr /r /c:":%%P .*LISTENING" >nul 2>&1
  if errorlevel 1 (
    echo - Port %%P is not listening.
  ) else (
    echo - Port %%P still has a listener.
  )
)
echo.
echo Shutdown complete.
echo.
endlocal