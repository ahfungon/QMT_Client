"""
系统配置文件
"""
import os
from pathlib import Path

# API 配置
API_HOST = "127.0.0.1"
API_PORT = 5000
API_VERSION = "v1"
API_BASE_URL = f"http://{API_HOST}:{API_PORT}/api/{API_VERSION}"

# 交易配置
INITIAL_CASH = 1000000  # 初始资金：100万
MIN_BUY_VOLUME = 100    # 最小买入数量：100股
MIN_SELL_VOLUME = 100   # 最小卖出数量：100股
VOLUME_STEP = 100       # 交易数量步长：100股的整数倍

# 定时任务配置
SCHEDULE_INTERVAL = 30  # 定时任务执行间隔（秒）

# 文件路径配置
BASE_DIR = Path(__file__).parent.parent  # 项目根目录
DATA_DIR = BASE_DIR / "data"            # 数据目录
LOG_DIR = BASE_DIR / "logs"             # 日志目录
POSITION_FILE = DATA_DIR / "positions.json"  # 持仓文件
ASSETS_FILE = DATA_DIR / "assets.json"      # 资产文件

# 日志配置
LOG_LEVEL = "INFO"  # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOG_DIR / "app.log"

# 持仓文件配置
POSITION_FILE_ENCODING = "utf-8"
POSITION_FILE_INDENT = 2

# 请求超时设置
REQUEST_TIMEOUT = 30  # 请求超时时间（秒）

# 重试配置
MAX_RETRIES = 3      # 最大重试次数
RETRY_DELAY = 1      # 重试延迟（秒）

# 交易时间配置
TRADING_START_TIME = "09:30:00"  # 交易开始时间
TRADING_END_TIME = "15:00:00"    # 交易结束时间
TRADING_DAYS = [1, 2, 3, 4, 5 ,6 ,7]   # 正常交易日（周一到周五） 为了测试，加上周末

# 资产更新配置
ASSETS_UPDATE_INTERVAL = 60  # 资产更新间隔（秒）