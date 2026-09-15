@echo off
cd /d "%~dp0Padelpie_Clubs"
if not exist .venv\Scripts\python.exe python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe club_app.py
pause
