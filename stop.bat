@echo off
REM 第二人格 · 英语练习系统 —— 停止（释放 5000 端口）
setlocal
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:5000" ^| findstr "LISTENING"') do (
    echo 结束进程 PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
echo 已停止（若上面无输出表示端口本就空闲）。
pause
