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
        if not self._config:
            self.load_config()

    def load_config(self, config_path: str = "config/config.yaml"):
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键名，支持点号分隔的多级键名
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def update(self, key: str, value: Any):
        """
        更新配置项
        
        Args:
            key: 配置键名，支持点号分隔的多级键名
            value: 新的配置值
        """
        keys = key.split('.')
        config = self._config
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
            yaml.safe_dump(self._config, f, allow_unicode=True)

# 创建全局配置实例
config = Config() 