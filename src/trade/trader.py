"""
交易模块核心类，实现买入和卖出功能
"""
from typing import Dict, Union, Optional
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
        """初始化交易类"""
        self.base_url = config.get('api.base_url')
        self.position_file = config.get('data.positions_file')
        self.assets_file = config.get('data.assets_file')
        self.quote_service = QuoteService()  # 初始化行情服务
        
        # 交易频率限制队列
        self.trade_times = deque(maxlen=config.get('trading.trade_frequency_limit', 10))
        
        # 初始化最后更新时间
        self._last_update = 0
        
        # 确保文件存在
        self._ensure_position_file()
        self._ensure_assets_file()
        
        # 加载资产信息
        self._load_initial_assets()
        
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
        path = Path(self.position_file)
        if not path.parent.exists():
            logger.info(f"创建持仓文件目录: {path.parent}")
            path.parent.mkdir(parents=True)
        if not path.exists() or path.stat().st_size == 0:
            logger.info(f"创建持仓文件: {path}")
            with open(path, 'w', encoding=config.get('data.file_encoding')) as f:
                json.dump({}, f, ensure_ascii=False, indent=config.get('data.json_indent'))
                
    def _load_positions(self) -> Dict:
        """加载持仓数据"""
        self._ensure_position_file()  # 确保文件存在且不为空
        logger.debug(f"加载持仓数据: {self.position_file}")
        with open(self.position_file, 'r', encoding=config.get('data.file_encoding')) as f:
            positions = json.load(f)
            if not self._validate_positions(positions):
                logger.warning("持仓数据验证失败，重置为空")
                positions = {}
            logger.debug(f"当前持仓: {positions}")
            return positions
            
    def _save_positions(self, positions: Dict) -> None:
        """保存持仓数据"""
        if not self._validate_positions(positions):
            raise ValueError("持仓数据格式无效")
            
        logger.debug(f"保存持仓数据: {positions}")
        with open(self.position_file, 'w', encoding=config.get('data.file_encoding')) as f:
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
        self._ensure_assets_file()  # 确保文件存在且不为空
        logger.debug(f"加载资产数据: {self.assets_file}")
        with open(self.assets_file, 'r', encoding=config.get('data.file_encoding')) as f:
            assets = json.load(f)
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
            logger.debug(f"当前资产: {assets}")
            return assets
            
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
        
        # 如果两个文件都为空，则初始化
        if not positions and not assets['positions']:
            logger.info("持仓和资产文件为空，开始初始化数据")
            try:
                # 从服务器获取最新持仓数据
                api_url = f"{self.base_url}/positions"
                response = requests.get(api_url, timeout=config.get('api.timeout'))
                response.raise_for_status()
                data = response.json()
                
                if data['code'] == 200 and 'data' in data:
                    positions_data = data['data']
                    if isinstance(positions_data, list):
                        positions = positions_data
                    elif isinstance(positions_data, dict) and 'positions' in positions_data:
                        positions = positions_data['positions']
                    else:
                        logger.error(f"无效的持仓数据格式: {positions_data}")
                        positions = []
                        
                    # 更新持仓数据
                    positions_dict = {}
                    total_cost_value = 0.0  # 总持仓成本
                    
                    for position in positions:
                        stock_code = position['stock_code']
                        volume = position['total_volume']
                        cost_price = position['dynamic_cost']
                        positions_dict[stock_code] = {
                            'volume': volume,
                            'price': cost_price,
                            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        total_cost_value += volume * cost_price  # 累加持仓成本
                        
                    # 保存持仓数据
                    self._save_positions(positions_dict)
                    
                    # 更新资产数据
                    initial_total_assets = config.get('account.total_assets')
                    assets = {
                        "cash": initial_total_assets - total_cost_value,  # 现金 = 总资产 - 持仓成本总和
                        "total_assets": initial_total_assets,
                        "total_market_value": total_cost_value,  # 初始时使用成本作为市值
                        "positions": {},
                        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # 更新持仓明细
                    for position in positions:
                        stock_code = position['stock_code']
                        volume = position['total_volume']
                        cost_price = position['dynamic_cost']
                        assets['positions'][stock_code] = {
                            'volume': volume,
                            'cost_price': cost_price,
                            'current_price': cost_price,  # 初始时使用成本价作为当前价
                            'market_value': volume * cost_price
                        }
                    
                    # 保存资产数据
                    self._save_assets(assets)
                    logger.info(f"数据初始化完成 - 总成本: {total_cost_value:.2f}, 现金: {assets['cash']:.2f}")
                    
            except Exception as e:
                logger.error(f"初始化数据失败: {str(e)}")
                # 如果初始化失败，使用配置的初始值
                initial_cash = config.get('account.initial_cash')
                assets = {
                    "cash": initial_cash,
                    "total_assets": initial_cash,
                    "total_market_value": 0.00,
                    "positions": {},
                    "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                self._save_assets(assets)
                self._save_positions({})
        else:
            logger.info("持仓和资产文件不为空，使用现有数据")
                
        # 加载最终的资产信息
        assets = self._load_assets()
        self.total_cash = assets['cash']
        self.total_assets = assets['total_assets']
        
        logger.info(f"初始化交易模块 - API地址: {self.base_url}")
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
        """更新资产信息"""
        self._sync_positions_to_assets()
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
            required_amount: 所需金额
            
        Returns:
            是否足够
        """
        is_sufficient = self.total_cash >= required_amount
        if not is_sufficient:
            logger.error(f"现金不足 - 需要: {required_amount:.2f}, 当前现金: {self.total_cash:.2f}")
        else:
            logger.info(f"现金充足 - 需要: {required_amount:.2f}, 当前现金: {self.total_cash:.2f}")
        return is_sufficient
        
    def _update_cash_balance(self, amount: float, is_buy: bool = True) -> None:
        """
        更新现金余额
        
        Args:
            amount: 交易金额
            is_buy: 是否为买入操作
        """
        old_cash = self.total_cash
        if is_buy:
            self.total_cash -= amount
        else:
            self.total_cash += amount
            
        logger.info(f"更新现金余额 - {'买入' if is_buy else '卖出'}金额: {amount:.2f}, "
                   f"原有现金: {old_cash:.2f}, 现有现金: {self.total_cash:.2f}")
                   
        # 更新资产文件中的现金余额
        assets = self._load_assets()
        assets['cash'] = self.total_cash
        self._save_assets(assets)
        
    def _calculate_buy_volume(self, price: float, position_ratio: float, stock_code: str) -> int:
        """
        计算可买入数量
        
        Args:
            price: 股票价格
            position_ratio: 仓位比例
            stock_code: 股票代码
            
        Returns:
            可买入数量（取100的整数倍）
        """
        logger.info(f"开始计算买入数量 - 股票: {stock_code}, 价格: {price}, 目标仓位: {position_ratio}")
        
        if price <= 0:
            logger.error(f"无效的价格: {price}")
            return 0
            
        if position_ratio <= 0 or position_ratio > 1:
            logger.error(f"无效的仓位比例: {position_ratio}")
            return 0
            
        try:
            # 获取最新的总资产和当前持仓
            assets = self._load_assets()
            total_assets = assets['total_assets']
            available_cash = assets['cash']
            
            logger.info(f"当前资产状况 - 总资产: {total_assets:.2f}, 可用现金: {available_cash:.2f}")
            
            # 计算目标市值
            target_value = total_assets * position_ratio
            logger.info(f"目标市值: {target_value:.2f}")
            
            # 检查是否超过单笔最大交易金额
            max_trade_amount = config.get('trading.max_trade_amount')
            if target_value > max_trade_amount:
                target_value = max_trade_amount
                logger.info(f"目标市值超过单笔最大交易金额，调整为: {max_trade_amount:.2f}")
            
            # 检查是否超过可用资金
            if target_value > available_cash:
                target_value = available_cash
                logger.info(f"目标市值超过可用资金，调整为: {available_cash:.2f}")
            
            # 计算最大可买数量
            max_volume = int(target_value / price)
            logger.info(f"初步计算的最大可买数量: {max_volume}")
            
            # 确保为 volume_step 的整数倍
            volume_step = config.get('trading.volume_step', 100)
            volume = (max_volume // volume_step) * volume_step
            logger.info(f"调整到交易数量步长的整数倍: {volume}")
            
            # 检查是否满足最小买入数量
            min_volume = config.get('trading.min_buy_volume', 100)
            if volume < min_volume:
                # 如果最大可买数量不足最小买入数量，但资金足够，则买入最小数量
                if min_volume * price <= available_cash:
                    volume = min_volume
                    logger.info(f"调整为最小买入数量: {volume}")
                else:
                    logger.warning(f"资金不足以买入最小交易数量 {min_volume}")
                    return 0
            
            # 最终检查
            if volume <= 0:
                logger.error("计算得到的买入数量小于等于0")
                return 0
            
            if volume * price > available_cash:
                logger.error(f"买入金额 {volume * price:.2f} 超过可用资金 {available_cash:.2f}")
                return 0
            
            logger.info(f"最终计算的买入数量: {volume}, 所需资金: {volume * price:.2f}")
            return volume
            
        except Exception as e:
            logger.error(f"计算买入数量时发生异常: {str(e)}")
            return 0
        
    def _calculate_sell_volume(self, current_volume: int, position_ratio: float) -> int:
        """
        计算可卖出数量
        
        Args:
            current_volume: 当前持仓量
            position_ratio: 卖出仓位比例（相对于当前持仓）
            
        Returns:
            可卖出数量（取100的整数倍）
        """
        logger.debug(f"计算卖出数量 - 当前持仓: {current_volume}, 卖出比例: {position_ratio}")
        
        if current_volume <= 0:
            logger.error(f"无效的当前持仓: {current_volume}")
            return 0
            
        if position_ratio <= 0 or position_ratio > 1:
            logger.error(f"无效的卖出比例: {position_ratio}")
            return 0
            
        # 直接计算卖出数量
        target_sell_volume = int(current_volume * position_ratio)
        logger.info(f"目标卖出数量: {target_sell_volume}")
        
        # 确保为 volume_step 的整数倍
        volume_step = config.get('trading.volume_step', 100)
        volume = (target_sell_volume // volume_step) * volume_step
        
        # 如果因为取整导致卖出数量为0，但实际需要卖出，则至少卖出一个步长
        if volume == 0 and target_sell_volume > 0:
            if current_volume >= volume_step:
                volume = volume_step
                logger.info(f"因为取整导致卖出数量为0，调整为最小步长: {volume}")
            else:
                logger.warning(f"当前持仓 {current_volume} 小于最小步长 {volume_step}")
                return 0
        
        # 检查是否满足最小卖出数量
        min_volume = config.get('trading.min_sell_volume', 100)
        if volume < min_volume:
            if current_volume >= min_volume:
                volume = min_volume
                logger.info(f"调整为最小卖出数量: {volume}")
            else:
                logger.warning(f"当前持仓 {current_volume} 小于最小卖出数量 {min_volume}")
                return 0
                
        # 确保不超过当前持仓
        if volume > current_volume:
            volume = current_volume
            logger.info(f"卖出数量超过持仓，调整为全部持仓: {volume}")
            
        logger.info(f"最终计算的卖出数量: {volume}")
        return volume
        
    def _get_current_price(self, stock_code: str, min_price: float, max_price: float, action: str = 'buy') -> Optional[float]:
        """
        获取当前价格并检查是否在指定区间内
        
        Args:
            stock_code: 股票代码
            min_price: 最低价格，为None时表示不限制最低价
            max_price: 最高价格，为None时表示不限制最高价
            action: 交易动作（buy/sell）
            
        Returns:
            当前价格，如果不满足条件则返回None
        """
        quote = self.quote_service.get_real_time_quote(stock_code)
        if not quote:
            logger.error(f"获取行情失败 - 股票代码: {stock_code}")
            return None
            
        current_price = quote['price']
        
        # 如果价格区间都为空，直接返回当前价格
        if min_price is None and max_price is None:
            logger.info(f"价格不限，当前价格: {current_price}")
            return current_price
            
        # 检查价格是否在指定区间内
        price_in_range = True
        if min_price is not None and current_price < min_price:
            price_in_range = False
        if max_price is not None and current_price > max_price:
            price_in_range = False
            
        if price_in_range:
            logger.info(f"当前价格: {current_price}, 在价格区间内 - 最低: {min_price or '不限'}, 最高: {max_price or '不限'}")
            return current_price
            
        logger.warning(f"当前价格 {current_price} 不在指定区间内 - 最低: {min_price or '不限'}, 最高: {max_price or '不限'}")
        return None
        
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
    def _record_execution(self, stock_code: str, action: str, price: float, volume: int, strategy_id: int = None) -> None:
        """
        记录交易执行
        
        Args:
            stock_code: 股票代码
            action: 交易动作（buy/sell）
            price: 成交价格
            volume: 成交数量
            strategy_id: 策略ID
        """
        try:
            # 检查是否达到目标持仓
            strategy_status = "partial"
            if strategy_id:
                # 获取策略信息
                api_url = f"{self.base_url}/strategies/{strategy_id}"
                response = requests.get(api_url, timeout=config.get('api.timeout'))
                response.raise_for_status()
                strategy_data = response.json()
                
                if strategy_data['code'] == 200 and 'data' in strategy_data:
                    strategy = strategy_data['data']
                    
                    # 获取当前持仓
                    positions = self._load_positions()
                    current_position = positions.get(stock_code, {})
                    current_volume = current_position.get('volume', 0)
                    
                    if action == 'buy':
                        # 买入策略的完成判断
                        target_value = strategy['position_ratio'] * self._load_assets()['total_assets']
                        current_value = current_volume * price
                        if current_value >= target_value * 0.95:
                            strategy_status = "completed"
                            logger.info(f"买入策略执行完成 - 当前市值: {current_value:.2f}, 目标市值: {target_value:.2f}")
                    else:  # sell
                        # 获取原始策略信息中的目标持仓数量
                        original_target_volume = strategy.get('original_volume', current_volume) * (1 - strategy['position_ratio'])
                        
                        # 检查是否已经达到原始策略的目标持仓
                        if current_volume <= original_target_volume + 100:  # 允许100股的误差
                            strategy_status = "completed"
                            logger.info(f"卖出策略执行完成 - 目标剩余: {original_target_volume}, 当前剩余: {current_volume}")
                        else:
                            logger.info(f"卖出策略部分完成 - 目标剩余: {original_target_volume}, 当前剩余: {current_volume}")
            
            # 调用API记录执行
            api_url = f"{self.base_url}/executions"
            data = {
                "strategy_id": strategy_id,
                "stock_code": stock_code,
                "action": action,
                "execution_price": price,
                "volume": volume,
                "strategy_status": strategy_status,
                "remarks": f"按计划执行{action}操作",
                "execution_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            response = requests.post(
                api_url,
                json=data,
                timeout=config.get('api.timeout')
            )
            response.raise_for_status()
            
            result = response.json()
            if result['code'] != 200:
                raise ApiError(f"API返回错误: {result['message']}")
                
            logger.info(f"记录交易执行成功 - 股票: {stock_code}, 动作: {action}, "
                       f"价格: {price}, 数量: {volume}, 状态: {strategy_status}")
                       
            # 如果策略完成，更新策略状态
            if strategy_status == "completed" and strategy_id:
                update_url = f"{self.base_url}/strategies/{strategy_id}"
                update_data = {
                    "execution_status": "completed",
                    "is_active": False  # 策略完成后设置为非活动状态
                }
                response = requests.put(
                    update_url,
                    json=update_data,
                    timeout=config.get('api.timeout')
                )
                response.raise_for_status()
                logger.info(f"更新策略状态为已完成 - 策略ID: {strategy_id}")
                
        except requests.RequestException as e:
            logger.error(f"记录交易执行请求失败 - 股票: {stock_code}, 错误: {str(e)}")
            raise ApiError(f"API请求异常: {str(e)}")
        except Exception as e:
            logger.error(f"记录交易执行异常 - 股票: {stock_code}, 错误: {str(e)}")
            # 这里我们只记录错误，不影响交易结果
            
    def buy_stock(self, stock_code: str, min_price: float, max_price: float, 
                  position_ratio: float, strategy_id: int = None) -> Dict[str, Union[str, int, float]]:
        """
        买入股票
        
        Args:
            stock_code: 股票代码
            min_price: 最低买入价格
            max_price: 最高买入价格
            position_ratio: 仓位比例
            strategy_id: 策略ID
            
        Returns:
            交易结果
            
        Raises:
            InvalidTimeError: 非交易时间
            InsufficientFundsError: 资金不足
            PriceNotMatchError: 价格不匹配
            FrequencyLimitError: 交易频率超限
            PositionLimitError: 持仓比例超限
            PriceDeviationError: 价格偏离度超限
            TradeError: 其他交易异常
        """
        logger.info(f"开始买入 - 股票: {stock_code}, 价格区间: [{min_price}, {max_price}], "
                   f"仓位: {position_ratio}, 策略ID: {strategy_id}")

        # 如果有策略ID，先检查策略状态
        if strategy_id:
            try:
                api_url = f"{self.base_url}/strategies/{strategy_id}"
                response = requests.get(api_url, timeout=config.get('api.timeout'))
                response.raise_for_status()
                strategy_data = response.json()
                
                if strategy_data['code'] == 200 and 'data' in strategy_data:
                    strategy = strategy_data['data']
                    execution_status = strategy.get('execution_status')
                    
                    if execution_status == "completed":
                        logger.info(f"策略 {strategy_id} 已完成，无需执行")
                        return {
                            'status': 'success',
                            'message': '策略已完成，无需执行',
                            'stock_code': stock_code,
                            'price': 0,
                            'volume': 0,
                            'amount': 0
                        }
                    elif execution_status == "partial":
                        logger.info(f"策略 {strategy_id} 部分完成，检查持仓是否达标")
                    else:
                        logger.info(f"策略 {strategy_id} 状态为 {execution_status}，继续执行")
            except Exception as e:
                logger.error(f"检查策略状态失败: {str(e)}")
                # 如果检查失败，继续执行，避免因为API问题影响交易
                
        # 检查交易时间
        if not self._is_trading_time():
            raise InvalidTimeError("当前不是交易时间")
            
        # 检查交易频率
        if not self._check_trade_frequency():
            raise FrequencyLimitError("交易频率超过限制")
            
        # 获取当前价格
        current_price = self._get_current_price(stock_code, min_price, max_price, 'buy')
        if not current_price:
            raise PriceNotMatchError(f"当前价格 {self.quote_service.get_real_time_quote(stock_code)['price']} 不在指定区间 [{min_price}, {max_price}] 内")
            
        # 检查价格偏离度
        if not self._check_price_deviation(stock_code, current_price):
            raise PriceDeviationError(f"价格偏离度超过限制")

        # 检查当前持仓是否已达到目标仓位
        assets = self._load_assets()
        total_assets = assets['total_assets']
        target_value = total_assets * position_ratio
        
        positions = self._load_positions()
        current_position = positions.get(stock_code, {})
        current_volume = current_position.get('volume', 0)
        current_value = current_volume * current_price
        
        if current_value >= target_value * 0.95:  # 允许 5% 的误差
            logger.info(f"当前持仓已达到目标仓位 - 当前市值: {current_value:.2f}, 目标市值: {target_value:.2f}")
            return {
                'status': 'success',
                'message': '持仓已达标，无需买入',
                'stock_code': stock_code,
                'price': current_price,
                'volume': 0,
                'amount': 0
            }
            
        # 计算买入数量（考虑已有持仓）
        remaining_target_value = target_value - current_value
        if remaining_target_value <= 0:
            logger.info("无需追加买入")
            return {
                'status': 'success',
                'message': '无需追加买入',
                'stock_code': stock_code,
                'price': current_price,
                'volume': 0,
                'amount': 0
            }
            
        # 使用剩余目标市值计算买入数量
        volume = self._calculate_buy_volume(current_price, remaining_target_value / total_assets, stock_code)
        if volume <= 0:
            min_trade_volume = config.get('trading.min_buy_volume', 100)
            return {
                'status': 'failed',
                'message': f'资金不足以买入最小交易数量（最小数量：{min_trade_volume}股，当前可用资金：{self.total_cash:.2f}，所需资金：{min_trade_volume * current_price:.2f}）',
                'stock_code': stock_code,
                'price': current_price,
                'volume': 0,
                'amount': 0
            }
            
        # 计算所需资金
        required_amount = current_price * volume
        
        # 检查持仓比例
        if not self._check_position_limit(stock_code, current_value + required_amount):
            raise PositionLimitError("持仓比例超过限制")
            
        # 检查资金是否足够
        if not self._check_cash_sufficient(required_amount):
            raise InsufficientFundsError(
                f"资金不足 - 需要: {required_amount:.2f}, 当前现金: {self.total_cash:.2f}"
            )
            
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
            
            logger.info(f"买入成功 - 股票: {stock_code}, 价格: {current_price}, "
                       f"数量: {volume}, 金额: {required_amount:.2f}")
                       
            return {
                'status': 'success',
                'message': '买入成功',
                'stock_code': stock_code,
                'price': current_price,
                'volume': volume,
                'amount': required_amount
            }
            
        except TradeError:
            raise
        except Exception as e:
            logger.error(f"买入失败 - 股票: {stock_code}, 错误: {str(e)}")
            raise TradeError(f"买入异常: {str(e)}")
            
    def sell_stock(self, stock_code: str, min_price: float, max_price: float,
                   position_ratio: float, strategy_id: int = None) -> Dict[str, Union[str, int, float]]:
        """
        卖出股票
        
        Args:
            stock_code: 股票代码
            min_price: 最低卖出价格，None表示不限制最低价
            max_price: 最高卖出价格，None表示不限制最高价
            position_ratio: 卖出仓位比例（相对于当前持仓）
            strategy_id: 策略ID
            
        Returns:
            交易结果
        """
        logger.info(f"开始卖出 - 股票: {stock_code}, 价格区间: [{min_price or '不限'}, {max_price or '不限'}], "
                   f"仓位: {position_ratio}, 策略ID: {strategy_id}")

        # 更新并获取最新持仓数据
        self.update_positions()
        positions = self._load_positions()
        
        # 检查是否有持仓
        if stock_code not in positions:
            raise NoPositionError(f"股票 {stock_code} 没有持仓")
            
        current_position = positions[stock_code]
        current_volume = current_position['volume']
        logger.info(f"当前持仓: {current_volume} 股")

        # 如果有策略ID，先检查策略状态
        if strategy_id:
            try:
                api_url = f"{self.base_url}/strategies/{strategy_id}"
                response = requests.get(api_url, timeout=config.get('api.timeout'))
                response.raise_for_status()
                strategy_data = response.json()
                
                if strategy_data['code'] == 200 and 'data' in strategy_data:
                    strategy = strategy_data['data']
                    execution_status = strategy.get('execution_status')
                    
                    if execution_status == "completed":
                        logger.info(f"策略 {strategy_id} 已完成，无需执行")
                        return {
                            'status': 'success',
                            'message': '策略已完成，无需执行',
                            'stock_code': stock_code,
                            'price': 0,
                            'volume': 0,
                            'amount': 0
                        }
                        
                    # 获取原始策略信息中的目标持仓数量
                    original_target_volume = strategy.get('original_volume', current_volume) * (1 - position_ratio)
                    current_target_volume = current_volume * (1 - position_ratio)
                    
                    # 检查是否已经达到原始策略的目标持仓
                    if current_volume <= original_target_volume + 100:  # 允许100股的误差
                        logger.info(f"当前持仓已达到原始策略目标 - 原始目标剩余: {original_target_volume}, 当前持仓: {current_volume}")
                        return {
                            'status': 'success',
                            'message': '当前持仓已达到目标',
                            'stock_code': stock_code,
                            'price': 0,
                            'volume': 0,
                            'amount': 0
                        }
                    logger.info(f"当前持仓需要调整 - 原始目标剩余: {original_target_volume}, 当前持仓: {current_volume}, 本次目标剩余: {current_target_volume}")
            except Exception as e:
                logger.error(f"检查策略状态失败: {str(e)}")
                # 如果检查失败，继续执行，避免因为API问题影响交易
                
        # 检查交易时间
        if not self._is_trading_time():
            raise InvalidTimeError("当前不是交易时间")
            
        # 检查交易频率
        if not self._check_trade_frequency():
            raise FrequencyLimitError("交易频率超过限制")
            
        # 获取当前价格
        current_price = self._get_current_price(stock_code, min_price, max_price, 'sell')
        if not current_price:
            raise PriceNotMatchError(f"当前价格不在指定区间内")
            
        # 检查价格偏离度
        if not self._check_price_deviation(stock_code, current_price):
            raise PriceDeviationError(f"价格偏离度超过限制")
            
        # 计算卖出数量
        volume = self._calculate_sell_volume(current_volume, position_ratio)
        if volume <= 0:
            raise TradeError("计算卖出数量失败")
            
        logger.info(f"计划卖出数量: {volume} 股，当前价格: {current_price}")
            
        try:
            # 计算卖出金额
            amount = current_price * volume
            
            # 更新持仓信息
            if volume >= current_volume:
                # 清仓
                del positions[stock_code]
                logger.info(f"清仓完成 - 股票: {stock_code}")
            else:
                # 部分卖出
                positions[stock_code]['volume'] -= volume
                positions[stock_code]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"部分卖出后剩余持仓: {positions[stock_code]['volume']} 股")
                
            # 保存持仓信息
            self._save_positions(positions)
            
            # 更新现金余额
            self._update_cash_balance(amount, is_buy=False)
            
            # 同步到资产文件
            self._sync_positions_to_assets()
            
            # 记录交易执行
            self._record_execution(stock_code, 'sell', current_price, volume, strategy_id)
            
            logger.info(f"卖出成功 - 股票: {stock_code}, 价格: {current_price}, "
                       f"数量: {volume}, 金额: {amount:.2f}")
                       
            return {
                'status': 'success',
                'message': '卖出成功',
                'stock_code': stock_code,
                'price': current_price,
                'volume': volume,
                'amount': amount
            }
            
        except TradeError:
            raise
        except Exception as e:
            logger.error(f"卖出失败 - 股票: {stock_code}, 错误: {str(e)}")
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
                with FileLock(self.position_file):
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