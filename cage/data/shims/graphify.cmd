@echo off
rem cage: graphify metering interceptor (Windows twin) - routes queries through
rem `cage interceptor graphify` so each query/path/explain files a token-saving receipt;
rem stdout/stderr/exit pass through unchanged. `graphify update .` and any non-query
rem verb pass straight through (nothing to meter). Installed by `cage setup`.
rem
rem Behaviour contract B1-B8 and the cmd-vs-sh divergences D1-D7 live in
rem docs/adr/0007_graphify.md §2. The POSIX twin is the extensionless `graphify` beside this
rem file; the two are hand-paired against that one contract rather than generated from
rem a shared template - batch and sh have no common syntax subset, the same reason
rem runshim.py hand-pairs its own twins.
rem
rem Recursion guard: the real graphify is resolved by walking PATH and SKIPPING every
rem cage-written interceptor, matched by CONTENT and never by filename (B3). Two stacked
rem shims that each stripped only their own directory resolved to each other and
rem recursed forever. That, the CAGE_GRAPHIFY_SHIM re-entry guard (B1), PATHEXT
rem blindness to the extensionless POSIX twin (D2) and a flat, call-free walk (B8)
rem together make a resolution loop impossible.
rem
rem The walk is ONE flat nested FOR (directory x extension) with no `call`/`goto`
rem back into it. An earlier draft used `call :subroutine` from inside this loop plus
rem a `goto` back-edge to re-enter it - reproduced on real Windows CI as cmd.exe's own
rem "Recursion Count=..., Stack Usage=... BATCH PROCESSING IS ABORTED" safety abort,
rem tripping around 335 hops even though this script's own counter never got near its
rem bound. cmd.exe's CALL/GOTO bookkeeping leaks stack frames under that combination;
rem a flat loop with no subroutine call has no such failure mode.
setlocal EnableDelayedExpansion
if not defined PATHEXT set "PATHEXT=.COM;.EXE;.BAT;.CMD"

rem B1 read side: already inside a metering shim => do not meter again.
set "_CAGE_GF_REENTRY=0"
if "%CAGE_GRAPHIFY_SHIM%"=="1" set "_CAGE_GF_REENTRY=1"

rem B2: walk PATH, directory-major (matches real shell resolution order - every
rem extension is tried in one directory before moving to the next). The
rem `"%PATH:;=" "%"` idiom splits the semicolon-delimited PATH into a properly quoted,
rem space-separated list for the outer FOR; an empty segment (a stray `;;`) yields an
rem empty item that matches nothing and is skipped, same as B2 requires.
rem
rem No `rem` line sits INSIDE the parenthesized block below, on purpose: cmd.exe's
rem parser still tokenizes redirection/pipe/paren characters inside a comment when
rem that comment is nested inside a multi-line `(...)` block, and a comment here once
rem read "<candidate>" - the `<`/`>` characters corrupted the block's parsing and
rem reproduced cmd.exe's own "BATCH RECURSION exceeds STACK limits" abort on every
rem real Windows CI run, identically across two structurally different walk
rem implementations, until this comment was moved out here. A candidate is claimed as
rem the real binary unless it self-identifies as one of ours (B3, content never
rem filename): `findstr` finds a marker => skip it; no match => claim it.
set "_CAGE_GF_REAL="
for %%d in ("%PATH:;=" "%") do (
  if not defined _CAGE_GF_REAL (
    for %%e in (%PATHEXT%) do (
      if not defined _CAGE_GF_REAL (
        set "_CAGE_GF_CAND=%%~d\graphify%%e"
        if exist "!_CAGE_GF_CAND!" (
          findstr /M /C:"cage interceptor graphify" /C:"cage data graphify" /C:"cage graphify" /C:"graphify metering interceptor" "!_CAGE_GF_CAND!" >nul 2>nul
          if errorlevel 1 set "_CAGE_GF_REAL=!_CAGE_GF_CAND!"
        )
      )
    )
  )
)

if defined _CAGE_GF_REAL goto cage_gf_found

rem Fail-open last resort (D3): a PATH entry the tokenizer above cannot split, or an
rem unusable PATHEXT. Ask the OS resolver, still content-filtered so an interceptor can
rem never be picked. A broken graphify is worse than an unmetered one.
for /f "usebackq delims=" %%p in (`where graphify 2^>nul`) do (
  if not defined _CAGE_GF_REAL (
    findstr /M /C:"cage interceptor graphify" /C:"cage data graphify" /C:"cage graphify" /C:"graphify metering interceptor" "%%p" >nul 2>nul
    if errorlevel 1 set "_CAGE_GF_REAL=%%p"
  )
)
if defined _CAGE_GF_REAL goto cage_gf_found

rem B4: only interceptors are on PATH - the real graphify is not installed. Refuse to
rem fall back to the bare name (that would re-enter a shim and recurse); fail cleanly.
1>&2 echo graphify: not found - only the metering interceptor shim is on PATH
exit /b 127

:cage_gf_found
rem Delayed expansion is turned OFF from here on: it would eat `!` out of the
rem forwarded %* below (B7). This is why the PATH-walk above sat inside its own
rem EnableDelayedExpansion scope instead of covering the whole script.
setlocal DisableDelayedExpansion

rem B5: meter only when cage can actually RUN the verb - two arms, tried in order. The
rem `--help` probe is what catches a renamed verb (F1) instead of silently running
rem unmetered. Arm 1 (the `cage` command) always wins first, so a standard install is
rem unchanged in behaviour and in latency.
if "%_CAGE_GF_REENTRY%"=="1" goto cage_gf_direct
where cage >nul 2>nul
if errorlevel 1 goto cage_gf_arm2
call cage interceptor graphify --help >nul 2>nul
if errorlevel 1 goto cage_gf_arm2
set "CAGE_GRAPHIFY_SHIM=1"
call cage interceptor graphify -- "%_CAGE_GF_REAL%" %*
exit /b %ERRORLEVEL%

rem Arm 2 (B5b, GF-LAUNCHER verdict B): no `cage` COMMAND is not no cage. D8 - the POSIX
rem twin says `python3` and this one cannot: `python3` is frequently absent on Windows,
rem where the launcher is `py -3`, with bare `python` as the fallback for a PATH install
rem that has no launcher. Two spellings, tried in that order; neither resolving means the
rem call was always going to be unmetered anyway. Flat gotos and no parenthesized block,
rem for the same B8 reason the PATH walk above is flat.
:cage_gf_arm2
py -3 -m cage interceptor graphify --help >nul 2>nul
if not errorlevel 1 goto cage_gf_arm2_py
python -m cage interceptor graphify --help >nul 2>nul
if not errorlevel 1 goto cage_gf_arm2_python
goto cage_gf_direct

:cage_gf_arm2_py
set "CAGE_GRAPHIFY_SHIM=1"
call py -3 -m cage interceptor graphify -- "%_CAGE_GF_REAL%" %*
exit /b %ERRORLEVEL%

:cage_gf_arm2_python
set "CAGE_GRAPHIFY_SHIM=1"
call python -m cage interceptor graphify -- "%_CAGE_GF_REAL%" %*
exit /b %ERRORLEVEL%

:cage_gf_direct
rem No cage / re-entry -> identical, unmetered behaviour. D1: `call` + `exit /b`, because
rem cmd has no `exec` - the real binary is a child process, not a replacement.
call "%_CAGE_GF_REAL%" %*
exit /b %ERRORLEVEL%
