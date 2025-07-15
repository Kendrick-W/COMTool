@echo off
echo 正在启动COMTool...

:: 检查可执行文件是否存在
if not exist COMTool.exe (
    echo 错误：找不到COMTool.exe文件！
    echo 请确保该批处理文件与COMTool.exe在同一目录下。
    pause
    exit /b 1
)

:: 启动程序
start "" "COMTool.exe"

:: 检查启动是否成功
if %ERRORLEVEL% neq 0 (
    echo 启动COMTool失败，错误代码：%ERRORLEVEL%
    echo 请尝试以管理员身份运行此批处理文件。
    pause
) else (
    echo COMTool已成功启动！
)