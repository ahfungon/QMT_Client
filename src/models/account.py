"""账户数据模型"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from src.models.position import Position

@dataclass
class Account:
    """账户数据类"""
    account_id: str  # 账户ID
    account_name: str  # 账户名称
    initial_assets: float  # 初始资金
    total_assets: float  # 总资产
    available_funds: float  # 可用资金
    frozen_funds: float  # 冻结资金
    market_value: float  # 持仓市值
    total_profit: float  # 总盈亏
    total_profit_ratio: float  # 总盈亏比例
    positions: Dict[str, Position]  # 持仓字典
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间
    
    @property
    def position_count(self) -> int:
        """持仓数量"""
        return len(self.positions)
        
    @property
    def has_position(self) -> bool:
        """是否有持仓"""
        return self.position_count > 0
        
    @property
    def is_profitable(self) -> bool:
        """是否盈利"""
        return self.total_profit > 0
        
    def get_position(self, stock_code: str) -> Optional[Position]:
        """
        获取持仓
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Optional[Position]: 持仓对象
        """
        return self.positions.get(stock_code)
        
    def add_position(self, position: Position) -> None:
        """
        添加持仓
        
        Args:
            position: 持仓对象
        """
        self.positions[position.stock_code] = position
        self._update_account_info()
        
    def remove_position(self, stock_code: str) -> None:
        """
        移除持仓
        
        Args:
            stock_code: 股票代码
        """
        if stock_code in self.positions:
            del self.positions[stock_code]
            self._update_account_info()
            
    def freeze_funds(self, amount: float) -> bool:
        """
        冻结资金
        
        Args:
            amount: 冻结金额
            
        Returns:
            bool: 是否成功
        """
        if amount <= 0:
            return False
            
        if amount > self.available_funds:
            return False
            
        self.available_funds -= amount
        self.frozen_funds += amount
        self.updated_at = datetime.now()
        return True
        
    def unfreeze_funds(self, amount: float) -> bool:
        """
        解冻资金
        
        Args:
            amount: 解冻金额
            
        Returns:
            bool: 是否成功
        """
        if amount <= 0:
            return False
            
        if amount > self.frozen_funds:
            return False
            
        self.available_funds += amount
        self.frozen_funds -= amount
        self.updated_at = datetime.now()
        return True
        
    def freeze_cash(self, amount: float) -> bool:
        """
        冻结资金（freeze_funds的别名）
        
        Args:
            amount: 冻结金额
            
        Returns:
            bool: 是否成功
        """
        return self.freeze_funds(amount)
        
    def unfreeze_cash(self, amount: float) -> bool:
        """
        解冻资金（unfreeze_funds的别名）
        
        Args:
            amount: 解冻金额
            
        Returns:
            bool: 是否成功
        """
        return self.unfreeze_funds(amount)
        
    def update_position_price(self, stock_code: str, price: float) -> None:
        """
        更新持仓价格
        
        Args:
            stock_code: 股票代码
            price: 最新价格
        """
        position = self.get_position(stock_code)
        if position:
            position.update_price(price)
            self._update_account_info()
            
    def _update_account_info(self) -> None:
        """更新账户信息"""
        # 计算持仓市值
        self.market_value = sum(p.market_value for p in self.positions.values())
        
        # 计算总资产
        self.total_assets = self.available_funds + self.frozen_funds + self.market_value
        
        # 计算总盈亏
        total_cost = sum(p.total_amount for p in self.positions.values())
        self.total_profit = self.market_value - total_cost
        
        # 计算总盈亏比例
        if total_cost > 0:
            self.total_profit_ratio = self.total_profit / total_cost * 100  # 转换为百分比
        else:
            self.total_profit_ratio = 0
            
        self.updated_at = datetime.now()
        
    @classmethod
    def create(cls, account_id: str, account_name: str, initial_cash: float) -> 'Account':
        """
        创建账户
        
        Args:
            account_id: 账户ID
            account_name: 账户名称
            initial_cash: 初始资金
            
        Returns:
            Account: 账户对象
        """
        now = datetime.now()
        return cls(
            account_id=account_id,
            account_name=account_name,
            initial_assets=initial_cash,
            total_assets=initial_cash,
            available_funds=initial_cash,
            frozen_funds=0.0,
            market_value=0.0,
            total_profit=0.0,
            total_profit_ratio=0.0,
            positions={},
            created_at=now,
            updated_at=now
        ) 