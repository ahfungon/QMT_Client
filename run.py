"""
主程序，实现定时任务调度和异常处理
"""
import time
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.strategy.strategy import StrategyManager
from src.trade.trader import StockTrader
from config.settings import (
    API_BASE_URL, LOG_LEVEL, LOG_FORMAT, LOG_FILE,
    SCHEDULE_INTERVAL, ASSETS_UPDATE_INTERVAL, POSITION_FILE
)

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradingApp:
    """交易应用类"""
    
    def __init__(self):
        """初始化应用"""
        self.strategy_manager = StrategyManager(base_url=API_BASE_URL)
        self.trader = StockTrader(base_url=API_BASE_URL, position_file=POSITION_FILE)
        self.scheduler = BackgroundScheduler()
        
    def _check_position_ratio(self, stock_code: str, target_ratio: float) -> bool:
        """
        检查当前持仓比例是否满足目标比例
        
        Args:
            stock_code: 股票代码
            target_ratio: 目标持仓比例
            
        Returns:
            是否需要补仓
        """
        # 获取最新资产信息
        assets = self.trader._load_assets()
        positions = assets['positions']
        total_assets = assets['total_assets']
        
        # 如果没有持仓，需要建仓
        if stock_code not in positions:
            logger.info(f"股票 {stock_code} 当前无持仓，需要建仓")
            return True
            
        # 获取当前持仓市值和总资产
        current_position = positions[stock_code]
        current_market_value = current_position['market_value']
        
        # 计算当前持仓比例（相对于总资产）
        current_ratio = current_market_value / total_assets
        
        # 计算比例差异（允许1%的误差范围）
        ratio_diff = abs(current_ratio - target_ratio)
        tolerance = 0.01  # 1%的容差
        
        logger.info(f"股票 {stock_code} 持仓检查 - 当前比例: {current_ratio:.2%}, 目标比例: {target_ratio:.2%}, "
                   f"差异: {ratio_diff:.2%}, 总资产: {total_assets:.2f}, 现金: {assets['cash']:.2f}")
        
        # 如果当前比例在目标比例的误差范围内，不需要调整
        if ratio_diff <= tolerance:
            logger.info(f"股票 {stock_code} 当前持仓比例在目标范围内，无需调整")
            return False
            
        # 如果当前比例小于目标比例，需要补仓
        if current_ratio < target_ratio:
            logger.info(f"股票 {stock_code} 当前持仓比例低于目标比例，需要补仓")
            return True
            
        # 如果当前比例大于目标比例，不需要补仓
        logger.info(f"股票 {stock_code} 当前持仓比例高于目标比例，无需补仓")
        return False
        
    def execute_strategy(self, strategy: dict) -> None:
        """
        执行单个策略
        
        Args:
            strategy: 策略信息
        """
        try:
            # 验证策略
            if not self.strategy_manager.validate_strategy(strategy):
                return
                
            stock_code = strategy['stock_code']
            position_ratio = strategy['position_ratio']
            
            # 如果是买入策略
            if strategy['action'] == 'buy':
                # 检查是否需要交易
                if not self._check_position_ratio(stock_code, position_ratio):
                    logger.info(f"股票 {stock_code} 当前持仓比例已满足要求，无需交易")
                    return
                    
                # 执行买入交易
                result = self.trader.buy_stock(
                    stock_code,
                    strategy['price_min'],
                    strategy['price_max'],
                    position_ratio,
                    strategy['id']
                )
            else:  # 卖出策略直接执行
                result = self.trader.sell_stock(
                    stock_code,
                    strategy['price_min'],
                    strategy['price_max'],
                    position_ratio,
                    strategy['id']
                )
                
            # 记录执行结果
            logger.info(f"策略执行结果 - 策略ID: {strategy['id']}, 股票: {stock_code}, "
                       f"动作: {strategy['action']}, 结果: {result['result']}, "
                       f"数量: {result['volume']}, 价格: {result['price']}, "
                       f"错误: {result['error']}")
                       
        except Exception as e:
            logger.error(f"执行策略异常: {str(e)}", exc_info=True)
            
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
                IntervalTrigger(seconds=SCHEDULE_INTERVAL),
                id='check_strategies',
                replace_existing=True
            )
            
            # 添加资产更新任务
            self.scheduler.add_job(
                self.update_assets,
                IntervalTrigger(seconds=ASSETS_UPDATE_INTERVAL),
                id='update_assets',
                replace_existing=True
            )
            
            # 启动调度器
            self.scheduler.start()
            logger.info(f"交易应用已启动，策略检查间隔：{SCHEDULE_INTERVAL} 秒，"
                       f"资产更新间隔：{ASSETS_UPDATE_INTERVAL} 秒")
            
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