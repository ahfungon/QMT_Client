"""
策略管理模块，实现策略查询和执行功能
"""
from typing import List, Dict, Optional
import requests
import logging
from datetime import datetime, timedelta

# 配置日志
logger = logging.getLogger(__name__)

class StrategyManager:
    """策略管理类"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5000/api/v1"):
        """
        初始化策略管理类
        
        Args:
            base_url: API基础URL
        """
        self.base_url = base_url
        logger.info(f"初始化策略管理器，API地址: {base_url}")
        
    def fetch_active_strategies(self) -> List[Dict]:
        """
        获取最近一周内的有效策略
        
        Returns:
            策略列表
        """
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        logger.info(f"开始获取策略，时间范围: {start_time} 至 {end_time}")
        
        try:
            # 构建请求参数
            params = {
                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': True,
                'sort_by': 'created_at',
                'order': 'desc'
            }
            logger.debug(f"请求参数: {params}")
            
            # 调用策略查询接口
            url = f"{self.base_url}/strategies/search"
            logger.info(f"调用策略查询接口: {url}")
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            result = response.json()
            
            if result['code'] == 200:
                strategies = result['data']
                logger.info(f"成功获取到 {len(strategies)} 个策略")
                logger.debug(f"策略详情: {strategies}")
                return strategies
            else:
                logger.error(f"获取策略失败: {result['message']}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"请求策略接口异常: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"获取策略时发生未知异常: {str(e)}")
            return []
            
    def validate_strategy(self, strategy: Dict) -> bool:
        """
        验证策略是否有效
        
        Args:
            strategy: 策略信息
            
        Returns:
            是否有效
        """
        logger.info(f"开始验证策略: {strategy.get('stock_code')} - {strategy.get('action')}")
        
        # 检查必要字段是否存在
        required_fields = [
            'stock_code', 'action', 'position_ratio',
            'is_active'  # price_min 和 price_max 可以为空
        ]
        
        for field in required_fields:
            if field not in strategy:
                logger.error(f"策略缺少必要字段: {field}")
                return False
            # 检查字段值是否为None
            if strategy[field] is None:
                logger.error(f"策略字段 {field} 的值为None")
                return False
                
        # 检查字段值
        if not strategy['is_active']:
            logger.error("策略已失效")
            return False
            
        try:
            # 转换为float进行数值比较
            position_ratio = float(strategy['position_ratio'])
            
            # 处理价格区间的特殊情况
            price_min = strategy.get('price_min')
            price_max = strategy.get('price_max')
            
            # 最低价为空或None时设为0
            if price_min is None or price_min == '':
                price_min = 0
                logger.info("最低价为空，设置为0")
            else:
                price_min = float(price_min)
                
            # 最高价为空或None时设为正无穷
            if price_max is None or price_max == '':
                price_max = float('inf')
                logger.info("最高价为空，设置为无穷大")
            else:
                price_max = float(price_max)
            
            # 更新策略中的价格值
            strategy['price_min'] = price_min
            strategy['price_max'] = price_max
            
            if position_ratio <= 0 or position_ratio > 1:
                logger.error(f"仓位比例无效: {position_ratio}")
                return False
                
            if price_min < 0:  # 只检查最低价是否小于0
                logger.error(f"最低价无效: {price_min}")
                return False
                
            if price_min > price_max:
                logger.error(f"最低价大于最高价: {price_min} > {price_max}")
                return False
                
        except (TypeError, ValueError) as e:
            logger.error(f"策略数值字段格式错误: {str(e)}")
            return False
            
        logger.info(f"策略验证通过 - 价格区间: {price_min} - {price_max}")
        return True 