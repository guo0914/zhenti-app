@echo off
chcp 65001 >nul
title 行测刷题
cd /d "%~dp0"

set "PY="
for %%P in (python.exe) do if not defined PY set "PY=%%~$PATH:P"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
if not defined PY if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

if not defined PY (
  echo   [错误] 没有找到 Python，请安装 Python 3.9+
  pause
  exit /b 1
)

"%PY%" launch_app.py
if errorlevel 1 (
  echo.
  echo   [启动异常] 请把上面的信息反馈给开发者。
  pause
)
exit
