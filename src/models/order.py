"""订单数据模型"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"  # 待执行
    SUBMITTING = "submitting"  # 提交中
    SUBMITTED = "submitted"  # 已提交
    PARTIAL_FILLED = "partial_filled"  # 部分成交
    FILLED = "filled"  # 全部成交
    CANCELLING = "cancelling"  # 撤单中
    CANCELLED = "cancelled"  # 已撤单
    REJECTED = "rejected"  # 已拒绝
    EXPIRED = "expired"  # 已过期
    UNKNOWN = "unknown"  # 未知状态

class OrderType(Enum):
    """订单类型枚举"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"  # 限价单
    
class OrderSide(Enum):
    """订单方向枚举"""
    BUY = "buy"  # 买入
    SELL = "sell"  # 卖出

@dataclass
class Order:
    """订单数据类"""
    order_id: str  # 订单ID
    strategy_id: str  # 策略ID
    stock_code: str  # 股票代码
    stock_name: str  # 股票名称
    order_type: OrderType  # 订单类型
    order_side: OrderSide  # 订单方向
    price: float  # 委托价格
    volume: int  # 委托数量
    filled_volume: int  # 成交数量
    filled_amount: float  # 成交金额
    filled_commission: float  # 成交手续费
    filled_tax: float  # 成交税费
    status: OrderStatus  # 订单状态
    status_message: str  # 状态信息
    position_ratio: float  # 仓位比例
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间
    
    @property
    def is_active(self) -> bool:
        """是否活跃订单"""
        return self.status in [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIAL_FILLED
        ]
        
    @property
    def is_final(self) -> bool:
        """是否最终状态"""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        ]
        
    @property
    def is_success(self) -> bool:
        """是否成交成功"""
        return self.status == OrderStatus.FILLED
        
    @property
    def unfilled_volume(self) -> int:
        """未成交数量"""
        return self.volume - self.filled_volume
        
    @property
    def filled_price(self) -> float:
        """成交均价"""
        if self.filled_volume > 0:
            return self.filled_amount / self.filled_volume
        return 0.0
        
    def update_filled(self, filled_volume: int, filled_price: float,
                     commission: float = 0, tax: float = 0) -> None:
        """
        更新成交信息
        
        Args:
            filled_volume: 成交数量
            filled_price: 成交价格
            commission: 手续费
            tax: 税费
        """
        if filled_volume <= 0:
            return
            
        self.filled_volume += filled_volume
        filled_amount = filled_volume * filled_price
        self.filled_amount += filled_amount
        self.filled_commission += commission
        self.filled_tax += tax
        
        if self.filled_volume >= self.volume:
            self.status = OrderStatus.FILLED
        elif self.filled_volume > 0:
            self.status = OrderStatus.PARTIAL_FILLED
            
        self.updated_at = datetime.now()
        
    def cancel(self) -> None:
        """取消订单"""
        if self.is_final:
            return
            
        self.status = OrderStatus.CANCELLED
        self.status_message = "已撤单"
        self.updated_at = datetime.now()
        
    def reject(self, message: str) -> None:
        """
        拒绝订单
        
        Args:
            message: 拒绝原因
        """
        if self.is_final:
            return
            
        self.status = OrderStatus.REJECTED
        self.status_message = message
        self.updated_at = datetime.now()
        
    @classmethod
    def create_market_order(cls, strategy_id: str, stock_code: str, stock_name: str,
                          side: OrderSide, volume: int, position_ratio: float = 0.0) -> 'Order':
        """
        创建市价单
        
        Args:
            strategy_id: 策略ID
            stock_code: 股票代码
            stock_name: 股票名称
            side: 交易方向
            volume: 委托数量
            position_ratio: 仓位比例
            
        Returns:
            Order: 订单对象
        """
        now = datetime.now()
        return cls(
            order_id=f"{strategy_id}_{now.strftime('%Y%m%d%H%M%S')}",
            strategy_id=strategy_id,
            stock_code=stock_code,
            stock_name=stock_name,
            order_type=OrderType.MARKET,
            order_side=side,
            price=0.0,
            volume=volume,
            filled_volume=0,
            filled_amount=0.0,
            filled_commission=0.0,
            filled_tax=0.0,
            status=OrderStatus.PENDING,
            status_message="待执行",
            position_ratio=position_ratio,
            created_at=now,
            updated_at=now
        )
        
    @classmethod
    def create_limit_order(cls, strategy_id: str, stock_code: str, stock_name: str,
                         side: OrderSide, price: float, volume: int, position_ratio: float = 0.0) -> 'Order':
        """
        创建限价单
        
        Args:
            strategy_id: 策略ID
            stock_code: 股票代码
            stock_name: 股票名称
            side: 交易方向
            price: 委托价格
            volume: 委托数量
            position_ratio: 仓位比例
            
        Returns:
            Order: 订单对象
        """
        now = datetime.now()
        return cls(
            order_id=f"{strategy_id}_{now.strftime('%Y%m%d%H%M%S')}",
            strategy_id=strategy_id,
            stock_code=stock_code,
            stock_name=stock_name,
            order_type=OrderType.LIMIT,
            order_side=side,
            price=price,
            volume=volume,
            filled_volume=0,
            filled_amount=0.0,
            filled_commission=0.0,
            filled_tax=0.0,
            status=OrderStatus.PENDING,
            status_message="待执行",
            position_ratio=position_ratio,
            created_at=now,
            updated_at=now
        ) 