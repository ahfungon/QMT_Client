"""主窗口模块"""
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QStatusBar, QMessageBox, QHeaderView, QGroupBox,
    QTextEdit, QDialog, QLineEdit, QFormLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QBrush
from src.broker.simulator import SimulatedBroker
from src.core.trader import Trader
from src.core.strategy_manager import StrategyManager

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """主窗口类"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QMT交易助手")
        self.resize(1200, 800)
        
        # 初始化交易组件
        self.init_trading()
        
        # 创建中心部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 创建布局
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 创建顶部工具栏
        self.create_toolbar()
        
        # 创建账户信息区域
        self.create_account_info()
        
        # 创建主要内容区域
        self.create_content()
        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")
        
        # 创建定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)  # 每秒更新一次
        
    def init_trading(self):
        """初始化交易组件"""
        try:
            # 创建模拟交易接口
            self.broker = SimulatedBroker()
            
            # 创建交易核心
            self.trader = Trader(self.broker)
            
            # 创建策略管理器
            self.strategy_manager = StrategyManager(self.trader)
            
            logger.info("交易组件初始化成功")
        except Exception as e:
            logger.error(f"交易组件初始化失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"交易组件初始化失败: {str(e)}")
        
    def create_toolbar(self):
        """创建工具栏"""
        toolbar_layout = QHBoxLayout()
        
        # 创建按钮
        self.btn_start = QPushButton("启动")
        self.btn_stop = QPushButton("停止")
        self.btn_add_strategy = QPushButton("添加策略")
        self.btn_settings = QPushButton("设置")
        
        # 添加按钮到布局
        toolbar_layout.addWidget(self.btn_start)
        toolbar_layout.addWidget(self.btn_stop)
        toolbar_layout.addWidget(self.btn_add_strategy)
        toolbar_layout.addWidget(self.btn_settings)
        toolbar_layout.addStretch()
        
        # 连接信号
        self.btn_start.clicked.connect(self.on_start)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_add_strategy.clicked.connect(self.on_add_strategy)
        self.btn_settings.clicked.connect(self.on_settings)
        
        self.main_layout.addLayout(toolbar_layout)
        
    def create_account_info(self):
        """创建账户信息区域"""
        account_group = QGroupBox("账户信息")
        account_layout = QHBoxLayout()
        
        # 创建标签
        self.label_total_assets = QLabel("总资产: 0.00")
        self.label_available_funds = QLabel("可用资金: 0.00")
        self.label_frozen_funds = QLabel("冻结资金: 0.00")
        self.label_total_profit = QLabel("总盈亏: 0.00")
        self.label_total_profit_ratio = QLabel("总收益率: 0.00%")
        
        # 设置字体
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        for label in [self.label_total_assets, self.label_available_funds,
                     self.label_frozen_funds, self.label_total_profit,
                     self.label_total_profit_ratio]:
            label.setFont(font)
            account_layout.addWidget(label)
            
        account_group.setLayout(account_layout)
        self.main_layout.addWidget(account_group)
        
    def create_content(self):
        """创建主要内容区域"""
        content_layout = QVBoxLayout()
        
        # 创建上半部分布局（策略和持仓）
        upper_layout = QHBoxLayout()
        
        # 创建左侧策略列表
        strategy_group = QGroupBox("策略列表")
        strategy_layout = QVBoxLayout()
        self.strategy_table = QTableWidget()
        self.strategy_table.setColumnCount(7)
        self.strategy_table.setHorizontalHeaderLabels([
            "股票", "方向", "仓位比例", "价格区间",
            "止盈价", "止损价", "状态"
        ])
        self.strategy_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        strategy_layout.addWidget(self.strategy_table)
        strategy_group.setLayout(strategy_layout)
        
        # 创建右侧持仓列表
        position_group = QGroupBox("持仓列表")
        position_layout = QVBoxLayout()
        self.position_table = QTableWidget()
        self.position_table.setColumnCount(7)
        self.position_table.setHorizontalHeaderLabels([
            "股票", "持仓量", "可用量", "成本价",
            "现价", "市值", "盈亏比例"
        ])
        self.position_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        position_layout.addWidget(self.position_table)
        position_group.setLayout(position_layout)
        
        # 添加到上半部分布局
        upper_layout.addWidget(strategy_group)
        upper_layout.addWidget(position_group)
        
        # 创建下半部分执行记录列表
        execution_group = QGroupBox("执行记录")
        execution_layout = QVBoxLayout()
        self.execution_table = QTableWidget()
        self.execution_table.setColumnCount(8)
        self.execution_table.setHorizontalHeaderLabels([
            "时间", "股票", "方向", "价格", "数量", 
            "仓位比例", "执行结果", "备注"
        ])
        self.execution_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        execution_layout.addWidget(self.execution_table)
        execution_group.setLayout(execution_layout)
        
        # 添加到主布局
        content_layout.addLayout(upper_layout)
        content_layout.addWidget(execution_group)
        
        self.main_layout.addLayout(content_layout)
        
    def on_start(self):
        """启动按钮点击事件"""
        try:
            reply = QMessageBox.question(
                self, "确认", "确定要启动交易程序吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.statusBar.showMessage("正在启动...")
                if self.strategy_manager.start():
                    self.statusBar.showMessage("启动成功")
                    self.btn_start.setEnabled(False)
                    self.btn_stop.setEnabled(True)
                else:
                    self.statusBar.showMessage("启动失败")
        except Exception as e:
            logger.error(f"启动失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"启动失败: {str(e)}")
            
    def on_stop(self):
        """停止按钮点击事件"""
        try:
            reply = QMessageBox.question(
                self, "确认", "确定要停止交易程序吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.statusBar.showMessage("正在停止...")
                if self.strategy_manager.stop():
                    self.statusBar.showMessage("停止成功")
                    self.btn_start.setEnabled(True)
                    self.btn_stop.setEnabled(False)
                else:
                    self.statusBar.showMessage("停止失败")
        except Exception as e:
            logger.error(f"停止失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"停止失败: {str(e)}")
            
    def on_add_strategy(self):
        """添加策略按钮点击事件"""
        dialog = AddStrategyDialog(self.strategy_manager, self)
        dialog.exec()
        
    def on_settings(self):
        """设置按钮点击事件"""
        QMessageBox.information(self, "提示", "设置功能开发中...")
        
    def update_status(self):
        """更新状态"""
        try:
            # 更新账户信息
            self.update_account_info()
            
            # 更新策略列表
            self.update_strategy_table()
            
            # 更新持仓列表
            self.update_position_table()
            
            # 更新执行记录列表
            self.update_execution_table()
            
            # 更新状态栏
            if self.strategy_manager.is_running:
                self.statusBar.showMessage("运行中")
            else:
                self.statusBar.showMessage("已停止")
        except Exception as e:
            logger.error(f"更新状态失败: {str(e)}")
            
    def update_account_info(self):
        """更新账户信息"""
        try:
            # 获取账户信息
            account_info = self.strategy_manager.get_account_info()
            if account_info:
                # 更新标签
                self.label_total_assets.setText(f"总资产: {account_info['total_assets']:,.2f}")
                self.label_available_funds.setText(f"可用资金: {account_info['available_funds']:,.2f}")
                self.label_frozen_funds.setText(f"冻结资金: {account_info['frozen_funds']:,.2f}")
                self.label_total_profit.setText(f"总盈亏: {account_info['total_profit']:,.2f}")
                self.label_total_profit_ratio.setText(f"总收益率: {account_info['total_profit_ratio']:.2f}%")
                
                # 设置颜色
                if account_info['total_profit'] > 0:
                    color = QColor(255, 0, 0)  # 红色表示盈利
                elif account_info['total_profit'] < 0:
                    color = QColor(0, 255, 0)  # 绿色表示亏损
                else:
                    color = QColor(0, 0, 0)  # 黑色表示持平
                    
                self.label_total_profit.setStyleSheet(f"color: {color.name()}")
                self.label_total_profit_ratio.setStyleSheet(f"color: {color.name()}")
                
        except Exception as e:
            logger.error(f"更新账户信息失败: {str(e)}")
            
    def update_strategy_table(self):
        """更新策略列表"""
        try:
            # 获取策略列表
            strategies = self.strategy_manager.get_strategies()
            if not strategies:
                logger.info("没有可用的策略")
                self.strategy_table.setRowCount(0)
                return
                
            # 设置表格行数
            self.strategy_table.setRowCount(len(strategies))
            
            # 填充数据
            for row, strategy in enumerate(strategies):
                try:
                    # 股票信息
                    stock_info = f"{strategy.get('stock_name', '')}({strategy.get('stock_code', '')})"
                    self.strategy_table.setItem(row, 0, QTableWidgetItem(stock_info))
                    
                    # 交易方向
                    action = strategy.get('action', '')
                    action_text = {
                        'buy': '买入',
                        'sell': '卖出',
                        'add': '加仓',
                        'trim': '减仓',
                        'hold': '持有'
                    }.get(action, '未知')
                    self.strategy_table.setItem(row, 1, QTableWidgetItem(action_text))
                    
                    # 仓位比例
                    position_ratio = strategy.get('position_ratio', 0)
                    if position_ratio is not None:
                        ratio_text = f"{position_ratio:.2f}%"
                    else:
                        ratio_text = "0.00%"
                    self.strategy_table.setItem(row, 2, QTableWidgetItem(ratio_text))
                    
                    # 价格区间
                    price_min = strategy.get('price_min')
                    price_max = strategy.get('price_max')
                    if price_min is not None and price_max is not None:
                        price_range = f"{price_min:.2f}-{price_max:.2f}"
                    else:
                        price_range = "未设置"
                    self.strategy_table.setItem(row, 3, QTableWidgetItem(price_range))
                    
                    # 止盈价
                    take_profit = strategy.get('take_profit_price')
                    if take_profit is not None:
                        take_profit_text = f"{take_profit:.2f}"
                    else:
                        take_profit_text = "未设置"
                    self.strategy_table.setItem(row, 4, QTableWidgetItem(take_profit_text))
                    
                    # 止损价
                    stop_loss = strategy.get('stop_loss_price')
                    if stop_loss is not None:
                        stop_loss_text = f"{stop_loss:.2f}"
                    else:
                        stop_loss_text = "未设置"
                    self.strategy_table.setItem(row, 5, QTableWidgetItem(stop_loss_text))
                    
                    # 执行状态
                    status = strategy.get('execution_status', '')
                    status_text = {
                        'pending': '待执行',
                        'partial': '部分执行',
                        'completed': '已完成',
                        'failed': '执行失败'
                    }.get(status, '未知')
                    status_item = QTableWidgetItem(status_text)
                    
                    # 设置状态颜色
                    if status == 'completed':
                        status_item.setForeground(QBrush(QColor('#28a745')))  # 绿色
                    elif status == 'partial':
                        status_item.setForeground(QBrush(QColor('#ffc107')))  # 黄色
                    elif status == 'failed':
                        status_item.setForeground(QBrush(QColor('#dc3545')))  # 红色
                        
                    self.strategy_table.setItem(row, 6, status_item)
                    
                except Exception as e:
                    logger.error(f"处理策略数据时出错: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"更新策略列表失败: {str(e)}")
            
    def update_position_table(self):
        """更新持仓列表"""
        try:
            # 获取持仓列表
            positions = self.strategy_manager.get_positions()
            if not positions:
                logger.info("没有持仓记录")
                self.position_table.setRowCount(0)
                return
                
            # 设置表格行数
            self.position_table.setRowCount(len(positions))
            
            # 填充数据
            for row, position in enumerate(positions):
                try:
                    # 股票信息
                    stock_info = f"{position.get('stock_name', '')}({position.get('stock_code', '')})"
                    self.position_table.setItem(row, 0, QTableWidgetItem(stock_info))
                    
                    # 总持仓
                    total_volume = position.get('total_volume', 0)
                    self.position_table.setItem(row, 1, QTableWidgetItem(str(total_volume)))
                    
                    # 可用持仓
                    total_volume = position.get('total_volume', 0)
                    frozen_volume = position.get('frozen_volume', 0)
                    available = total_volume - frozen_volume
                    self.position_table.setItem(row, 2, QTableWidgetItem(str(available)))
                    
                    # 成本价
                    cost = position.get('dynamic_cost', 0)
                    if cost > 0:
                        cost_text = f"{cost:.2f}"
                    else:
                        cost_text = "0.00"
                    self.position_table.setItem(row, 3, QTableWidgetItem(cost_text))
                    
                    # 最新价
                    price = position.get('latest_price', 0)
                    if price > 0:
                        price_text = f"{price:.2f}"
                    else:
                        price_text = "0.00"
                    self.position_table.setItem(row, 4, QTableWidgetItem(price_text))
                    
                    # 市值
                    market_value = position.get('market_value', 0)
                    if market_value > 0:
                        value_text = f"{market_value:.2f}"
                    else:
                        value_text = "0.00"
                    self.position_table.setItem(row, 5, QTableWidgetItem(value_text))
                    
                    # 盈亏比例
                    profit_ratio = position.get('floating_profit_ratio', 0)
                    if profit_ratio == 999999:
                        ratio_text = "♾️"
                    else:
                        ratio_text = f"{profit_ratio:.2f}%"
                        
                    ratio_item = QTableWidgetItem(ratio_text)
                    if profit_ratio > 0:
                        ratio_item.setForeground(QBrush(QColor('#28a745')))  # 绿色
                    elif profit_ratio < 0:
                        ratio_item.setForeground(QBrush(QColor('#dc3545')))  # 红色
                        
                    self.position_table.setItem(row, 6, ratio_item)
                    
                except Exception as e:
                    logger.error(f"处理持仓数据时出错: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"更新持仓列表失败: {str(e)}")
            
    def update_execution_table(self):
        """更新执行记录列表"""
        try:
            # 获取执行记录列表
            executions = self.strategy_manager.get_executions()
            
            if executions is None:
                self.execution_table.setRowCount(0)
                return
                
            if not executions:
                self.execution_table.setRowCount(0)
                return
                
            self.execution_table.setRowCount(len(executions))
            
            for row, execution in enumerate(executions):
                try:
                    # 执行时间
                    execution_time = execution.get('execution_time', '')
                    self.execution_table.setItem(
                        row, 0,
                        QTableWidgetItem(execution_time)
                    )
                    
                    # 股票信息
                    stock_name = execution.get('stock_name', '')
                    stock_code = execution.get('stock_code', '')
                    self.execution_table.setItem(
                        row, 1,
                        QTableWidgetItem(f"{stock_name}({stock_code})" if stock_name and stock_code else "未知")
                    )
                    
                    # 交易方向
                    action = execution.get('action', '')
                    action_text = {
                        'buy': '买入',
                        'sell': '卖出',
                        'add': '加仓',
                        'trim': '减仓',
                        'hold': '持有'
                    }.get(action, '未知')
                    self.execution_table.setItem(row, 2, QTableWidgetItem(action_text))
                    
                    # 成交价格
                    execution_price = execution.get('execution_price', 0)
                    self.execution_table.setItem(
                        row, 3,
                        QTableWidgetItem(f"{execution_price:.3f}" if execution_price else "0.000")
                    )
                    
                    # 成交数量
                    volume = execution.get('volume', 0)
                    self.execution_table.setItem(
                        row, 4,
                        QTableWidgetItem(f"{volume:,}" if volume else "0")
                    )
                    
                    # 仓位比例
                    position_ratio = execution.get('position_ratio', 0)
                    self.execution_table.setItem(
                        row, 5,
                        QTableWidgetItem(f"{position_ratio:.1f}%" if position_ratio is not None else "0.0%")
                    )
                    
                    # 执行结果
                    result = execution.get('execution_result', '')
                    result_text = {
                        'success': '成功',
                        'partial': '部分成功',
                        'failed': '失败'
                    }.get(result, '未知')
                    
                    result_item = QTableWidgetItem(result_text)
                    if result == 'success':
                        result_item.setForeground(QColor(0, 128, 0))  # 绿色表示成功
                    elif result == 'partial':
                        result_item.setForeground(QColor(255, 165, 0))  # 橙色表示部分成功
                    elif result == 'failed':
                        result_item.setForeground(QColor(255, 0, 0))  # 红色表示失败
                        
                    self.execution_table.setItem(row, 6, result_item)
                    
                    # 备注
                    remarks = execution.get('remarks', '')
                    self.execution_table.setItem(row, 7, QTableWidgetItem(remarks))
                    
                except Exception as e:
                    logger.error(f"处理执行记录 {row} 时出错: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"更新执行记录列表失败: {str(e)}")
            self.execution_table.setRowCount(0)
            
    def closeEvent(self, event):
        """关闭窗口事件"""
        try:
            reply = QMessageBox.question(
                self, "确认", "确定要退出程序吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 停止策略管理器
                if self.strategy_manager.is_running:
                    self.strategy_manager.stop()
                    
                # 停止定时器
                self.timer.stop()
                
                event.accept()
            else:
                event.ignore()
        except Exception as e:
            logger.error(f"关闭窗口失败: {str(e)}")
            event.accept()
            
class AddStrategyDialog(QDialog):
    """添加策略对话框"""
    def __init__(self, strategy_manager: StrategyManager, parent=None):
        super().__init__(parent)
        self.strategy_manager = strategy_manager
        self.setWindowTitle("添加策略")
        self.resize(600, 400)
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 创建表单
        form_layout = QFormLayout()
        
        # 创建输入框
        self.strategy_text = QTextEdit()
        self.strategy_text.setPlaceholderText("请输入策略描述，例如：买入贵州茅台（600519）100股")
        form_layout.addRow("策略描述:", self.strategy_text)
        
        # 添加到主布局
        layout.addLayout(form_layout)
        
        # 创建分析结果显示区域
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(QLabel("分析结果:"))
        layout.addWidget(self.result_text)
        
        # 创建按钮
        button_layout = QHBoxLayout()
        self.btn_analyze = QPushButton("分析")
        self.btn_confirm = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        
        button_layout.addWidget(self.btn_analyze)
        button_layout.addWidget(self.btn_confirm)
        button_layout.addWidget(self.btn_cancel)
        
        # 连接信号
        self.btn_analyze.clicked.connect(self.on_analyze)
        self.btn_confirm.clicked.connect(self.on_confirm)
        self.btn_cancel.clicked.connect(self.reject)
        
        layout.addLayout(button_layout)
        
    def on_analyze(self):
        """分析按钮点击事件"""
        try:
            # 获取策略文本
            strategy_text = self.strategy_text.toPlainText().strip()
            if not strategy_text:
                QMessageBox.warning(self, "警告", "请输入策略描述")
                return
                
            # 分析策略
            result = self.strategy_manager.analyze_strategy(strategy_text)
            if not result:
                QMessageBox.warning(self, "警告", "策略分析失败")
                return
                
            # 显示分析结果
            self.result_text.clear()
            self.result_text.append(f"股票: {result['stock_name']}({result['stock_code']})")
            self.result_text.append(f"操作: {'买入' if result['action'] == 'buy' else '卖出'}")
            self.result_text.append(f"建议仓位: {result['position_ratio']:.1f}%")
            self.result_text.append(f"分析结果: {result['analysis_result']}")
            self.result_text.append(f"置信度: {result['confidence']:.2f}")
            
            # 显示市场分析
            market = result.get('market_analysis', {})
            if market:
                self.result_text.append("\n市场分析:")
                self.result_text.append(f"当前价格: {market['current_price']:.2f}")
                self.result_text.append(f"市盈率: {market['pe_ratio']:.1f}")
                self.result_text.append(f"市净率: {market['pb_ratio']:.1f}")
                self.result_text.append(f"市场趋势: {market['market_trend']}")
                
        except Exception as e:
            logger.error(f"分析策略失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"分析策略失败: {str(e)}")
            
    def on_confirm(self):
        """确定按钮点击事件"""
        try:
            # 获取策略文本
            strategy_text = self.strategy_text.toPlainText().strip()
            if not strategy_text:
                QMessageBox.warning(self, "警告", "请输入策略描述")
                return
                
            # 分析策略
            result = self.strategy_manager.analyze_strategy(strategy_text)
            if not result:
                QMessageBox.warning(self, "警告", "策略分析失败")
                return
                
            # 检查是否已存在相同策略
            exists = self.strategy_manager.check_strategy_exists(
                result['stock_code'],
                result['action']
            )
            if exists:
                QMessageBox.warning(self, "警告", "已存在相同的策略")
                return
                
            # 创建策略
            strategy = {
                'stock_name': result['stock_name'],
                'stock_code': result['stock_code'],
                'action': result['action'],
                'position_ratio': result['position_ratio'],
                'price_min': result['market_analysis']['current_price'] * 0.98,  # 默认下限-2%
                'price_max': result['market_analysis']['current_price'] * 1.02,  # 默认上限+2%
                'take_profit_price': result['market_analysis']['current_price'] * 1.05,  # 默认止盈+5%
                'stop_loss_price': result['market_analysis']['current_price'] * 0.95,  # 默认止损-5%
                'other_conditions': result['analysis_result'],
                'reason': f"AI分析建议（置信度: {result['confidence']:.2f}）"
            }
            
            # 提交策略
            if self.strategy_manager.create_strategy(strategy):
                QMessageBox.information(self, "提示", "策略创建成功")
                self.accept()
            else:
                QMessageBox.warning(self, "警告", "策略创建失败")
                
        except Exception as e:
            logger.error(f"创建策略失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"创建策略失败: {str(e)}") 