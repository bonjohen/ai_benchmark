@echo off
setlocal
set ANTHROPIC_API_KEY=
set ANTHROPIC_AUTH_TOKEN=
echo Key is: [%ANTHROPIC_API_KEY%]
set ANTHROPIC 2>nul
echo ---
claude auth status
echo ---
claude -p "Reply with exactly: OAUTH_OK"
echo Exit code: %ERRORLEVEL%
endlocal
