@echo off
rem cage: graphify metering interceptor (Windows twin) - routes queries through
rem `cage data graphify` so each query/path/explain files a token-saving receipt;
rem stdout/stderr/exit pass through unchanged. `graphify update .` and any non-query
rem verb pass straight through (nothing to meter). Installed by `cage setup`.
rem
rem Behaviour contract B1-B8 and the cmd-vs-sh divergences D1-D7 live in
rem docs/shim-contract.md. The POSIX twin is the extensionless `graphify` beside this
rem file; the two are hand-paired against that one contract rather than generated from
rem a shared template - batch and sh have no common syntax subset, the same reason
rem runshim.py hand-pairs its own twins.
rem
rem Recursion guard: the real graphify is resolved by walking PATH and SKIPPING every
rem cage-written interceptor, matched by CONTENT and never by filename (B3). Two stacked
rem shims that each stripped only their own directory resolved to each other and
rem recursed forever. That, the CAGE_GRAPHIFY_SHIM re-entry guard (B1), PATHEXT
rem blindness to the extensionless POSIX twin (D2) and the bounded walk (B8) together
rem make a resolution loop impossible.
rem
rem Delayed expansion is deliberately NOT enabled: it would eat `!` out of %* (B7).
setlocal
if not defined PATHEXT set "PATHEXT=.COM;.EXE;.BAT;.CMD"

rem B1 read side: already inside a metering shim => do not meter again.
set "_CAGE_GF_REENTRY=0"
if "%CAGE_GRAPHIFY_SHIM%"=="1" set "_CAGE_GF_REENTRY=1"

rem B2: walk PATH head-first. Bounded at 512 hops (B8) so a PATH the tokenizer cannot
rem split degrades to the fail-open resolver below instead of spinning forever.
set "_CAGE_GF_REAL="
set "_CAGE_GF_REST=%PATH%"
set "_CAGE_GF_HOPS=0"

:cage_gf_walk
if not defined _CAGE_GF_REST goto cage_gf_walked
set /a _CAGE_GF_HOPS+=1
if %_CAGE_GF_HOPS% GTR 512 goto cage_gf_walked
set "_CAGE_GF_DIR="
for /f "tokens=1* delims=;" %%a in ("%_CAGE_GF_REST%") do (
  set "_CAGE_GF_DIR=%%~a"
  set "_CAGE_GF_REST=%%b"
)
if not defined _CAGE_GF_DIR goto cage_gf_walk
for %%e in (%PATHEXT%) do (
  if not defined _CAGE_GF_REAL call :cage_gf_try "%_CAGE_GF_DIR%\graphify%%e"
)
if not defined _CAGE_GF_REAL goto cage_gf_walk

:cage_gf_walked
if defined _CAGE_GF_REAL goto cage_gf_found
rem Fail-open last resort (D3): a PATH entry the tokenizer above cannot split, or an
rem unusable PATHEXT. Ask the OS resolver, still content-filtered so an interceptor can
rem never be picked. A broken graphify is worse than an unmetered one.
for /f "usebackq delims=" %%p in (`where graphify 2^>nul`) do (
  if not defined _CAGE_GF_REAL call :cage_gf_try "%%~p"
)
if defined _CAGE_GF_REAL goto cage_gf_found
rem B4: only interceptors are on PATH - the real graphify is not installed. Refuse to
rem fall back to the bare name (that would re-enter a shim and recurse); fail cleanly.
1>&2 echo graphify: not found - only the metering interceptor shim is on PATH
exit /b 127

:cage_gf_found
rem B5: meter only when a cage command resolves AND still accepts the verb. The second
rem probe is what catches a renamed verb (F1) instead of silently running unmetered.
if "%_CAGE_GF_REENTRY%"=="1" goto cage_gf_direct
where cage >nul 2>nul
if errorlevel 1 goto cage_gf_direct
call cage data graphify --help >nul 2>nul
if errorlevel 1 goto cage_gf_direct
set "CAGE_GRAPHIFY_SHIM=1"
call cage data graphify -- "%_CAGE_GF_REAL%" %*
exit /b %ERRORLEVEL%

:cage_gf_direct
rem No cage / re-entry -> identical, unmetered behaviour. D1: `call` + `exit /b`, because
rem cmd has no `exec` - the real binary is a child process, not a replacement.
call "%_CAGE_GF_REAL%" %*
exit /b %ERRORLEVEL%

:cage_gf_try
rem "<candidate>" -> claim it as the real binary unless it self-identifies as one of
rem ours (B3). Content, never filename. An unreadable file is not ours to skip, which
rem matches the sh twin's `grep ... 2>/dev/null` returning non-zero.
if not exist "%~1" goto :eof
findstr /M /C:"cage data graphify" /C:"cage graphify" /C:"graphify metering interceptor" "%~1" >nul 2>nul
if not errorlevel 1 goto :eof
set "_CAGE_GF_REAL=%~1"
goto :eof
