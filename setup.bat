@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 公招助手 安装 / Recruit Helper Setup

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 (
  echo.
  echo  未找到 Python 3.9+ / Python 3.9+ not found.
  echo  按任意键用 winget 安装 Python 3.11；或关闭窗口，自行从 python.org 安装后重新运行 setup.bat
  echo  Press any key to install Python 3.11 via winget, or close this window and install it yourself.
  pause >nul
  winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements
  echo.
  echo  Python 安装完成后，请重新运行 setup.bat / Please run setup.bat again.
  pause
  exit /b
)

echo [1/2] 安装依赖 / Installing dependencies ...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo  默认源失败，改用清华镜像 / Retrying with Tsinghua mirror ...
  python -m pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
if errorlevel 1 (
  echo  依赖安装失败 / Dependency install failed.
  pause
  exit /b 1
)

echo [2/2] 打开设置向导 / Opening setup wizard ...
start "" pythonw app.py --setup
