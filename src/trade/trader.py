"""
交易模块核心类，实现买入和卖出功能
"""
from typing import Dict, Union, Optional, List, Tuple
import json
import os
import time
import portalocker
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.quote.quote import QuoteService
from src.config import config

# 配置日志
logger = logging.getLogger(__name__)

class TradeError(Exception):
    """交易异常基类"""
    pass

class InvalidTimeError(TradeError):
    """非交易时间异常"""
    pass

class InsufficientFundsError(TradeError):
    """资金不足异常"""
    pass

class NoPositionError(TradeError):
    """无持仓异常"""
    pass

class PriceNotMatchError(TradeError):
    """价格不匹配异常"""
    pass

class ApiError(TradeError):
    """API调用异常"""
    pass

class FrequencyLimitError(TradeError):
    """交易频率超限异常"""
    pass

class PositionLimitError(TradeError):
    """持仓比例超限异常"""
    pass

class PriceDeviationError(TradeError):
    """价格偏离度超限异常"""
    pass

class FileLock:
    """跨平台文件锁"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.lock_file = f"{file_path}.lock"
        self.lock = None
        self.retries = 3
        self.retry_delay = 1
        
    def __enter__(self):
        for attempt in range(self.retries):
            try:
                # 创建锁文件的父目录（如果不存在）
                lock_dir = os.path.dirname(self.lock_file)
                if lock_dir and not os.path.exists(lock_dir):
                    os.makedirs(lock_dir)
                    
                # 检查是否存在过期的锁文件
                if os.path.exists(self.lock_file):
                    try:
                        # 尝试读取锁定时间
                        with open(self.lock_file, 'r') as f:
                            lock_time = float(f.read().strip() or '0')
                            if time.time() - lock_time > 300:  # 5分钟超时
                                os.remove(self.lock_file)
                                logger.warning(f"删除过期的锁文件: {self.lock_file}")
                    except (ValueError, IOError, OSError) as e:
                        logger.warning(f"处理过期锁文件时出错: {str(e)}")
                        # 如果无法读取锁定时间，直接删除锁文件
                        try:
                            os.remove(self.lock_file)
                        except OSError:
                            pass
                
                # 创建新的锁文件
                self.lock = open(self.lock_file, 'w')
                
                # 尝试获取文件锁
                portalocker.lock(self.lock, portalocker.LOCK_EX | portalocker.LOCK_NB)
                
                # 写入当前时间
                self.lock.write(str(time.time()))
                self.lock.flush()
                return self
                
            except (portalocker.LockException, IOError, OSError) as e:
                logger.warning(f"获取文件锁失败，尝试次数 {attempt + 1}/{self.retries}: {str(e)}")
                if self.lock:
                    try:
                        self.lock.close()
                    except:
                        pass
                    self.lock = None
                
                if attempt < self.retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"无法获取文件锁: {str(e)}")
                    raise
                    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.lock:
                portalocker.unlock(self.lock)
                self.lock.close()
                self.lock = None
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception as e:
            logger.warning(f"释放文件锁失败: {str(e)}")
            # 即使释放失败也不抛出异常，避免影响主流程
            pass

class StockTrader:
    """股票交易类"""
    
    def __init__(self):
        """
        初始化交易对象
        """
        # 初始化日志记录器
        self.logger = logging.getLogger(__name__)
        
        # 设置API基础URL
        self.api_base_url = "http://localhost:5000/api/v1"
        
        # 初始化资产相关属性
        self.cash = 0.0
        self.total_assets = 0.0
        self.positions = {}
        
        # 初始化文件路径
        self.positions_file = "data/positions.json"
        self.assets_file = "data/assets.json"
        
        # 确保数据文件存在
        self._ensure_position_file()
        self._ensure_assets_file()
        
        # 加载初始资产数据
        self._load_initial_assets()
        
        # 初始化报价服务
        self.quote_service = QuoteService()
        
        self.logger.info("交易对象初始化完成")
        
        # 交易频率限制队列
        self.trade_times = deque(maxlen=config.get('trading.trade_frequency_limit', 10))
        
        # 初始化最后更新时间
        self._last_update = 0
        
        # 缓存最近执行记录，防止重复执行
        self._recent_executions = {}
        
        # 检查API连接
        self._check_api_connection()
        
    def _check_api_connection(self) -> bool:
        """
        检查API连接状态，如果主API不可用，尝试切换到备用API
        
        Returns:
            bool: 是否成功连接到API
        """
        # 获取健康检查路径
        health_path = config.get('api.health_path', '/ping')
        
        # 尝试的路径列表，按优先级排序
        paths_to_try = [
            health_path,  # 配置的健康检查路径
            '/ping',      # 简单的ping接口
            '/health',    # 标准健康检查接口
            '/',          # API根路径
        ]
        
        # 首先尝试主API
        main_api_available = False
        for path in paths_to_try:
            try:
                logger.info(f"检查主API连接: {self.api_base_url}，路径: {path}")
                response = requests.get(f"{self.api_base_url}{path}", timeout=config.get('api.timeout', 10))
                if 200 <= response.status_code < 300:  # 只有2xx状态码才表示成功
                    logger.info(f"主API连接正常，路径: {path}，状态码: {response.status_code}")
                    main_api_available = True
                    # 更新健康检查路径为可用的路径
                    if path != health_path:
                        logger.info(f"更新健康检查路径为: {path}")
                    break
                elif response.status_code == 404:
                    # 404表示路径不存在，但服务器在运行
                    logger.warning(f"主API路径 {path} 不存在，状态码: 404，服务器可能正常但缺少此接口")
                    # 继续尝试其他路径
                else:
                    logger.warning(f"主API路径 {path} 连接异常，状态码: {response.status_code}")
            except Exception as e:
                logger.warning(f"主API路径 {path} 连接失败: {str(e)}")
        
        if main_api_available:
            return True
            
        # 如果主API不可用，尝试备用API
        if self.backup_urls:
            for i, backup_url in enumerate(self.backup_urls):
                for path in paths_to_try:
                    try:
                        logger.info(f"尝试备用API[{i+1}]: {backup_url}，路径: {path}")
                        response = requests.get(f"{backup_url}{path}", timeout=config.get('api.timeout', 10))
                        if 200 <= response.status_code < 300:  # 只有2xx状态码才表示成功
                            logger.info(f"切换到备用API: {backup_url}，路径: {path}，状态码: {response.status_code}")
                            self.api_base_url = backup_url
                            return True
                        elif response.status_code == 404:
                            # 404表示路径不存在，但服务器在运行
                            logger.warning(f"备用API[{i+1}]路径 {path} 不存在，状态码: 404，服务器可能正常但缺少此接口")
                            # 继续尝试其他路径
                        else:
                            logger.warning(f"备用API[{i+1}]路径 {path} 连接异常，状态码: {response.status_code}")
                    except Exception as e:
                        logger.warning(f"备用API[{i+1}]路径 {path} 连接失败: {str(e)}")
        
        # 所有API都不可用，使用主API
        logger.warning("所有API均不可用，将使用主API")
        self.api_base_url = config.get('api.base_url')
        return False
        
    def _validate_assets(self, assets: Dict) -> bool:
        """
        验证资产数据格式
        
        Args:
            assets: 资产数据
            
        Returns:
            bool: 是否有效
        """
        required_fields = ['cash', 'total_assets', 'total_market_value', 'positions', 'updated_at']
        for field in required_fields:
            if field not in assets:
                logger.error(f"资产数据缺少必要字段: {field}")
                return False
                
        try:
            # 验证数值字段
            if not isinstance(assets['cash'], (int, float)) or assets['cash'] < 0:
                logger.error(f"现金字段无效: {assets['cash']}")
                return False
                
            if not isinstance(assets['total_assets'], (int, float)) or assets['total_assets'] < 0:
                logger.error(f"总资产字段无效: {assets['total_assets']}")
                return False
                
            if not isinstance(assets['total_market_value'], (int, float)) or assets['total_market_value'] < 0:
                logger.error(f"总市值字段无效: {assets['total_market_value']}")
                return False
                
            # 验证持仓数据
            if not isinstance(assets['positions'], dict):
                logger.error("持仓数据格式错误")
                return False
                
            for code, pos in assets['positions'].items():
                if not isinstance(pos, dict):
                    logger.error(f"股票 {code} 的持仓数据格式错误")
                    return False
                    
                required_pos_fields = ['volume', 'cost_price', 'current_price', 'market_value']
                for field in required_pos_fields:
                    if field not in pos:
                        logger.error(f"股票 {code} 的持仓数据缺少字段: {field}")
                        return False
                        
            # 验证时间格式
            datetime.strptime(assets['updated_at'], '%Y-%m-%d %H:%M:%S')
            
            return True
            
        except (TypeError, ValueError) as e:
            logger.error(f"资产数据验证失败: {str(e)}")
            return False
            
    def _validate_positions(self, positions: Dict) -> bool:
        """
        验证持仓数据格式
        
        Args:
            positions: 持仓数据
            
        Returns:
            bool: 是否有效
        """
        try:
            if not isinstance(positions, dict):
                logger.error("持仓数据必须是字典格式")
                return False
                
            for code, pos in positions.items():
                if not isinstance(pos, dict):
                    logger.error(f"股票 {code} 的持仓数据格式错误")
                    return False
                    
                required_fields = ['volume', 'price', 'updated_at']
                for field in required_fields:
                    if field not in pos:
                        logger.error(f"股票 {code} 的持仓数据缺少字段: {field}")
                        return False
                        
                # 验证数值字段
                if not isinstance(pos['volume'], int) or pos['volume'] <= 0:
                    logger.error(f"股票 {code} 的持仓量无效: {pos['volume']}")
                    return False
                    
                if not isinstance(pos['price'], (int, float)) or pos['price'] <= 0:
                    logger.error(f"股票 {code} 的持仓价格无效: {pos['price']}")
                    return False
                    
                # 验证时间格式
                datetime.strptime(pos['updated_at'], '%Y-%m-%d %H:%M:%S')
                
            return True
            
        except (TypeError, ValueError) as e:
            logger.error(f"持仓数据验证失败: {str(e)}")
            return False
            
    def _ensure_position_file(self) -> None:
        """确保持仓文件存在"""
        path = Path(self.positions_file)
        if not path.parent.exists():
            logger.info(f"创建持仓文件目录: {path.parent}")
            path.parent.mkdir(parents=True)
        if not path.exists() or path.stat().st_size == 0:
            logger.info(f"创建持仓文件: {path}")
            with open(path, 'w', encoding=config.get('data.file_encoding')) as f:
                json.dump({}, f, ensure_ascii=False, indent=config.get('data.json_indent'))
                
    def _load_positions(self) -> Dict:
        """加载持仓数据"""
        try:
            # 尝试从API获取持仓数据
            positions_list = self._get_position()
            if positions_list:
                logger.info("从API获取持仓数据成功")
                # 将列表格式转换为字典格式
                positions_dict = {}
                for position in positions_list:
                    if isinstance(position, dict) and 'stock_code' in position:
                        stock_code = position['stock_code']
                        positions_dict[stock_code] = {
                            'volume': position.get('total_volume', 0),
                            'price': position.get('average_cost', 0) or position.get('original_cost', 0),
                            'updated_at': position.get('updated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        }
                logger.info(f"成功转换持仓数据为字典格式，共{len(positions_dict)}个持仓")
                return positions_dict
        except Exception as e:
            logger.warning(f"从API获取持仓数据失败，将使用本地文件: {str(e)}")
            
        # 如果API获取失败，则从本地文件加载
        self._ensure_position_file()  # 确保文件存在且不为空
        logger.debug(f"从本地文件加载持仓数据: {self.positions_file}")
        with open(self.positions_file, 'r', encoding=config.get('data.file_encoding')) as f:
            positions = json.load(f)
            if not self._validate_positions(positions):
                logger.warning("持仓数据验证失败，重置为空")
                positions = {}
            logger.debug(f"当前持仓: {positions}")
            return positions
            
    def _get_position(self) -> List[Dict]:
        """
        从服务器获取持仓信息
        
        Returns:
            List[Dict]: 持仓列表
        """
        # 获取持仓API路径
        position_path = config.get('api.positions_path', '/api/v1/positions')
        
        # 尝试的路径列表，按优先级排序
        paths_to_try = [
            position_path,
            '/api/v1/positions',
            '/api/positions',
            '/positions'
        ]
        
        for path in paths_to_try:
            try:
                logger.info(f"获取持仓信息，路径: {path}")
                response = requests.get(f"{self.api_base_url}{path}", timeout=config.get('api.timeout', 10))
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"持仓API响应: {data}")
                    
                    # 处理不同的响应格式
                    if isinstance(data, dict) and 'data' in data:
                        # 标准格式: {"code": 200, "message": "success", "data": [...]}
                        positions_data = data.get('data')
                        if isinstance(positions_data, list):
                            logger.info(f"成功获取持仓信息: {len(positions_data)}个持仓")
                            return positions_data
                        elif isinstance(positions_data, dict) and 'positions' in positions_data:
                            # 格式: {"code": 200, "message": "success", "data": {"positions": [...]}}
                            positions = positions_data.get('positions', [])
                            logger.info(f"成功获取持仓信息: {len(positions)}个持仓")
                            return positions
                        else:
                            logger.warning(f"持仓数据格式异常: {positions_data}")
                    elif isinstance(data, list):
                        # 直接返回列表格式
                        logger.info(f"成功获取持仓信息: {len(data)}个持仓")
                        return data
                    else:
                        logger.warning(f"持仓API响应格式异常: {data}")
                else:
                    logger.warning(f"获取持仓信息失败，路径: {path}，状态码: {response.status_code}")
            except Exception as e:
                logger.warning(f"获取持仓信息异常，路径: {path}，错误: {str(e)}")
        
        # 所有路径都失败，返回空列表
        logger.error("所有持仓API路径均失败，返回空持仓列表")
        return []
        
    def _save_positions(self, positions: Dict) -> None:
        """保存持仓数据"""
        if not self._validate_positions(positions):
            raise ValueError("持仓数据格式无效")
            
        logger.debug(f"保存持仓数据: {positions}")
        with open(self.positions_file, 'w', encoding=config.get('data.file_encoding')) as f:
            json.dump(positions, f, ensure_ascii=False, indent=config.get('data.json_indent'))
            
    def _ensure_assets_file(self) -> None:
        """确保资产文件存在，如果不存在则创建（使用配置的初始资金）"""
        path = Path(self.assets_file)
        if not path.parent.exists():
            logger.info(f"创建资产文件目录: {path.parent}")
            path.parent.mkdir(parents=True)
            
        if not path.exists() or path.stat().st_size == 0:
            logger.info(f"创建资产文件: {path}")
            initial_cash = config.get('account.initial_cash')
            initial_assets = {
                "cash": initial_cash,
                "total_assets": initial_cash,
                "total_market_value": 0.00,
                "positions": {},
                "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(path, 'w', encoding=config.get('data.file_encoding')) as f:
                json.dump(initial_assets, f, ensure_ascii=False, indent=config.get('data.json_indent'))
                
    def _load_assets(self) -> Dict:
        """加载资产数据"""
        try:
            # 尝试从API获取资产数据
            api_assets = self._get_total_assets()
            if api_assets and (api_assets.get('cash', 0) > 0 or api_assets.get('total_assets', 0) > 0):
                logger.info("从API获取资产数据成功")
                
                # 确保返回的资产数据包含positions字段
                if 'positions' not in api_assets:
                    # 从本地文件加载持仓数据或创建空持仓
                    try:
                        with open(self.assets_file, 'r', encoding=config.get('data.file_encoding')) as f:
                            local_assets = json.load(f)
                            api_assets['positions'] = local_assets.get('positions', {})
                    except Exception:
                        api_assets['positions'] = {}
                        
                # 确保包含total_market_value字段
                if 'total_market_value' not in api_assets:
                    api_assets['total_market_value'] = 0.0
                    
                # 确保包含updated_at字段
                if 'updated_at' not in api_assets:
                    api_assets['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                return api_assets
        except Exception as e:
            logger.warning(f"从API获取资产数据失败，将使用本地文件: {str(e)}")
            
        # 如果API获取失败，则从本地文件加载
        self._ensure_assets_file()  # 确保文件存在且不为空
        logger.debug(f"从本地文件加载资产数据: {self.assets_file}")
        try:
            with open(self.assets_file, 'r', encoding=config.get('data.file_encoding')) as f:
                assets = json.load(f)
                
                # 确保资产数据包含必要的字段
                if not self._validate_assets(assets):
                    logger.warning("资产数据验证失败，使用初始配置")
                    initial_cash = config.get('account.initial_cash')
                    assets = {
                        "cash": initial_cash,
                        "total_assets": initial_cash,
                        "total_market_value": 0.00,
                        "positions": {},
                        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                # 确保包含positions字段
                if 'positions' not in assets:
                    assets['positions'] = {}
                    
                logger.debug(f"当前资产: {assets}")
                return assets
        except Exception as e:
            logger.error(f"加载资产数据异常: {str(e)}")
            # 返回默认资产数据
            initial_cash = config.get('account.initial_cash')
            return {
                "cash": initial_cash,
                "total_assets": initial_cash,
                "total_market_value": 0.00,
                "positions": {},
                "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
    def _get_total_assets(self) -> Dict:
        """
        从服务器获取总资产信息
        
        Returns:
            Dict: 总资产信息, 包含cash和total_assets
        """
        # 获取账户资金API路径
        funds_path = config.get('api.account_funds_path', '/api/v1/account/funds')
        
        # 尝试的路径列表，按优先级排序
        paths_to_try = [
            funds_path,
            '/api/v1/account/funds',
            '/api/account/funds',
            '/account/funds'
        ]
        
        for path in paths_to_try:
            try:
                logger.info(f"获取账户资金信息，路径: {path}")
                response = requests.get(f"{self.api_base_url}{path}", timeout=config.get('api.timeout', 10))
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == 200 and 'data' in data:
                        return {
                            'cash': float(data['data'].get('available_cash', 0)),
                            'total_assets': float(data['data'].get('total_assets', 0))
                        }
                    else:
                        logger.warning(f"获取账户资金信息失败，路径: {path}，响应: {data}")
                else:
                    logger.warning(f"获取账户资金信息失败，路径: {path}，状态码: {response.status_code}")
            except Exception as e:
                logger.warning(f"获取账户资金信息异常，路径: {path}，错误: {str(e)}")
        
        # 所有路径都失败，尝试从持仓计算总资产
        try:
            logger.info("尝试从持仓计算总资产")
            positions = self._get_position()
            if positions:
                # 计算持仓市值
                market_value = sum(float(p.get('market_value', 0)) for p in positions)
                
                # 从本地缓存获取现金信息
                assets = self._load_assets()
                cash = assets.get('available_cash', 0)
                
                # 计算总资产
                total_assets = market_value + cash
                
                logger.info(f"从持仓计算总资产: 现金={cash}, 市值={market_value}, 总资产={total_assets}")
                return {'cash': cash, 'total_assets': total_assets}
        except Exception as e:
            logger.error(f"从持仓计算总资产异常: {str(e)}")
        
        # 所有方法都失败，返回默认值
        logger.error("所有获取资产信息的方法均失败，返回默认资产信息")
        return {'cash': 0, 'total_assets': 0}
        
    def _save_assets(self, assets: Dict) -> None:
        """保存资产数据"""
        if not self._validate_assets(assets):
            raise ValueError("资产数据格式无效")
            
        logger.debug(f"保存资产数据: {assets}")
        with open(self.assets_file, 'w', encoding=config.get('data.file_encoding')) as f:
            json.dump(assets, f, ensure_ascii=False, indent=config.get('data.json_indent'))
            
    def _load_initial_assets(self) -> None:
        """加载初始资产信息"""
        # 先检查持仓和资产文件是否为空
        positions = self._load_positions()
        assets = self._load_assets()
        
        # 检查是否需要初始化
        positions_empty = not positions
        assets_positions_empty = 'positions' not in assets or not assets['positions']
        
        if positions_empty and assets_positions_empty:
            logger.info("持仓和资产文件为空，开始初始化数据")
            try:
                # 从服务器获取最新持仓数据
                positions_list = self._get_position()
                
                # 转换持仓列表为字典格式
                positions_dict = {}
                for position in positions_list:
                    if not isinstance(position, dict):
                        continue
                        
                    stock_code = position.get('stock_code')
                    if stock_code:
                        # 确保有current_price字段，如果没有则使用latest_price或默认值
                        current_price = position.get('latest_price', 0.0)
                        if current_price == 0:
                            # 尝试从行情服务获取当前价格
                            try:
                                quote_data = self.quote_service.get_real_time_quote(stock_code)
                                current_price = quote_data.get('price', 0.0)
                                logger.info(f"从行情服务获取股票 {stock_code} 当前价格: {current_price}")
                            except Exception as e:
                                logger.warning(f"获取股票 {stock_code} 行情失败: {str(e)}")
                        
                        positions[stock_code] = {
                            'stock_name': position.get('stock_name', ''),
                            'volume': position.get('total_volume', 0),
                            'cost_price': position.get('average_cost', 0.0) or position.get('original_cost', 0.0),
                            'current_price': current_price,  # 确保有current_price字段
                            'market_value': position.get('market_value', 0.0),
                            'latest_price': position.get('latest_price', 0.0),
                            'floating_profit': position.get('floating_profit', 0.0),
                            'position_ratio': position.get('original_position_ratio', 0),
                            'updated_at': position.get('updated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        }
                
                # 获取账户资金信息
                assets_data = self._get_total_assets()
                
                # 构建完整的资产信息
                assets = {
                    "cash": assets_data.get('cash', config.get('account.initial_cash')),
                    "total_assets": assets_data.get('total_assets', config.get('account.total_assets')),
                    "total_market_value": sum(pos.get('market_value', 0.0) for pos in positions_dict.values()),
                    "positions": positions_dict,
                    "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 保存资产和持仓信息
                self._save_assets(assets)
                self._save_positions(positions_dict)
                
                logger.info(f"初始化资产数据成功: 现金={assets['cash']:.2f}, 总资产={assets['total_assets']:.2f}")
                
            except Exception as e:
                logger.warning(f"从API获取初始数据失败: {str(e)}")
                # 使用配置中的初始值
                initial_cash = config.get('account.initial_cash')
                total_assets = config.get('account.total_assets')
                
                assets = {
                    "cash": initial_cash,
                    "total_assets": total_assets,
                    "total_market_value": 0.0,
                    "positions": {},
                    "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                self._save_assets(assets)
                logger.info(f"使用配置的初始资产: 现金={initial_cash:.2f}, 总资产={total_assets:.2f}")
        else:
            logger.info(f"加载现有资产数据: 现金={assets.get('cash', 0):.2f}, 总资产={assets.get('total_assets', 0):.2f}")
        
        # 加载最终的资产信息
        assets = self._load_assets()
        self.total_cash = assets['cash']
        self.total_assets = assets['total_assets']
        
        logger.info(f"初始化交易模块 - API地址: {self.api_base_url}")
        logger.info(f"当前资产状况 - 现金: {self.total_cash:.2f}, 总资产: {self.total_assets:.2f}")
        
    def _sync_positions_from_assets(self) -> None:
        """从 assets.json 同步持仓信息到 positions.json"""
        assets = self._load_assets()
        positions = {}
        
        # 转换持仓格式
        for code, pos in assets['positions'].items():
            positions[code] = {
                'volume': pos['volume'],
                'price': pos['cost_price'],
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        # 保存到持仓文件
        self._save_positions(positions)
        logger.info("同步持仓信息完成")
        
    def _sync_positions_to_assets(self) -> None:
        """将 positions.json 的变化同步到 assets.json"""
        positions = self._load_positions()
        assets = self._load_assets()
        
        # 更新持仓信息
        assets['positions'] = {}
        total_market_value = 0
        
        for code, pos in positions.items():
            # 获取最新行情
            quote = self.quote_service.get_real_time_quote(code)
            if quote:
                current_price = quote['price']
                market_value = current_price * pos['volume']
                total_market_value += market_value
                
                # 更新持仓信息
                assets['positions'][code] = {
                    'volume': pos['volume'],
                    'cost_price': pos['price'],
                    'current_price': current_price,
                    'market_value': market_value,
                    'profit_loss': market_value - pos['price'] * pos['volume']
                }
                
        # 更新总资产和时间
        assets['total_market_value'] = total_market_value
        assets['total_assets'] = self.total_cash + total_market_value
        assets['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存更新后的资产信息
        self._save_assets(assets)
        logger.info(f"同步资产信息完成 - 现金: {self.total_cash:.2f}, 总资产: {assets['total_assets']:.2f}")
        
    def update_assets(self) -> Dict:
        """
        更新资产信息
        
        Returns:
            Dict: 更新后的资产信息
        """
        try:
            logger.info("开始更新资产信息...")
            
            # 获取总资产信息
            assets_data = self._get_total_assets()
            if not assets_data or (assets_data.get('cash', 0) == 0 and assets_data.get('total_assets', 0) == 0):
                logger.warning("获取总资产信息失败，使用本地缓存")
                return self._load_assets()
                
            # 获取持仓信息
            positions_list = self._get_position()
            
            # 转换持仓列表为字典格式
            positions = {}
            for position in positions_list:
                if not isinstance(position, dict):
                    logger.warning(f"持仓数据不是字典格式: {position}")
                    continue
                    
                stock_code = position.get('stock_code')
                if stock_code:
                    # 确保有current_price字段，如果没有则使用latest_price或默认值
                    current_price = position.get('latest_price', 0.0)
                    if current_price == 0:
                        # 尝试从行情服务获取当前价格
                        try:
                            quote_data = self.quote_service.get_real_time_quote(stock_code)
                            current_price = quote_data.get('price', 0.0)
                            logger.info(f"从行情服务获取股票 {stock_code} 当前价格: {current_price}")
                        except Exception as e:
                            logger.warning(f"获取股票 {stock_code} 行情失败: {str(e)}")
                    
                    positions[stock_code] = {
                        'stock_name': position.get('stock_name', ''),
                        'volume': position.get('total_volume', 0),
                        'cost_price': position.get('average_cost', 0.0) or position.get('original_cost', 0.0),
                        'current_price': current_price,  # 确保有current_price字段
                        'market_value': position.get('market_value', 0.0),
                        'latest_price': position.get('latest_price', 0.0),
                        'floating_profit': position.get('floating_profit', 0.0),
                        'position_ratio': position.get('original_position_ratio', 0),
                        'updated_at': position.get('updated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    }
            
            # 计算总市值
            total_market_value = sum(pos.get('market_value', 0.0) for pos in positions.values())
            
            # 构建完整的资产信息
            assets = {
                "cash": assets_data.get('cash', 0.0),
                "total_assets": assets_data.get('total_assets', 0.0),
                "total_market_value": total_market_value,
                "positions": positions,
                "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 保存资产信息
            self._save_assets(assets)
            logger.info(f"资产信息更新成功: 现金={assets['cash']:.2f}, 总资产={assets['total_assets']:.2f}, 持仓数量={len(positions)}")
            
            return assets
        except Exception as e:
            logger.error(f"更新资产信息异常: {str(e)}", exc_info=True)
            # 返回本地缓存的资产信息
            return self._load_assets()
        
    def _calculate_weighted_average_price(self, old_volume: int, old_price: float,
                                        new_volume: int, new_price: float) -> float:
        """
        计算加权平均价格
        
        Args:
            old_volume: 原持仓量
            old_price: 原持仓价格
            new_volume: 新交易量
            new_price: 新交易价格
            
        Returns:
            加权平均价格
        """
        total_volume = old_volume + new_volume
        weighted_price = (old_volume * old_price + new_volume * new_price) / total_volume
        return weighted_price
        
    def _check_cash_sufficient(self, required_amount: float) -> bool:
        """
        检查现金是否足够
        
        Args:
            required_amount: 所需现金金额
            
        Returns:
            bool: 现金是否足够
        """
        try:
            # 使用类的total_cash属性
            if self.total_cash >= required_amount:
                logger.info(f"现金充足 - 需要: {required_amount:.2f}, 当前现金: {self.total_cash:.2f}")
                return True
            else:
                logger.error(f"现金不足 - 需要: {required_amount:.2f}, 当前现金: {self.total_cash:.2f}")
                return False
                
        except Exception as e:
            logger.error(f"检查现金是否足够异常: {str(e)}")
            return False
        
    def _update_cash_balance(self, amount: float, is_buy: bool = True) -> None:
        """
        更新现金余额
        
        Args:
            amount: 交易金额
            is_buy: 是否为买入操作，True表示买入，False表示卖出
        """
        try:
            # 获取最新的资金数据
            response = requests.get(f"{self.api_base_url}/account/funds")
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200 and 'data' in data:
                    self.cash = float(data['data'].get('cash', 0))
                    self.total_assets = float(data['data'].get('total_assets', 0))
                    self.logger.info("从API获取资产数据成功")
                else:
                    self.logger.error(f"获取资金数据失败: {data}")
                    return
            else:
                self.logger.error(f"请求资金数据失败: {response.status_code}")
                return

            # 计算新的现金余额
            if is_buy:
                new_cash = self.cash - amount
            else:
                new_cash = self.cash + amount
                
            # 更新本地现金余额
            self.cash = new_cash
            
            self.logger.info(f"更新现金余额 - {'买入' if is_buy else '卖出'}金额: {amount:.2f}, 原有现金: {self.cash:.2f}, 现有现金: {new_cash:.2f}")
            
        except Exception as e:
            self.logger.error(f"更新现金余额异常: {str(e)}")
            raise
        
    def _calculate_buy_volume(self, stock_code: str, position_ratio: int, price: float) -> int:
        """
        计算买入数量
        
        Args:
            stock_code: 股票代码
            position_ratio: 仓位比例(0-100整数)
            price: 买入价格
            
        Returns:
            int: 买入数量
        """
        try:
            if price <= 0:
                logger.error(f"买入价格必须大于0: {price}")
                return 0
                
            # 获取总资产
            assets = self.update_assets()
            total_assets = assets['total_assets']
            available_cash = assets['cash']
            
            # 计算目标买入金额 (仓位比例需要转换为小数)
            target_amount = total_assets * (position_ratio / 100.0)
            
            # 检查可用资金是否足够
            if target_amount > available_cash:
                logger.warning(f"可用资金不足 - 目标金额: {target_amount:.2f}, 可用资金: {available_cash:.2f}")
                target_amount = available_cash
                
            # 计算可买数量（向下取整到100的倍数）
            volume_step = config.get('trading.volume_step', 100)
            volume = int(target_amount / price / volume_step) * volume_step
            
            # 检查最小买入数量
            min_volume = config.get('trading.min_volume', 100)
            if volume < min_volume:
                if target_amount >= min_volume * price:
                    volume = min_volume
                else:
                    logger.warning(f"买入金额不足最小买入量 - 目标金额: {target_amount:.2f}, 最小买入金额: {min_volume * price:.2f}")
                    return 0
                    
            logger.info(f"计算买入数量 - 总资产: {total_assets:.2f}, 可用资金: {available_cash:.2f}, 目标金额: {target_amount:.2f}, 买入数量: {volume}")
            return volume
            
        except Exception as e:
            logger.error(f"计算买入数量异常: {str(e)}")
            return 0
        
    def _calculate_sell_volume(self, stock_code: str, position_ratio: int, 
                              current_holdings: Optional[int] = None) -> int:
        """
        计算卖出数量，position_ratio相对于当前持仓
        
        Args:
            stock_code: 股票代码
            position_ratio: 卖出比例(0-100整数)，相对于当前持仓的百分比
            current_holdings: 当前持仓数量，如果不提供则自动获取
            
        Returns:
            int: 卖出数量
        """
        try:
            # 获取当前持仓
            if current_holdings is None:
                position = self._load_positions().get(stock_code, {})
                if not position:
                    logger.error(f"没有持仓记录 - 股票代码: {stock_code}")
                    return 0
                current_holdings = position.get('volume', 0)
                
            # 持仓检查
            if current_holdings <= 0:
                logger.error(f"当前持仓数量无效: {current_holdings}")
                return 0
                
            # 卖出比例检查
            if position_ratio <= 0 or position_ratio > 100:
                logger.error(f"卖出比例无效: {position_ratio}%")
                return 0
                
            # 计算卖出数量 (卖出比例需要转换为小数)
            sell_ratio = position_ratio / 100.0
            sell_volume = int(current_holdings * sell_ratio)
            
            # 检查最小卖出数量
            min_volume = config.get('trading.min_volume', 100)
            if 0 < sell_volume < min_volume:
                if current_holdings >= min_volume:
                    # 如果持仓足够卖出最小量，则使用最小量
                    sell_volume = min_volume
                else:
                    # 持仓不足最小卖出量，则返回0
                    logger.warning(f"卖出数量小于最小限制 - 计算卖出量: {sell_volume}, 最小卖出量: {min_volume}")
                    return 0
                    
            # 确保卖出量不超过持仓量
            sell_volume = min(sell_volume, current_holdings)
            
            # 确保卖出量是volume_step的整数倍
            volume_step = config.get('trading.volume_step', 100)
            sell_volume = int(sell_volume / volume_step) * volume_step
            
            # 如果卖出量为0，可能是因为比例太小，检查是否应当使用最小卖出量
            if sell_volume == 0 and current_holdings >= min_volume:
                sell_volume = min_volume
                
            logger.info(f"计算卖出数量 - 当前持仓: {current_holdings}, 卖出比例: {position_ratio}%, 卖出数量: {sell_volume}")
            return sell_volume
            
        except Exception as e:
            logger.error(f"计算卖出数量异常: {str(e)}")
            return 0
        
    def _get_current_price(self, stock_code: str, min_price: Optional[float] = None, max_price: Optional[float] = None, action: str = 'buy') -> Optional[float]:
        """
        获取当前价格并检查是否在指定区间内
        
        Args:
            stock_code: 股票代码
            min_price: 最低价格
            max_price: 最高价格
            action: 交易动作（buy/sell）
            
        Returns:
            float: 当前价格，如果不在区间内则返回None
        """
        # 获取当前价格
        quote_data = self.quote_service.get_real_time_quote(stock_code)
        current_price = quote_data['price']
        
        # 如果没有指定价格区间，直接返回当前价格
        if min_price is None and max_price is None:
            logger.info(f"【价格检查】价格不限，当前价格: {current_price} - 股票: {stock_code}")
            return current_price
            
        # 检查价格是否在区间内
        price_in_range = True
        reason = ""
        
        if min_price is not None and max_price is not None:
            # 同时指定了最低价和最高价
            if not (min_price <= current_price <= max_price):
                price_in_range = False
                reason = f"当前价格 {current_price} 不在指定区间 [{min_price}, {max_price}] 内"
        elif min_price is not None:
            # 只指定了最低价
            if current_price < min_price:
                price_in_range = False
                reason = f"当前价格 {current_price} 低于最低价 {min_price}"
        elif max_price is not None:
            # 只指定了最高价
            if current_price > max_price:
                price_in_range = False
                reason = f"当前价格 {current_price} 高于最高价 {max_price}"
                
        # 特殊情况：买入时价格低于最低价或卖出时价格高于最高价，这是更优的价格
        if not price_in_range:
            if action == 'buy' and min_price is not None and current_price < min_price:
                logger.info(f"【价格更优】买入/加仓策略：当前价格 {current_price} 低于最低价 {min_price}，价格更优，接受交易 - 股票: {stock_code}")
                return current_price
            elif action == 'sell' and max_price is not None and current_price > max_price:
                logger.info(f"【价格更优】卖出/减仓策略：当前价格 {current_price} 高于最高价 {max_price}，价格更优，接受交易 - 股票: {stock_code}")
                return current_price
            else:
                logger.warning(f"【价格不匹配】{reason} - 股票: {stock_code}, 交易类型: {action}")
                return None
                
        logger.info(f"【价格匹配】当前价格: {current_price}, 满足交易条件 - 最低: {min_price or '不限'}, 最高: {max_price or '不限'} - 股票: {stock_code}")
        return current_price
        
    def _is_trading_time(self) -> bool:
        """
        检查当前是否为交易时间
        
        Returns:
            bool: 是否为交易时间
        """
        now = datetime.now()
        current_time = now.time()
        
        # 获取交易时间配置
        trading_start = datetime.strptime(config.get('trading.trading_hours.start'), '%H:%M:%S').time()
        trading_end = datetime.strptime(config.get('trading.trading_hours.end'), '%H:%M:%S').time()
        trading_days = config.get('trading.trading_days')  # 1-7，1表示周一
        
        # 检查是否为交易日
        if now.isoweekday() not in trading_days:
            logger.warning(f"当前不是交易日 - 星期{now.isoweekday()}")
            return False
            
        # 检查是否在交易时间内
        if not (trading_start <= current_time <= trading_end):
            logger.warning(f"当前不是交易时间 - {current_time}")
            return False
            
        return True
        
    def _check_trade_frequency(self) -> bool:
        """
        检查交易频率是否超限
        
        Returns:
            bool: 是否允许交易
        """
        now = datetime.now()
        # 清理超过1分钟的记录
        while self.trade_times and (now - self.trade_times[0]).total_seconds() > 60:
            self.trade_times.popleft()
            
        # 检查是否超过限制
        if len(self.trade_times) >= config.get('trading.trade_frequency_limit', 10):
            logger.warning("交易频率超过限制")
            return False
            
        # 记录本次交易时间
        self.trade_times.append(now)
        return True
        
    def _check_price_deviation(self, stock_code: str, target_price: float) -> bool:
        """
        检查价格偏离度是否超限
        
        Args:
            stock_code: 股票代码
            target_price: 目标价格
            
        Returns:
            bool: 是否允许交易
            
        Raises:
            PriceDeviationError: 价格偏离度超限异常
        """
        # 获取最新行情
        quote = self.quote_service.get_real_time_quote(stock_code)
        if not quote:
            raise PriceDeviationError("无法获取最新行情")
            
        current_price = quote['price']
        deviation = abs(current_price - target_price) / target_price
        max_deviation = config.get('trading.price_deviation', 0.02)
        
        if deviation > max_deviation:
            logger.warning(f"价格偏离度 {deviation:.2%} 超过限制 {max_deviation:.2%}")
            return False
            
        return True
        
    def _check_position_limit(self, stock_code: str, target_value: float) -> bool:
        """
        检查持仓比例是否超限
        
        Args:
            stock_code: 股票代码
            target_value: 目标市值
            
        Returns:
            bool: 是否允许交易
            
        Raises:
            PositionLimitError: 持仓比例超限异常
        """
        assets = self._load_assets()
        total_assets = assets['total_assets']
        
        # 计算目标持仓比例
        target_ratio = target_value / total_assets
        max_position_ratio = config.get('trading.max_position_ratio', 0.3)
        
        if target_ratio > max_position_ratio:
            logger.warning(f"目标持仓比例 {target_ratio:.2%} 超过限制 {max_position_ratio:.2%}")
            return False
            
        return True
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.RequestException, ApiError))
    )
    def _record_execution(self, stock_code: str, action: str, price: float, volume: int, strategy_id: Optional[int] = None) -> None:
        """
        记录交易执行
        
        Args:
            stock_code: 股票代码
            action: 交易动作（buy/sell/hold/add/trim）
            price: 成交价格
            volume: 成交数量
            strategy_id: 策略ID
        """
        try:
            # 获取当前持仓
            positions = self._load_positions()
            position = positions.get(stock_code, {})
            
            # 构建执行记录
            execution = {
                'stock_code': stock_code,
                'action': action,
                'price': price,
                'volume': volume,
                'amount': price * volume,
                'position_before': position.get('volume', 0),
                'position_after': position.get('volume', 0) + (volume if action in ['buy', 'add'] else -volume if action in ['sell', 'trim'] else 0),
                'strategy_id': strategy_id,
                'executed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 保存执行记录
            executions_file = os.path.join(config.get('data.dir'), 'executions.json')
            executions = []
            if os.path.exists(executions_file):
                with open(executions_file, 'r', encoding=config.get('data.file_encoding')) as f:
                    executions = json.load(f)
                    
            executions.append(execution)
            with open(executions_file, 'w', encoding=config.get('data.file_encoding')) as f:
                json.dump(executions, f, ensure_ascii=False, indent=config.get('data.json_indent'))
                
            logger.info(f"记录交易执行成功 - 股票: {stock_code}, 动作: {action}, 价格: {price}, 数量: {volume}")
            
        except Exception as e:
            logger.error(f"记录交易执行异常 - 股票: {stock_code}, 错误: {str(e)}")
            # 不抛出异常，避免影响主流程
        
    def buy_stock(self, stock_code: str, min_price: Optional[float] = None, max_price: Optional[float] = None, 
                  position_ratio: int = 10, strategy_id: Optional[int] = None) -> Dict:
        """
        买入股票
        
        Args:
            stock_code: 股票代码
            min_price: 最低买入价格
            max_price: 最高买入价格
            position_ratio: 仓位比例(0-100整数)
            strategy_id: 策略ID
            
        Returns:
            Dict: 交易结果
        """
        try:
            # 获取当前价格
            quote_data = self.quote_service.get_real_time_quote(stock_code)
            current_price = quote_data['price']
            
            # 检查价格是否在指定区间内
            if min_price is not None and current_price < min_price:
                logger.warning(f"【价格不匹配】当前价格 {current_price} 低于最低价 {min_price} - 股票: {stock_code}, 交易类型: buy")
                raise PriceNotMatchError(f"当前价格 {current_price} 不在指定区间 [{min_price}, {max_price}] 内")
                
            if max_price is not None and current_price > max_price:
                logger.warning(f"【价格不匹配】当前价格 {current_price} 高于最高价 {max_price} - 股票: {stock_code}, 交易类型: buy")
                raise PriceNotMatchError(f"当前价格 {current_price} 不在指定区间 [{min_price}, {max_price}] 内")
                
            # 获取持仓信息
            positions = self._load_positions()
            
            # 计算买入数量
            volume = self._calculate_buy_volume(stock_code, position_ratio, current_price)
            if volume <= 0:
                min_trade_volume = config.get('trading.min_volume', 100)
                logger.warning(f"【资金不足】资金不足以买入最小交易数量 - 股票: {stock_code}, 最小数量: {min_trade_volume}股, 当前可用资金: {self.total_cash:.2f}")
                return {
                    'status': 'failed',
                    'message': f'资金不足以买入最小交易数量（最小数量：{min_trade_volume}股，当前可用资金：{self.total_cash:.2f}）',
                    'stock_code': stock_code,
                    'price': current_price,
                    'volume': 0,
                    'amount': 0
                }
                
            # 计算所需资金
            required_amount = current_price * volume
            
            # 检查资金是否足够
            if not self._check_cash_sufficient(required_amount):
                logger.warning(f"【资金不足】资金不足 - 股票: {stock_code}, 需要: {required_amount:.2f}, 当前现金: {self.total_cash:.2f}")
                raise InsufficientFundsError(f"资金不足 - 需要: {required_amount:.2f}, 当前现金: {self.total_cash:.2f}")
                
            try:
                # 更新持仓信息
                if stock_code in positions:
                    # 已有持仓，更新均价
                    old_volume = positions[stock_code]['volume']
                    old_price = positions[stock_code]['price']
                    new_price = self._calculate_weighted_average_price(
                        old_volume, old_price, volume, current_price
                    )
                    positions[stock_code]['volume'] += volume
                    positions[stock_code]['price'] = new_price
                else:
                    # 新建持仓
                    positions[stock_code] = {
                        'volume': volume,
                        'price': current_price,
                        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                # 保存持仓信息
                self._save_positions(positions)
                
                # 更新现金余额
                self._update_cash_balance(required_amount, is_buy=True)
                
                # 同步到资产文件
                self._sync_positions_to_assets()
                
                # 记录交易执行
                self._record_execution(stock_code, 'buy', current_price, volume, strategy_id)
                
                logger.info(f"【交易成功】买入成功 - 股票: {stock_code}, 价格: {current_price}, 数量: {volume}, 金额: {required_amount:.2f}")
                
                return {
                    'status': 'success',
                    'message': '买入成功',
                    'stock_code': stock_code,
                    'price': current_price,
                    'volume': volume,
                    'amount': required_amount
                }
                
            except Exception as e:
                logger.error(f"【交易异常】买入股票异常 - 股票: {stock_code}, 错误: {str(e)}")
                raise TradeError(f"买入异常: {str(e)}")
            
        except (PriceNotMatchError, InvalidTimeError, FrequencyLimitError, 
                PriceDeviationError, InsufficientFundsError) as e:
            # 这些是预期内的交易限制异常，直接向上抛出，不转换为TradeError
            logger.error(f"【交易异常】买入股票异常 - 股票: {stock_code}, 错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"【交易异常】买入股票异常 - 股票: {stock_code}, 错误: {str(e)}")
            raise TradeError(f"买入异常: {str(e)}")
        
    def sell_stock(self, stock_code: str, min_price: Optional[float] = None, max_price: Optional[float] = None, 
                   position_ratio: int = 100, strategy_id: Optional[int] = None) -> Dict:
        """
        卖出股票
        
        Args:
            stock_code: 股票代码
            min_price: 最低卖出价格
            max_price: 最高卖出价格
            position_ratio: 卖出比例（占当前持仓的百分比）
            strategy_id: 策略ID
            
        Returns:
            Dict: 交易结果
            
        Raises:
            PriceNotMatchError: 价格不匹配异常
            InvalidTimeError: 非交易时间异常
            FrequencyLimitError: 交易频率超限异常
            PriceDeviationError: 价格偏离度超限异常
            NoPositionError: 无持仓异常
            TradeError: 其他交易异常
        """
        is_trim_operation = False
        
        try:
            # 检查是否是减仓操作
            if strategy_id:
                try:
                    api_url = f"{self.api_base_url}/strategies/{strategy_id}"
                    response = requests.get(api_url, timeout=config.get('api.timeout'))
                    response.raise_for_status()
                    strategy_data = response.json()
                    
                    if strategy_data['code'] == 200 and 'data' in strategy_data:
                        strategy = strategy_data['data']
                        if strategy.get('action') == 'trim':
                            is_trim_operation = True
                            logger.info(f"【操作类型】检测到减仓操作 - 策略ID: {strategy_id}, 股票: {stock_code}")
                except Exception as e:
                    logger.error(f"检查策略类型失败: {str(e)}")
            
            logger.info(f"【交易开始】开始{'减仓' if is_trim_operation else '卖出'} - 股票: {stock_code}, 价格区间: [{min_price or '不限'}, {max_price or '不限'}], 仓位比例: {position_ratio}%, 策略ID: {strategy_id or '无'}")
            
            # 检查策略状态
            if strategy_id:
                try:
                    api_url = f"{self.api_base_url}/strategies/{strategy_id}"
                    response = requests.get(api_url, timeout=config.get('api.timeout'))
                    response.raise_for_status()
                    strategy_data = response.json()
                    
                    if strategy_data['code'] == 200 and 'data' in strategy_data:
                        strategy = strategy_data['data']
                        execution_status = strategy.get('execution_status')
                        
                        if execution_status == "completed":
                            logger.info(f"【策略跳过】策略 {strategy_id} 已完成，无需执行 - 股票: {stock_code}")
                            return {
                                'status': 'success',
                                'message': '策略已完成，无需执行',
                                'stock_code': stock_code,
                                'price': 0,
                                'volume': 0,
                                'amount': 0
                            }
                        elif execution_status == "partial":
                            logger.info(f"【策略继续】策略 {strategy_id} 部分完成，继续执行 - 股票: {stock_code}")
                        else:
                            logger.info(f"【策略执行】策略 {strategy_id} 状态为 {execution_status}，继续执行 - 股票: {stock_code}")
                except Exception as e:
                    logger.error(f"检查策略状态失败: {str(e)}")
                    # 如果检查失败，继续执行，避免因为API问题影响交易
                    
            # 检查交易时间
            if not self._is_trading_time():
                logger.warning(f"【非交易时间】当前不是交易时间 - 股票: {stock_code}")
                raise InvalidTimeError("当前不是交易时间")
                
            # 检查交易频率
            if not self._check_trade_frequency():
                logger.warning(f"【频率限制】交易频率超过限制 - 股票: {stock_code}")
                raise FrequencyLimitError("交易频率超过限制")
                
            # 获取当前价格
            current_price = self._get_current_price(stock_code, min_price, max_price, 'sell')
            if not current_price:
                # _get_current_price方法已经记录了详细日志，这里不再重复
                quote_data = self.quote_service.get_real_time_quote(stock_code)
                current_price_value = quote_data['price']
                logger.warning(f"【价格不匹配】当前价格 {current_price_value} 不满足交易条件 - 股票: {stock_code}, 价格区间: [{min_price or '不限'}, {max_price or '不限'}]")
                # 直接抛出PriceNotMatchError，不转换为TradeError
                raise PriceNotMatchError(f"当前价格 {current_price_value} 不在指定区间 [{min_price}, {max_price}] 内")
                
            # 检查价格偏离度
            if not self._check_price_deviation(stock_code, current_price):
                logger.warning(f"【价格偏离】价格偏离度超过限制 - 股票: {stock_code}, 当前价格: {current_price}")
                raise PriceDeviationError(f"价格偏离度超过限制")
                
            # 获取持仓信息
            positions = self._load_positions()
            if stock_code not in positions:
                logger.warning(f"【无持仓】没有持仓记录 - 股票: {stock_code}")
                raise NoPositionError(f"没有持仓记录 - 股票代码: {stock_code}")
                
            current_position = positions[stock_code]
            current_volume = current_position.get('volume', 0)
            
            if current_volume <= 0:
                logger.warning(f"【无持仓】持仓数量为0 - 股票: {stock_code}")
                raise NoPositionError(f"持仓数量为0 - 股票代码: {stock_code}")
                
            # 计算卖出数量
            if is_trim_operation:
                # 减仓操作：使用_calculate_trim_volume方法
                sell_volume = self._calculate_trim_volume(stock_code, position_ratio, current_volume)
            else:
                # 普通卖出操作：使用_calculate_sell_volume方法
                sell_volume = self._calculate_sell_volume(stock_code, position_ratio, current_volume)
                
            if sell_volume <= 0:
                logger.warning(f"【卖出数量无效】计算的卖出数量为0 - 股票: {stock_code}, 当前持仓: {current_volume}, 卖出比例: {position_ratio}%")
                return {
                    'status': 'failed',
                    'message': f'计算的卖出数量为0（当前持仓：{current_volume}，卖出比例：{position_ratio}%）',
                    'stock_code': stock_code,
                    'price': current_price,
                    'volume': 0,
                    'amount': 0
                }
                
            # 计算卖出金额
            sell_amount = current_price * sell_volume
            
            try:
                # 更新持仓信息
                if sell_volume >= current_volume:
                    # 全部卖出
                    del positions[stock_code]
                else:
                    # 部分卖出
                    positions[stock_code]['volume'] -= sell_volume
                    
                # 保存持仓信息
                self._save_positions(positions)
                
                # 更新现金余额
                self._update_cash_balance(sell_amount, is_buy=False)
                
                # 同步到资产文件
                self._sync_positions_to_assets()
                
                # 记录交易执行
                action = 'trim' if is_trim_operation else 'sell'
                self._record_execution(stock_code, action, current_price, sell_volume, strategy_id)
                
                logger.info(f"【交易成功】{'减仓' if is_trim_operation else '卖出'}成功 - 股票: {stock_code}, 价格: {current_price}, 数量: {sell_volume}, 金额: {sell_amount:.2f}")
                
                return {
                    'status': 'success',
                    'message': '减仓成功' if is_trim_operation else '卖出成功',
                    'stock_code': stock_code,
                    'price': current_price,
                    'volume': sell_volume,
                    'amount': sell_amount
                }
                
            except Exception as e:
                logger.error(f"【交易失败】{'减仓' if is_trim_operation else '卖出'}失败 - 股票: {stock_code}, 错误: {str(e)}")
                raise TradeError(f"{'减仓' if is_trim_operation else '卖出'}异常: {str(e)}")
                
        except (PriceNotMatchError, InvalidTimeError, FrequencyLimitError, 
                PriceDeviationError, NoPositionError) as e:
            # 这些是预期内的交易限制异常，直接向上抛出，不转换为TradeError
            logger.error(f"【交易异常】卖出股票异常 - 股票: {stock_code}, 错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"【交易异常】卖出股票异常 - 股票: {stock_code}, 错误: {str(e)}")
            raise TradeError(f"卖出异常: {str(e)}")

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
            logger.info(f"正在从服务器获取持仓信息: {api_url}")
            
            response = requests.get(api_url, timeout=config.get('api.timeout', 30))
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"服务器返回数据: {data}")
            
            if data.get('code') == 200 and 'data' in data:
                positions_data = data['data']
                if isinstance(positions_data, list):
                    # 直接使用返回的持仓列表
                    positions = positions_data
                elif isinstance(positions_data, dict) and 'positions' in positions_data:
                    # 从嵌套的 positions 字段获取持仓列表
                    positions = positions_data['positions']
                else:
                    logger.error(f"无效的持仓数据格式: {positions_data}")
                    return False
                
                # 更新持仓数据
                positions_dict = {}
                total_market_value = 0.0
                
                for position in positions:
                    stock_code = position['stock_code']
                    positions_dict[stock_code] = {
                        'volume': position['total_volume'],
                        'price': position['dynamic_cost'],
                        'market_value': position['market_value'],
                        'floating_profit': position['floating_profit'],
                        'floating_profit_ratio': position['floating_profit_ratio'],
                        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    total_market_value += position['market_value']
                
                # 保存持仓数据
                with FileLock(self.positions_file):
                    self._save_positions(positions_dict)
                
                # 更新资产数据
                assets = self._load_assets()
                available_cash = assets['cash']
                total_assets = total_market_value + available_cash
                
                assets.update({
                    'total_assets': total_assets,
                    'total_market_value': total_market_value,
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                # 保存资产数据
                with FileLock(self.assets_file):
                    self._save_assets(assets)
                
                # 更新时间戳
                self._last_update = now
                
                logger.info(f"持仓数据更新成功 - 总市值: {total_market_value:.2f}, "
                          f"可用现金: {available_cash:.2f}, 总资产: {total_assets:.2f}")
                
                # 输出详细持仓信息
                if positions_dict:
                    logger.info("当前持仓详情:")
                    for code, pos in positions_dict.items():
                        logger.info(f"股票: {code}, 数量: {pos['volume']}, "
                                  f"成本: {pos['price']:.2f}, "
                                  f"市值: {pos['market_value']:.2f}, "
                                  f"盈亏: {pos['floating_profit']:.2f} "
                                  f"({pos['floating_profit_ratio']:.2%})")
                else:
                    logger.info("当前无持仓")
                
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

    def _calculate_trim_volume(self, stock_code: str, trim_ratio: int, current_holdings: int) -> int:
        """
        计算减仓(trim)操作的卖出数量，基于原始买入仓位比例
        
        Args:
            stock_code: 股票代码
            trim_ratio: 减仓比例(0-100整数)
            current_holdings: 当前持仓数量
            
        Returns:
            int: 卖出数量
        """
        try:
            logger.info(f"【减仓计算】计算减仓数量 - 股票: {stock_code}, 减仓比例: {trim_ratio}%, 当前持仓: {current_holdings}")
            
            # 获取原始买入仓位比例
            api_url = f"{self.api_base_url}/positions/{stock_code}"
            logger.info(f"【API请求】获取原始买入仓位比例 - API: {api_url}")
            
            response = requests.get(api_url, timeout=config.get('api.timeout'))
            response.raise_for_status()
            position_data = response.json()
            
            if position_data['code'] != 200 or 'data' not in position_data:
                logger.error(f"【API错误】获取持仓信息失败: {position_data.get('message', '未知错误')}")
                return 0
                
            # 获取原始买入仓位比例
            original_position_ratio = position_data['data'].get('original_position_ratio')
            if not original_position_ratio:
                logger.warning(f"【计算警告】未找到原始买入仓位比例，将使用普通卖出逻辑")
                # 如果没有原始买入仓位比例，退化为普通卖出逻辑
                return self._calculate_sell_volume(stock_code, trim_ratio, current_holdings)
                
            logger.info(f"【持仓信息】获取到原始买入仓位比例: {original_position_ratio}%")
            
            # 计算卖出比例: 减仓比例 / 原始买入仓位比例
            if original_position_ratio <= 0:
                logger.error(f"【计算错误】原始买入仓位比例无效: {original_position_ratio}")
                return 0
                
            sell_ratio = trim_ratio / original_position_ratio
            # 限制最大卖出比例为100%
            sell_ratio = min(sell_ratio, 1.0)
            
            # 计算卖出数量
            sell_volume = int(current_holdings * sell_ratio)
            
            # 确保卖出量是volume_step的整数倍
            volume_step = config.get('trading.volume_step', 100)
            sell_volume = (sell_volume // volume_step) * volume_step
            
            # 如果计算结果为0但持仓足够，至少卖出一个最小单位
            min_volume = config.get('trading.min_volume', 100)
            if sell_volume == 0 and current_holdings >= min_volume:
                sell_volume = min_volume
                
            # 确保不超过当前持仓
            sell_volume = min(sell_volume, current_holdings)
            
            logger.info(f"【减仓结果】减仓计算结果 - 原始买入比例: {original_position_ratio}%, 减仓比例: {trim_ratio}%, "
                        f"计算卖出比例: {sell_ratio:.2%}, 卖出数量: {sell_volume}股")
            
            return sell_volume
            
        except requests.RequestException as e:
            logger.error(f"【API异常】获取持仓数据请求失败: {str(e)}")
            return 0
        except Exception as e:
            logger.error(f"【计算异常】计算减仓数量异常: {str(e)}")
            return 0