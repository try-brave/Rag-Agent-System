@echo off
title RAG Agent - One-click Launcher

echo ============================================
echo   RAG Agent - One-click Launcher
echo ============================================
echo.

echo [1/3] Starting Docker infra (PostgreSQL + Milvus)...
docker start postgres-deep milvus-etcd milvus-minio milvus-standalone >nul 2>&1
echo       waiting 10s for services to be ready...
timeout /t 10 /nobreak >nul

echo [2/3] Launching backend on :8001 ...
start "RAG-Backend" cmd /k "cd /d C:\Users\yj\Desktop\rag_agent\backend && .venv\Scripts\python.exe run.py"

echo [3/3] Launching frontend on :5174 ...
start "RAG-Frontend" cmd /k "cd /d C:\Users\yj\Desktop\rag_agent\front\rag_front && npm run dev -- --open"

echo.
echo All services launched.
echo   Backend : http://localhost:8001/health
echo   Frontend: http://localhost:5174
echo Close the two opened windows to stop the servers.
echo.
pause
