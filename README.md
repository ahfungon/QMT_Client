# QMT交易助手

QMT交易助手是一个基于Python的自动化交易程序，支持策略管理、自动交易和持仓管理等功能。

## 功能特点

- 策略管理：支持创建、修改和删除交易策略
- 自动交易：根据策略自动执行交易
- 持仓管理：实时监控持仓状态和盈亏情况
- 资金管理：自动计算交易费用和资金分配
- 可视化界面：直观展示交易和持仓信息

## 系统要求

- Python 3.10或更高版本
- Windows 10/11操作系统
- 2GB以上可用内存
- 显示器分辨率不低于1920x1080

## 安装步骤

1. 克隆代码仓库：
```bash
git clone https://github.com/your-username/qmt-client.git
cd qmt-client
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置参数：
- 复制`config/config.example.yaml`为`config/config.yaml`
- 根据实际情况修改配置参数

4. 启动程序：
- Windows: 双击`start.bat`
- 命令行：`python run.py`

## 使用说明

1. 策略管理
- 在"策略管理"页面可以查看和管理交易策略
- 支持添加、修改和删除策略
- 可以设置交易条件和参数

2. 持仓管理
- 在"持仓管理"页面可以查看当前持仓
- 实时显示持仓盈亏情况
- 支持手动交易操作

3. 订单管理
- 在"订单管理"页面可以查看交易订单
- 显示订单状态和执行情况
- 支持撤单操作

4. 成交记录
- 在"成交记录"页面可以查看历史成交
- 记录详细的交易信息
- 支持数据导出

## 开发说明

1. 项目结构
```
qmt-client/
├── config/         # 配置文件
├── data/          # 数据文件
├── docs/          # 文档
├── logs/          # 日志文件
├── src/           # 源代码
│   ├── broker/    # 券商接口
│   ├── core/      # 核心模块
│   ├── models/    # 数据模型
│   ├── ui/        # 界面模块
│   └── utils/     # 工具模块
├── tests/         # 测试代码
├── README.md      # 说明文档
├── requirements.txt # 依赖列表
└── run.py         # 启动文件
```

2. 开发规范
- 使用Python类型注解
- 遵循PEP 8编码规范
- 编写单元测试
- 添加详细注释

3. 测试运行
```bash
# 运行所有测试
pytest

# 运行指定测试
pytest tests/test_trader.py

# 生成测试覆盖率报告
pytest --cov=src tests/
```

## 常见问题

1. 程序无法启动
- 检查Python版本是否正确
- 检查依赖是否安装完整
- 查看日志文件了解详细错误

2. 界面显示异常
- 检查显示器分辨率设置
- 确认PyQt6安装正确
- 尝试重新启动程序

3. 交易执行失败
- 检查网络连接
- 确认账户资金是否充足
- 查看日志了解具体原因

## 更新日志

### v1.0.0 (2024-03-21)
- 实现基础交易功能
- 添加可视化界面
- 支持策略管理
- 实现自动交易

## 联系方式

- 作者：Your Name
- 邮箱：your.email@example.com
- GitHub：https://github.com/your-username

## 许可证

本项目采用MIT许可证，详见[LICENSE](LICENSE)文件。 