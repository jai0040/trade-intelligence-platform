@echo off
title Trade Intelligence Platform Launcher
echo ===================================================
echo   Trade Intelligence Platform - Starting Servers
echo ===================================================
echo.

echo Starting FastAPI Backend on http://localhost:8000 ...
start "Trade Intelligence Backend" powershell -NoExit -Command ".\.venv\Scripts\python.exe scripts\run_local_backend.py"

echo Starting Next.js Frontend on http://localhost:3000 ...
start "Trade Intelligence Frontend" powershell -NoExit -Command "npm run dev --prefix frontend"

echo.
echo ===================================================
echo   Both servers launched in separate windows!
echo   Frontend: http://localhost:3000
echo   Backend Docs: http://localhost:8000/docs
echo   Demo Login: admin@tradeintel.com / AdminPass123!
echo ===================================================
pause
