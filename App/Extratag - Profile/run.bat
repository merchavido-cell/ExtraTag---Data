@echo off

:: 1. שומר את הנתיב של התיקייה הפנימית שבה לחצו על ה-bat
set "APP_DIR=%~dp0"

:: 2. זז רק תיקייה אחת למעלה כדי להגיע לתיקיית האב הראשית
cd /d "%APP_DIR%"
cd ..

:: 3. מגדיר את הנתיבים לקובץ ה-main.py ולפייתון השקט
set "MAIN_PY=%cd%\main.py"
set "PYTHON_EXE=%cd%\python_env\Scripts\pythonw.exe"

:: 4. מריץ את הפייתון ברקע, שולח לו את נתיב האפליקציה כפרמטר, וסוגר את הטרמינל מיד!
if exist "%PYTHON_EXE%" (
    start "" "%PYTHON_EXE%" "%MAIN_PY%" "%APP_DIR%"
) else (
    start "" pythonw "%MAIN_PY%" "%APP_DIR%"
)
exit