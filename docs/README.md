# 量化交易自动化客户端产品需求文档

## 1. 产品概述

### 1.1 产品定位
本产品是一个无界面的自动化量化交易客户端程序，通过定时调用策略服务接口进行股票交易。程序会根据预设的交易策略，在满足特定条件时自动执行买入或卖出操作，实现交易的自动化和智能化。

### 1.2 目标用户
- 量化交易团队
- 自动化交易系统开发者
- 算法交易策略研究者

### 1.3 核心价值
- 提高交易效率
- 降低人为操作风险
- 保证策略执行的一致性
- 实现 7x24 小时自动化监控

## 2. 功能模块

### 2.1 策略管理模块
1. **策略监控**
   - 定时轮询获取有效策略列表
   - 自动过滤已完成和已失效的策略
   - 支持多策略并行监控
   - 实时更新策略执行状态

2. **策略分析**
   - 解析策略执行条件
   - 验证策略有效性
   - 计算目标交易量
   - 评估执行可行性

### 2.2 交易执行模块
1. **条件检测**
   - 实时获取股票行情
   - 价格区间判断
   - 止盈止损条件检查
   - 交易时间窗口验证

2. **交易控制**
   - 自动计算交易数量
   - 持仓限额检查
   - 资金充足性验证
   - 分批执行管理

3. **风险控制**
   - 单笔交易限额
   - 持仓比例限制
   - 价格偏离度检查
   - 频率限制

### 2.3 持仓管理模块
1. **持仓监控**
   - 实时更新持仓信息
   - 计算持仓成本
   - 统计盈亏情况
   - 风险度评估

2. **资金管理**
   - 可用资金计算
   - 资金使用率监控
   - 盈亏实时统计
   - 成本动态更新

### 2.4 执行记录模块
1. **交易记录**
   - 详细记录每笔交易
   - 执行结果跟踪
   - 异常情况记录
   - 执行状态更新

2. **统计分析**
   - 策略执行效果分析
   - 成功率统计
   - 盈亏分析
   - 偏差分析

## 3. 业务流程

### 3.1 策略执行流程
1. **策略获取**
   - 定时轮询策略接口
   - 获取待执行策略列表
   - 过滤无效策略
   - 排序确定执行优先级

2. **执行条件检查**
   - 价格条件验证
   - 时间窗口检查
   - 持仓限制验证
   - 资金充足性检查

3. **交易执行**
   - 计算执行数量
   - 提交交易请求
   - 更新策略状态
   - 记录执行结果

4. **结果处理**
   - 更新持仓信息
   - 计算最新盈亏
   - 更新策略状态
   - 生成执行报告

### 3.2 风险控制流程
1. **交易前检查**
   - 资金规模检查
   - 持仓比例检查
   - 价格偏离检查
   - 频率限制检查

2. **执行中监控**
   - 实时价格监控
   - 成交状态跟踪
   - 资金变动监控
   - 风险指标计算

3. **异常处理**
   - 超时处理
   - 失败重试
   - 应急止损
   - 错误恢复

### 3.3 监控报告流程
1. **实时监控**
   - 系统状态监控
   - 策略执行监控
   - 持仓状态监控
   - 资金状态监控

2. **报告生成**
   - 执行情况汇总
   - 盈亏统计分析
   - 异常情况统计
   - 性能指标统计

## 4. 系统要求

### 4.1 性能要求
- 策略轮询间隔：30秒
- 价格更新延迟：<1秒
- 交易响应时间：<3秒
- 系统运行时间：>99.9%

### 4.2 安全要求
- 完整的错误处理机制
- 交易指令安全校验
- 资金安全保护
- 数据加密传输

### 4.3 可靠性要求
- 故障自动恢复
- 数据实时备份
- 操作日志完整
- 异常自动报警

## 5. 运维要求

### 5.1 监控要求
- 系统运行状态
- 策略执行情况
- 资源使用情况
- 错误和异常

### 5.2 报警要求
- 系统异常报警
- 策略执行异常
- 资金异常波动
- 持仓异常变动

### 5.3 日志要求
- 详细的操作日志
- 完整的错误日志
- 性能监控日志
- 交易执行日志

## 6. 接口调用说明

### 6.1 策略管理接口
1. **获取策略列表**
   - 接口：GET `/api/v1/strategies`
   - 参数：
     * `is_active`: true（只获取有效策略）
     * `execution_status`: ['pending', 'partial']（未执行或部分执行）
   - 处理逻辑：
     * 定时轮询（30秒间隔）
     * 缓存策略列表用于比对变化
     * 按更新时间排序确定优先级

2. **更新策略状态**
   - 接口：PUT `/api/v1/strategies/{id}`
   - 参数：
     * `execution_status`: 策略执行状态
     * `position_ratio`: 剩余仓位比例
   - 处理逻辑：
     * 执行完成后更新状态
     * 部分执行时更新剩余仓位

### 6.2 交易执行接口
1. **创建执行记录**
   - 接口：POST `/api/v1/executions`
   - 参数：
     * `strategy_id`: 策略ID
     * `execution_price`: 执行价格
     * `volume`: 交易量
     * `strategy_status`: 策略状态（partial/completed）
   - 处理逻辑：
     * 验证执行价格在区间内
     * 检查是否触发止盈止损
     * 计算合适的交易量
     * 确认是否完成策略目标

2. **查询执行记录**
   - 接口：GET `/api/v1/executions`
   - 参数：
     * `strategy_id`: 策略ID
     * `start_time`: 开始时间
     * `end_time`: 结束时间
   - 处理逻辑：
     * 统计执行效果
     * 分析成功率
     * 计算平均偏差

### 6.3 持仓管理接口
1. **查询持仓信息**
   - 接口：GET `/api/v1/positions/{stock_code}`
   - 处理逻辑：
     * 验证是否有足够持仓
     * 计算可用数量
     * 检查持仓限额

2. **更新持仓市值**
   - 接口：PUT `/api/v1/positions/{stock_code}/market_value`
   - 参数：
     * `latest_price`: 最新价格
   - 处理逻辑：
     * 定时更新市值
     * 计算浮动盈亏
     * 评估风险度

### 6.4 逻辑处理要点

1. **交易时间判断**
   ```
   交易时间：
   - 上午：09:30 - 11:30
   - 下午：13:00 - 15:00
   - 排除节假日
   ```

2. **价格条件判断**
   ```
   买入条件：
   - 现价 >= price_min
   - 现价 <= price_max
   - 现价 > stop_loss_price
   - 现价 < take_profit_price

   卖出条件：
   - 现价 <= stop_loss_price
   - 现价 >= take_profit_price
   ```

3. **交易量计算**
   ```
   买入数量 = min(
     floor(可用资金 * position_ratio / 最新价格),
     floor(单笔最大交易额 / 最新价格)
   )

   卖出数量 = min(
     floor(持仓数量 * position_ratio),
     持仓数量
   )
   ```

4. **风险控制**
   ```
   交易限制：
   - 单笔交易额 <= 最大交易限额
   - 持仓市值占比 <= 最大持仓比例
   - 价格偏离度 <= 允许偏差
   - 每分钟交易次数 <= 频率限制
   ```

5. **异常处理**
   ```
   重试策略：
   - 网络超时：最多重试3次
   - API错误：等待5秒后重试
   - 价格获取失败：切换备用数据源
   - 执行失败：记录原因并报警
   ```

6. **状态更新**
   ```
   策略状态：
   - pending -> partial：首次部分执行
   - partial -> completed：完成所有目标
   - completed -> partial：增加目标仓位
   
   持仓状态：
   - 买入：增加持仓、更新成本
   - 卖出：减少持仓、确认盈亏
   - 清仓：删除持仓记录
   ```

### 6.5 数据缓存策略

1. **行情数据**
   - 缓存时间：1秒
   - 定时更新：实时行情
   - 缓存内容：最新价、涨跌幅

2. **策略数据**
   - 缓存时间：30秒
   - 定时更新：策略列表
   - 缓存内容：有效策略详情

3. **持仓数据**
   - 缓存时间：1分钟
   - 定时更新：持仓市值
   - 缓存内容：持仓明细、盈亏

## 健康检查与API连接

QMT客户端实现了健壮的API连接机制，支持以下特性：

1. **多路径健康检查**：系统会尝试多种健康检查路径，确保能够连接到服务器
   - 配置的健康检查路径（默认为 `/ping`）
   - `/ping` - 简单的ping接口
   - `/health` - 标准健康检查接口
   - `/` - API根路径

2. **备用API支持**：当主API不可用时，系统会自动尝试切换到备用API
   - 在配置文件中可以设置多个备用API地址
   - 系统会按顺序尝试连接，直到找到可用的API

3. **多路径API访问**：系统支持多种API路径格式，增强兼容性
   - 持仓查询支持多种路径格式
   - 账户资金查询支持多种路径格式

4. **定期健康检查**：系统会定期执行健康检查，确保API连接正常
   - 健康检查间隔可在配置文件中设置
   - 当检测到API连接异常时，会自动尝试重新连接

5. **错误处理与恢复**：系统实现了完善的错误处理机制
   - 当API请求失败时，会尝试使用本地缓存数据
   - 提供详细的日志记录，便于问题诊断 