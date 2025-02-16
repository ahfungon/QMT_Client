# QMT Server API 文档

## 基础信息

- 基础URL: 
  - `http://localhost:5000/api/v1`
  - `http://127.0.0.1:5000/api/v1`
- 所有响应格式均为 JSON
- 时间格式: `YYYY-MM-DD HH:mm:ss`

## 通用响应格式

```json
{
    "code": 200,       // 状态码
    "message": "成功",  // 响应消息
    "data": {}         // 响应数据
}
```

## 错误码说明

- 200: 成功
- 400: 请求参数错误
- 404: 资源不存在
- 500: 服务器内部错误

## 接口列表

### 1. 策略分析

#### 请求信息
- 路径: `/api/v1/analyze_strategy`
- 方法: POST
- Content-Type: application/json

#### 请求参数
```json
{
    "strategy_text": "我看好贵州茅台，计划以1500-1600元价格区间买入，止盈1700，止损1450，日线MACD金叉"
}
```

#### 响应示例
```json
{
    "code": 200,
    "message": "策略分析成功",
    "data": {
        "stock_name": "贵州茅台",
        "stock_code": "600519",
        "action": "buy",
        "position_ratio": 0.1,
        "price_min": 1500,
        "price_max": 1600,
        "take_profit_price": 1700,
        "stop_loss_price": 1450,
        "other_conditions": "日线MACD金叉",
        "reason": "技术面向好，估值合理"
    }
}
```

### 2. 获取策略列表

#### 请求信息
- 路径: `/api/v1/strategies`
- 方法: GET

#### 查询参数
- `sort_by`: 排序字段，可选值：updated_at, created_at，默认 updated_at
- `order`: 排序方式，可选值：desc, asc，默认 desc

#### 响应示例
```json
{
    "code": 200,
    "message": "success",
    "data": [
        {
            "id": 1,
            "stock_name": "贵州茅台",
            "stock_code": "600519",
            "action": "buy",
            "position_ratio": 0.1,
            "price_min": 1500,
            "price_max": 1600,
            "take_profit_price": 1700,
            "stop_loss_price": 1450,
            "other_conditions": "日线MACD金叉",
            "reason": "技术面向好，估值合理",
            "execution_status": "pending",
            "is_active": true,
            "created_at": "2024-02-01 10:00:00",
            "updated_at": "2024-02-01 10:00:00"
        }
    ]
}
```

### 3. 创建策略

#### 请求信息
- 路径: `/api/v1/strategies`
- 方法: POST
- Content-Type: application/json

#### 请求参数
```json
{
    "stock_name": "贵州茅台",
    "stock_code": "600519",
    "action": "buy",
    "position_ratio": 0.1,
    "price_min": 1500,
    "price_max": 1600,
    "take_profit_price": 1700,
    "stop_loss_price": 1450,
    "other_conditions": "日线MACD金叉",
    "reason": "技术面向好，估值合理"
}
```

#### 响应示例
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "id": 1,
        "stock_name": "贵州茅台",
        "stock_code": "600519",
        "action": "buy",
        "position_ratio": 0.1,
        "price_min": 1500,
        "price_max": 1600,
        "take_profit_price": 1700,
        "stop_loss_price": 1450,
        "other_conditions": "日线MACD金叉",
        "reason": "技术面向好，估值合理",
        "execution_status": "pending",
        "is_active": true,
        "created_at": "2024-02-01 10:00:00",
        "updated_at": "2024-02-01 10:00:00"
    }
}
```

### 4. 更新策略

#### 请求信息
- 路径: `/api/v1/strategies/{id}`
- 方法: PUT
- Content-Type: application/json

#### 请求参数
```json
{
    "position_ratio": 0.2,
    "price_min": 1550,
    "price_max": 1650,
    "take_profit_price": 1750,
    "stop_loss_price": 1500,
    "other_conditions": "日线MACD金叉，成交量放大",
    "reason": "技术面继续向好，估值依然合理"
}
```

#### 响应示例
```json
{
    "code": 200,
    "message": "策略更新成功",
    "data": {
        "id": 1,
        "stock_name": "贵州茅台",
        "stock_code": "600519",
        "action": "buy",
        "position_ratio": 0.2,
        "price_min": 1550,
        "price_max": 1650,
        "take_profit_price": 1750,
        "stop_loss_price": 1500,
        "other_conditions": "日线MACD金叉，成交量放大",
        "reason": "技术面继续向好，估值依然合理",
        "execution_status": "pending",
        "is_active": true,
        "created_at": "2024-02-01 10:00:00",
        "updated_at": "2024-02-01 10:30:00"
    }
}
```

### 5. 检查策略是否存在

#### 请求信息
- 路径: `/api/v1/strategies/check`
- 方法: POST
- Content-Type: application/json

#### 请求参数
```json
{
    "stock_name": "贵州茅台",
    "stock_code": "600519",
    "action": "buy"
}
```

#### 响应示例
```json
{
    "code": 200,
    "message": "成功",
    "data": {
        "id": 1,
        "stock_name": "贵州茅台",
        "stock_code": "600519",
        "action": "buy",
        "position_ratio": 0.2,
        "price_min": 1550,
        "price_max": 1650,
        "take_profit_price": 1750,
        "stop_loss_price": 1500,
        "other_conditions": "日线MACD金叉，成交量放大",
        "reason": "技术面继续向好，估值依然合理",
        "execution_status": "partial",
        "is_active": true,
        "created_at": "2024-02-01 10:00:00",
        "updated_at": "2024-02-01 11:00:00"
    }
}
```

### 6. 搜索策略列表

#### 请求信息
- 路径: `/api/v1/strategies/search`
- 方法: GET

#### 查询参数
- `start_time`: 开始时间，格式：YYYY-MM-DD HH:mm:ss
- `end_time`: 结束时间，格式：YYYY-MM-DD HH:mm:ss
- `stock_code`: 股票代码
- `stock_name`: 股票名称
- `action`: 交易动作（buy/sell）
- `sort_by`: 排序字段，可选值: updated_at, created_at
- `order`: 排序方式，可选值: desc, asc
- `is_active`: 是否只查询有效策略（true/false）

#### 响应示例
```json
{
    "code": 200,
    "message": "success",
    "data": [
        {
            "id": 1,
            "stock_name": "贵州茅台",
            "stock_code": "600519",
            "action": "buy",
            "position_ratio": 0.2,
            "price_min": 1550,
            "price_max": 1650,
            "take_profit_price": 1750,
            "stop_loss_price": 1500,
            "other_conditions": "日线MACD金叉，成交量放大",
            "reason": "技术面继续向好，估值依然合理",
            "execution_status": "partial",
            "is_active": true,
            "created_at": "2024-02-01 10:00:00",
            "updated_at": "2024-02-01 10:30:00"
        }
    ]
}
```

### 7. 创建执行记录

#### 请求信息
- 路径: `/api/v1/executions`
- 方法: POST
- Content-Type: application/json

#### 请求参数
```json
{
    "strategy_id": 1,
    "execution_price": 1580,
    "volume": 100,
    "strategy_status": "partial",
    "remarks": "按计划执行"
}
```

#### 响应示例
```json
{
    "code": 200,
    "message": "执行记录创建成功",
    "data": {
        "id": 1,
        "strategy_id": 1,
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "action": "buy",
        "execution_price": 1580,
        "volume": 100,
        "execution_time": "2024-02-01 10:35:00",
        "execution_result": "success",
        "remarks": "按计划执行",
        "created_at": "2024-02-01 10:35:00",
        "updated_at": "2024-02-01 10:35:00"
    }
}
```

### 8. 获取执行记录列表

#### 请求信息
- 路径: `/api/v1/executions`
- 方法: GET

#### 查询参数
- `strategy_id`: 策略ID
- `stock_code`: 股票代码
- `start_time`: 开始时间
- `end_time`: 结束时间
- `action`: 执行操作（buy/sell）
- `result`: 执行结果（success/failed/partial）
- `sort_by`: 排序字段（execution_time/created_at）
- `order`: 排序方式（desc/asc）
- `limit`: 限制返回数量

#### 响应示例
```json
{
    "code": 200,
    "message": "success",
    "data": [
        {
            "id": 1,
            "strategy_id": 1,
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "action": "buy",
            "execution_price": 1580.5,
            "volume": 100,
            "execution_result": "success",
            "remarks": "按计划执行",
            "execution_time": "2024-02-01 14:30:00",
            "created_at": "2024-02-01 14:30:00",
            "updated_at": "2024-02-01 14:30:00"
        }
    ]
}
```

### 9. 设置策略状态

#### 请求信息
- 路径: `/api/v1/strategies/{id}/deactivate` 或 `/api/v1/strategies/{id}/activate`
- 方法: POST

#### 响应示例
```json
{
    "code": 200,
    "message": "成功",
    "data": {
        "id": 1,
        "stock_name": "贵州茅台",
        "stock_code": "600519",
        "action": "buy",
        "position_ratio": 0.2,
        "price_min": 1550,
        "price_max": 1650,
        "take_profit_price": 1750,
        "stop_loss_price": 1500,
        "other_conditions": "日线MACD金叉，成交量放大",
        "reason": "技术面继续向好，估值依然合理",
        "execution_status": "partial",
        "is_active": false,  // 或 true
        "created_at": "2024-02-01 10:00:00",
        "updated_at": "2024-02-01 11:00:00"
    }
}
```

## 持仓相关接口

### 获取所有持仓

获取系统中所有的股票持仓信息。

- **URL**: `/api/positions`
- **方法**: `GET`
- **参数**: 无
- **响应**:
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "positions": [
        {
          "id": 1,
          "stock_code": "600519",
          "stock_name": "贵州茅台",
          "total_volume": 100,
          "original_cost": 1500.00,
          "dynamic_cost": 1450.00,
          "total_amount": 150000.00,
          "latest_price": 1600.00,
          "market_value": 160000.00,
          "floating_profit": 10000.00,
          "floating_profit_ratio": 6.67,
          "created_at": "2024-02-15 10:00:00",
          "updated_at": "2024-02-15 15:30:00"
        }
      ]
    }
  }
  ```
- **响应说明**:
  - `floating_profit_ratio`: 浮动盈亏比例
    - 正常情况：实际的盈亏比例值
    - 特殊情况：当 dynamic_cost <= 0 时，值为 999999
    - 前端显示：当值为 999999 时显示为 ♾️ 符号

### 获取单个股票持仓

获取指定股票代码的持仓信息。

- **URL**: `/api/v1/positions/{stock_code}`
- **方法**: `GET`
- **URL参数**:
  - `stock_code`: 股票代码

**响应示例**:
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "id": 1,
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "total_volume": 100,
        "average_cost": 1550.5,
        "total_amount": 155050.0,
        "latest_price": 1600.0,
        "market_value": 160000.0,
        "floating_profit": 4950.0,
        "floating_profit_ratio": 0.0319,
        "created_at": "2025-02-14 19:42:44",
        "updated_at": "2025-02-15 17:09:32"
    }
}
```

### 更新股票市值

更新指定股票的最新价格和市值信息。

- **URL**: `/api/v1/positions/{stock_code}/market_value`
- **方法**: `PUT`
- **URL参数**:
  - `stock_code`: 股票代码
- **请求体**:
```json
{
    "latest_price": 1600.0
}
```

**响应示例**:
```json
{
    "code": 200,
    "message": "更新市值成功",
    "data": {
        "id": 1,
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "total_volume": 100,
        "original_cost": 1580,
        "dynamic_cost": 1580,
        "total_amount": 158000,
        "latest_price": 1600,
        "market_value": 160000,
        "floating_profit": 2000,
        "floating_profit_ratio": 0.0127,
        "created_at": "2024-02-01 10:35:00",
        "updated_at": "2024-02-01 10:40:00"
    }
}
```

**错误响应**:
```json
{
    "code": 404,
    "message": "股票 600519 没有持仓记录",
    "data": null
}
```

### 更新持仓（卖出）
- **URL**: `/api/positions/{id}/sell`
- **方法**: `POST`
- **参数**:
  ```json
  {
    "volume": 50,
    "price": 1600.00
  }
  ```
- **响应**:
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "position": {
        "id": 1,
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "total_volume": 50,
        "original_cost": 1500.00,
        "dynamic_cost": 1450.00,
        "total_amount": 75000.00,
        "latest_price": 1600.00,
        "market_value": 80000.00,
        "floating_profit": 5000.00,
        "floating_profit_ratio": 6.67,
        "created_at": "2024-02-15 10:00:00",
        "updated_at": "2024-02-15 15:30:00"
      }
    }
  }
  ```
- **错误响应**:
  ```json
  {
    "code": 400,
    "message": "卖出数量 200 超过持仓数量 100",
    "data": null
  }
  ``` 