@echo off
title Spreadsheet Analyzer
echo ========================================
echo   Spreadsheet Deep Analyzer
echo ========================================
echo.
echo Pilih mode:
echo   [1] Web Lokal Dash    (python web_app.py - port 8050)
echo   [2] Web Vercel/Next   (npm run dev - port 3000, butuh vercel dev untuk API)
echo.
set /p MODE="Pilihan [1/2, default=1]: "
if "%MODE%"=="2" goto NEXTJS

:LEGACY
echo Memulai Dash Analyzer...
cd /d "%~dp0"
netstat -ano | findstr ":8050" >nul 2>&1
if %errorlevel% == 0 (
    echo Analyzer sudah berjalan, membuka browser...
    start http://localhost:8050
    exit /b
)
start "Spreadsheet Analyzer Server" /min cmd /c "python web_app.py"
timeout /t 4 /nobreak >nul
start http://localhost:8050
echo Buka http://localhost:8050
pause
taskkill /f /fi "WINDOWTITLE eq Spreadsheet Analyzer Server" >nul 2>&1
exit /b

:NEXTJS
cd /d "%~dp0"
where vercel >nul 2>&1
if %errorlevel% == 0 (
    echo Menjalankan vercel dev (Next.js + Python API)...
    start http://localhost:3000
    vercel dev
) else (
    echo Vercel CLI tidak ditemukan. Jalankan: npm install -g vercel
    echo Lalu: vercel dev
    echo Atau deploy ke Vercel untuk akses production.
    npm run dev
)
pause
