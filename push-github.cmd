@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Push to GitHub

rem ---- 定位项目目录（脚本可能被放在桌面）----
set "REPODIR=%~dp0"
if not exist "!REPODIR!.git" set "REPODIR=C:\Users\严睿霖\Documents\deepseek-harness\default-workspace\quiz-app\"
if not exist "!REPODIR!.git" set "REPODIR=%~dp0..\quiz-app\"

cd /d "!REPODIR!"
if errorlevel 1 goto nodir
if not exist ".git" goto nodir

echo ============================================================
echo    Push code to GitHub - for iOS build
echo ============================================================
echo.
echo   Repo dir: !REPODIR!
echo.
echo   Make sure you created a PUBLIC repo named:
echo     zhenti-app
echo   at https://github.com/new
echo.

set "GHUSER=%~1"
if "%GHUSER%"=="" set /p GHUSER=  GitHub username: 

if "%GHUSER%"=="" (
  echo.
  echo   ERROR: No username. Aborting.
  pause
  exit /b 1
)

set REPO=zhenti-app
set URL=https://github.com/%GHUSER%/%REPO%.git

echo.
echo   Target: %URL%
echo.

git remote | findstr /x "github" >nul 2>&1
if errorlevel 1 (
  echo   [1/2] Adding remote ...
  git remote add github %URL%
) else (
  echo   [1/2] Updating remote URL ...
  git remote set-url github %URL%
)

echo   [2/2] Pushing 92MB (a few minutes) ...
echo.
echo   If asked for a password, use a Personal Access Token:
echo     GitHub ^> Settings ^> Developer settings ^> Tokens (classic)
echo     Scope: repo. Paste the token as password.
echo.

git push -u github main
if errorlevel 1 goto failed

echo.
echo ============================================================
echo   PUSH OK
echo ============================================================
echo.
echo   Next steps:
echo     1. Open https://github.com/%GHUSER%/%REPO%/actions
echo     2. Left: click "Build iOS IPA"
echo     3. Right: "Run workflow" -^> green button
echo     4. Wait 10-15 minutes
echo     5. Artifacts -^> App-unsigned-ipa
echo     6. Install with Sideloadly
echo.
pause
exit /b 0

:nodir
echo ============================================================
echo   ERROR: git repo not found
echo ============================================================
echo.
echo   Looked at: !REPODIR!
echo   Expected the quiz-app folder containing .git
echo.
pause
exit /b 1

:failed
echo.
echo ============================================================
echo   PUSH FAILED
echo ============================================================
echo.
echo   1. Repo exists and PUBLIC?
echo      https://github.com/new  -^> name: zhenti-app
echo   2. Username correct?
echo   3. Auth failed? Use Personal Access Token, NOT password.
echo      Settings -^> Developer settings -^> Tokens (classic)
echo   4. Network problem? Try again.
echo.
pause
exit /b 1
