"""
交易模块核心类，实现买入和卖出功能
"""
from typing import Dict, Union, Optional
import json
import os
import requests
import logging
from datetime import datetime
from pathlib import Path
from src.quote.quote import QuoteService
from config.settings import (
    API_BASE_URL, POSITION_FILE, ASSETS_FILE, INITIAL_CASH,
    MIN_BUY_VOLUME, MIN_SELL_VOLUME, VOLUME_STEP,
    POSITION_FILE_ENCODING, POSITION_FILE_INDENT,
    REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)

# 配置日志
logger = logging.getLogger(__name__)

class StockTrader:
    """股票交易类"""
    
    def __init__(self, base_url: str = API_BASE_URL, position_file: str = POSITION_FILE):
        """
        初始化交易类
        
        Args:
            base_url: API基础URL
            position_file: 持仓文件路径
        """
        self.base_url = base_url
        self.position_file = position_file
        self.assets_file = ASSETS_FILE
        self.quote_service = QuoteService()  # 初始化行情服务
        self._ensure_position_file()
        self._ensure_assets_file()
        
        # 加载当前资产信息
        assets = self._load_assets()
        self.total_cash = assets['cash']
        logger.info(f"初始化交易模块，API地址: {base_url}，持仓文件: {position_file}，"
                   f"资产文件: {self.assets_file}，当前现金: {self.total_cash}")
                   
    def _ensure_position_file(self) -> None:
        """确保持仓文件存在"""
        path = Path(self.position_file)
        if not path.parent.exists():
            logger.info(f"创建持仓文件目录: {path.parent}")
            path.parent.mkdir(parents=True)
        if not path.exists():
            logger.info(f"创建持仓文件: {path}")
            with open(path, 'w', encoding=POSITION_FILE_ENCODING) as f:
                json.dump({}, f, ensure_ascii=False, indent=POSITION_FILE_INDENT)
                
    def _load_positions(self) -> Dict:
        """加载持仓数据"""
        logger.debug(f"加载持仓数据: {self.position_file}")
        with open(self.position_file, 'r', encoding=POSITION_FILE_ENCODING) as f:
            positions = json.load(f)
            logger.debug(f"当前持仓: {positions}")
            return positions
            
    def _save_positions(self, positions: Dict) -> None:
        """保存持仓数据"""
        logger.debug(f"保存持仓数据: {positions}")
        with open(self.position_file, 'w', encoding=POSITION_FILE_ENCODING) as f:
            json.dump(positions, f, ensure_ascii=False, indent=POSITION_FILE_INDENT)
            
    def _ensure_assets_file(self) -> None:
        """确保资产文件存在"""
        path = Path(self.assets_file)
        if not path.parent.exists():
            logger.info(f"创建资产文件目录: {path.parent}")
            path.parent.mkdir(parents=True)
        if not path.exists():
            logger.info(f"创建资产文件: {path}")
            initial_assets = {
                "cash": INITIAL_CASH,
                "total_assets": INITIAL_CASH,
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "positions": {}
            }
            with open(path, 'w', encoding=POSITION_FILE_ENCODING) as f:
                json.dump(initial_assets, f, ensure_ascii=False, indent=POSITION_FILE_INDENT)
                
    def _load_assets(self) -> Dict:
        """加载资产数据"""
        logger.debug(f"加载资产数据: {self.assets_file}")
        with open(self.assets_file, 'r', encoding=POSITION_FILE_ENCODING) as f:
            assets = json.load(f)
            logger.debug(f"当前资产: {assets}")
            return assets
            
    def _save_assets(self, assets: Dict) -> None:
        """保存资产数据"""
        logger.debug(f"保存资产数据: {assets}")
        with open(self.assets_file, 'w', encoding=POSITION_FILE_ENCODING) as f:
            json.dump(assets, f, ensure_ascii=False, indent=POSITION_FILE_INDENT)
            
    def update_assets(self) -> Dict:
        """
        更新资产信息
        
        Returns:
            更新后的资产信息
        """
        logger.info("开始更新资产信息...")
        
        # 加载当前持仓和资产信息
        positions = self._load_positions()
        assets = self._load_assets()
        
        # 更新现金
        assets['cash'] = self.total_cash
        
        # 计算各个持仓的市值
        total_market_value = 0
        assets['positions'] = {}
        
        for code, pos in positions.items():
            if code == 'cash':
                continue
                
            # 获取最新行情
            quote = self.quote_service.get_real_time_quote(code)
            if quote:
                current_price = quote['price']
                market_value = current_price * pos['volume']
                total_market_value += market_value
                
                # 更新持仓信息
                assets['positions'][code] = {
                    'volume': pos['volume'],
                    'cost_price': pos['price'],  # 成本价
                    'current_price': current_price,
                    'market_value': market_value,
                    'profit_loss': market_value - pos['price'] * pos['volume']  # 浮动盈亏
                }
                
        # 更新总资产和时间
        assets['total_assets'] = self.total_cash + total_market_value
        assets['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存更新后的资产信息
        self._save_assets(assets)
        
        logger.info(f"资产信息更新完成 - 总资产: {assets['total_assets']:.2f}, "
                   f"现金: {self.total_cash:.2f}, 持仓市值: {total_market_value:.2f}")
        
        return assets
        
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
        
    def _calculate_buy_volume(self, price: float, position_ratio: float) -> int:
        """
        计算可买入数量
        
        Args:
            price: 股票价格
            position_ratio: 仓位比例
            
        Returns:
            可买入数量（取100的整数倍）
        """
        logger.debug(f"计算买入数量 - 价格: {price}, 仓位: {position_ratio}")
        
        if price <= 0 or position_ratio <= 0:
            logger.error(f"无效的参数 - 价格: {price}, 仓位: {position_ratio}")
            return 0
            
        # 获取最新的总资产
        assets = self._load_assets()
        total_assets = assets['total_assets']
        
        # 计算目标金额
        available_amount = total_assets * position_ratio
        
        # 检查现金是否足够
        if not self._check_cash_sufficient(available_amount):
            return 0
            
        volume = int(available_amount / price / VOLUME_STEP) * VOLUME_STEP
        result = max(volume, MIN_BUY_VOLUME)
        
        # 再次检查实际所需金额是否超过现金余额
        required_amount = result * price
        if not self._check_cash_sufficient(required_amount):
            volume = int(self.total_cash / price / VOLUME_STEP) * VOLUME_STEP
            result = max(volume, MIN_BUY_VOLUME)
            if result * price > self.total_cash:
                logger.error(f"现金不足以购买最小数量 - 需要: {MIN_BUY_VOLUME * price:.2f}, 现有: {self.total_cash:.2f}")
                return 0
                
        logger.debug(f"计算结果 - 可用金额: {available_amount}, 买入数量: {result}, 所需资金: {result * price:.2f}")
        return result
        
    def _calculate_sell_volume(self, current_volume: int, position_ratio: float) -> int:
        """
        计算可卖出数量
        
        Args:
            current_volume: 当前持仓数量
            position_ratio: 卖出仓位比例
            
        Returns:
            可卖出数量（取100的整数倍）
        """
        logger.debug(f"计算卖出数量 - 当前持仓: {current_volume}, 卖出比例: {position_ratio}")
        
        if current_volume <= 0 or position_ratio <= 0:
            logger.error(f"无效的参数 - 当前持仓: {current_volume}, 卖出比例: {position_ratio}")
            return 0
            
        volume = int(current_volume * position_ratio / VOLUME_STEP) * VOLUME_STEP
        result = max(min(volume, current_volume), MIN_SELL_VOLUME)  # 最少卖出配置的最小数量
        
        logger.debug(f"计算结果 - 卖出数量: {result}")
        return result
        
    def _get_current_price(self, stock_code: str, min_price: float, max_price: float, action: str = 'buy') -> Optional[float]:
        """
        获取当前股票价格
        
        Args:
            stock_code: 股票代码
            min_price: 最低价格
            max_price: 最高价格
            action: 交易动作（buy/sell）
            
        Returns:
            当前价格，如果获取失败则返回None
        """
        quote = self.quote_service.get_real_time_quote(stock_code)
        if not quote:
            logger.error(f"获取股票 {stock_code} 行情数据失败")
            return None
            
        current_price = quote['price']
        logger.info(f"股票 {stock_code} {quote['name']} 当前价格: {current_price}, 价格区间: {min_price}-{max_price}")
        
        # 根据买卖方向判断价格
        if action == 'buy':
            # 买入时：当前价格 < 最低价，立即成交；当前价格 > 最高价，不成交
            if current_price > max_price:
                logger.info(f"当前价格 {current_price} 高于最高买入价 {max_price}，不执行买入")
                return None
            # 当前价格 <= 最高价时都可以买入（包括低于最低价的情况）
            logger.info(f"当前价格 {current_price} {'低于最低买入价' if current_price < min_price else '在买入价格区间内'}，可以买入")
            return current_price
        else:  # sell
            # 卖出时：当前价格 > 最高价，立即成交；当前价格 < 最低价，不成交
            if current_price < min_price:
                logger.info(f"当前价格 {current_price} 低于最低卖出价 {min_price}，不执行卖出")
                return None
            # 当前价格 >= 最低价时都可以卖出（包括高于最高价的情况）
            logger.info(f"当前价格 {current_price} {'高于最高卖出价' if current_price > max_price else '在卖出价格区间内'}，可以卖出")
            return current_price
        
    def buy_stock(self, stock_code: str, min_price: float, max_price: float, 
                  position_ratio: float, strategy_id: int = None) -> Dict[str, Union[str, int, float]]:
        """
        买入股票
        
        Args:
            stock_code: 股票代码
            min_price: 最低买入价
            max_price: 最高买入价
            position_ratio: 仓位比例
            strategy_id: 策略ID
            
        Returns:
            交易结果字典
        """
        logger.info(f"开始买入股票 - 代码: {stock_code}, 价格区间: {min_price}-{max_price}, 仓位: {position_ratio}, 策略ID: {strategy_id}")
        
        # 获取当前价格（指定买入动作）
        current_price = self._get_current_price(stock_code, min_price, max_price, 'buy')
        if not current_price:
            return {
                'result': 'failed',
                'volume': 0,
                'price': 0,
                'error': '获取当前价格失败或价格高于最高买入价'
            }
            
        # 加载当前持仓
        positions = self._load_positions()
        current_volume = positions.get(stock_code, {}).get('volume', 0)
        logger.info(f"当前持仓数量: {current_volume}")
        
        # 计算买入数量
        volume = self._calculate_buy_volume(current_price, position_ratio)
        
        if volume <= 0:
            logger.error("买入数量为0，交易失败")
            return {
                'result': 'failed',
                'volume': 0,
                'price': current_price,
                'error': '计算买入数量为0'
            }
            
        # 计算交易金额
        trade_amount = volume * current_price
        
        # 更新持仓
        positions[stock_code] = {
            'volume': current_volume + volume,
            'price': current_price,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 更新现金余额
        self._update_cash_balance(trade_amount, is_buy=True)
        
        # 保存持仓
        self._save_positions(positions)
        logger.info(f"更新持仓成功 - 新持仓量: {current_volume + volume}")
        
        # 记录执行结果
        self._record_execution(stock_code, 'buy', current_price, volume, strategy_id)
        
        logger.info(f"买入交易完成 - 数量: {volume}, 价格: {current_price}, 金额: {trade_amount:.2f}")
        return {
            'result': 'success',
            'volume': volume,
            'price': current_price,
            'error': None
        }
        
    def sell_stock(self, stock_code: str, min_price: float, max_price: float,
                   position_ratio: float, strategy_id: int = None) -> Dict[str, Union[str, int, float]]:
        """
        卖出股票
        
        Args:
            stock_code: 股票代码
            min_price: 最低卖出价
            max_price: 最高卖出价
            position_ratio: 卖出仓位比例
            strategy_id: 策略ID
            
        Returns:
            交易结果字典
        """
        logger.info(f"开始卖出股票 - 代码: {stock_code}, 价格区间: {min_price}-{max_price}, 仓位: {position_ratio}, 策略ID: {strategy_id}")
        
        # 获取当前价格（指定卖出动作）
        current_price = self._get_current_price(stock_code, min_price, max_price, 'sell')
        if not current_price:
            return {
                'result': 'failed',
                'volume': 0,
                'price': 0,
                'error': '获取当前价格失败或价格低于最低卖出价'
            }
            
        # 加载当前持仓
        positions = self._load_positions()
        current_volume = positions.get(stock_code, {}).get('volume', 0)
        logger.info(f"当前持仓数量: {current_volume}")
        
        if current_volume <= 0:
            logger.error("当前无持仓，无法卖出")
            return {
                'result': 'failed',
                'volume': 0,
                'price': current_price,
                'error': '当前无持仓'
            }
            
        # 计算卖出数量
        volume = self._calculate_sell_volume(current_volume, position_ratio)
        
        if volume <= 0:
            logger.error("卖出数量为0，交易失败")
            return {
                'result': 'failed',
                'volume': 0,
                'price': current_price,
                'error': '计算卖出数量为0'
            }
            
        # 计算交易金额
        trade_amount = volume * current_price
        
        # 更新持仓
        new_volume = current_volume - volume
        if new_volume > 0:
            positions[stock_code]['volume'] = new_volume
            positions[stock_code]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"更新持仓成功 - 新持仓量: {new_volume}")
        else:
            del positions[stock_code]
            logger.info("清空持仓")
            
        # 更新现金余额
        self._update_cash_balance(trade_amount, is_buy=False)
        
        # 保存持仓
        self._save_positions(positions)
        
        # 记录执行结果
        self._record_execution(stock_code, 'sell', current_price, volume, strategy_id)
        
        logger.info(f"卖出交易完成 - 数量: {volume}, 价格: {current_price}, 金额: {trade_amount:.2f}")
        return {
            'result': 'success',
            'volume': volume,
            'price': current_price,
            'error': None
        }
        
    def _record_execution(self, stock_code: str, action: str, price: float, volume: int, strategy_id: int = None) -> None:
        """
        记录交易执行结果
        
        Args:
            stock_code: 股票代码
            action: 交易动作
            price: 成交价格
            volume: 成交数量
            strategy_id: 策略ID
        """
        logger.info(f"记录交易执行结果 - 代码: {stock_code}, 动作: {action}, 价格: {price}, 数量: {volume}, 策略ID: {strategy_id}")
        
        try:
            url = f"{self.base_url}/executions"
            data = {
                "strategy_id": strategy_id,
                "stock_code": stock_code,
                "execution_price": price,
                "volume": volume,
                "remarks": f"模拟{action}交易"
            }
            logger.debug(f"调用执行记录接口 - URL: {url}, 数据: {data}")
            
            response = requests.post(url, json=data)
            response.raise_for_status()
            logger.info("记录交易执行结果成功")
            
        except Exception as e:
            logger.error(f"记录执行结果失败: {str(e)}") 