@echo off
chcp 65001 >nul
echo 正在启动串口工具...
echo.
echo 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到Python环境！
    echo 请先安装Python 3.7或更高版本
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python环境检查通过
echo.
echo 检查依赖包...
python -c "import PyQt5, serial" >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 依赖包安装失败！请检查网络连接或手动安装
        echo 手动安装命令：pip install PyQt5 pyserial
        pause
        exit /b 1
    )
    echo 依赖包安装完成
)

echo 启动应用程序...
echo.
python main.py
if errorlevel 1 (
    echo.
    echo 程序运行出错！
    pause
)