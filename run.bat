@echo off
call venv\Scripts\activate
echo ---------------------------------------------
echo Visit your app in your browser:
echo http://localhost:8000
echo ---------------------------------------------
python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
