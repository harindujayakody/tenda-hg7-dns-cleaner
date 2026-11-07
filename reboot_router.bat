@echo off
:: Clear screen
cls

title Router Rebooter - Tenda HG7

:: Move to script directory
cd /d "%~dp0"

:: Confirmation prompt
echo ==========================================
echo   Tenda HG7 Router Rebooter
echo ==========================================
echo.
set /p CONFIRM="Do you really want to reboot the router? (Y/N): "

if /I "%CONFIRM%" NEQ "Y" (
    echo.
    echo Cancelled. Router will not reboot.
    timeout /t 3 >nul
    exit /b
)

:: Run the Python script with arguments
python tenda_reboot_tui.py --host 192.168.1.1
:: Credentials are NOT stored here: set TENDA_ROUTER_USER / TENDA_ROUTER_PASS,
:: or the script will prompt for them. Never put your router password in this file.

:: Pause so window stays open after completion
echo.
echo Press any key to close...
pause >nul

