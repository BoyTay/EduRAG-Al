@echo off
REM Chay EduRAG local: FastAPI + React/Vite

echo ============================================================
echo            EduRAG - Khoi dong he thong
echo ============================================================

curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Ollama chua chay. Dang khoi dong...
    start "EduRAG Ollama" ollama serve
    timeout /t 3 /nobreak >nul
)

echo Khoi dong Backend (FastAPI port 8000)...
if exist venv\Scripts\activate.bat (
    start "EduRAG Backend" cmd /k "call venv\Scripts\activate.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
) else (
    start "EduRAG Backend" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
)

echo Khoi dong Frontend (Vite port 3000)...
start "EduRAG Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo   Frontend UI: http://localhost:3000
echo   API Docs:    http://localhost:8000/docs
echo.
timeout /t 3 /nobreak >nul
start http://localhost:3000
