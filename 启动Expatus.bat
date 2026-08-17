@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [Expatus] 未找到 .venv，请先按 README 完成第一次安装。
  pause
  exit /b 1
)
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe app.py
pause
