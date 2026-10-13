@echo off
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% --version >nul 2>nul || (
  echo Python nahi mila. python.org se install karein aur "Add python.exe to PATH" tick karein.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Pehli dafa setup ho raha hai, 1-2 minute lagenge...
  %PY% -m venv .venv
)
.venv\Scripts\python -c "import flask, bs4, lxml, tldextract, dns, dateutil" >nul 2>nul || (
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt || (
    echo Install fail hua. Internet check karein aur dobara chalayein.
    pause
    exit /b 1
  )
)
start "" http://127.0.0.1:5000
echo Tool chal raha hai: http://127.0.0.1:5000   (band karne ke liye ye window close karein)
.venv\Scripts\python app.py
pause
