"""持仓数据模型"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Position:
    """持仓数据类"""
    stock_code: str  # 股票代码
    stock_name: str  # 股票名称
    total_volume: int  # 总持仓量
    available_volume: int  # 可用持仓量
    frozen_volume: int  # 冻结持仓量
    average_cost: float  # 平均成本
    total_amount: float  # 总金额
    latest_price: float  # 最新价格
    market_value: float  # 市值
    floating_profit: float  # 浮动盈亏
    floating_profit_ratio: float  # 浮动盈亏比例
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间
    original_position_ratio: float = 0.0  # 原始仓位比例
    
    @property
    def is_empty(self) -> bool:
        """是否为空仓"""
        return self.total_volume == 0
        
    @property
    def has_frozen(self) -> bool:
        """是否有冻结持仓"""
        return self.frozen_volume > 0
        
    @property
    def is_profitable(self) -> bool:
        """是否盈利"""
        return self.floating_profit > 0
        
    def update_price(self, latest_price: float) -> None:
        """
        更新最新价格
        
        Args:
            latest_price: 最新价格
        """
        self.latest_price = latest_price
        self.market_value = self.total_volume * latest_price
        self.floating_profit = self.market_value - self.total_amount
        if self.total_amount > 0:
            self.floating_profit_ratio = self.floating_profit / self.total_amount
        else:
            self.floating_profit_ratio = 0
        self.updated_at = datetime.now()
        
    def freeze(self, volume: int) -> bool:
        """
        冻结持仓
        
        Args:
            volume: 冻结数量
            
        Returns:
            bool: 是否成功
        """
        if volume <= 0:
            return False
            
        if volume > self.available_volume:
            return False
            
        self.available_volume -= volume
        self.frozen_volume += volume
        self.updated_at = datetime.now()
        return True
        
    def unfreeze(self, volume: int) -> bool:
        """
        解冻持仓
        
        Args:
            volume: 解冻数量
            
        Returns:
            bool: 是否成功
        """
        if volume <= 0:
            return False
            
        if volume > self.frozen_volume:
            return False
            
        self.available_volume += volume
        self.frozen_volume -= volume
        self.updated_at = datetime.now()
        return True
        
    def add(self, volume: int, price: float, position_ratio: float = 0.0) -> None:
        """
        增加持仓
        
        Args:
            volume: 增加数量
            price: 成交价格
            position_ratio: 仓位比例
        """
        amount = volume * price
        new_total_amount = self.total_amount + amount
        self.average_cost = new_total_amount / (self.total_volume + volume)
        self.total_volume += volume
        self.available_volume += volume
        self.total_amount = new_total_amount
        self.market_value = self.total_volume * self.latest_price
        self.floating_profit = self.market_value - self.total_amount
        if self.total_amount > 0:
            self.floating_profit_ratio = self.floating_profit / self.total_amount
        else:
            self.floating_profit_ratio = 0
            
        # 更新原始仓位比例
        if position_ratio > 0:
            self.original_position_ratio += position_ratio
            
        self.updated_at = datetime.now()
        
    def reduce(self, volume: int, price: float, position_ratio: float = 0.0) -> None:
        """
        减少持仓
        
        Args:
            volume: 减少数量
            price: 成交价格
            position_ratio: 减少的仓位比例
        """
        if volume > self.available_volume:
            return
            
        self.total_volume -= volume
        self.available_volume -= volume
        if self.total_volume > 0:
            self.total_amount = self.total_volume * self.average_cost
            self.market_value = self.total_volume * self.latest_price
            self.floating_profit = self.market_value - self.total_amount
            self.floating_profit_ratio = self.floating_profit / self.total_amount
            
            # 更新原始仓位比例
            if position_ratio > 0:
                self.original_position_ratio -= position_ratio
        else:
            self.total_amount = 0
            self.market_value = 0
            self.floating_profit = 0
            self.floating_profit_ratio = 0
            self.original_position_ratio = 0  # 清仓时清零原始仓位比例
            
        self.updated_at = datetime.now()
        
    @classmethod
    def create(cls, stock_code: str, stock_name: str, price: float, position_ratio: float = 0.0) -> 'Position':
        """
        创建空持仓
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            price: 最新价格
            position_ratio: 初始仓位比例
            
        Returns:
            Position: 持仓对象
        """
        now = datetime.now()
        return cls(
            stock_code=stock_code,
            stock_name=stock_name,
            total_volume=0,
            available_volume=0,
            frozen_volume=0,
            average_cost=0,
            total_amount=0,
            latest_price=price,
            market_value=0,
            floating_profit=0,
            floating_profit_ratio=0,
            created_at=now,
            updated_at=now,
            original_position_ratio=position_ratio
        ) 