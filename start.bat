@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  VocalApp launcher — opens two windows: FastAPI backend + Next.js dev.
REM  Once both are up, open http://localhost:3000 in your browser.
REM ─────────────────────────────────────────────────────────────────────────

set ROOT=%~dp0

REM Use `python -m uvicorn` (not bare `uvicorn`) so it works even if
REM C:\Users\<you>\AppData\Roaming\Python\Python3xx\Scripts\ is not on PATH.
start "VocalApp backend"  cmd /k "cd /d %ROOT%backend && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

start "VocalApp frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo.
echo Backend  :  http://127.0.0.1:8000   (uvicorn)
echo Frontend :  http://localhost:3000   (Next.js dev)
echo.
echo Open http://localhost:3000 in your browser once both windows say "ready".
