@echo off
cd /d "C:\Users\16142\Desktop\AI ENGINE"

set LOCKFILE=bot.lock

IF EXIST %LOCKFILE% (
    echo Bot already running. Exiting.
    exit /b
)

echo Running > %LOCKFILE%

set "TELEGRAM_BOT_TOKEN=8636128819:AAFLcXGKirTCBFXNC50B2rR_QTEvMktGhiw"
set "TELEGRAM_CHAT_ID=8661143355"
set "DEBUG_MODE=true"
set "BOT_NAME=Heartbeat Live Control Center"
set "POLL_INTERVAL_SECONDS=2"

echo Starting Heartbeat Live Control Center...
echo Chat ID: %TELEGRAM_CHAT_ID%
echo Poll Interval: %POLL_INTERVAL_SECONDS%s

:loop
IF EXIST stop_bot.txt (
    echo Stop file detected. Cleaning up...
    del %LOCKFILE%
    exit /b
)

python telegram_live_listener.py

IF EXIST stop_bot.txt (
    echo Stop file detected after bot exit. Cleaning up...
    del %LOCKFILE%
    exit /b
)

IF NOT EXIST %LOCKFILE% (
    echo Lock file missing. Exiting.
    exit /b
)

echo Script crashed or stopped. Restarting in 5 seconds...
timeout /t 5 >nul
goto loop