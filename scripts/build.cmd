@echo off
setlocal

:: Repository root (folder containing this script's parent)
set "REPO_ROOT=%~dp0.."
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

REM --- Extract version from pyproject.toml ---
for /f "tokens=2 delims== " %%V in ('findstr /R "^version" "%REPO_ROOT%\pyproject.toml"') do (
    set "APP_VERSION=%%~V"
)
echo [INFO] Version: %APP_VERSION%

:: Use PyInstaller via Python (no PATH needed)
set "PYINSTALLER=python -m PyInstaller"

set "ICON_PNG=%REPO_ROOT%\resources\calmweb.png"
set "ICON_ICO=%REPO_ROOT%\resources\calmweb.ico"
set "ICON_SWITCH="
if /i "%NO_ICON%"=="1" (
  echo NO_ICON=1 set: skipping icon.
) else (
  if exist "%ICON_ICO%" (
    set "ICON_SWITCH=--icon "%ICON_ICO%""
  ) else if exist "%ICON_PNG%" (
    set "ICON_SWITCH=--icon "%ICON_PNG%""
    echo Using PNG icon. If PyInstaller errors, install Pillow:  pip install pillow
  ) else (
    echo No icon found; skipping icon. Set NO_ICON=1 to suppress this message.
  )
)

set "ENTRY=%REPO_ROOT%\scripts\pyinstaller_entry.py"
set "DIST_DIR=%REPO_ROOT%\dist"
set "DIST_EXE=%DIST_DIR%\calmweb_installer.exe"
set "BUILD_SWITCH=--onefile"
set "RUNTIME_SWITCH="

if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

:: Allow forcing onedir build: set ONEDIR=1 before running
if /i "%ONEDIR%"=="1" (
  set "BUILD_SWITCH=--onedir"
  set "RUNTIME_SWITCH="
)

:: Best effort: remove previous exe so PyInstaller can overwrite
if exist "%DIST_EXE%" (
  del /f /q "%DIST_EXE%" >nul 2>&1
)

REM --- Write VERSION file for PyInstaller bundle ---
echo %APP_VERSION%> "%REPO_ROOT%\VERSION"

%PYINSTALLER% ^
  --clean ^
  --name calmweb_installer ^
  --hidden-import urllib3 ^
  --hidden-import tkinter ^
  --hidden-import tkinter.scrolledtext ^
  --hidden-import darkdetect ^
  --collect-all customtkinter ^
  --add-data "%REPO_ROOT%\resources\calmweb.png;." ^
  --add-data "%REPO_ROOT%\resources\calmweb_active.png;." ^
  --add-data "%REPO_ROOT%\VERSION;." ^
  %BUILD_SWITCH% ^
  --noconsole ^
  --paths "%REPO_ROOT%\src" ^
  %RUNTIME_SWITCH% ^
  %ICON_SWITCH% ^
  --distpath "%DIST_DIR%" ^
  "%ENTRY%"

if %errorlevel% neq 0 (
  echo Build failed.
  pause
  exit /b %errorlevel%
)

echo.
echo Build complete. Output: "%DIST_EXE%"

:: --- Step 2: Build Inno Setup installer ---
echo.
echo Building installer package...

set "ISCC="
for /f "delims=" %%I in ('where iscc 2^>nul') do (
    set "ISCC=%%I"
    goto :found_iscc
)
:found_iscc
if not defined ISCC (
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
        set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    )
)

if not defined ISCC (
    echo.
    echo Inno Setup not found. Skipping installer package.
    echo Install from: https://jrsoftware.org/isinfo.php
    goto :done
)

"%ISCC%" /DMyAppVersion=%APP_VERSION% "%REPO_ROOT%\installer\calmweb.iss"

if %errorlevel% neq 0 (
    echo Installer build failed.
    pause
    exit /b %errorlevel%
)

echo.
echo Installer built: "%REPO_ROOT%\dist\CalmWeb_Setup.exe"

:: Clean up intermediate PyInstaller executable (bundled inside the Setup)
if exist "%DIST_EXE%" (
    del /f /q "%DIST_EXE%" >nul 2>&1
    echo Cleaned up intermediate file: calmweb_installer.exe
)

:done
pause
