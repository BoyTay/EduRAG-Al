@echo off
REM run.bat - Chạy EduRAG (backend + frontend) trong 2 cửa sổ terminal riêng
REM Đảm bảo đã chạy setup.bat (nếu muốn dùng venv) hoặc cài global trước

echo ============================================================
echo            EduRAG - Khoi dong he thong
echo ============================================================

REM Kiểm tra Ollama
echo Kiem tra Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Ollama chua chay. Dang khoi dong...
    start "" ollama serve
    timeout /t 3 /nobreak >nul
)

REM Chạy Backend
echo Khoi dong Backend (FastAPI port 8000)...
if exist venv\Scripts\activate.bat (
    start "EduRAG Backend" cmd /k "call venv\Scripts\activate.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
) else (
    start "EduRAG Backend" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
)

REM Đợi backend khởi động
echo Doi backend khoi dong (8 giay)...
timeout /t 8 /nobreak >nul

REM Chạy Frontend
echo Khoi dong Frontend (Streamlit port 8501)...
if exist venv\Scripts\activate.bat (
    start "EduRAG Frontend" cmd /k "call venv\Scripts\activate.bat && cd frontend && python -m streamlit run app.py --server.port 8501"
) else (
    start "EduRAG Frontend" cmd /k "cd frontend && python -m streamlit run app.py --server.port 8501"
)


echo.
echo He thong dang khoi dong...
echo   Backend API: http://localhost:8000
echo   API Docs:    http://localhost:8000/docs
echo   Frontend UI: http://localhost:8501
echo.
timeout /t 3 /nobreak >nul
start http://localhost:8501


