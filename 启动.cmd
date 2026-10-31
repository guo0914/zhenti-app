@echo off
setlocal
title 资料分析刷题 - 本地服务
cd /d "%~dp0"

rem 传 --lan 时监听所有网卡，供手机在同一 WiFi 下访问
set "LAN="
set "ARGS="
:parse
if "%~1"=="" goto run
if /i "%~1"=="--lan" goto setlan
set "ARGS=%ARGS% %~1"
shift
goto parse

:setlan
set "LAN=--host 0.0.0.0"
shift
goto parse

:run
set "PY="
for %%P in (python.exe) do if not defined PY set "PY=%%~$PATH:P"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
if not defined PY if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

if not defined PY goto nopy

"%PY%" -c "import sqlite3" >nul 2>nul
if errorlevel 1 goto badpy

echo.
echo   正在启动资料分析刷题服务，稍后浏览器会自动打开。
if defined LAN echo   已开启局域网访问（手机可用本机内网 IP 打开）。
echo   实际地址以本窗口显示为准；关闭本窗口即可停止服务。
echo.

if defined ARGS "%PY%" server.py %LAN% %ARGS%
if not defined ARGS "%PY%" server.py %LAN% --port 8000 --open
goto end

:nopy
echo.
echo   [错误] 没有找到 Python。
echo   请先安装 Python 3.9 或更高版本：https://www.python.org/downloads/
echo   安装时请勾选 "Add Python to PATH"。
echo.
pause
exit /b 1

:badpy
echo.
echo   [错误] 这个 Python 缺少 sqlite3 模块，无法运行。
echo.
pause
exit /b 1

:end
if errorlevel 1 pause
