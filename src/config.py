"""
配置加载模块
"""
import os
import yaml
from typing import Dict, Any

class Config:
    """配置管理类"""
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.config = {}
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        config_path = os.path.join('config', 'config.yaml')
        if not os.path.exists(config_path):
            config_path = os.path.join('config', 'config.example.yaml')
            
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def update(self, key: str, value: Any):
        """
        更新配置项
        
        Args:
            key: 配置键名，支持点号分隔的多级键名
            value: 新的配置值
        """
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value

    def save(self, config_path: str = "config/config.yaml"):
        """
        保存配置到文件
        
        Args:
            config_path: 配置文件路径
        """
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self.config, f, allow_unicode=True)

# 创建全局配置实例
config = Config() 