import pytest
from pathlib import Path
import json
from src.services.trade_service import TradeService

@pytest.fixture
def trade_service(tmp_path):
    """创建测试用的交易服务实例"""
    position_file = tmp_path / "test_positions.json"
    return TradeService(position_file=str(position_file))

def test_buy_stock(trade_service):
    """测试买入股票"""
    # 执行买入
    success, message, quantity = trade_service.buy_stock(
        code="600519",
        price=1688.0,
        quantity=100
    )
    
    # 验证结果
    assert success is True
    assert message == "买入成功"
    assert quantity == 100
    
    # 验证持仓更新
    positions = json.loads(trade_service.position_file.read_text(encoding='utf-8'))
    assert "600519" in positions
    assert positions["600519"]["quantity"] == 100
    assert positions["600519"]["average_price"] == 1688.0

def test_sell_stock(trade_service):
    """测试卖出股票"""
    # 先买入
    trade_service.buy_stock("600519", 1688.0, 100)
    
    # 执行卖出
    success, message, quantity = trade_service.sell_stock(
        code="600519",
        price=1700.0,
        quantity=50
    )
    
    # 验证结果
    assert success is True
    assert message == "卖出成功"
    assert quantity == 50
    
    # 验证持仓更新
    positions = json.loads(trade_service.position_file.read_text(encoding='utf-8'))
    assert "600519" in positions
    assert positions["600519"]["quantity"] == 50

def test_sell_insufficient_position(trade_service):
    """测试持仓不足的情况"""
    success, message, quantity = trade_service.sell_stock(
        code="600519",
        price=1700.0,
        quantity=100
    )
    
    assert success is False
    assert message == "持仓不足"
    assert quantity == 0 