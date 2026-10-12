@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo CineForge AI - moteur video LTX-2.5 pour Android
echo ================================================
echo.
echo Installation des dependances du serveur mobile...
python -m pip install -r requirements-mobile-server.txt
if errorlevel 1 (
  echo Echec installation serveur. Verifie Python et la connexion Internet.
  pause
  exit /b 1
)
echo.
echo IMPORTANT : le moteur video necessite PyTorch compatible avec ton materiel.
echo Le modele LTX-2.5 peut telecharger plusieurs gigaoctets au premier rendu.
echo Autorise Python dans le pare-feu Windows sur ton reseau prive.
echo Garde le code temporaire affiche dans cette console.
echo.
python -m uvicorn engine.mobile_server:app --host 0.0.0.0 --port 8765
pause
