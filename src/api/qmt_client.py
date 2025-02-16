from typing import Dict, List, Optional
import requests
from pydantic import BaseModel
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from src.config import config

class QMTClient:
    """QMT服务器API客户端"""
    
    def __init__(self):
        """初始化QMT客户端"""
        self.base_url = config.get('api.base_url')
        logger.info(f"初始化QMT客户端，API地址: {self.base_url}")

    @retry(
        stop=stop_after_attempt(config.get('api.retry_times', 3)), 
        wait=wait_exponential(
            multiplier=1, 
            min=config.get('api.retry_interval', 4), 
            max=config.get('api.retry_interval', 4) * 2
        )
    )
    async def get_strategies(self, 
                           start_time: Optional[str] = None, 
                           end_time: Optional[str] = None) -> List[Dict]:
        """
        获取指定时间范围内的策略列表
        
        Args:
            start_time: 开始时间，默认为一周前
            end_time: 结束时间，默认为当前时间
            
        Returns:
            List[Dict]: 策略列表
        """
        # 如果未指定时间，默认查询最近一周
        if not start_time:
            start_time = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        if not end_time:
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        params = {
            "start_time": start_time,
            "end_time": end_time,
            "is_active": True,
            "sort_by": "updated_at",
            "order": "desc"
        }
        
        try:
            logger.info(f"正在查询策略列表: {params}")
            response = requests.get(
                f"{self.base_url}/strategies/search", 
                params=params,
                timeout=config.get('api.timeout')
            )
            response.raise_for_status()
            data = response.json()["data"]
            logger.info(f"成功获取到 {len(data)} 条策略")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"查询策略失败: {str(e)}")
            raise 