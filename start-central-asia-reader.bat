@echo off
setlocal
cd /d "%~dp0"
echo Starting RSS proxy in a new window...
start "Central Asia Reader - RSS Proxy" cmd /k "python rss_proxy.py"
echo Waiting 2 seconds for proxy startup...
timeout /t 2 /nobreak >nul
echo Starting static web server in a new window...
start "Central Asia Reader - Web Server" cmd /k "python -m http.server 8080"
echo Opening app in browser...
start "" "http://localhost:8080/central-asia-reader-free_1.html"
echo.
echo Central Asia Reader launch sequence complete.
echo Keep both terminal windows open while using the app.