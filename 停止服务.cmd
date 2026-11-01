@echo off
chcp 65001 >nul
setlocal

REM ═══════════════════════════════════════════════════════════
REM   停止服务 —— 关闭服务器与隧道
REM ═══════════════════════════════════════════════════════════

cd /d "%~dp0"

echo.
echo 正在停止...

taskkill /F /IM cloudflared.exe >nul 2>&1

for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| find "PID:"') do (
  taskkill /F /PID %%i >nul 2>&1
)

timeout /t 2 /nobreak >nul

echo.
echo 已停止。
echo.
pause
