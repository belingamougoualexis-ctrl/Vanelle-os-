@echo off
setlocal
py -3.11 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
 echo.
echo Base installee. Pour la video, installe PyTorch adapte au GPU puis requirements-video.txt.
pause
