@echo off
REM ------------------------------------------------------------
REM Build the Minesweeper game with PyInstaller (onedir mode)
REM
REM WHY onedir and not --onefile?
REM   * --onefile extracts itself to %TEMP% on every launch. On this
REM     machine that step gets blocked (antivirus heuristics flag
REM     unsigned exes extracting to temp) and the game dies instantly
REM     with "Could not create temporary directory!".
REM   * onedir runs straight from its own folder - no temp needed,
REM     and much less likely to trigger antivirus.
REM
REM NOTE: the game reads keyboard input from the console, so the exe
REM MUST keep its console window (do NOT use --noconsole).
REM
REM RESULT: Minesweeper.exe + _internal folder at this project root.
REM         Keep them together; double-click Minesweeper.exe to play.
REM ------------------------------------------------------------
cd /d "%~dp0"

REM Kill any stale/hung game instances so files are not locked
taskkill /f /im Minesweeper.exe 2>nul

echo Removing the previous build...
if exist Minesweeper.exe del /q Minesweeper.exe
if exist _internal rd /q /s _internal

echo Installing PyInstaller (skipped automatically if present)...
python -m pip install --quiet --upgrade pyinstaller

echo Building (onedir) ...
python -m PyInstaller --onedir --name Minesweeper ^
    --distpath . --workpath build --specpath build ^
    src\minesweeper.py

REM Flatten PyInstaller's app-named subfolder to this root
if exist Minesweeper\Minesweeper.exe (
    move /y Minesweeper\Minesweeper.exe . >nul
    move /y Minesweeper\_internal . >nul
    rd /q /s Minesweeper 2>nul
)

rd /q /s build 2>nul

if exist Minesweeper.exe (
    echo.
    echo Build finished successfully.
    echo Run the game with:  Minesweeper.exe
    echo ^(keep Minesweeper.exe next to the _internal folder^)
) else (
    echo.
    echo Build FAILED - check the messages above.
)
pause
