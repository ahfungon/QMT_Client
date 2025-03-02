"""券商接口基类"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
from src.models.order import Order, OrderStatus, OrderSide, OrderType
from src.models.account import Account
from src.models.position import Position

class BaseBroker(ABC):
    """券商接口基类"""
    
    def __init__(self):
        self.account: Optional[Account] = None
        
    @abstractmethod
    def connect(self) -> bool:
        """
        连接券商
        
        Returns:
            bool: 是否成功
        """
        pass
        
    @abstractmethod
    def disconnect(self) -> bool:
        """
        断开连接
        
        Returns:
            bool: 是否成功
        """
        pass
        
    @abstractmethod
    def is_connected(self) -> bool:
        """
        是否已连接
        
        Returns:
            bool: 是否已连接
        """
        pass
        
    @abstractmethod
    def get_account(self) -> Account:
        """
        获取账户信息
        
        Returns:
            Account: 账户对象
        """
        pass
        
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        获取持仓列表
        
        Returns:
            List[Position]: 持仓列表
        """
        pass
        
    @abstractmethod
    def get_position(self, stock_code: str) -> Optional[Position]:
        """
        获取持仓信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Optional[Position]: 持仓对象
        """
        pass
        
    @abstractmethod
    def get_orders(self, is_active: bool = True) -> List[Order]:
        """
        获取订单列表
        
        Args:
            is_active: 是否只获取活跃订单
            
        Returns:
            List[Order]: 订单列表
        """
        pass
        
    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            
        Returns:
            Optional[Order]: 订单对象
        """
        pass
        
    @abstractmethod
    def place_order(self, order: Order) -> bool:
        """
        下单
        
        Args:
            order: 订单对象
            
        Returns:
            bool: 是否成功
        """
        pass
        
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        撤单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 是否成功
        """
        pass
        
    @abstractmethod
    def get_quote(self, stock_code: str) -> Dict:
        """
        获取行情
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Dict: 行情数据
        """
        pass
        
    @abstractmethod
    def get_trading_calendar(self) -> List[str]:
        """
        获取交易日历
        
        Returns:
            List[str]: 交易日列表
        """
        pass
        
    @abstractmethod
    def is_trading_day(self) -> bool:
        """
        是否是交易日
        
        Returns:
            bool: 是否是交易日
        """
        pass
        
    @abstractmethod
    def is_trading_time(self) -> bool:
        """
        是否是交易时间
        
        Returns:
            bool: 是否是交易时间
        """
        pass
        
    @abstractmethod
    def get_trading_day(self) -> str:
        """
        获取交易日
        
        Returns:
            str: 交易日（YYYY-MM-DD）
            
        Raises:
            BrokerError: 查询失败
        """
        pass
        
class BrokerError(Exception):
    """券商接口异常"""
    pass
    
class OrderSubmitError(BrokerError):
    """订单提交异常"""
    pass
    
class OrderCancelError(BrokerError):
    """订单撤销异常"""
    pass
    
class QueryError(BrokerError):
    """查询异常"""
    pass
    
class LoginError(BrokerError):
    """登录异常"""
    pass
    
class ConnectionError(BrokerError):
    """连接异常"""
    pass 