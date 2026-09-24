@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY if exist "C:\Users\lbx13\.workbuddy\binaries\python\versions\3.13.12\python.exe" set "PY=C:\Users\lbx13\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not defined PY (
  echo 没有找到 Python，无法启动资产库服务。
  echo 可编辑本文件，把 PY 指向你的 python.exe。
  pause
  exit /b 1
)

echo 正在启动资产库服务，浏览器会自动打开…
start "" /b cmd /c "timeout /t 2 >nul & start "" http://localhost:8800"

"%PY%" serve_v3.py

echo.
echo 服务已停止。
pause
