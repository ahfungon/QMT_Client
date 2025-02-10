from typing import Dict, Tuple, Optional
import json
from pathlib import Path
from datetime import datetime
from loguru import logger

class TradeService:
    """交易服务"""
    
    def __init__(self, position_file: str = "data/positions.json"):
        """
        初始化交易服务
        
        Args:
            position_file: 持仓文件路径
        """
        self.position_file = Path(position_file)
        self.position_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 如果持仓文件不存在，创建空文件
        if not self.position_file.exists():
            self._save_positions({})

    def buy_stock(self, code: str, price: float, quantity: int) -> Tuple[bool, str, int]:
        """
        买入股票
        
        Args:
            code: 股票代码
            price: 买入价格
            quantity: 买入数量
            
        Returns:
            Tuple[bool, str, int]: (是否成功, 消息, 成交数量)
        """
        try:
            logger.info(f"准备买入: 股票{code}, 价格{price}, 数量{quantity}")
            
            # 模拟交易执行
            success = True
            message = "买入成功"
            traded_quantity = quantity
            
            # 更新持仓
            if success:
                self._update_position(code, price, traded_quantity, "buy")
                logger.info(f"买入成功: 股票{code}, 成交数量{traded_quantity}")
            
            return success, message, traded_quantity
            
        except Exception as e:
            logger.error(f"买入失败: {str(e)}")
            return False, f"买入失败: {str(e)}", 0

    def sell_stock(self, code: str, price: float, quantity: int) -> Tuple[bool, str, int]:
        """
        卖出股票
        
        Args:
            code: 股票代码
            price: 卖出价格
            quantity: 卖出数量
            
        Returns:
            Tuple[bool, str, int]: (是否成功, 消息, 成交数量)
        """
        try:
            logger.info(f"准备卖出: 股票{code}, 价格{price}, 数量{quantity}")
            
            # 检查持仓是否足够
            positions = self._load_positions()
            if code not in positions or positions[code]["quantity"] < quantity:
                return False, "持仓不足", 0
            
            # 模拟交易执行
            success = True
            message = "卖出成功"
            traded_quantity = quantity
            
            # 更新持仓
            if success:
                self._update_position(code, price, traded_quantity, "sell")
                logger.info(f"卖出成功: 股票{code}, 成交数量{traded_quantity}")
            
            return success, message, traded_quantity
            
        except Exception as e:
            logger.error(f"卖出失败: {str(e)}")
            return False, f"卖出失败: {str(e)}", 0

    def _update_position(self, code: str, price: float, quantity: int, action: str):
        """
        更新持仓信息
        
        Args:
            code: 股票代码
            price: 交易价格
            quantity: 交易数量
            action: 交易动作（buy/sell）
        """
        positions = self._load_positions()
        
        if action == "buy":
            if code not in positions:
                positions[code] = {
                    "quantity": quantity,
                    "average_price": price,
                    "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                old_quantity = positions[code]["quantity"]
                old_price = positions[code]["average_price"]
                new_quantity = old_quantity + quantity
                new_price = (old_quantity * old_price + quantity * price) / new_quantity
                
                positions[code].update({
                    "quantity": new_quantity,
                    "average_price": new_price,
                    "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
        
        elif action == "sell":
            current_quantity = positions[code]["quantity"]
            new_quantity = current_quantity - quantity
            
            if new_quantity == 0:
                del positions[code]
            else:
                positions[code].update({
                    "quantity": new_quantity,
                    "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
        self._save_positions(positions)

    def _load_positions(self) -> Dict:
        """加载持仓数据"""
        try:
            with open(self.position_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载持仓数据失败: {str(e)}")
            return {}

    def _save_positions(self, positions: Dict):
        """保存持仓数据"""
        try:
            with open(self.position_file, 'w', encoding='utf-8') as f:
                json.dump(positions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存持仓数据失败: {str(e)}")
            raise 