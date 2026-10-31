@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo ============================================
echo   时政资讯一键更新
echo ============================================
echo.
echo [1/2] 抓取多源时政资讯（含正文摘要）...
python scripts\fetch_news.py --fetch-content
if errorlevel 1 (
    echo.
    echo [失败] 请确认已安装 Python 并加入 PATH
    pause
    exit /b 1
)
echo.
echo [2/2] 完成！请刷新浏览器页面查看最新资讯。
echo.
pause
