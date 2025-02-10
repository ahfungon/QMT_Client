from datetime import datetime, timedelta
from loguru import logger
from ..api.qmt_client import QMTClient
from .trade_service import TradeService

class StrategyService:
    """策略服务"""
    
    def __init__(self):
        self.qmt_client = QMTClient()
        self.trade_service = TradeService()

    async def execute_strategies(self):
        """执行策略"""
        try:
            # 获取策略列表
            strategies = await self.qmt_client.get_strategies()
            
            for strategy in strategies:
                await self._execute_single_strategy(strategy)
                
        except Exception as e:
            logger.error(f"执行策略失败: {str(e)}")

    async def _execute_single_strategy(self, strategy: dict):
        """执行单个策略"""
        try:
            code = strategy["stock_code"]
            action = strategy["action"]
            price = (strategy["price_min"] + strategy["price_max"]) / 2
            quantity = 100  # 默认交易100股
            
            if action == "buy":
                success, message, traded_quantity = self.trade_service.buy_stock(
                    code=code,
                    price=price,
                    quantity=quantity
                )
            elif action == "sell":
                success, message, traded_quantity = self.trade_service.sell_stock(
                    code=code,
                    price=price,
                    quantity=quantity
                )
            
            logger.info(f"策略执行结果: {message}")
            
        except Exception as e:
            logger.error(f"执行策略 {strategy['id']} 失败: {str(e)}") 