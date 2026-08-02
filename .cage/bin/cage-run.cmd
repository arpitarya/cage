@echo off
rem cage-run.cmd — cage-managed runtime resolver (committed; identical on every machine).
rem Windows twin of cage-run: same order, same fail-open exit 0 when cage is absent.
rem CAGE_RUN_PYTHON=1 skips the exe probe (`cage query restricted-env`).
rem UNVERIFIED on a real Windows agent host (same label discipline as paths.py).
if "%CAGE_RUN_PYTHON%"=="1" goto pyonly
where cage >nul 2>nul
if %errorlevel%==0 (
  cage %*
  exit /b %errorlevel%
)
if exist "%USERPROFILE%\.local\bin\cage.exe" (
  "%USERPROFILE%\.local\bin\cage.exe" %*
  exit /b %errorlevel%
)
if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\cage.exe" (
  "%VIRTUAL_ENV%\Scripts\cage.exe" %*
  exit /b %errorlevel%
)
py -3 -c "import cage" >nul 2>nul
if %errorlevel%==0 (
  py -3 -m cage %*
  exit /b %errorlevel%
)
exit /b 0
:pyonly
py -3 -c "import cage" >nul 2>nul
if not %errorlevel%==0 exit /b 0
py -3 -m cage %*
exit /b %errorlevel%
