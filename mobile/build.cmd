@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Build iOS App (www + sync + verify)
echo ============================================================

if not exist "node_modules" (
  echo [1/4] Installing dependencies...
  call npm install --no-audit --no-fund
  if errorlevel 1 goto fail
) else (
  echo [1/4] Dependencies OK
)

echo [2/4] Building www ...
call node scripts/prepare-www.js
if errorlevel 1 goto fail

echo [3/4] Syncing to iOS project ...
call npx cap sync ios
if errorlevel 1 goto fail

echo [4/4] Verifying ...
call node scripts/verify-www.js
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   BUILD OK
echo ============================================================
echo.
echo   iOS project: %CD%\ios\App\App.xcodeproj
echo.
echo   Next steps (no Mac - use cloud build):
echo     1. Push code to GitHub
echo     2. Go to https://codemagic.io
echo     3. Add application, select your repo
echo     4. Start build with workflow: ios-unsigned
echo     5. Download App-unsigned.ipa from Artifacts
echo     6. Sign and install with Sideloadly on Windows
echo.
echo   Full guide: see 无Mac安装指南.md
echo.
rem pause removed for CI
exit /b 0

:fail
echo.
echo ============================================================
echo   BUILD FAILED - see error above
echo ============================================================
rem pause removed for CI
exit /b 1
