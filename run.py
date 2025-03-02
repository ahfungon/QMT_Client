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
import requests
import sys
import os
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

# 配置日志
def setup_logging():
    """配置日志"""
    # 创建日志目录
    log_dir = config.get('logging.dir', 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # 创建日志格式
    formatter = logging.Formatter(
        fmt=config.get('logging.format'),
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 创建文件处理器
    log_file = os.path.join(log_dir, config.get('logging.filename', 'app.log'))
    file_handler = logging.FileHandler(
        filename=log_file,
        encoding=config.get('data.file_encoding', 'utf-8')
    )
    file_handler.setFormatter(formatter)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(config.get('logging.level', 'INFO'))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return root_logger

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
            
            # 验证assets是否为字典类型
            if not isinstance(assets, dict):
                logger.error(f"资产数据格式错误: 预期字典类型，实际为 {type(assets)}")
                # 初始化一个默认的资产数据结构
                assets = {
                    "available_cash": config.get('account.initial_cash', 0.0),
                    "total_assets": config.get('account.total_assets', 0.0),
                    "total_market_value": 0.0,
                    "positions": {},
                    "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            logger.info(f"初始资产同步完成 - 总资产: {assets.get('total_assets', 0.0):.2f}, "
                       f"现金: {assets.get('available_cash', 0.0):.2f}")
            
            # 获取并显示当前持仓
            positions = assets.get('positions', {})
            if positions and isinstance(positions, dict):
                logger.info("当前持仓情况:")
                for code, pos in positions.items():
                    if not isinstance(pos, dict):
                        logger.warning(f"持仓数据格式错误: 股票 {code} 的数据不是字典类型")
                        continue
                    logger.info(f"股票: {code}, 数量: {pos.get('volume', 0)}, "
                              f"成本: {pos.get('cost_price', 0):.2f}, "
                              f"市值: {pos.get('market_value', 0):.2f}, "
                              f"盈亏: {pos.get('floating_profit', 0):.2f}")
            else:
                logger.info("当前无持仓")
        except Exception as e:
            logger.error(f"初始化持仓数据失败: {str(e)}", exc_info=True)
            # 不抛出异常，而是继续运行，使用默认值
            logger.info("使用默认资产数据继续运行")
            # 初始化调度器，避免后续代码依赖self.scheduler
        
    def _check_position_ratio(self, stock_code: str, target_ratio: int, action: str = 'buy') -> bool:
        """
        检查持仓比例是否超限
        
        Args:
            stock_code: 股票代码
            target_ratio: 目标仓位比例(0-100整数)
            action: 交易动作（buy/sell/hold/add/trim）
            
        Returns:
            bool: 是否允许交易
        """
        try:
            # 卖出、减仓、持有操作不受最大持仓比例限制
            if action in ['sell', 'trim', 'hold']:
                logger.info(f"{action}操作，不检查最大持仓比例限制")
                return True

            # 获取当前资产信息
            assets = self.trader.update_assets()
            
            # 验证assets是否为字典类型
            if not isinstance(assets, dict):
                logger.error(f"资产数据格式错误: 预期字典类型，实际为 {type(assets)}")
                return False
                
            total_assets = assets.get('total_assets', 0.0)
            
            # 获取当前持仓
            positions = assets.get('positions', {})
            if not isinstance(positions, dict):
                logger.error(f"持仓数据格式错误: 预期字典类型，实际为 {type(positions)}")
                return False
                
            current_position = positions.get(stock_code, {})
            if not isinstance(current_position, dict):
                logger.error(f"股票 {stock_code} 的持仓数据格式错误: 预期字典类型，实际为 {type(current_position)}")
                current_position = {}
                
            current_market_value = current_position.get('market_value', 0)
            
            # 计算目标市值
            target_market_value = total_assets * (target_ratio / 100.0)
            
            # 检查是否超过最大持仓比例
            max_position_ratio = config.get('trading.max_position_ratio', 30)
            if target_ratio > max_position_ratio:
                logger.warning(f"目标持仓比例 {target_ratio}% 超过最大限制 {max_position_ratio}%")
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
            # 验证策略数据格式
            if not isinstance(strategy, dict):
                logger.error(f"策略数据格式错误: 预期字典类型，实际为 {type(strategy)}")
                return
                
            # 获取必要字段，使用get方法避免KeyError
            stock_code = strategy.get('stock_code')
            if not stock_code:
                logger.error("策略缺少股票代码，无法执行")
                return
                
            action = strategy.get('action')
            if not action:
                logger.error("策略缺少交易动作，无法执行")
                return
                
            position_ratio = strategy.get('position_ratio', 0)  # 这里获取的是整数(0-100)
            
            # 转换动作为中文描述
            action_desc = {
                'buy': '买入',
                'sell': '卖出',
                'hold': '持有',
                'add': '加仓',
                'trim': '减仓'
            }.get(action, action)
            
            logger.info("="*50)
            logger.info(f"开始执行策略 - ID: {strategy.get('id')}")
            logger.info("="*50)
            logger.info("策略详情:")
            logger.info(f"    股票: {strategy.get('stock_name', '未知')}({stock_code})")
            logger.info(f"    动作: {action_desc}")
            logger.info(f"    仓位比例: {position_ratio}%")  # 显示为百分比
            logger.info(f"    价格区间: {strategy.get('price_min', '不限')} - {strategy.get('price_max', '不限')}")
            logger.info(f"    执行状态: {strategy.get('execution_status', '未知')}")
            
            # 检查策略状态
            if strategy.get('execution_status') == 'completed':
                logger.info("策略已完成，跳过执行")
                return
                
            # 检查持仓比例（买入和加仓需要检查）
            if action in ['buy', 'add']:
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
                    position_ratio=position_ratio,  # 传递整数(0-100)
                    strategy_id=strategy.get('id')
                )
            elif action == 'sell':
                logger.info("-"*30)
                logger.info("执行卖出操作")
                logger.info("-"*30)
                result = self.trader.sell_stock(
                    stock_code=stock_code,
                    min_price=strategy.get('price_min'),
                    max_price=strategy.get('price_max'),
                    position_ratio=position_ratio,  # 传递整数(0-100)
                    strategy_id=strategy.get('id')
                )
            elif action == 'hold':
                logger.info("-"*30)
                logger.info("执行持有操作")
                logger.info("-"*30)
                # 持有策略不需要实际交易，只需要检查并记录
                try:
                    # 获取当前持仓
                    holdings = self.trader._load_positions().get(stock_code, {})
                    if not holdings:
                        logger.warning(f"持有策略无法执行：没有 {stock_code} 的持仓")
                        result = {
                            'status': 'failed',
                            'message': f'无持仓记录',
                            'stock_code': stock_code,
                            'price': 0,
                            'volume': 0,
                            'amount': 0
                        }
                    else:
                        # 获取当前价格
                        current_price = self.trader.quote_service.get_real_time_quote(stock_code)['price']
                        logger.info(f"持有策略执行：持有 {holdings.get('volume')} 股 {stock_code}，当前价格 {current_price}")
                        # 记录策略执行
                        self.trader._record_execution(
                            stock_code=stock_code,
                            action='hold',
                            price=current_price,
                            volume=0,  # 持有策略不交易量
                            strategy_id=strategy.get('id')
                        )
                        result = {
                            'status': 'success',
                            'message': '持有策略执行成功',
                            'stock_code': stock_code,
                            'price': current_price,
                            'volume': 0,
                            'amount': 0
                        }
                except Exception as e:
                    logger.error(f"持有策略执行失败: {str(e)}")
                    result = {
                        'status': 'failed',
                        'message': f'持有策略执行失败: {str(e)}',
                        'stock_code': stock_code,
                        'price': 0,
                        'volume': 0,
                        'amount': 0
                    }
            elif action == 'add':
                logger.info("-"*30)
                logger.info("执行加仓操作")
                logger.info("-"*30)
                # 加仓实际上是买入操作，但需要确保已有持仓
                holdings = self.trader._load_positions().get(stock_code, {})
                if not holdings:
                    logger.warning(f"加仓策略转为买入：没有 {stock_code} 的持仓")
                
                result = self.trader.buy_stock(
                    stock_code=stock_code,
                    min_price=strategy.get('price_min'),
                    max_price=strategy.get('price_max'),
                    position_ratio=position_ratio,  # 传递整数(0-100)
                    strategy_id=strategy.get('id')
                )
            elif action == 'trim':
                logger.info("-"*30)
                logger.info("执行减仓操作")
                logger.info("-"*30)
                # 减仓实际上是部分卖出操作
                result = self.trader.sell_stock(
                    stock_code=stock_code,
                    min_price=strategy.get('price_min'),
                    max_price=strategy.get('price_max'),
                    position_ratio=position_ratio,  # 传递整数(0-100)
                    strategy_id=strategy.get('id')
                )
            else:
                logger.error(f"不支持的策略类型: {action}")
                return
                
            # 验证结果格式
            if not isinstance(result, dict):
                logger.error(f"交易结果格式错误: 预期字典类型，实际为 {type(result)}")
                return
                
            logger.info("执行结果:")
            logger.info(f"    状态: {result.get('status', '未知')}")
            logger.info(f"    消息: {result.get('message', '无消息')}")
            logger.info(f"    价格: {result.get('price', 0)}")
            logger.info(f"    数量: {result.get('volume', 0)}")
            logger.info(f"    金额: {result.get('amount', 0)}")
            logger.info("="*50)
            
        except (InvalidTimeError, NoPositionError) as e:
            # 这些是预期内的交易限制，使用 INFO 级别记录
            logger.info(f"【策略受限】策略执行受限 - 原因: {str(e)}")
            logger.info("="*50)
        except (InsufficientFundsError, FrequencyLimitError, 
                PositionLimitError, PriceDeviationError, PriceNotMatchError) as e:
            # 这些是需要关注的交易限制，使用 WARNING 级别记录
            if isinstance(e, PriceNotMatchError):
                logger.warning(f"【价格不匹配】策略执行受限 - 股票: {strategy.get('stock_code')}, 原因: {str(e)}")
                # 记录策略信息以便后续调整
                logger.warning(f"【策略详情】ID: {strategy.get('id')}, 价格区间: [{strategy.get('price_min')}, {strategy.get('price_max')}]")
                # 价格不匹配时，策略状态保持为pending，不更新为partial
                logger.info(f"【策略状态】策略 {strategy.get('id')} 因价格不匹配暂未执行，状态保持为pending")
            else:
                logger.warning(f"【策略受限】策略执行受限 - 原因: {str(e)}")
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
            
            # 验证策略列表格式
            if not isinstance(strategies, list):
                logger.error(f"策略数据格式错误: 预期列表类型，实际为 {type(strategies)}")
                return
                
            logger.info(f"获取到 {len(strategies)} 个有效策略")
            
            # 执行每个策略
            for strategy in strategies:
                if not isinstance(strategy, dict):
                    logger.error(f"策略数据格式错误: 预期字典类型，实际为 {type(strategy)}")
                    continue
                self.execute_strategy(strategy)
                
        except Exception as e:
            logger.error(f"检查执行策略异常: {str(e)}", exc_info=True)
            
    def update_assets(self) -> None:
        """更新资产信息"""
        try:
            assets = self.trader.update_assets()
            
            # 验证assets是否为字典类型
            if not isinstance(assets, dict):
                logger.error(f"资产数据格式错误: 预期字典类型，实际为 {type(assets)}")
                return
                
            logger.info(f"资产更新完成 - 总资产: {assets.get('total_assets', 0.0):.2f}, "
                       f"现金: {assets.get('available_cash', 0.0):.2f}")
        except Exception as e:
            logger.error(f"更新资产信息异常: {str(e)}", exc_info=True)
            
    def health_check(self) -> bool:
        """
        健康检查，检查API连接状态
        """
        try:
            logger.info("执行健康检查...")
            # 获取健康检查路径
            health_path = config.get('api.health_path', '/ping')
            
            # 尝试的路径列表，按优先级排序
            paths_to_try = [
                health_path,  # 配置的健康检查路径
                '/ping',      # 简单的ping接口
                '/health',    # 标准健康检查接口
                '/',          # API根路径
            ]
            
            # 尝试所有路径
            for path in paths_to_try:
                try:
                    response = requests.get(f"{self.trader.base_url}{path}", timeout=config.get('api.timeout', 10))
                    if 200 <= response.status_code < 300:  # 只有2xx状态码才表示成功
                        logger.info(f"健康检查成功，路径: {path}，状态码: {response.status_code}")
                        return True
                    elif response.status_code == 404:
                        # 404表示路径不存在，但服务器在运行
                        logger.warning(f"健康检查路径不存在，路径: {path}，状态码: 404，服务器可能正常但缺少此接口")
                        # 继续尝试其他路径
                    else:
                        logger.warning(f"健康检查失败，路径: {path}，状态码: {response.status_code}")
                except Exception as e:
                    logger.warning(f"健康检查异常，路径: {path}，错误: {str(e)}")
            
            # 如果所有路径都失败，尝试重新初始化交易模块
            logger.warning("所有健康检查路径均失败，尝试重新初始化交易模块")
            self.trader._check_api_connection()
            return False
        except Exception as e:
            logger.error(f"健康检查异常: {str(e)}")
            # 尝试重新初始化交易模块
            self.trader._check_api_connection()
            return False
            
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
            
            # 添加健康检查任务
            self.scheduler.add_job(
                self.health_check,
                IntervalTrigger(seconds=config.get('monitor.health_check_interval')),
                id='health_check',
                replace_existing=True
            )
            
            # 启动调度器
            self.scheduler.start()
            logger.info(f"交易应用已启动，策略检查间隔：{config.get('monitor.check_interval')} 秒，"
                       f"资产更新间隔：{config.get('cache.position_ttl')} 秒，"
                       f"健康检查间隔：{config.get('monitor.health_check_interval')} 秒")
            
            # 立即执行一次资产更新和策略检查
            logger.info("执行首次资产更新...")
            self.update_assets()
            logger.info("执行首次策略检查...")
            self.check_and_execute_strategies()
            logger.info("执行首次健康检查...")
            self.health_check()
            
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
            
    def _update_strategy_status(self, strategy_id, status):
        """
        更新策略状态
        
        Args:
            strategy_id: 策略ID
            status: 新状态 (pending/partial/completed)
        """
        try:
            api_url = f"{self.trader.base_url}/strategies/{strategy_id}"
            update_data = {
                "execution_status": status
            }
            
            response = requests.put(
                api_url,
                json=update_data,
                timeout=config.get('api.timeout', 10)
            )
            response.raise_for_status()
            result = response.json()
            
            if result['code'] != 200:
                logger.error(f"【API错误】更新策略状态失败: {result.get('message', '未知错误')}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"【更新异常】更新策略状态异常: {str(e)}")
            return False
            
def main():
    """主函数"""
    try:
        # 配置日志
        logger = setup_logging()
        logger.info("="*50)
        logger.info("程序启动")
        logger.info("="*50)
        
        # 创建应用
        app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindow()
        window.show()
        
        # 运行应用
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"程序异常: {str(e)}", exc_info=True)
        sys.exit(1)
        
if __name__ == '__main__':
    main() 