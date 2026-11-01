@echo off
chcp 65001 >nul
setlocal

REM ═══════════════════════════════════════════════════════════
REM   行测刷题 —— 一键启动（服务器 + 公网隧道）
REM
REM   作用：
REM     1. 启动 server.py（监听 0.0.0.0:8000）
REM     2. 启动 cloudflared 隧道，输出公网地址
REM     3. 把地址写入 tunnel-url.txt，方便复制
REM
REM   用法：双击运行，保持窗口开启
REM ═══════════════════════════════════════════════════════════

cd /d "%~dp0"

echo.
echo ============================================================
echo   行测刷题 一键启动
echo ============================================================
echo.

REM ── 检查 python ──
set "PYEXE=C:\Users\严睿霖\AppData\Local\Programs\Python\Python39\python.exe"
if not exist "%PYEXE%" (
  set "PYEXE=python"
)

REM ── 清理旧进程 ──
echo [1/3] 清理旧进程...
taskkill /F /IM cloudflared.exe >nul 2>&1
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| find "PID:"') do (
  taskkill /F /PID %%i >nul 2>&1
)
timeout /t 2 /nobreak >nul

REM ── 启动服务器 ──
echo [2/3] 启动服务器（端口 8000）...
start "行测刷题-服务器" /min "%PYEXE%" server.py --host 0.0.0.0 --port 8000
timeout /t 6 /nobreak >nul

REM ── 启动隧道 ──
echo [3/3] 启动公网隧道...
if not exist "cloudflared.exe" (
  echo.
  echo   [!] 找不到 cloudflared.exe
  echo       请从 https://github.com/cloudflare/cloudflared/releases 下载
  echo       文件名 cloudflared-windows-amd64.exe，重命名为 cloudflared.exe
  echo.
  pause
  exit /b 1
)

del /q "%TEMP%\cf-run.log" >nul 2>&1
start "行测刷题-隧道" /min cmd /c "cloudflared.exe tunnel --url http://127.0.0.1:8000 --no-autoupdate > ""%TEMP%\cf-run.log"" 2>&1"

echo.
echo   等待隧道建立...
timeout /t 15 /nobreak >nul

REM ── 解析地址 ──
set "URL="
for /f "tokens=*" %%a in ('findstr /R /C:"https://.*trycloudflare.com" "%TEMP%\cf-run.log" 2^>nul') do (
  set "LINE=%%a"
  call :EXTRACT
)

if "%URL%"=="" (
  echo.
  echo   [!] 未能解析隧道地址，请查看 %TEMP%\cf-run.log
  echo.
  pause
  exit /b 1
)

echo %URL%> tunnel-url.txt

echo.
echo ============================================================
echo   启动完成
echo ============================================================
echo.
echo   公网地址（手机用这个）：
echo.
echo     %URL%
echo.
echo   局域网地址（同 WiFi 可用）：
echo.
echo     http://192.168.1.21:8000
echo.
echo   已保存到 tunnel-url.txt
echo.
echo   注意：关闭本窗口后服务和隧道会继续运行；
echo         如需停止，运行「停止服务.cmd」
echo.
pause
exit /b 0

:EXTRACT
set "TMP=%LINE%"
set "TMP=%TMP:*https://=https://%"
for /f "tokens=1 delims= " %%b in ("%TMP%") do set "CAND=%%b"
set "CAND=%CAND:"=%"
set "CAND=%CAND:)=%"
set "CAND=%CAND:,=%"
if not "%CAND%"=="" set "URL=%CAND%"
goto :eof
