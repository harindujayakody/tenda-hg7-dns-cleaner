@echo off
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)
set "DIR=%~dp0"
where wt >nul 2>&1
if %errorLevel% equ 0 (
    wt --title "NetMaintain" cmd /k "python \"%DIR%NetMaintain.py\""
) else (
    start "NetMaintain" cmd /k "python \"%DIR%NetMaintain.py\""
)
