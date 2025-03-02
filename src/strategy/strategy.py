"""
策略管理模块，实现策略查询和执行功能
"""
from typing import List, Dict, Optional
import requests
import logging
from datetime import datetime, timedelta
from src.config import config

# 配置日志
logger = logging.getLogger(__name__)

class StrategyManager:
    """策略管理类"""
    
    def __init__(self):
        """初始化策略管理类"""
        self.base_url = config.get('api.base_url')
        logger.info(f"初始化策略管理器，API地址: {self.base_url}")
        
    def fetch_active_strategies(self) -> List[Dict]:
        """
        获取最近一周内的有效策略
        
        Returns:
            策略列表
        """
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        logger.info("="*50)
        logger.info("开始获取策略")
        logger.info("="*50)
        logger.info(f"查询时间范围: {start_time} 至 {end_time}")
        
        try:
            # 构建请求参数
            params = {
                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': True,
                'sort_by': 'created_at',
                'order': 'desc'
            }
            logger.info(f"请求参数: {params}")
            
            # 调用策略查询接口
            url = f"{self.base_url}/strategies/search"
            logger.info(f"调用策略查询接口: {url}")
            
            response = requests.get(
                url, 
                params=params,
                timeout=config.get('api.timeout')
            )
            response.raise_for_status()
            result = response.json()
            
            if result['code'] == 200:
                strategies = result['data']
                logger.info("-"*50)
                logger.info(f"获取到 {len(strategies)} 个策略")
                logger.info("-"*50)
                
                # 详细输出每个策略的信息
                for i, strategy in enumerate(strategies, 1):
                    logger.info(f"策略 {i}:")
                    logger.info(f"    ID: {strategy.get('id')}")
                    logger.info(f"    股票: {strategy.get('stock_name')}({strategy.get('stock_code')})")
                    
                    # 优化显示交易动作
                    action = strategy.get('action')
                    action_desc = {
                        'buy': '买入',
                        'sell': '卖出',
                        'hold': '持有',
                        'add': '加仓',
                        'trim': '减仓'
                    }.get(action, action)
                    logger.info(f"    动作: {action_desc}")
                    
                    logger.info(f"    仓位比例: {strategy.get('position_ratio')}%")
                    logger.info(f"    价格区间: {strategy.get('price_min', '不限')} - {strategy.get('price_max', '不限')}")
                    logger.info(f"    执行状态: {strategy.get('execution_status')}")
                    logger.info(f"    是否有效: {strategy.get('is_active')}")
                    logger.info(f"    创建时间: {strategy.get('created_at')}")
                    logger.info(f"    更新时间: {strategy.get('updated_at')}")
                    logger.info("-"*30)
                
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
            
    def validate_strategy(self, strategy: dict) -> bool:
        """
        验证策略是否有效
        
        Args:
            strategy: 策略数据
            
        Returns:
            bool: 是否有效
        """
        try:
            # 检查必要字段
            required_fields = ['stock_code', 'stock_name', 'action', 'position_ratio']
            for field in required_fields:
                if field not in strategy:
                    logger.error(f"策略缺少必要字段: {field}")
                    return False
            
            # 检查策略状态是否激活
            if not strategy.get('is_active', True):
                logger.info(f"策略 {strategy.get('id')} 未激活")
                return False
                
            # 检查交易类型
            valid_actions = ['buy', 'sell', 'hold', 'add', 'trim']
            if strategy['action'] not in valid_actions:
                logger.error(f"策略交易类型无效: {strategy['action']}")
                return False
                
            # 检查持仓比例是否超过最大限制（只有买入和加仓需要检查）
            if strategy['action'] in ['buy', 'add']:
                max_position_ratio = config.get('trading.max_position_ratio', 30)
                if strategy['position_ratio'] > max_position_ratio:
                    logger.warning(f"策略持仓比例 {strategy['position_ratio']}% 超过最大限制 {max_position_ratio}%")
                    return False
                
            # 检查价格限制
            if 'price_min' not in strategy:
                strategy['price_min'] = None
                logger.info(f"策略 {strategy.get('id')} 未设置最低价格限制")
                
            if 'price_max' not in strategy:
                strategy['price_max'] = None
                logger.info(f"策略 {strategy.get('id')} 未设置最高价格限制")
                
            return True
            
        except Exception as e:
            logger.error(f"验证策略异常: {str(e)}")
            return False 