"""策略管理模块"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import threading
import time
import logging
import requests
from src.models.order import Order, OrderType, OrderSide
from src.core.trader import Trader
from src.config import config

logger = logging.getLogger(__name__)

class StrategyError(Exception):
    """策略异常基类"""
    pass

class StrategyNotFoundError(StrategyError):
    """策略不存在异常"""
    pass

class InvalidStrategyError(StrategyError):
    """无效策略异常"""
    pass

class StrategyManager:
    """策略管理器"""
    
    def __init__(self, trader: Trader):
        """
        初始化策略管理器
        
        Args:
            trader: 交易核心对象
        """
        self.trader = trader
        self.strategies = {}
        self.is_running = False
        self.api_base_url = config.get('api.base_url', 'http://127.0.0.1:5000/api/v1')
        self.api_timeout = config.get('api.timeout', 10)
        
        # 启动策略监控线程
        self._stop_flag = False
        self._monitor_thread = threading.Thread(target=self._monitor_strategies)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        logger.info(f"初始化策略管理器，API地址: {self.api_base_url}")
        
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
                
            logger.debug(f"API响应数据: {data}")
            return data['data']
            
        except Exception as e:
            logger.error(f"API请求异常: {str(e)}")
            return None
            
    def get_strategies(self) -> List[Dict]:
        """获取所有策略"""
        try:
            # 调用策略列表接口
            data = self._make_request('GET', 'strategies')
            if data:
                self.strategies = {str(strategy['id']): strategy for strategy in data}
                return list(self.strategies.values())
            return []
        except Exception as e:
            logger.error(f"获取策略列表失败: {str(e)}")
            return []
            
    def get_account_info(self) -> Dict:
        """获取账户资金信息"""
        try:
            # 调用账户资金接口
            data = self._make_request('GET', 'account/funds')
            if data:
                return {
                    'total_assets': data['total_assets'],          # 资产总值
                    'available_funds': data['available_funds'],    # 可用资金
                    'frozen_funds': data['frozen_funds'],          # 冻结资金
                    'total_profit': data['total_profit'],          # 总盈亏
                    'total_profit_ratio': data['total_profit_ratio'],  # 总收益率
                    'initial_assets': data['initial_assets'],      # 初始资金
                    'updated_at': data['updated_at']              # 更新时间
                }
            return None
        except Exception as e:
            logger.error(f"获取账户资金信息失败: {str(e)}")
            return None
            
    def get_positions(self) -> List[Dict]:
        """获取持仓列表"""
        try:
            # 调用持仓列表接口
            data = self._make_request('GET', 'positions')
            if data:
                return data
            return []
        except Exception as e:
            logger.error(f"获取持仓列表失败: {str(e)}")
            return []
            
    def analyze_strategy(self, strategy_text: str) -> Dict:
        """
        分析策略文本
        
        Args:
            strategy_text: 策略文本
            
        Returns:
            Dict: 分析结果
        """
        try:
            # 调用策略分析接口
            data = self._make_request(
                'POST',
                'analyze_strategy',
                json={'strategy_text': strategy_text}
            )
            if data:
                return {
                    'stock_name': data['stock_name'],
                    'stock_code': data['stock_code'],
                    'action': data['action'],
                    'position_ratio': data.get('suggested_position', 0),
                    'analysis_result': data.get('analysis_result', ''),
                    'confidence': data.get('confidence', 0),
                    'market_analysis': data.get('market_analysis', {})
                }
            return None
        except Exception as e:
            logger.error(f"分析策略失败: {str(e)}")
            return None
            
    def create_strategy(self, strategy: Dict) -> Dict:
        """
        创建策略
        
        Args:
            strategy: 策略信息
            
        Returns:
            Dict: 创建结果
        """
        try:
            # 调用创建策略接口
            data = self._make_request(
                'POST',
                'strategies',
                json=strategy
            )
            if data:
                strategy_id = str(data['id'])
                self.strategies[strategy_id] = data
                return data
            return None
        except Exception as e:
            logger.error(f"创建策略失败: {str(e)}")
            return None
            
    def update_strategy(self, strategy_id: str, strategy: Dict) -> Dict:
        """
        更新策略
        
        Args:
            strategy_id: 策略ID
            strategy: 策略信息
            
        Returns:
            Dict: 更新结果
        """
        try:
            # 调用更新策略接口
            data = self._make_request(
                'PUT',
                f'strategies/{strategy_id}',
                json=strategy
            )
            if data:
                self.strategies[strategy_id] = data
                return data
            return None
        except Exception as e:
            logger.error(f"更新策略失败: {str(e)}")
            return None
            
    def check_strategy_exists(self, stock_code: str, action: str) -> Dict:
        """
        检查策略是否存在
        
        Args:
            stock_code: 股票代码
            action: 交易动作
            
        Returns:
            Dict: 检查结果
        """
        try:
            # 调用检查策略接口
            data = self._make_request(
                'POST',
                'strategies/check',
                json={
                    'stock_code': stock_code,
                    'action': action
                }
            )
            return data
        except Exception as e:
            logger.error(f"检查策略失败: {str(e)}")
            return None
            
    def set_strategy_status(self, strategy_id: str, is_active: bool) -> bool:
        """
        设置策略状态
        
        Args:
            strategy_id: 策略ID
            is_active: 是否有效
            
        Returns:
            bool: 是否成功
        """
        try:
            # 调用设置策略状态接口
            endpoint = f"strategies/{strategy_id}/{'activate' if is_active else 'deactivate'}"
            data = self._make_request('POST', endpoint)
            if data:
                if strategy_id in self.strategies:
                    self.strategies[strategy_id]['is_active'] = is_active
                return True
            return False
        except Exception as e:
            logger.error(f"设置策略状态失败: {str(e)}")
            return False
            
    def search_strategies(self, **kwargs) -> List[Dict]:
        """
        搜索策略
        
        Args:
            **kwargs: 搜索参数
            
        Returns:
            List[Dict]: 搜索结果
        """
        try:
            # 调用搜索策略接口
            data = self._make_request(
                'GET',
                'strategies/search',
                params=kwargs
            )
            if data:
                return data
            return []
        except Exception as e:
            logger.error(f"搜索策略失败: {str(e)}")
            return []
            
    def record_execution(self, execution: Dict) -> Dict:
        """
        记录策略执行
        
        Args:
            execution: 执行记录
            
        Returns:
            Dict: 记录结果
        """
        try:
            # 调用创建执行记录接口
            data = self._make_request(
                'POST',
                'executions',
                json=execution
            )
            return data
        except Exception as e:
            logger.error(f"记录执行结果失败: {str(e)}")
            return None
            
    def start(self):
        """启动策略管理器"""
        if self.is_running:
            logger.warning("策略管理器已经在运行中")
            return False
            
        try:
            logger.info("正在启动策略管理器...")
            # 启动交易程序
            if not self.trader.start():
                logger.error("启动交易程序失败")
                return False
                
            # 加载策略
            self._load_strategies()
            
            self.is_running = True
            logger.info("策略管理器启动成功")
            return True
        except Exception as e:
            logger.error(f"启动策略管理器失败: {str(e)}")
            return False
            
    def stop(self):
        """停止策略管理器"""
        if not self.is_running:
            logger.warning("策略管理器已经停止")
            return False
            
        try:
            logger.info("正在停止策略管理器...")
            # 停止交易程序
            if not self.trader.stop():
                logger.error("停止交易程序失败")
                return False
                
            self.is_running = False
            self._stop_flag = True
            if self._monitor_thread.is_alive():
                self._monitor_thread.join()
            logger.info("策略管理器停止成功")
            return True
        except Exception as e:
            logger.error(f"停止策略管理器失败: {str(e)}")
            return False
            
    def add_strategy(self, strategy: Dict):
        """添加策略"""
        try:
            # 验证策略参数
            if not self._validate_strategy(strategy):
                return False
                
            # 添加策略
            if not self.trader.add_strategy(strategy):
                return False
                
            strategy_id = strategy['id']
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
                
            # 移除策略
            if not self.trader.remove_strategy(strategy_id):
                return False
                
            del self.strategies[strategy_id]
            logger.info(f"移除策略成功: {strategy_id}")
            return True
        except Exception as e:
            logger.error(f"移除策略失败: {str(e)}")
            return False
            
    def get_strategy(self, strategy_id: str) -> Optional[Dict]:
        """获取指定策略"""
        return self.strategies.get(strategy_id)
        
    def _load_strategies(self):
        """加载策略"""
        try:
            # TODO: 从数据库或配置文件加载策略
            pass
        except Exception as e:
            logger.error(f"加载策略失败: {str(e)}")
            
    def _validate_strategy(self, strategy: Dict) -> bool:
        """验证策略参数"""
        required_fields = ['id', 'stock_code', 'stock_name', 'action']
        for field in required_fields:
            if field not in strategy:
                logger.error(f"策略缺少必要字段: {field}")
                return False
                
        # 验证交易方向
        if strategy['action'] not in ['buy', 'sell']:
            logger.error(f"无效的交易方向: {strategy['action']}")
            return False
            
        return True
            
    def _should_execute(self, strategy_id: int, strategy: Dict) -> bool:
        """判断策略是否需要执行"""
        # 检查策略状态
        execution_status = strategy.get('execution_status')
        if execution_status == 'completed':
            logger.debug(f"策略 {strategy_id} 已完成，跳过")
            return False
        
        if execution_status not in ['pending', 'partial']:
            logger.debug(f"策略 {strategy_id} 状态为 {execution_status}，跳过")
            return False
        
        # 检查策略是否激活
        if not strategy.get('is_active', True):
            logger.debug(f"策略 {strategy_id} 未激活，跳过")
            return False
        
        # 检查是否有未完成的订单
        orders = self.trader.broker.get_orders(is_active=True)
        if orders:
            logger.debug(f"策略 {strategy_id} 有未完成的订单，等待订单完成")
            return False
        
        logger.info(f"策略 {strategy_id} 需要执行")
        return True
        
    def execute_strategy(self, strategy_id: int, strategy: Dict) -> Dict:
        """执行策略"""
        try:
            # 获取账户信息
            account = self.trader.broker.get_account()
            logger.info(f"当前可用资金: {account.available_funds}")
            
            # 获取股票信息
            stock_code = strategy.get('stock_code')
            stock_name = strategy.get('stock_name')
            action = strategy.get('action')
            position_ratio = strategy.get('position_ratio', 0)
            
            # 获取最新报价
            quote = self.trader.broker.get_quote(stock_code)
            current_price = quote['price']
            
            # 根据操作类型处理
            if action == 'buy':
                # 计算买入金额：需要购买的股票金额 = 总资产 × 仓位
                target_amount = account.total_assets * (position_ratio / 100)
                
                # 获取已有持仓
                position = self.trader.broker.get_position(stock_code)
                if position:
                    # 减去已持仓金额
                    target_amount -= position.market_value
                    
                if target_amount <= 0:
                    logger.info(f"策略 {strategy_id} 已达到目标仓位")
                    # 更新策略状态为完成
                    self.update_strategy(str(strategy_id), {
                        'execution_status': 'completed',
                        'is_active': False
                    })
                    return {
                        'strategy_id': strategy_id,
                        'stock_code': stock_code,
                        'action': action,
                        'status': 'completed',
                        'message': '已达到目标仓位'
                    }
                    
                # 计算可买数量（向下取整到100的倍数）
                volume = int(target_amount / current_price / 100) * 100
                
                if volume == 0:
                    logger.warning(f"策略 {strategy_id} 可用资金不足，无法买入")
                    # 更新策略状态为未完成
                    self.update_strategy(str(strategy_id), {
                        'execution_status': 'pending'
                    })
                    return {
                        'strategy_id': strategy_id,
                        'stock_code': stock_code,
                        'action': action,
                        'status': 'pending',
                        'message': '可用资金不足'
                    }
                    
            elif action == 'sell':
                # 获取持仓信息
                position = self.trader.broker.get_position(stock_code)
                if not position:
                    logger.warning(f"策略 {strategy_id} 没有持仓，无法卖出")
                    # 更新策略状态为完成
                    self.update_strategy(str(strategy_id), {
                        'execution_status': 'completed',
                        'is_active': False
                    })
                    return {
                        'strategy_id': strategy_id,
                        'stock_code': stock_code,
                        'action': action,
                        'status': 'completed',
                        'message': '没有持仓'
                    }
                    
                # 计算卖出数量：持仓数量 × 卖出比例
                volume = int(position.total_volume * (position_ratio / 100))
                # 确保是100的整数倍
                volume = (volume // 100) * 100
                
                if volume == 0:
                    logger.warning(f"策略 {strategy_id} 卖出数量太小")
                    # 更新策略状态为未完成
                    self.update_strategy(str(strategy_id), {
                        'execution_status': 'pending'
                    })
                    return {
                        'strategy_id': strategy_id,
                        'stock_code': stock_code,
                        'action': action,
                        'status': 'pending',
                        'message': '卖出数量太小'
                    }
                    
            elif action == 'add':
                # 获取持仓信息
                position = self.trader.broker.get_position(stock_code)
                if not position:
                    logger.info(f"策略 {strategy_id} 没有持仓，转为买入操作")
                    # 计算买入金额：需要购买的股票金额 = 总资产 × 仓位
                    target_amount = account.total_assets * (position_ratio / 100)
                    
                    # 计算可买数量（向下取整到100的倍数）
                    volume = int(target_amount / current_price / 100) * 100
                    
                    if volume == 0:
                        logger.warning(f"策略 {strategy_id} 可用资金不足，无法买入")
                        # 更新策略状态为未完成
                        self.update_strategy(str(strategy_id), {
                            'execution_status': 'pending'
                        })
                        return {
                            'strategy_id': strategy_id,
                            'stock_code': stock_code,
                            'action': action,
                            'status': 'pending',
                            'message': '可用资金不足'
                        }
                        
                else:
                    # 计算加仓数量：当前持股量 × (加仓比例 ÷ 原始仓位比例)
                    if position.original_position_ratio <= 0:
                        logger.warning(f"策略 {strategy_id} 原始仓位比例异常")
                        # 更新策略状态为未完成
                        self.update_strategy(str(strategy_id), {
                            'execution_status': 'pending'
                        })
                        return {
                            'strategy_id': strategy_id,
                            'stock_code': stock_code,
                            'action': action,
                            'status': 'pending',
                            'message': '原始仓位比例异常'
                        }
                        
                    volume = int(position.total_volume * (position_ratio / position.original_position_ratio))
                    # 确保是100的整数倍
                    volume = (volume // 100) * 100
                    
                    if volume == 0:
                        logger.warning(f"策略 {strategy_id} 加仓数量太小")
                        # 更新策略状态为未完成
                        self.update_strategy(str(strategy_id), {
                            'execution_status': 'pending'
                        })
                        return {
                            'strategy_id': strategy_id,
                            'stock_code': stock_code,
                            'action': action,
                            'status': 'pending',
                            'message': '加仓数量太小'
                        }
                        
                    # 检查可用资金是否足够
                    required_amount = volume * current_price
                    if required_amount > account.available_funds:
                        logger.warning(f"策略 {strategy_id} 可用资金不足，无法加仓")
                        # 更新策略状态为未完成
                        self.update_strategy(str(strategy_id), {
                            'execution_status': 'pending'
                        })
                        return {
                            'strategy_id': strategy_id,
                            'stock_code': stock_code,
                            'action': action,
                            'status': 'pending',
                            'message': '可用资金不足'
                        }
                    
            elif action == 'trim':
                # 获取持仓信息
                position = self.trader.broker.get_position(stock_code)
                if not position:
                    logger.warning(f"策略 {strategy_id} 没有持仓，无法减仓")
                    # 更新策略状态为完成
                    self.update_strategy(str(strategy_id), {
                        'execution_status': 'completed',
                        'is_active': False
                    })
                    return {
                        'strategy_id': strategy_id,
                        'stock_code': stock_code,
                        'action': action,
                        'status': 'completed',
                        'message': '没有持仓'
                    }
                    
                # 计算减仓数量：当前持股量 × (减仓比例 ÷ 原始仓位比例)
                if position.original_position_ratio <= 0:
                    logger.warning(f"策略 {strategy_id} 原始仓位比例异常")
                    # 更新策略状态为未完成
                    self.update_strategy(str(strategy_id), {
                        'execution_status': 'pending'
                    })
                    return {
                        'strategy_id': strategy_id,
                        'stock_code': stock_code,
                        'action': action,
                        'status': 'pending',
                        'message': '原始仓位比例异常'
                    }
                    
                volume = int(position.total_volume * (position_ratio / position.original_position_ratio))
                # 确保是100的整数倍
                volume = (volume // 100) * 100
                
                if volume == 0:
                    logger.warning(f"策略 {strategy_id} 减仓数量太小")
                    # 更新策略状态为未完成
                    self.update_strategy(str(strategy_id), {
                        'execution_status': 'pending'
                    })
                    return {
                        'strategy_id': strategy_id,
                        'stock_code': stock_code,
                        'action': action,
                        'status': 'pending',
                        'message': '减仓数量太小'
                    }
                    
                # 检查可用持仓是否足够
                if volume > position.available_volume:
                    logger.warning(f"策略 {strategy_id} 可用持仓不足，无法减仓")
                    # 更新策略状态为未完成
                    self.update_strategy(str(strategy_id), {
                        'execution_status': 'pending'
                    })
                    return {
                        'strategy_id': strategy_id,
                        'stock_code': stock_code,
                        'action': action,
                        'status': 'pending',
                        'message': '可用持仓不足'
                    }
                    
            elif action == 'hold':
                # 持有不进行实际交易
                logger.info(f"策略 {strategy_id} 执行持有操作")
                # 更新策略状态为完成
                self.update_strategy(str(strategy_id), {
                    'execution_status': 'completed',
                    'is_active': False
                })
                return {
                    'strategy_id': strategy_id,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'action': action,
                    'execution_price': current_price,
                    'volume': 0,
                    'position_ratio': 0,
                    'status': 'completed',
                    'message': '持有策略执行成功'
                }
                
            else:
                logger.warning(f"策略 {strategy_id} 不支持的操作类型: {action}")
                # 更新策略状态为完成
                self.update_strategy(str(strategy_id), {
                    'execution_status': 'completed',
                    'is_active': False
                })
                return {
                    'strategy_id': strategy_id,
                    'stock_code': stock_code,
                    'action': action,
                    'status': 'completed',
                    'message': f'不支持的操作类型: {action}'
                }
                
            # 创建订单
            order = Order.create_limit_order(
                strategy_id=str(strategy_id),
                stock_code=stock_code,
                stock_name=stock_name,
                side=OrderSide.SELL if action in ['sell', 'trim'] else OrderSide.BUY,
                price=current_price,
                volume=volume,
                position_ratio=position_ratio  # 添加仓位比例参数
            )
            
            # 提交订单
            if self.trader.broker.place_order(order):
                logger.info(f"策略 {strategy_id} 订单提交成功")
                # 更新策略状态为部分执行
                self.update_strategy(str(strategy_id), {
                    'execution_status': 'partial'
                })
                return {
                    'strategy_id': strategy_id,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'action': action,
                    'execution_price': current_price,
                    'volume': volume,
                    'position_ratio': position_ratio,
                    'status': 'partial',
                    'message': '订单提交成功'
                }
            else:
                logger.error(f"策略 {strategy_id} 订单提交失败")
                # 更新策略状态为未完成
                self.update_strategy(str(strategy_id), {
                    'execution_status': 'pending'
                })
                return {
                    'strategy_id': strategy_id,
                    'stock_code': stock_code,
                    'action': action,
                    'status': 'pending',
                    'message': '订单提交失败'
                }
                
        except Exception as e:
            logger.error(f"执行策略 {strategy_id} 异常: {str(e)}")
            # 更新策略状态为未完成
            self.update_strategy(str(strategy_id), {
                'execution_status': 'pending'
            })
            return {
                'strategy_id': strategy_id,
                'stock_code': stock_code if 'stock_code' in locals() else None,
                'action': action if 'action' in locals() else None,
                'status': 'pending',
                'message': f'执行异常: {str(e)}'
            }
            
    def _monitor_strategies(self):
        """监控策略"""
        while not self._stop_flag:
            try:
                if not self.is_running:
                    time.sleep(5)
                    continue
                    
                # 获取策略列表
                logger.info("开始获取策略列表...")
                strategies = self.get_strategies()
                if not strategies:
                    logger.debug("没有获取到策略")
                    time.sleep(5)
                    continue
                    
                logger.info(f"获取到 {len(strategies)} 个策略")
                
                # 检查每个策略
                for strategy in strategies:
                    strategy_id = strategy.get('id')
                    if not strategy_id:
                        logger.warning("策略ID为空，跳过")
                        continue
                        
                    logger.info(f"检查策略 {strategy_id}:")
                    logger.info(f"    股票: {strategy.get('stock_name')}({strategy.get('stock_code')})")
                    logger.info(f"    动作: {strategy.get('action')}")
                    logger.info(f"    状态: {strategy.get('execution_status')}")
                    logger.info(f"    是否激活: {strategy.get('is_active')}")
                    
                    # 检查是否需要执行
                    if self._should_execute(strategy_id, strategy):
                        logger.info(f"开始执行策略 {strategy_id}...")
                        result = self.execute_strategy(strategy_id, strategy)
                        
                        # 不再创建执行记录，因为已经在 SimulatedBroker 中创建了
                        
                time.sleep(5)  # 每5秒检查一次策略
                
            except Exception as e:
                logger.error(f"监控策略异常: {str(e)}")
                time.sleep(5)  # 发生异常时等待5秒后继续

    def _create_execution_record(self, execution: Dict) -> None:
        """创建执行记录"""
        try:
            # 构造请求参数
            request_data = {
                "strategy_id": execution['strategy_id'],
                "stock_code": execution['stock_code'],
                "stock_name": execution['stock_name'],
                "action": execution['action'],
                "execution_price": execution['execution_price'],
                "volume": execution['volume'],
                "position_ratio": execution.get('position_ratio', 0),
                "original_position_ratio": execution.get('position_ratio', 0),
                "strategy_status": "partial",  # 默认为部分执行
                "execution_result": "success",  # 默认为成功
                "execution_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # 添加执行时间
                "remarks": execution.get('remarks', '按计划执行')
            }
            
            # 发送请求
            response = self._make_request('POST', 'executions', json=request_data)
            
            if response:
                logger.info(f"创建执行记录成功: {response}")
            else:
                logger.error("创建执行记录失败: API返回空响应")
                
        except Exception as e:
            logger.error(f"创建执行记录异常: {str(e)}")
            
    def get_executions(self) -> List[Dict]:
        """获取执行记录列表"""
        try:
            # 调用执行记录列表接口
            data = self._make_request(
                'GET',
                'executions',
                params={
                    'sort_by': 'execution_time',
                    'order': 'desc',
                    'limit': 100  # 最多显示最近100条记录
                }
            )
            if data:
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'items' in data:
                    return data.get('items', [])
            logger.warning("获取执行记录失败，返回数据格式不正确")
            return []
        except Exception as e:
            logger.error(f"获取执行记录列表失败: {str(e)}")
            return [] 