@echo off
cd /d %~dp0
set PY=D:\python-3-11\python.exe
if not exist "%PY%" set PY=python
if not exist .venv (
  "%PY%" -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if not exist .env copy .env.example .env
start "" http://localhost:5000
.venv\Scripts\python.exe app.py
pause
