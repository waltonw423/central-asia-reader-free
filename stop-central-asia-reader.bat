@echo off
taskkill /FI "WINDOWTITLE eq Central Asia Reader - RSS Proxy*" /T /F
taskkill /FI "WINDOWTITLE eq Central Asia Reader - Web Server*" /T /F
echo Stopped proxy and web server windows.