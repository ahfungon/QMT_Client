@echo off
echo 正在启动QMT交易助手...

:: 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到Python环境，请安装Python 3.10或更高版本
    pause
    exit /b 1
)

:: 检查依赖
echo 正在检查依赖...
pip install -r requirements.txt

:: 启动程序
echo 正在启动程序...
python run.py

pause 