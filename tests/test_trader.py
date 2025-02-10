"""
交易模块测试用例
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.trade.trader import StockTrader

@pytest.fixture
def trader():
    """创建交易对象"""
    # 使用临时文件作为持仓文件
    trader = StockTrader(position_file="tests/data/test_positions.json")
    return trader

@pytest.fixture
def mock_positions():
    """模拟持仓数据"""
    return {
        "600519": {
            "volume": 100,
            "price": 1688.88,
            "updated_at": "2024-02-08 10:00:00"
        }
    }

def test_buy_stock_new_position(trader, mock_positions):
    """测试买入新股票"""
    # 准备测试数据
    stock_code = "601318"
    min_price = 1500
    max_price = 1600
    position_ratio = 0.1
    
    # Mock持仓文件操作
    with patch.object(trader, '_load_positions', return_value={}), \
         patch.object(trader, '_save_positions') as mock_save, \
         patch.object(trader, '_record_execution') as mock_record:
        
        # 执行买入操作
        result = trader.buy_stock(stock_code, min_price, max_price, position_ratio)
        
        # 验证结果
        assert result['result'] == 'success'
        assert result['volume'] > 0
        assert result['error'] is None
        
        # 验证持仓更新
        mock_save.assert_called_once()
        # 验证交易记录
        mock_record.assert_called_once()

def test_buy_stock_existing_position(trader, mock_positions):
    """测试买入已有持仓的股票"""
    # 准备测试数据
    stock_code = "600519"
    min_price = 1600
    max_price = 1700
    position_ratio = 0.1
    
    # Mock持仓文件操作
    with patch.object(trader, '_load_positions', return_value=mock_positions), \
         patch.object(trader, '_save_positions') as mock_save, \
         patch.object(trader, '_record_execution') as mock_record:
        
        # 执行买入操作
        result = trader.buy_stock(stock_code, min_price, max_price, position_ratio)
        
        # 验证结果
        assert result['result'] == 'success'
        assert result['volume'] > 0
        assert result['error'] is None
        
        # 验证持仓更新
        mock_save.assert_called_once()
        # 验证交易记录
        mock_record.assert_called_once()

def test_sell_stock_full_position(trader, mock_positions):
    """测试全部卖出"""
    # 准备测试数据
    stock_code = "600519"
    min_price = 1700
    max_price = 1800
    position_ratio = 1.0
    
    # Mock持仓文件操作
    with patch.object(trader, '_load_positions', return_value=mock_positions), \
         patch.object(trader, '_save_positions') as mock_save, \
         patch.object(trader, '_record_execution') as mock_record:
        
        # 执行卖出操作
        result = trader.sell_stock(stock_code, min_price, max_price, position_ratio)
        
        # 验证结果
        assert result['result'] == 'success'
        assert result['volume'] == 100
        assert result['error'] is None
        
        # 验证持仓更新
        mock_save.assert_called_once()
        # 验证交易记录
        mock_record.assert_called_once()

def test_sell_stock_partial_position(trader, mock_positions):
    """测试部分卖出"""
    # 准备测试数据
    stock_code = "600519"
    min_price = 1700
    max_price = 1800
    position_ratio = 0.5
    
    # Mock持仓文件操作
    with patch.object(trader, '_load_positions', return_value=mock_positions), \
         patch.object(trader, '_save_positions') as mock_save, \
         patch.object(trader, '_record_execution') as mock_record:
        
        # 执行卖出操作
        result = trader.sell_stock(stock_code, min_price, max_price, position_ratio)
        
        # 验证结果
        assert result['result'] == 'success'
        assert result['volume'] == 100
        assert result['error'] is None
        
        # 验证持仓更新
        mock_save.assert_called_once()
        # 验证交易记录
        mock_record.assert_called_once()

def test_sell_stock_no_position(trader):
    """测试卖出无持仓股票"""
    # 准备测试数据
    stock_code = "601318"
    min_price = 1700
    max_price = 1800
    position_ratio = 1.0
    
    # Mock持仓文件操作
    with patch.object(trader, '_load_positions', return_value={}):
        # 执行卖出操作
        result = trader.sell_stock(stock_code, min_price, max_price, position_ratio)
        
        # 验证结果
        assert result['result'] == 'failed'
        assert result['volume'] == 0
        assert result['error'] == '当前无持仓' 