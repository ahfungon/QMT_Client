"""
策略管理模块测试用例
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from src.strategy.strategy import StrategyManager

@pytest.fixture
def strategy_manager():
    """创建策略管理对象"""
    return StrategyManager()

@pytest.fixture
def mock_strategy():
    """模拟策略数据"""
    return {
        "id": 1,
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "action": "buy",
        "position_ratio": 0.1,
        "price_min": 1500,
        "price_max": 1600,
        "is_active": True,
        "created_at": "2024-02-08 10:00:00",
        "updated_at": "2024-02-08 10:00:00"
    }

def test_fetch_active_strategies_success(strategy_manager, mock_strategy):
    """测试成功获取策略"""
    # 准备模拟响应
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 200,
        "message": "success",
        "data": [mock_strategy]
    }
    mock_response.raise_for_status.return_value = None
    
    # Mock请求
    with patch('requests.get', return_value=mock_response):
        # 执行获取策略
        strategies = strategy_manager.fetch_active_strategies()
        
        # 验证结果
        assert len(strategies) == 1
        assert strategies[0]['stock_code'] == "600519"
        assert strategies[0]['action'] == "buy"

def test_fetch_active_strategies_failed(strategy_manager):
    """测试获取策略失败"""
    # 准备模拟响应
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 500,
        "message": "服务器错误",
        "data": None
    }
    mock_response.raise_for_status.return_value = None
    
    # Mock请求
    with patch('requests.get', return_value=mock_response):
        # 执行获取策略
        strategies = strategy_manager.fetch_active_strategies()
        
        # 验证结果
        assert len(strategies) == 0

def test_validate_strategy_success(strategy_manager, mock_strategy):
    """测试策略验证成功"""
    # 执行验证
    result = strategy_manager.validate_strategy(mock_strategy)
    
    # 验证结果
    assert result is True

def test_validate_strategy_missing_field(strategy_manager, mock_strategy):
    """测试策略缺少字段"""
    # 删除必要字段
    del mock_strategy['action']
    
    # 执行验证
    result = strategy_manager.validate_strategy(mock_strategy)
    
    # 验证结果
    assert result is False

def test_validate_strategy_invalid_ratio(strategy_manager, mock_strategy):
    """测试无效的仓位比例"""
    # 设置无效的仓位比例
    mock_strategy['position_ratio'] = 1.5
    
    # 执行验证
    result = strategy_manager.validate_strategy(mock_strategy)
    
    # 验证结果
    assert result is False

def test_validate_strategy_invalid_price(strategy_manager, mock_strategy):
    """测试无效的价格区间"""
    # 设置无效的价格区间
    mock_strategy['price_min'] = 1600
    mock_strategy['price_max'] = 1500
    
    # 执行验证
    result = strategy_manager.validate_strategy(mock_strategy)
    
    # 验证结果
    assert result is False 