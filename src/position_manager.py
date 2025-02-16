"""
持仓数据管理模块
"""
import os
import json
import time
from typing import Dict, List, Optional
import requests
from datetime import datetime

from .config import config
from .logger import logger

class PositionManager:
    """持仓管理类"""
    _instance = None
    _positions: Dict = {}
    _assets: Dict = {}
    _last_update: float = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PositionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.initialize_data()

    def initialize_data(self):
        """初始化数据，如果文件不存在则使用配置的初始资金"""
        try:
            positions_file = config.get('data.positions_file')
            assets_file = config.get('data.assets_file')
            
            # 确保数据目录存在
            os.makedirs(os.path.dirname(positions_file), exist_ok=True)
            os.makedirs(os.path.dirname(assets_file), exist_ok=True)

            # 尝试加载现有数据
            positions_loaded = False
            assets_loaded = False

            if os.path.exists(positions_file):
                with open(positions_file, 'r', encoding='utf-8') as f:
                    self._positions = json.load(f)
                    positions_loaded = True
                logger.info("已加载现有持仓数据")

            if os.path.exists(assets_file):
                with open(assets_file, 'r', encoding='utf-8') as f:
                    self._assets = json.load(f)
                    assets_loaded = True
                logger.info("已加载现有资产数据")

            # 如果没有现有数据，使用配置的初始资金
            if not assets_loaded:
                initial_cash = config.get('account.initial_cash', 1000000.00)
                self._assets = {
                    'total_assets': initial_cash,
                    'total_market_value': 0.00,
                    'available_cash': initial_cash,
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                logger.info(f"使用配置的初始资金: {initial_cash}")
                self.save_data()

            if not positions_loaded:
                self._positions = {}
                logger.info("初始化空持仓数据")
                self.save_data()

        except Exception as e:
            logger.error(f"初始化数据失败: {str(e)}")
            raise

    def save_data(self):
        """保存持仓和资产数据"""
        try:
            # 保存持仓数据
            positions_file = config.get('data.positions_file')
            with open(positions_file, 'w', encoding='utf-8') as f:
                json.dump(self._positions, f, ensure_ascii=False, indent=2)

            # 保存资产数据
            assets_file = config.get('data.assets_file')
            with open(assets_file, 'w', encoding='utf-8') as f:
                json.dump(self._assets, f, ensure_ascii=False, indent=2)

            logger.info("数据保存成功")
        except Exception as e:
            logger.error(f"保存数据失败: {str(e)}")
            raise

    def update_positions(self) -> bool:
        """
        从服务器更新持仓信息，保持现金不变
        
        Returns:
            bool: 更新是否成功
        """
        # 检查更新间隔
        now = time.time()
        if now - self._last_update < config.get('cache.position_ttl', 60):
            return True

        try:
            # 调用API获取持仓信息
            api_url = f"{config.get('api.base_url')}/positions"
            response = requests.get(api_url, timeout=config.get('api.timeout', 30))
            response.raise_for_status()
            
            data = response.json()
            if data['code'] == 200 and 'data' in data:
                positions = data['data'].get('positions', [])
                
                # 更新持仓数据
                self._positions = {
                    p['stock_code']: p for p in positions
                }
                
                # 计算总市值
                total_market_value = sum(p['market_value'] for p in positions)
                
                # 保持现金不变，只更新总市值和总资产
                available_cash = self._assets['available_cash']
                total_assets = total_market_value + available_cash
                
                # 更新资产数据
                self._assets.update({
                    'total_assets': total_assets,
                    'total_market_value': total_market_value,
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                # 保存数据到文件
                self.save_data()
                
                # 更新时间戳
                self._last_update = now
                
                logger.info(f"持仓数据更新成功 - 总市值: {total_market_value:.2f}, 可用现金: {available_cash:.2f}")
                return True
            else:
                logger.error(f"获取持仓数据失败: {data.get('message', '未知错误')}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"请求持仓数据失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"更新持仓数据异常: {str(e)}")
            return False

    def update_cash(self, amount: float, reason: str):
        """
        更新现金金额
        
        Args:
            amount: 变动金额（正数表示增加，负数表示减少）
            reason: 变动原因
        """
        try:
            old_cash = self._assets['available_cash']
            new_cash = old_cash + amount
            
            if new_cash < 0:
                raise ValueError(f"现金不足，当前现金: {old_cash:.2f}, 需要: {abs(amount):.2f}")
            
            self._assets['available_cash'] = new_cash
            self._assets['total_assets'] = new_cash + self._assets['total_market_value']
            self._assets['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            self.save_data()
            logger.info(f"现金更新成功 - 原值: {old_cash:.2f}, 变动: {amount:.2f}, "
                       f"新值: {new_cash:.2f}, 原因: {reason}")
            
        except Exception as e:
            logger.error(f"更新现金失败: {str(e)}")
            raise

    def get_position(self, stock_code: str) -> Optional[Dict]:
        """
        获取指定股票的持仓信息
        
        Args:
            stock_code: 股票代码
        
        Returns:
            Dict: 持仓信息，如果不存在返回None
        """
        return self._positions.get(stock_code)

    def get_all_positions(self) -> List[Dict]:
        """
        获取所有持仓信息
        
        Returns:
            List[Dict]: 持仓信息列表
        """
        return list(self._positions.values())

    def get_assets(self) -> Dict:
        """
        获取资产信息
        
        Returns:
            Dict: 资产信息
        """
        return self._assets.copy()  # 返回副本以防止外部修改

# 创建全局持仓管理实例
position_manager = PositionManager() 