@echo off
chcp 65001 >nul
title 内网穿透 - 让手机在不同网络也能访问
cd /d "%~dp0"

rem 优先用系统 Python，其次工作区 Python
set "PY="
for %%P in (python.exe) do if not defined PY set "PY=%%~$PATH:P"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
if not defined PY if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

if not defined PY goto nopy

"%PY%" tunnel.py
goto end

:nopy
echo.
echo   [错误] 没有找到 Python，无法运行穿透脚本。
echo   请先安装 Python：https://www.python.org/downloads/
echo.
pause

:end
