@echo off
rem Build a single exe: dist\ArknightsRecruitHelper.exe  (uses a clean venv to keep it small)
cd /d "%~dp0"
if not exist .venv-build\Scripts\python.exe python -m venv .venv-build || exit /b 1
set PY=.venv-build\Scripts\python.exe
%PY% -m pip install -q -r requirements.txt pyinstaller || exit /b 1
rem headless OpenCV: no GUI/video codecs, ~70MB smaller
%PY% -m pip uninstall -y -q opencv-python >nul 2>nul
%PY% -m pip install -q --force-reinstall --no-deps opencv-python-headless || exit /b 1
%PY% -c "import cv2, rapidocr_onnxruntime" || exit /b 1
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
  --name ArknightsRecruitHelper --icon icon.ico ^
  --add-data "data/pool_cn.json;data" --add-data "data/pool_en.json;data" ^
  --collect-all rapidocr_onnxruntime --hidden-import pystray._win32 ^
  --exclude-module matplotlib --exclude-module scipy --exclude-module pandas ^
  app.py || exit /b 1
echo.
echo Built: dist\ArknightsRecruitHelper.exe
