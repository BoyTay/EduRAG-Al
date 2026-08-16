@echo off
REM setup.bat - Script cài đặt nhanh EduRAG trên Windows
REM Chạy: setup.bat

echo ============================================================
echo         EduRAG - Setup Script (Windows)
echo ============================================================
echo.

REM Kiểm tra Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python chua duoc cai dat! Vui long cai Python 3.10+
    pause
    exit /b 1
)
echo [OK] Python da san sang.

REM Kiểm tra Ollama
ollama --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Ollama chua duoc cai dat hoac chua trong PATH.
    echo        Vui long cai Ollama tai: https://ollama.ai
) else (
    echo [OK] Ollama da san sang.
)

REM Tạo virtual environment
echo.
echo [1/4] Tao virtual environment...
if not exist "venv" (
    python -m venv venv
    echo [OK] Virtual environment da tao.
) else (
    echo [SKIP] Virtual environment da ton tai.
)

REM Kích hoạt venv
call venv\Scripts\activate.bat

REM Cài đặt dependencies
echo.
echo [2/4] Cai dat dependencies backend...
pip install -r backend/requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Loi cai dat backend dependencies!
    pause
    exit /b 1
)
echo [OK] Backend dependencies da cai dat.

echo.
echo [3/4] Cai dat dependencies frontend...
pip install -r frontend/requirements.txt --quiet
echo [OK] Frontend dependencies da cai dat.

REM Tạo thư mục
echo.
echo [4/4] Tao thu muc can thiet...
if not exist "data" mkdir data
if not exist "chroma_db" mkdir chroma_db
echo [OK] Thu muc da san sang.

echo.
echo ============================================================
echo         Cai dat hoan tat!
echo ============================================================
echo.
echo BUOC TIEP THEO:
echo   1. Dat file PDF/DOCX vao thu muc: data\
echo   2. Kiem tra Ollama dang chay: ollama list
echo   3. Tao vector store: python scripts\build_index.py
echo   4. Chay backend (Terminal 1): cd backend ^&^& uvicorn main:app --port 8000 --reload
echo   5. Chay frontend (Terminal 2): cd frontend ^&^& streamlit run app.py
echo.
echo Giao dien: http://localhost:8501
echo API Docs:  http://localhost:8000/docs
echo.
pause
