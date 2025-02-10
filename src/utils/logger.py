import sys
from loguru import logger
from pathlib import Path
from config.settings import LOG_LEVEL, LOG_FORMAT, LOG_FILE

def setup_logger():
    """配置日志"""
    # 创建日志目录
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format=LOG_FORMAT,
        level=LOG_LEVEL,
        colorize=True
    )
    
    # 添加文件处理器
    logger.add(
        LOG_FILE,
        format=LOG_FORMAT,
        level=LOG_LEVEL,
        rotation="1 day",    # 每天轮换一次
        retention="30 days", # 保留30天
        compression="zip"    # 压缩旧日志
    ) 