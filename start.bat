@echo off
REM 第二人格 · 英语练习系统 —— 一键启动
REM 用 managed venv 的 python 启动 Flask，自动清理占用 5000 端口的旧进程，并打开浏览器。
setlocal

set PY="C:/Users/LIUZHANXIN/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
set APP="D:/workbuddy/English Learning/practice-app/app.py"
set URL=http://127.0.0.1:5000

REM 若 5000 已被占用（LISTENING），结束其进程，避免 Address already in use
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:5000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo 正在启动练习系统...
start "" /min %PY% %APP%

REM 等待服务起来后自动打开浏览器
timeout /t 2 >nul
start "" %URL%

echo 已启动，若浏览器未弹出请手动访问： %URL%
echo 关闭窗口不会停止服务；停止请运行 stop.bat 或结束 5000 端口进程。
pause
