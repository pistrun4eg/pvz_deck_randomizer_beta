@echo off
rem Запуск PVZ DECK RANDOMIZER от имени администратора (UAC попросит разрешение)
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Запрашиваю права администратора...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
where py >nul 2>&1 && (py pvz_randomizer.py & goto end)
where python >nul 2>&1 && (python pvz_randomizer.py & goto end)
echo Не найден Python. Установи с python.org и тикни "Add Python to PATH".
pause
:end
