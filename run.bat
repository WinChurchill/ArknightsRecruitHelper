@echo off
cd /d "%~dp0"
rem 已运行过 setup：通过计划任务以管理员启动（不弹 UAC）；否则先走安装
schtasks /run /tn ArkRecruitHelper_Open >nul 2>nul && exit /b
if not exist config.json (call setup.bat & exit /b)
start "" pythonw app.py
