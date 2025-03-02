"""订单管理模块"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import threading
import time
import logging
from src.models.order import Order, OrderStatus
from src.broker.base import BaseBroker
from src.config import config

logger = logging.getLogger(__name__)

class OrderManager:
    """订单管理器"""
    
    def __init__(self, broker: BaseBroker):
        """
        初始化订单管理器
        
        Args:
            broker: 券商接口对象
        """
        self.broker = broker
        self.orders: Dict[str, Order] = {}  # 订单字典
        self.pending_orders: Dict[str, Order] = {}  # 待成交订单
        
        # 启动订单监控线程
        self._stop_flag = False
        self._monitor_thread = threading.Thread(target=self._monitor_orders)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
    def add_order(self, order_id: str, order: Order) -> None:
        """
        添加订单
        
        Args:
            order_id: 订单ID
            order: 订单对象
        """
        self.orders[order_id] = order
        if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL]:
            self.pending_orders[order_id] = order
            
    def remove_order(self, order_id: str) -> None:
        """
        移除订单
        
        Args:
            order_id: 订单ID
        """
        if order_id in self.orders:
            del self.orders[order_id]
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]
            
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        获取订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            Optional[Order]: 订单对象
        """
        return self.orders.get(order_id)
        
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
        orders = list(self.orders.values())
        
        # 按时间过滤
        if start_time:
            orders = [o for o in orders if o.created_at >= start_time]
        if end_time:
            orders = [o for o in orders if o.created_at <= end_time]
            
        return orders
        
    def get_pending_orders(self) -> List[Order]:
        """
        获取待成交订单列表
        
        Returns:
            List[Order]: 待成交订单列表
        """
        return list(self.pending_orders.values())
        
    def update_order_status(self, order_id: str, status: OrderStatus) -> None:
        """
        更新订单状态
        
        Args:
            order_id: 订单ID
            status: 新状态
        """
        if order_id in self.orders:
            order = self.orders[order_id]
            old_status = order.status
            order.status = status
            
            # 更新待成交订单
            if status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                if order_id in self.pending_orders:
                    del self.pending_orders[order_id]
            elif status in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL]:
                self.pending_orders[order_id] = order
                
            logger.info(
                f"订单状态更新 - 订单号: {order_id}, "
                f"原状态: {old_status.value}, "
                f"新状态: {status.value}"
            )
            
    def _monitor_orders(self) -> None:
        """订单监控线程"""
        while not self._stop_flag:
            try:
                # 获取订单超时时间
                timeout = config.get('trading.order.timeout', 120)
                auto_cancel = config.get('trading.order.auto_cancel', True)
                
                # 检查待成交订单
                for order_id, order in list(self.pending_orders.items()):
                    # 检查订单状态
                    try:
                        status = self.broker.get_order_status(order_id)
                        if status != order.status:
                            self.update_order_status(order_id, status)
                    except Exception as e:
                        logger.error(f"获取订单状态异常 - 订单号: {order_id}, 错误: {str(e)}")
                        continue
                        
                    # 检查是否超时
                    if auto_cancel and order.is_timeout():
                        logger.warning(f"订单超时 - 订单号: {order_id}, 已超过 {timeout} 秒")
                        try:
                            if self.broker.cancel_order(order_id):
                                logger.info(f"超时订单已撤销 - 订单号: {order_id}")
                            else:
                                logger.error(f"超时订单撤销失败 - 订单号: {order_id}")
                        except Exception as e:
                            logger.error(f"撤销超时订单异常 - 订单号: {order_id}, 错误: {str(e)}")
                            
            except Exception as e:
                logger.error(f"订单监控异常: {str(e)}")
                
            # 休眠一段时间
            time.sleep(1)
            
    def stop(self) -> None:
        """停止订单监控"""
        self._stop_flag = True
        if self._monitor_thread.is_alive():
            self._monitor_thread.join() 