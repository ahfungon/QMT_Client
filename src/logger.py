"""
日志模块
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from .config import config

def setup_logger() -> logging.Logger:
    """
    设置日志记录器
    
    Returns:
        logging.Logger: 日志记录器实例
    """
    # 创建日志记录器
    logger = logging.getLogger('QMT_Client')
    logger.setLevel(config.get('logging.level', 'INFO'))

    # 创建日志格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 创建文件处理器
    log_file = config.get('logging.file_path', 'logs/app.log')
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=config.get('logging.max_size', 100) * 1024 * 1024,  # 转换为字节
        backupCount=config.get('logging.backup_count', 30),
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# 创建全局日志记录器实例
logger = setup_logger() 