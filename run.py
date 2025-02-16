"""
主程序，实现定时任务调度和异常处理
"""
import time
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.strategy.strategy import StrategyManager
from src.trade.trader import (
    StockTrader, InvalidTimeError, NoPositionError, PriceNotMatchError,
    InsufficientFundsError, FrequencyLimitError, PositionLimitError,
    PriceDeviationError
)
from src.config import config

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.get('logging.level', 'INFO')),
    format=config.get('logging.format'),
    handlers=[
        logging.FileHandler(config.get('logging.file_path'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradingApp:
    """交易应用类"""
    
    def __init__(self):
        """初始化应用"""
        self.strategy_manager = StrategyManager()
        self.trader = StockTrader()
        self.scheduler = BackgroundScheduler()
        
        # 启动时同步持仓数据
        logger.info("开始同步初始持仓数据...")
        try:
            assets = self.trader.update_assets()
            logger.info(f"初始资产同步完成 - 总资产: {assets['total_assets']:.2f}, "
                       f"现金: {assets['cash']:.2f}")
            
            # 获取并显示当前持仓
            positions = assets.get('positions', {})
            if positions:
                logger.info("当前持仓情况:")
                for code, pos in positions.items():
                    logger.info(f"股票: {code}, 数量: {pos.get('volume', 0)}, "
                              f"成本: {pos.get('cost_price', 0):.2f}, "
                              f"市值: {pos.get('market_value', 0):.2f}, "
                              f"盈亏: {pos.get('floating_profit', 0):.2f}")
            else:
                logger.info("当前无持仓")
        except Exception as e:
            logger.error(f"初始化持仓数据失败: {str(e)}", exc_info=True)
            raise
        
    def _check_position_ratio(self, stock_code: str, target_ratio: float, action: str = 'buy') -> bool:
        """
        检查持仓比例是否超限
        
        Args:
            stock_code: 股票代码
            target_ratio: 目标仓位比例
            action: 交易动作（buy/sell）
            
        Returns:
            bool: 是否允许交易
        """
        try:
            # 卖出操作不受最大持仓比例限制
            if action == 'sell':
                logger.info(f"卖出操作，不检查最大持仓比例限制")
                return True

            # 获取当前资产信息
            assets = self.trader.update_assets()
            total_assets = assets['total_assets']
            
            # 获取当前持仓
            positions = assets.get('positions', {})
            current_position = positions.get(stock_code, {})
            current_market_value = current_position.get('market_value', 0)
            
            # 计算目标市值
            target_market_value = total_assets * target_ratio
            
            # 检查是否超过最大持仓比例
            max_position_ratio = config.get('trading.max_position_ratio')
            if target_market_value / total_assets > max_position_ratio:
                logger.warning(f"目标持仓比例 {target_ratio:.2%} 超过最大限制 {max_position_ratio:.2%}")
                return False
                
            logger.info(f"持仓检查通过 - 当前市值: {current_market_value:.2f}, "
                       f"目标市值: {target_market_value:.2f}, 总资产: {total_assets:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"检查持仓比例异常: {str(e)}")
            return False
            
    def execute_strategy(self, strategy: dict) -> None:
        """
        执行单个策略
        
        Args:
            strategy: 策略信息
        """
        try:
            stock_code = strategy['stock_code']
            action = strategy['action']
            position_ratio = strategy['position_ratio']
            
            logger.info("="*50)
            logger.info(f"开始执行策略 - ID: {strategy.get('id')}")
            logger.info("="*50)
            logger.info("策略详情:")
            logger.info(f"    股票: {strategy.get('stock_name')}({stock_code})")
            logger.info(f"    动作: {action}")
            logger.info(f"    仓位比例: {position_ratio}")
            logger.info(f"    价格区间: {strategy.get('price_min', '不限')} - {strategy.get('price_max', '不限')}")
            logger.info(f"    执行状态: {strategy.get('execution_status')}")
            
            # 检查策略状态
            if strategy.get('execution_status') == 'completed':
                logger.info("策略已完成，跳过执行")
                return
                
            # 检查持仓比例
            if not self._check_position_ratio(stock_code, position_ratio, action):
                logger.info("持仓比例检查未通过，跳过执行")
                return
                
            # 执行交易
            if action == 'buy':
                logger.info("-"*30)
                logger.info("执行买入操作")
                logger.info("-"*30)
                result = self.trader.buy_stock(
                    stock_code=stock_code,
                    min_price=strategy.get('price_min'),
                    max_price=strategy.get('price_max'),
                    position_ratio=position_ratio,
                    strategy_id=strategy.get('id')
                )
            else:  # sell
                logger.info("-"*30)
                logger.info("执行卖出操作")
                logger.info("-"*30)
                result = self.trader.sell_stock(
                    stock_code=stock_code,
                    min_price=strategy.get('price_min'),
                    max_price=strategy.get('price_max'),
                    position_ratio=position_ratio,
                    strategy_id=strategy.get('id')
                )
                
            logger.info("执行结果:")
            logger.info(f"    状态: {result.get('status')}")
            logger.info(f"    消息: {result.get('message')}")
            logger.info(f"    价格: {result.get('price')}")
            logger.info(f"    数量: {result.get('volume')}")
            logger.info(f"    金额: {result.get('amount')}")
            logger.info("="*50)
            
        except (InvalidTimeError, NoPositionError, PriceNotMatchError) as e:
            # 这些是预期内的交易限制，使用 INFO 级别记录
            logger.info(f"策略执行受限: {str(e)}")
            logger.info("="*50)
        except (InsufficientFundsError, FrequencyLimitError, 
                PositionLimitError, PriceDeviationError) as e:
            # 这些是需要关注的交易限制，使用 WARNING 级别记录
            logger.warning(f"策略执行受限: {str(e)}")
            logger.info("="*50)
        except Exception as e:
            # 这些是意外错误，使用 ERROR 级别记录
            logger.error(f"策略执行异常: {str(e)}", exc_info=True)
            logger.info("="*50)
            
    def check_and_execute_strategies(self) -> None:
        """检查并执行策略"""
        try:
            # 获取有效策略
            strategies = self.strategy_manager.fetch_active_strategies()
            logger.info(f"获取到 {len(strategies)} 个有效策略")
            
            # 执行每个策略
            for strategy in strategies:
                self.execute_strategy(strategy)
                
        except Exception as e:
            logger.error(f"检查执行策略异常: {str(e)}", exc_info=True)
            
    def update_assets(self) -> None:
        """更新资产信息"""
        try:
            assets = self.trader.update_assets()
            logger.info(f"资产更新完成 - 总资产: {assets['total_assets']:.2f}, "
                       f"现金: {assets['cash']:.2f}")
        except Exception as e:
            logger.error(f"更新资产信息异常: {str(e)}", exc_info=True)
            
    def start(self) -> None:
        """启动应用"""
        try:
            # 添加策略检查任务
            self.scheduler.add_job(
                self.check_and_execute_strategies,
                IntervalTrigger(seconds=config.get('monitor.check_interval')),
                id='check_strategies',
                replace_existing=True
            )
            
            # 添加资产更新任务
            self.scheduler.add_job(
                self.update_assets,
                IntervalTrigger(seconds=config.get('cache.position_ttl')),
                id='update_assets',
                replace_existing=True
            )
            
            # 启动调度器
            self.scheduler.start()
            logger.info(f"交易应用已启动，策略检查间隔：{config.get('monitor.check_interval')} 秒，"
                       f"资产更新间隔：{config.get('cache.position_ttl')} 秒")
            
            # 立即执行一次资产更新和策略检查
            logger.info("执行首次资产更新...")
            self.update_assets()
            logger.info("执行首次策略检查...")
            self.check_and_execute_strategies()
            
            # 保持程序运行
            while True:
                time.sleep(1)
                
        except (KeyboardInterrupt, SystemExit):
            logger.info("正在停止交易应用...")
            self.scheduler.shutdown()
            logger.info("交易应用已停止")
        except Exception as e:
            logger.error(f"应用运行异常: {str(e)}", exc_info=True)
            if self.scheduler.running:
                self.scheduler.shutdown()
            
if __name__ == '__main__':
    app = TradingApp()
    app.start() 