"""模拟交易接口"""
import logging
import requests
from datetime import datetime, time
from typing import Dict, List, Optional
from src.broker.base import BaseBroker
from src.models.account import Account
from src.models.order import Order, OrderStatus, OrderType, OrderSide
from src.models.position import Position
from src.config import config
from src.quote.quote import QuoteService

logger = logging.getLogger(__name__)

class SimulatedBroker(BaseBroker):
    """模拟交易接口"""
    def __init__(self):
        super().__init__()
        self.connected = False
        self.orders: Dict[str, Order] = {}
        self.api_base_url = config.get('api.base_url', 'http://127.0.0.1:5000/api/v1')
        self.api_timeout = config.get('api.timeout', 10)
        self.quote_service = QuoteService()
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        发送HTTP请求
        
        Args:
            method: 请求方法
            endpoint: 接口地址
            **kwargs: 请求参数
            
        Returns:
            Dict: 响应数据
        """
        try:
            url = f"{self.api_base_url}/{endpoint}"
            response = requests.request(
                method=method,
                url=url,
                timeout=self.api_timeout,
                **kwargs
            )
            response.raise_for_status()
            data = response.json()
            
            if data['code'] != 200:
                logger.error(f"API请求失败: {data['message']}")
                return None
                
            return data['data']
            
        except Exception as e:
            logger.error(f"API请求异常: {str(e)}")
            return None
            
    def connect(self) -> bool:
        """连接模拟交易接口"""
        try:
            logger.info("正在连接模拟交易接口...")
            # 获取账户资金信息
            data = self._make_request('GET', 'account/funds')
            if not data:
                logger.error("获取账户资金信息失败")
                return False
                
            # 创建模拟账户
            self.account = Account.create(
                account_id="SIM001",
                account_name="模拟账户",
                initial_cash=data['initial_assets']
            )
            
            # 更新账户资金信息
            self.account.available_funds = data['available_funds']
            self.account.frozen_funds = data['frozen_funds']
            self.account.total_assets = data['total_assets']
            self.account.total_profit = data['total_profit']
            self.account.total_profit_ratio = data['total_profit_ratio']
            
            # 获取持仓信息
            positions_data = self._make_request('GET', 'positions')
            if positions_data:
                for pos in positions_data:
                    position = Position.create(
                        stock_code=pos['stock_code'],
                        stock_name=pos['stock_name'],
                        price=pos['latest_price'],
                        position_ratio=pos.get('original_position_ratio', 0)  # 设置原始仓位比例
                    )
                    position.total_volume = pos['total_volume']
                    position.available_volume = pos['total_volume'] - pos.get('frozen_volume', 0)
                    position.frozen_volume = pos.get('frozen_volume', 0)
                    position.average_cost = pos.get('dynamic_cost', 0)
                    position.total_amount = pos.get('total_amount', 0)
                    position.market_value = pos.get('market_value', 0)
                    position.floating_profit = pos.get('floating_profit', 0)
                    position.floating_profit_ratio = pos.get('floating_profit_ratio', 0)
                    position.original_position_ratio = pos.get('original_position_ratio', 0)  # 设置原始仓位比例
                    self.account.add_position(position)
            
            self.connected = True
            logger.info("模拟交易接口连接成功")
            return True
        except Exception as e:
            logger.error(f"连接模拟交易接口失败: {str(e)}")
            return False
            
    def disconnect(self) -> bool:
        """断开模拟交易接口"""
        try:
            logger.info("正在断开模拟交易接口...")
            self.connected = False
            logger.info("模拟交易接口断开成功")
            return True
        except Exception as e:
            logger.error(f"断开模拟交易接口失败: {str(e)}")
            return False
            
    def is_connected(self) -> bool:
        """是否已连接"""
        return self.connected
        
    def get_account(self) -> Account:
        """获取账户信息"""
        try:
            # 获取账户资金信息
            data = self._make_request('GET', 'account/funds')
            if data:
                # 更新账户资金信息
                self.account.available_funds = data['available_funds']
                self.account.frozen_funds = data['frozen_funds']
                self.account.total_assets = data['total_assets']
                self.account.total_profit = data['total_profit']
                self.account.total_profit_ratio = data['total_profit_ratio']
                
                # 获取持仓信息
                positions_data = self._make_request('GET', 'positions')
                if positions_data:
                    # 清空旧的持仓信息
                    self.account.positions.clear()
                    # 添加新的持仓信息
                    for pos in positions_data:
                        position = Position.create(
                            stock_code=pos['stock_code'],
                            stock_name=pos['stock_name'],
                            price=pos['latest_price'],
                            position_ratio=pos.get('original_position_ratio', 0)  # 设置原始仓位比例
                        )
                        position.total_volume = pos['total_volume']
                        position.available_volume = pos['total_volume'] - pos.get('frozen_volume', 0)
                        position.frozen_volume = pos.get('frozen_volume', 0)
                        position.average_cost = pos.get('dynamic_cost', 0)
                        position.total_amount = pos.get('total_amount', 0)
                        position.market_value = pos.get('market_value', 0)
                        position.floating_profit = pos.get('floating_profit', 0)
                        position.floating_profit_ratio = pos.get('floating_profit_ratio', 0)
                        position.original_position_ratio = pos.get('original_position_ratio', 0)  # 设置原始仓位比例
                        self.account.add_position(position)
                
        except Exception as e:
            logger.error(f"获取账户资金信息失败: {str(e)}")
            
        return self.account
        
    def get_positions(self) -> List[Position]:
        """获取持仓列表"""
        return list(self.account.positions.values())
        
    def get_position(self, stock_code: str) -> Optional[Position]:
        """获取持仓信息"""
        return self.account.get_position(stock_code)
        
    def get_orders(self, is_active: bool = True) -> List[Order]:
        """获取订单列表"""
        if is_active:
            return [order for order in self.orders.values() if order.is_active]
        return list(self.orders.values())
        
    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单信息"""
        return self.orders.get(order_id)
        
    def place_order(self, order: Order) -> bool:
        """
        下单
        
        Args:
            order: 订单对象
            
        Returns:
            bool: 是否成功
        """
        try:
            # 检查订单有效性
            if not self._validate_order(order):
                return False
                
            # 买入时冻结资金
            if order.order_side == OrderSide.BUY:
                amount = order.price * order.volume
                # 计算手续费和印花税
                commission = amount * 0.00025  # 佣金费率万分之2.5
                tax = 0  # 买入不收印花税
                total_amount = amount + commission + tax
                
                if not self.account.freeze_funds(total_amount):
                    logger.error("冻结资金失败")
                    return False
                    
            # 卖出时冻结持仓
            elif order.order_side == OrderSide.SELL:
                position = self.get_position(order.stock_code)
                if not position:
                    logger.error(f"没有持仓: {order.stock_code}")
                    return False
                if not position.freeze(order.volume):
                    logger.error("冻结持仓失败")
                    return False
                    
            # 添加订单
            self.orders[order.order_id] = order
            
            # 模拟成交
            self._simulate_trade(order)
            
            return True
        except Exception as e:
            logger.error(f"下单失败: {str(e)}")
            return False
            
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        try:
            order = self.get_order(order_id)
            if not order:
                logger.warning(f"订单不存在: {order_id}")
                return False
                
            if not order.is_active:
                logger.warning(f"订单已完成: {order_id}")
                return False
                
            # 解冻资金或持仓
            if order.order_side == OrderSide.BUY:
                unfilled_amount = order.price * order.unfilled_volume
                self.account.unfreeze_cash(unfilled_amount)
            else:
                position = self.get_position(order.stock_code)
                if position:
                    position.unfreeze(order.unfilled_volume)
                    
            # 更新订单状态
            order.cancel()
            
            return True
        except Exception as e:
            logger.error(f"撤单失败: {str(e)}")
            return False
            
    def get_quote(self, stock_code: str) -> Dict:
        """获取行情"""
        try:
            # 使用 QuoteService 获取真实行情
            quote_data = self.quote_service.get_real_time_quote(stock_code)
            if quote_data:
                return quote_data
                
            logger.warning(f"获取股票 {stock_code} 行情失败，使用模拟数据")
            # 如果获取失败，返回模拟数据
            return {
                'code': stock_code,
                'price': 10.0,
                'high': 10.5,
                'low': 9.5,
                'open': 9.8,
                'close': 10.0,
                'volume': 100000,
                'amount': 1000000.0,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 行情异常: {str(e)}")
            return {
                'code': stock_code,
                'price': 10.0,
                'high': 10.5,
                'low': 9.5,
                'open': 9.8,
                'close': 10.0,
                'volume': 100000,
                'amount': 1000000.0,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
    def get_trading_calendar(self) -> List[str]:
        """获取交易日历"""
        # 模拟交易日历
        return ['2024-03-01', '2024-03-04', '2024-03-05', '2024-03-06', '2024-03-07', '2024-03-08']
        
    def get_trading_day(self) -> str:
        """获取交易日"""
        return datetime.now().strftime('%Y-%m-%d')
        
    def is_trading_day(self) -> bool:
        """是否是交易日"""
        # 从配置文件获取交易日
        trading_days = config.get('trading.trading_days', [1, 2, 3, 4, 5])
        return datetime.now().weekday() + 1 in trading_days
        
    def is_trading_time(self) -> bool:
        """是否是交易时间"""
        if not self.is_trading_day():
            logger.debug("当前不是交易日")
            return False
            
        current_time = datetime.now().time()
        
        # 从配置文件获取交易时间
        try:
            start_time = datetime.strptime(config.get('trading.trading_hours.start'), '%H:%M:%S').time()
            end_time = datetime.strptime(config.get('trading.trading_hours.end'), '%H:%M:%S').time()
            
            is_trading = start_time <= current_time <= end_time
            if not is_trading:
                logger.debug(f"当前时间 {current_time} 不在交易时间 {start_time} - {end_time} 内")
            
            return is_trading
            
        except Exception as e:
            logger.error(f"解析交易时间配置异常: {str(e)}")
            # 如果配置有问题，使用默认的交易时间
            morning_start = time(9, 30)
            morning_end = time(11, 30)
            afternoon_start = time(13, 0)
            afternoon_end = time(15, 0)
            
            return (morning_start <= current_time <= morning_end) or \
                   (afternoon_start <= current_time <= afternoon_end)
               
    def _validate_order(self, order: Order) -> bool:
        """
        验证订单
        
        Args:
            order: 订单对象
            
        Returns:
            bool: 是否有效
        """
        try:
            # 检查交易时间
            if not self.is_trading_time():
                order.reject("非交易时间")
                return False
                
            # 检查订单类型
            if order.order_type not in [OrderType.MARKET, OrderType.LIMIT]:
                order.reject("不支持的订单类型")
                return False
                
            # 检查委托价格
            if order.order_type == OrderType.LIMIT and order.price <= 0:
                order.reject("无效的委托价格")
                return False
                
            # 检查委托数量
            if order.volume <= 0:
                order.reject("无效的委托数量")
                return False
                
            # 买入数量必须是100的整数倍
            if order.order_side == OrderSide.BUY and order.volume % 100 != 0:
                order.reject("买入数量必须是100的整数倍")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"验证订单异常: {str(e)}")
            order.reject(f"验证订单异常: {str(e)}")
            return False
        
    def _simulate_trade(self, order: Order) -> None:
        """
        模拟成交
        
        Args:
            order: 订单对象
        """
        try:
            # 获取最新行情
            quote = self.get_quote(order.stock_code)
            current_price = quote['price']
            
            # 判断是否可以成交
            can_trade = False
            if order.order_type == OrderType.MARKET:
                can_trade = True
            elif order.order_type == OrderType.LIMIT:
                if order.order_side == OrderSide.BUY and order.price >= current_price:
                    can_trade = True
                elif order.order_side == OrderSide.SELL and order.price <= current_price:
                    can_trade = True
                    
            if not can_trade:
                logger.info(f"订单 {order.order_id} 当前无法成交")
                return
            
            # 计算成交金额和费用
            amount = current_price * order.volume
            commission = amount * 0.00025  # 佣金费率万分之2.5
            tax = amount * 0.001 if order.order_side == OrderSide.SELL else 0  # 卖出收取千分之一印花税
            total_amount = amount + commission + tax
            
            # 更新订单成交信息
            order.update_filled(
                filled_volume=order.volume,
                filled_price=current_price,
                commission=commission,
                tax=tax
            )
            
            # 更新账户和持仓
            if order.order_side == OrderSide.BUY:
                # 解冻资金
                self.account.unfreeze_funds(total_amount)
                
                # 更新或创建持仓
                position = self.get_position(order.stock_code)
                if position:
                    # 如果是首次买入，设置原始仓位比例
                    if position.total_volume == 0:
                        position.original_position_ratio = order.position_ratio
                    position.add(order.volume, current_price, order.position_ratio)
                else:
                    position = Position.create(
                        stock_code=order.stock_code,
                        stock_name=order.stock_name,
                        price=current_price,
                        position_ratio=order.position_ratio  # 设置原始仓位比例
                    )
                    position.add(order.volume, current_price, order.position_ratio)
                    self.account.add_position(position)
                    
            else:  # SELL
                # 解冻持仓
                position = self.get_position(order.stock_code)
                if position:
                    position.unfreeze(order.volume)
                    # 更新原始持仓比例：新的原始持仓比例 = 原始持仓比例 * (1 - 卖出数量/总数量)
                    new_ratio = position.original_position_ratio * (1 - order.volume / position.total_volume)
                    position.reduce(order.volume, current_price, new_ratio)
                    if position.is_empty:
                        self.account.remove_position(order.stock_code)
                    
                # 增加可用资金
                self.account.available_funds += total_amount
                
            # 创建执行记录并立即更新策略状态
            execution_status = "completed"  # 只要成交就标记为完成
            self._create_execution_record(order, execution_status)
            
            # 立即更新策略状态
            try:
                update_data = {
                    'execution_status': execution_status,
                    'is_active': False
                }
                self._make_request('PUT', f'strategies/{order.strategy_id}', json=update_data)
            except Exception as e:
                logger.error(f"更新策略状态异常: {str(e)}")
            
        except Exception as e:
            logger.error(f"模拟成交失败: {str(e)}")
            order.reject(str(e))
            
    def _create_execution_record(self, order: Order, execution_status: str) -> None:
        """
        创建执行记录
        
        Args:
            order: 订单对象
            execution_status: 执行状态
        """
        try:
            # 构造请求参数
            request_data = {
                "strategy_id": order.strategy_id,
                "stock_code": order.stock_code,
                "stock_name": order.stock_name,
                "action": "buy" if order.order_side == OrderSide.BUY else "sell",
                "execution_price": order.filled_price,
                "volume": order.filled_volume,
                "position_ratio": order.position_ratio,
                "original_position_ratio": order.position_ratio,
                "strategy_status": execution_status,
                "execution_result": "success" if order.is_success else "partial",
                "execution_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "remarks": order.status_message
            }
            
            # 发送创建执行记录请求
            logger.info(f"正在创建执行记录: {request_data}")
            response = self._make_request('POST', 'executions', json=request_data)
            
            if response:
                logger.info(f"创建执行记录成功: {response}")
            else:
                logger.error("创建执行记录失败: API返回空响应")
                
        except Exception as e:
            logger.error(f"创建执行记录异常: {str(e)}")
            # 记录详细的请求信息以便调试
            if hasattr(e, 'response'):
                logger.error(f"API响应状态码: {e.response.status_code}")
                logger.error(f"API响应内容: {e.response.text}") 