"""交易核心模块"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
import logging
from src.models.order import Order, OrderStatus, OrderType, OrderSide
from src.models.account import Account
from src.models.position import Position
from src.broker.base import BaseBroker, BrokerError
from src.utils.fee_calculator import TradingFeeCalculator
from src.config import config
from decimal import Decimal
from enum import Enum

logger = logging.getLogger(__name__)

class TradeError(Exception):
    """交易异常基类"""
    pass

class InsufficientFundsError(TradeError):
    """资金不足异常"""
    pass

class PositionNotFoundError(TradeError):
    """持仓不存在异常"""
    pass

class InvalidOrderError(TradeError):
    """无效订单异常"""
    pass

class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单

class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"           # 待执行
    SUBMITTED = "submitted"       # 已提交
    PARTIAL_FILLED = "partial"    # 部分成交
    FILLED = "filled"            # 全部成交
    CANCELLED = "cancelled"      # 已撤销
    REJECTED = "rejected"        # 已拒绝

class Trader:
    """交易核心类"""
    
    def __init__(self, broker: BaseBroker):
        """
        初始化交易核心
        
        Args:
            broker: 券商接口对象
        """
        self.broker = broker  # 券商接口
        self.fee_calculator = TradingFeeCalculator()  # 费用计算器
        self.strategies = {}  # 策略字典
        self.positions = {}   # 持仓字典
        self.is_running = False
        self.is_connected = False
        
        # 连接券商接口
        self._connect()
        
    def _connect(self) -> None:
        """连接券商接口"""
        try:
            logger.info("正在连接券商接口...")
            if not self.broker.connect():
                raise TradeError("连接券商接口失败")
            logger.info("券商接口连接成功")
        except Exception as e:
            logger.error(f"连接券商接口异常: {str(e)}")
            raise TradeError(f"连接券商接口异常: {str(e)}")
            
    def _check_order(self, order: Order) -> None:
        """
        检查订单有效性
        
        Args:
            order: 订单对象
            
        Raises:
            InvalidOrderError: 订单无效
        """
        # 检查基本参数
        if not order.stock_code:
            raise InvalidOrderError("股票代码不能为空")
        if order.volume <= 0:
            raise InvalidOrderError("委托数量必须大于0")
        if order.price <= 0:
            raise InvalidOrderError("委托价格必须大于0")
            
        # 检查数量步长
        volume_step = config.get('trading.volume_step', 100)
        if order.volume % volume_step != 0:
            raise InvalidOrderError(f"委托数量必须是{volume_step}的整数倍")
            
        # 检查最小数量
        min_volume = config.get('trading.min_volume', 100)
        if order.volume < min_volume:
            raise InvalidOrderError(f"委托数量不能小于{min_volume}")
            
        # 检查交易金额限制
        amount = order.price * order.volume
        if amount < config.get('trading.min_trade_amount', 1000):
            raise InvalidOrderError(f"委托金额不能小于{config.get('trading.min_trade_amount')}元")
        if amount > config.get('trading.max_trade_amount', 500000):
            raise InvalidOrderError(f"委托金额不能超过{config.get('trading.max_trade_amount')}元")
            
        # 买入时检查资金是否足够
        if order.side == OrderSide.BUY:
            required_amount = order.required_amount  # 包含手续费
            if not self.broker.account.check_cash_sufficient(required_amount):
                raise InsufficientFundsError(
                    f"资金不足 - 需要: {required_amount:.2f}, "
                    f"可用: {self.broker.account.available_cash:.2f}"
                )
                
        # 卖出时检查持仓是否足够
        elif order.side == OrderSide.SELL:
            positions = self.broker.get_positions()
            if order.stock_code not in positions:
                raise PositionNotFoundError(f"没有持仓 - 股票: {order.stock_code}")
            position = positions[order.stock_code]
            if position.available_volume < order.volume:
                raise InvalidOrderError(
                    f"可用持仓不足 - 需要: {order.volume}, "
                    f"可用: {position.available_volume}"
                )
                
    def _calculate_position_ratio(self, stock_code: str, amount: float) -> float:
        """
        计算持仓比例
        
        Args:
            stock_code: 股票代码
            amount: 交易金额
            
        Returns:
            float: 持仓比例(0-100)
        """
        # 获取账户信息
        account = self.broker.get_account()
        total_assets = account.total_assets
        
        # 获取当前持仓
        positions = self.broker.get_positions()
        current_position = positions.get(stock_code)
        current_value = current_position.market_value if current_position else 0
        
        # 计算持仓比例
        position_ratio = (current_value + amount) / total_assets * 100
        return position_ratio
        
    def buy_stock(self, stock_code: str, price: float, volume: int,
                  order_type: OrderType = OrderType.LIMIT,
                  strategy_id: Optional[int] = None) -> Dict:
        """
        买入股票
        
        Args:
            stock_code: 股票代码
            price: 买入价格
            volume: 买入数量
            order_type: 订单类型
            strategy_id: 策略ID
            
        Returns:
            Dict: 交易结果
        """
        try:
            # 创建订单对象
            order = Order(
                stock_code=stock_code,
                side=OrderSide.BUY,
                order_type=order_type,
                volume=volume,
                price=price,
                strategy_id=strategy_id
            )
            
            # 检查订单有效性
            self._check_order(order)
            
            # 检查持仓比例是否超限
            amount = price * volume
            position_ratio = self._calculate_position_ratio(stock_code, amount)
            max_ratio = config.get('trading.max_position_ratio', 30)
            if position_ratio > max_ratio:
                raise InvalidOrderError(
                    f"持仓比例超限 - 目标: {position_ratio:.2f}%, "
                    f"上限: {max_ratio}%"
                )
                
            # 冻结资金
            required_amount = order.required_amount
            if not self.broker.account.freeze_cash(required_amount):
                raise InsufficientFundsError(
                    f"资金冻结失败 - 金额: {required_amount:.2f}, "
                    f"可用: {self.broker.account.available_cash:.2f}"
                )
                
            try:
                # 提交订单
                order_id = self.broker.submit_order(order)
                logger.info(
                    f"买入委托已提交 - 股票: {stock_code}, "
                    f"价格: {price}, 数量: {volume}, "
                    f"订单号: {order_id}"
                )
                
                return {
                    'status': 'success',
                    'message': '买入委托已提交',
                    'order_id': order_id,
                    'stock_code': stock_code,
                    'price': price,
                    'volume': volume,
                    'amount': required_amount
                }
                
            except Exception as e:
                # 提交失败，解冻资金
                self.broker.account.unfreeze_cash(required_amount)
                raise TradeError(f"买入委托提交失败: {str(e)}")
                
        except Exception as e:
            logger.error(f"买入股票异常: {str(e)}")
            raise
            
    def sell_stock(self, stock_code: str, price: float, volume: int,
                   order_type: OrderType = OrderType.LIMIT,
                   strategy_id: Optional[int] = None) -> Dict:
        """
        卖出股票
        
        Args:
            stock_code: 股票代码
            price: 卖出价格
            volume: 卖出数量
            order_type: 订单类型
            strategy_id: 策略ID
            
        Returns:
            Dict: 交易结果
        """
        try:
            # 创建订单对象
            order = Order(
                stock_code=stock_code,
                side=OrderSide.SELL,
                order_type=order_type,
                volume=volume,
                price=price,
                strategy_id=strategy_id
            )
            
            # 检查订单有效性
            self._check_order(order)
            
            # 冻结持仓
            positions = self.broker.get_positions()
            if stock_code not in positions:
                raise PositionNotFoundError(f"没有持仓 - 股票: {stock_code}")
            position = positions[stock_code]
            if not position.freeze(volume):
                raise InvalidOrderError(
                    f"持仓冻结失败 - 需要: {volume}, "
                    f"可用: {position.available_volume}"
                )
                
            try:
                # 提交订单
                order_id = self.broker.submit_order(order)
                logger.info(
                    f"卖出委托已提交 - 股票: {stock_code}, "
                    f"价格: {price}, 数量: {volume}, "
                    f"订单号: {order_id}"
                )
                
                return {
                    'status': 'success',
                    'message': '卖出委托已提交',
                    'order_id': order_id,
                    'stock_code': stock_code,
                    'price': price,
                    'volume': volume,
                    'amount': price * volume
                }
                
            except Exception as e:
                # 提交失败，解冻持仓
                position.unfreeze(volume)
                raise TradeError(f"卖出委托提交失败: {str(e)}")
                
        except Exception as e:
            logger.error(f"卖出股票异常: {str(e)}")
            raise
            
    def cancel_order(self, order_id: str) -> Dict:
        """
        撤销订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            Dict: 撤销结果
        """
        try:
            # 获取订单状态
            status = self.broker.get_order_status(order_id)
            if status not in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL]:
                raise InvalidOrderError(f"订单状态不允许撤销: {status.value}")
                
            # 撤销订单
            if self.broker.cancel_order(order_id):
                logger.info(f"订单撤销成功 - 订单号: {order_id}")
                return {
                    'status': 'success',
                    'message': '订单撤销成功',
                    'order_id': order_id
                }
            else:
                raise TradeError(f"订单撤销失败 - 订单号: {order_id}")
                
        except Exception as e:
            logger.error(f"撤销订单异常: {str(e)}")
            raise
            
    def get_orders(self, start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> List[Order]:
        """
        获取订单列表
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[Order]: 订单列表
        """
        try:
            return self.broker.get_orders(start_time, end_time)
        except Exception as e:
            logger.error(f"获取订单列表异常: {str(e)}")
            raise
            
    def get_positions(self) -> Dict[str, Position]:
        """
        获取持仓列表
        
        Returns:
            Dict[str, Position]: 持仓字典
        """
        try:
            return self.broker.get_positions()
        except Exception as e:
            logger.error(f"获取持仓列表异常: {str(e)}")
            raise
            
    def get_account(self) -> Account:
        """
        获取账户信息
        
        Returns:
            Account: 账户信息
        """
        try:
            return self.broker.get_account()
        except Exception as e:
            logger.error(f"获取账户信息异常: {str(e)}")
            raise

    def start(self):
        """启动交易"""
        if self.is_running:
            logger.warning("交易程序已经在运行中")
            return False
            
        try:
            logger.info("正在启动交易程序...")
            # TODO: 实现启动逻辑
            self.is_running = True
            logger.info("交易程序启动成功")
            return True
        except Exception as e:
            logger.error(f"启动交易程序失败: {str(e)}")
            return False
            
    def stop(self):
        """停止交易"""
        if not self.is_running:
            logger.warning("交易程序已经停止")
            return False
            
        try:
            logger.info("正在停止交易程序...")
            # TODO: 实现停止逻辑
            self.is_running = False
            logger.info("交易程序停止成功")
            return True
        except Exception as e:
            logger.error(f"停止交易程序失败: {str(e)}")
            return False
            
    def add_strategy(self, strategy: Dict):
        """添加策略"""
        try:
            strategy_id = strategy.get('id')
            if not strategy_id:
                logger.error("策略ID不能为空")
                return False
                
            if strategy_id in self.strategies:
                logger.warning(f"策略 {strategy_id} 已存在")
                return False
                
            self.strategies[strategy_id] = strategy
            logger.info(f"添加策略成功: {strategy}")
            return True
        except Exception as e:
            logger.error(f"添加策略失败: {str(e)}")
            return False
            
    def remove_strategy(self, strategy_id: str):
        """移除策略"""
        try:
            if strategy_id not in self.strategies:
                logger.warning(f"策略 {strategy_id} 不存在")
                return False
                
            del self.strategies[strategy_id]
            logger.info(f"移除策略成功: {strategy_id}")
            return True
        except Exception as e:
            logger.error(f"移除策略失败: {str(e)}")
            return False
            
    def get_strategies(self) -> List[Dict]:
        """获取所有策略"""
        return list(self.strategies.values())
        
    def update_position(self, position: Dict):
        """更新持仓"""
        try:
            stock_code = position.get('stock_code')
            if not stock_code:
                logger.error("股票代码不能为空")
                return False
                
            self.positions[stock_code] = position
            logger.info(f"更新持仓成功: {position}")
            return True
        except Exception as e:
            logger.error(f"更新持仓失败: {str(e)}")
            return False
            
    def get_position(self, stock_code: str) -> Optional[Dict]:
        """获取指定股票的持仓"""
        return self.positions.get(stock_code)
        
    def is_trading_time(self) -> bool:
        """判断是否在交易时间"""
        try:
            # 检查是否是交易日
            if not self.broker.is_trading_day():
                return False
                
            # 获取当前时间
            now = datetime.now().time()
            
            # 上午交易时间：9:30 - 11:30
            morning_start = time(9, 30)
            morning_end = time(11, 30)
            
            # 下午交易时间：13:00 - 15:00
            afternoon_start = time(13, 0)
            afternoon_end = time(15, 0)
            
            # 判断是否在交易时间内
            return ((morning_start <= now <= morning_end) or 
                   (afternoon_start <= now <= afternoon_end))
                   
        except Exception as e:
            logger.error(f"检查交易时间异常: {str(e)}")
            return False
        
    def place_order(self, order: Order) -> bool:
        """
        下单
        
        Args:
            order: 订单对象
            
        Returns:
            bool: 是否成功
        """
        try:
            # 检查交易时间
            if not self.is_trading_time():
                logger.warning("非交易时间")
                return False
                
            # 检查订单有效性
            if not self._validate_order(order):
                return False
                
            # 提交订单
            return self.broker.place_order(order)
        except Exception as e:
            logger.error(f"下单失败: {str(e)}")
            return False
            
    def cancel_order(self, order_id: str) -> bool:
        """
        撤单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 是否成功
        """
        try:
            # 检查交易时间
            if not self.is_trading_time():
                logger.warning("非交易时间")
                return False
                
            # 撤销订单
            return self.broker.cancel_order(order_id)
        except Exception as e:
            logger.error(f"撤单失败: {str(e)}")
            return False
            
    def get_orders(self, is_active: bool = True) -> List[Order]:
        """
        获取订单列表
        
        Args:
            is_active: 是否只获取活跃订单
            
        Returns:
            List[Order]: 订单列表
        """
        return self.broker.get_orders(is_active)
        
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            
        Returns:
            Optional[Order]: 订单对象
        """
        return self.broker.get_order(order_id)
        
    def _validate_order(self, order: Order) -> bool:
        """
        验证订单
        
        Args:
            order: 订单对象
            
        Returns:
            bool: 是否有效
        """
        # 检查订单类型
        if order.order_type not in [OrderType.MARKET, OrderType.LIMIT]:
            logger.error("不支持的订单类型")
            return False
            
        # 检查委托价格
        if order.order_type == OrderType.LIMIT and order.price <= 0:
            logger.error("无效的委托价格")
            return False
            
        # 检查委托数量
        if order.volume <= 0 or order.volume % 100 != 0:
            logger.error("无效的委托数量")
            return False
            
        return True

    def connect(self) -> bool:
        """连接交易接口
        
        Returns:
            bool: 是否连接成功
        """
        try:
            if self.is_connected:
                return True
                
            if self.broker.connect():
                self.is_connected = True
                logger.info("连接交易接口成功")
                return True
            else:
                logger.error("连接交易接口失败")
                return False
                
        except Exception as e:
            logger.error(f"连接交易接口异常: {str(e)}")
            return False
            
    def disconnect(self) -> bool:
        """断开交易接口
        
        Returns:
            bool: 是否断开成功
        """
        try:
            if not self.is_connected:
                return True
                
            if self.broker.disconnect():
                self.is_connected = False
                logger.info("断开交易接口成功")
                return True
            else:
                logger.error("断开交易接口失败")
                return False
                
        except Exception as e:
            logger.error(f"断开交易接口异常: {str(e)}")
            return False
            
    def place_order(
        self,
        stock_code: str,
        action: str,
        volume: int,
        price: float,
        order_type: OrderType = OrderType.LIMIT,
        strategy_id: Optional[int] = None
    ) -> Optional[Dict]:
        """下单
        
        Args:
            stock_code: 股票代码
            action: 交易动作（buy/sell）
            volume: 数量
            price: 价格
            order_type: 订单类型
            strategy_id: 策略ID
            
        Returns:
            Dict: 订单信息
        """
        try:
            # 检查连接状态
            if not self.is_connected:
                logger.error("未连接到交易接口")
                return None
                
            # 检查交易时间
            if not self.is_trading_time():
                logger.error("非交易时间")
                return None
                
            # 检查参数
            if not self._validate_order_params(stock_code, action, volume, price):
                return None
                
            # 计算交易费用
            fees = self._calculate_fees(action, price, volume)
            
            # 检查资金是否足够
            if action == 'buy':
                account = self.broker.get_account()
                if not account:
                    logger.error("获取账户信息失败")
                    return None
                    
                total_amount = price * volume + fees
                if total_amount > account['available_funds']:
                    logger.error("可用资金不足")
                    return None
                    
            # 检查持仓是否足够
            if action == 'sell':
                position = self.broker.get_position(stock_code)
                if not position:
                    logger.error("获取持仓信息失败")
                    return None
                    
                if volume > position['total_volume']:
                    logger.error("可用持仓不足")
                    return None
                    
            # 提交订单
            order = self.broker.place_order(
                stock_code=stock_code,
                action=action,
                volume=volume,
                price=price,
                order_type=order_type.value
            )
            
            if order:
                # 添加策略ID
                if strategy_id:
                    order['strategy_id'] = strategy_id
                    
                logger.info(f"下单成功: {order}")
                return order
            else:
                logger.error("下单失败")
                return None
                
        except Exception as e:
            logger.error(f"下单异常: {str(e)}")
            return None
            
    def _validate_order_params(
        self,
        stock_code: str,
        action: str,
        volume: int,
        price: float
    ) -> bool:
        """验证订单参数
        
        Args:
            stock_code: 股票代码
            action: 交易动作
            volume: 数量
            price: 价格
            
        Returns:
            bool: 是否验证通过
        """
        # 验证股票代码
        if not stock_code or len(stock_code) != 6:
            logger.error("股票代码无效")
            return False
            
        # 验证交易动作
        if action not in ['buy', 'sell']:
            logger.error("交易动作无效")
            return False
            
        # 验证数量
        if not isinstance(volume, int) or volume <= 0 or volume % 100 != 0:
            logger.error("交易数量无效")
            return False
            
        # 验证价格
        if not isinstance(price, (int, float)) or price <= 0:
            logger.error("交易价格无效")
            return False
            
        return True
        
    def _calculate_fees(self, action: str, price: float, volume: int) -> float:
        """计算交易费用
        
        Args:
            action: 交易动作
            price: 价格
            volume: 数量
            
        Returns:
            float: 交易费用
        """
        # 计算交易金额
        amount = Decimal(str(price)) * Decimal(str(volume))
        
        # 佣金费率（万分之二点五）
        commission_rate = Decimal('0.00025')
        commission = amount * commission_rate
        
        # 最低佣金5元
        if commission < Decimal('5'):
            commission = Decimal('5')
            
        # 过户费（上海股票收取，深圳股票不收）
        transfer_fee = Decimal('0')
        if stock_code.startswith('6'):
            transfer_fee = amount * Decimal('0.00002')
            
        # 印花税（卖出收取）
        stamp_duty = Decimal('0')
        if action == 'sell':
            stamp_duty = amount * Decimal('0.001')
            
        # 合计费用
        total_fee = float(commission + transfer_fee + stamp_duty)
        
        return total_fee 