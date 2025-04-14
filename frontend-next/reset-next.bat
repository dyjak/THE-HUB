@echo on
echo Resetowanie projektu Next.js...

:: Usuwanie katalogu node_modules
echo Usuwanie katalogu node_modules...
if exist node_modules (
    rd /s /q node_modules
) else (
    echo Folder node_modules nie istnieje.
)

:: Usuwanie pliku package-lock.json
echo Usuwanie pliku package-lock.json...
if exist package-lock.json (
    del /f /q package-lock.json
) else (
    echo Plik package-lock.json nie istnieje.
)

:: Czyszczenie cache npm
echo Czyszczenie cache npm...
call npm cache clean --force
set ERR_CACHE=%ERRORLEVEL%
if NOT "%ERR_CACHE%"=="0" (
    echo Wystąpił błąd podczas czyszczenia cache. Kod: %ERR_CACHE%
)

:: Instalowanie zależności
echo Instalowanie zależności...
call npm install
set ERR_INSTALL=%ERRORLEVEL%
if NOT "%ERR_INSTALL%"=="0" (
    echo Wystąpił błąd podczas instalacji zależności. Kod: %ERR_INSTALL%
)

echo.
echo Zakończono resetowanie projektu.
echo Naciśnij dowolny klawisz, aby zamknąć...
pause >nul
