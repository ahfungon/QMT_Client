import pytest
from datetime import datetime, timedelta
from src.api.qmt_client import QMTClient
from unittest.mock import patch

@pytest.fixture
def qmt_client():
    """创建测试用的QMT客户端实例"""
    return QMTClient()

@pytest.mark.asyncio
async def test_get_strategies(qmt_client):
    """测试获取策略列表"""
    # 模拟API响应
    mock_response = {
        "code": 200,
        "message": "success",
        "data": [
            {
                "id": 1,
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "action": "buy",
                "price_min": 1680.0,
                "price_max": 1700.0
            }
        ]
    }
    
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None
        
        # 调用方法
        strategies = await qmt_client.get_strategies()
        
        # 验证结果
        assert len(strategies) == 1
        assert strategies[0]["stock_code"] == "600519"
        assert strategies[0]["action"] == "buy" 