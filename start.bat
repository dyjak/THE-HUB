@echo off
setlocal ENABLEDELAYEDEXPANSION
echo [THE-HUB] Starting services...
echo Current root: %CD%

REM Backend
cd backend-fastapi
echo Backend dir: %CD%
if exist venv\Scripts\activate (
	call venv\Scripts\activate
) else (
	echo [WARN] venv not found at backend-fastapi\venv. Ensure dependencies are installed.
)
REM Force reloader to watch app and test module dirs (Windows file watchers can be flaky)
start cmd /k "uvicorn app.main:app --reload --reload-dir app --reload-dir app\tests\parametrize_advanced_test --reload-dir app\tests\parametrize_sampling_test"

REM Frontend
cd ..\frontend-next
echo Frontend dir: %CD%
start cmd /k "npm run dev"

endlocal
exit
