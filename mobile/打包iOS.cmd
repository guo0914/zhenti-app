@echo off
chcp 65001 >nul
title 打包 iOS App - 构建与自检
cd /d "%~dp0"

echo ============================================================
echo   iOS App 打包工具
echo ============================================================
echo.
echo   本工具在 Windows 上完成「构建」这一步。
echo   最终编译成 .ipa 需要 Mac 或云构建（见 README-iOS.md）
echo.

rem 检查 Node
where node >nul 2>nul
if errorlevel 1 (
  echo   [错误] 未找到 Node.js
  echo   请先安装：https://nodejs.org/
  pause
  exit /b 1
)

rem 检查依赖
if not exist "node_modules" (
  echo   [1/3] 首次运行，安装依赖...
  call npm install
  if errorlevel 1 ( echo   安装失败 & pause & exit /b 1 )
) else (
  echo   [1/3] 依赖已安装
)

echo.
echo   [2/3] 构建 www...
call node scripts/prepare-www.js
if errorlevel 1 ( echo   构建失败 & pause & exit /b 1 )

echo.
echo   [3/3] 同步到 iOS 工程...
call npx cap sync ios
if errorlevel 1 ( echo   同步失败 & pause & exit /b 1 )

echo.
echo ============================================================
echo   自检
echo ============================================================
call node scripts/verify-www.js
if errorlevel 1 (
  echo.
  echo   自检未通过，请修复后再打包。
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   构建完成！
echo ============================================================
echo.
echo   iOS 工程位置：
echo     %CD%\ios\App\App.xcodeproj
echo.
echo   下一步怎么做：
echo.
echo     [有 Mac]
echo       把 mobile 目录拷到 Mac，执行：
echo         cd mobile ^&^& npm install ^&^& npm run sync
echo         cd ios/App ^&^& pod install
echo       然后用 Xcode 打开 App.xcodeproj 编译
echo.
echo     [没 Mac - 云构建]
echo       Codemagic: https://codemagic.io  ^(免费 500 分钟/月^)
echo       GitHub Actions: 见 README-iOS.md
echo.
echo     [没 Mac - 想在 Windows 装到 iPhone]
echo       1. 云构建拿到未签名 .ipa
echo       2. 下载 Sideloadly: https://sideloadly.io/
echo       3. 数据线连 iPhone，拖入 ipa，填 Apple ID，点 Start
echo       4. iPhone 设置 - 通用 - VPN与设备管理 - 信任证书
echo       注意：免费账号 7 天需重签一次
echo.
echo     [最省事 - 不打包]
echo       iPhone Safari 打开你的站点
echo       点分享 - 添加到主屏幕
echo       5 分钟搞定，图标+全屏+离线都有
echo.
pause
