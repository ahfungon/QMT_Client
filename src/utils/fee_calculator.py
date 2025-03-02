"""费用计算器模块"""
import logging
from typing import Dict
from src.config import config

logger = logging.getLogger(__name__)

class TradingFeeCalculator:
    """交易费用计算器类"""
    def __init__(self):
        # 从配置文件加载费率
        self.commission_rate = config.get('trading.commission_rate', 0.00025)  # 佣金率，默认万分之2.5
        self.min_commission = config.get('trading.min_commission', 5)  # 最低佣金，默认5元
        self.stamp_duty_rate = config.get('trading.stamp_duty_rate', 0.001)  # 印花税率，默认千分之1
        self.transfer_fee_rate = config.get('trading.transfer_fee_rate', 0.00002)  # 过户费率，默认万分之0.2
        
    def calculate_buy_fee(self, price: float, volume: int) -> Dict[str, float]:
        """
        计算买入费用
        
        Args:
            price: 买入价格
            volume: 买入数量
            
        Returns:
            Dict[str, float]: 费用明细
        """
        try:
            # 计算交易金额
            amount = price * volume
            
            # 计算佣金
            commission = max(amount * self.commission_rate, self.min_commission)
            
            # 计算过户费
            transfer_fee = amount * self.transfer_fee_rate
            
            # 计算总费用
            total_fee = commission + transfer_fee
            
            return {
                'commission': round(commission, 2),
                'transfer_fee': round(transfer_fee, 2),
                'total_fee': round(total_fee, 2)
            }
        except Exception as e:
            logger.error(f"计算买入费用失败: {str(e)}")
            return {
                'commission': 0,
                'transfer_fee': 0,
                'total_fee': 0
            }
            
    def calculate_sell_fee(self, price: float, volume: int) -> Dict[str, float]:
        """
        计算卖出费用
        
        Args:
            price: 卖出价格
            volume: 卖出数量
            
        Returns:
            Dict[str, float]: 费用明细
        """
        try:
            # 计算交易金额
            amount = price * volume
            
            # 计算佣金
            commission = max(amount * self.commission_rate, self.min_commission)
            
            # 计算印花税
            stamp_duty = amount * self.stamp_duty_rate
            
            # 计算过户费
            transfer_fee = amount * self.transfer_fee_rate
            
            # 计算总费用
            total_fee = commission + stamp_duty + transfer_fee
            
            return {
                'commission': round(commission, 2),
                'stamp_duty': round(stamp_duty, 2),
                'transfer_fee': round(transfer_fee, 2),
                'total_fee': round(total_fee, 2)
            }
        except Exception as e:
            logger.error(f"计算卖出费用失败: {str(e)}")
            return {
                'commission': 0,
                'stamp_duty': 0,
                'transfer_fee': 0,
                'total_fee': 0
            }
            
    def calculate_total_fee(self, price: float, volume: int, is_buy: bool = True) -> float:
        """
        计算总费用
        
        Args:
            price: 交易价格
            volume: 交易数量
            is_buy: 是否买入
            
        Returns:
            float: 总费用
        """
        try:
            if is_buy:
                return self.calculate_buy_fee(price, volume)['total_fee']
            else:
                return self.calculate_sell_fee(price, volume)['total_fee']
        except Exception as e:
            logger.error(f"计算总费用失败: {str(e)}")
            return 0 