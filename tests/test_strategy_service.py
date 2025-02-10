import pytest
from src.services.strategy_service import StrategyService
from unittest.mock import patch, MagicMock

@pytest.fixture
def strategy_service():
    """创建测试用的策略服务实例"""
    return StrategyService()

@pytest.mark.asyncio
async def test_execute_strategies(strategy_service):
    """测试执行策略"""
    # 模拟策略数据
    mock_strategies = [
        {
            "id": 1,
            "stock_code": "600519",
            "action": "buy",
            "price_min": 1680.0,
            "price_max": 1700.0
        }
    ]
    
    # 模拟API调用
    with patch.object(strategy_service.qmt_client, 'get_strategies') as mock_get:
        mock_get.return_value = mock_strategies
        
        # 模拟交易服务
        with patch.object(strategy_service.trade_service, 'buy_stock') as mock_buy:
            mock_buy.return_value = (True, "买入成功", 100)
            
            # 执行策略
            await strategy_service.execute_strategies()
            
            # 验证调用
            mock_get.assert_called_once()
            mock_buy.assert_called_once_with(
                code="600519",
                price=1690.0,  # (1680 + 1700) / 2
                quantity=100
            ) 