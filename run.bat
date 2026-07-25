@echo off
REM HyGraph one-click start (Windows)
REM Double-click this file to start the server at http://localhost:8000

cd /d "%~dp0backend"
if not exist venv (
    echo [HyGraph] venv not found, creating and installing deps...
    python -m venv venv
    venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo [HyGraph] starting server at http://localhost:8000
venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
