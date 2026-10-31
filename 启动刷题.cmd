@echo off
chcp 65001 >nul
title 行测刷题 - 本地服务
cd /d "%~dp0"

set "PY="
for %%P in (python.exe) do if not defined PY set "PY=%%~$PATH:P"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
if not defined PY if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

if not defined PY goto nopy

"%PY%" -c "import sqlite3" >nul 2>nul
if errorlevel 1 goto badpy

echo.
echo   ============================================
echo   行测刷题服务启动中...
echo   本机访问： http://127.0.0.1:8000/
echo   局域网：   http://192.168.1.21:8000/  （同一 WiFi）
echo   Tailscale：http://100.97.10.38:8000/  （跨网络，手机装 Tailscale 后）
echo   关闭本窗口即停止服务。
echo   ============================================
echo.

"%PY%" server.py --port 8000 --open
goto end

:nopy
echo   [错误] 没有找到 Python，请安装 Python 3.9+。
pause
exit /b 1

:badpy
echo   [错误] Python 缺少 sqlite3 模块。
pause
exit /b 1

:end
if errorlevel 1 pause
