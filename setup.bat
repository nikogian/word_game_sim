@echo off
echo Creating virtual environment
python -m venv venv

echo Activating virtual environment
call venv\Scripts\activate.bat

echo Upgrading pip
python -m pip install --upgrade pip

echo Installing dependencies
pip install -r requirements.txt

pause
