@echo off
REM Cai dat nhanh EduRAG cho Windows: FastAPI + React/Vite

echo ============================================================
echo                 EduRAG - Setup
echo ============================================================

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Can cai Python 3.10 tro len.
    pause
    exit /b 1
)

node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Can cai Node.js 20 tro len.
    pause
    exit /b 1
)

ollama --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Ollama chua co trong PATH. Hay cai Ollama truoc khi chay chat.
)

if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat

echo Cai dependencies backend...
pip install -r backend\requirements.txt
if %ERRORLEVEL% NEQ 0 exit /b 1

echo Cai dependencies frontend React...
pushd frontend
npm install
if %ERRORLEVEL% NEQ 0 (
    popd
    exit /b 1
)
popd

if not exist "data" mkdir data
if not exist "chroma_db" mkdir chroma_db

echo.
echo Cai dat hoan tat. Chay run.bat hoac dung Docker Compose.
echo Frontend: http://localhost:3000
pause
