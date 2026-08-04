@echo off

:: שומר את הנתיב המלא של תיקיית המייל ומנקה לוכסן בסוף
set "CURRENT_APP_DIR=%~dp0"
if "%CURRENT_APP_DIR:~-1%"=="\" set "CURRENT_APP_DIR=%CURRENT_APP_DIR:~0,-1%"

:: עובר לתיקיית האב ומריץ בצורה נקייה
cd ..
python main.py
pause