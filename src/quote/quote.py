"""
股票行情查询模块
"""
import re
import logging
import requests
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class QuoteService:
    """股票行情服务类"""
    
    def __init__(self):
        """初始化行情服务"""
        self.base_url = "https://qt.gtimg.cn"
        logger.info("初始化行情查询服务")
        
    def _format_stock_code(self, stock_code: str) -> str:
        """
        格式化股票代码
        
        Args:
            stock_code: 原始股票代码
            
        Returns:
            格式化后的股票代码（带市场前缀）
        """
        # 去除可能存在的前缀
        pure_code = stock_code.replace('sh', '').replace('sz', '').replace('hk', '')
        
        # 根据代码规则判断市场
        if len(pure_code) == 5:  # 港股
            market = 'hk'
            # 补齐前导零到5位
            while len(pure_code) < 5:
                pure_code = '0' + pure_code
        elif pure_code.startswith(('600', '601', '603', '688')):  # 上海主板、科创板
            market = 'sh'
        else:  # 深圳主板、创业板、中小板
            market = 'sz'
            
        full_code = f"{market}{pure_code}"
        logger.debug(f"格式化股票代码: {stock_code} -> {full_code}")
        return full_code
        
    def get_real_time_quote(self, stock_code: str) -> Optional[Dict]:
        """
        获取股票实时行情
        
        Args:
            stock_code: 股票代码（如：000001、00700）
            
        Returns:
            行情数据字典，包含：
            - code: 股票代码
            - name: 股票名称
            - price: 当前价格
            - pre_close: 昨收价
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - volume: 成交量
            - amount: 成交额
            - date: 日期
            - time: 时间
        """
        try:
            # 格式化股票代码
            full_code = self._format_stock_code(stock_code)
            
            # 构建请求URL
            url = f"{self.base_url}/q={full_code}"
            logger.debug(f"请求行情数据 - URL: {url}")
            
            # 发送请求
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            # 解析返回数据
            text = response.text
            if not text:
                logger.error("获取行情数据为空")
                return None
                
            # 提取行情数据
            pattern = r'v_' + full_code + r'="(.+?)"'
            match = re.search(pattern, text)
            if not match:
                logger.error("行情数据格式错误")
                return None
                
            # 分割数据
            data = match.group(1).split('~')
            if len(data) < 40:
                logger.error("行情数据字段不完整")
                return None
                
            # 构建返回数据
            quote = {
                'code': stock_code,
                'name': data[1],
                'price': float(data[3]),
                'pre_close': float(data[4]),
                'open': float(data[5]),
                'volume': int(data[6]),
                'amount': float(data[37]) if data[37] != '' else 0,
                'high': float(data[33]),
                'low': float(data[34]),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'market': 'HK' if len(stock_code) == 5 else 'A股'  # 添加市场标识
            }
            
            logger.info(f"获取行情数据成功 - {quote['market']} {stock_code} {quote['name']} 当前价格: {quote['price']}")
            return quote
            
        except requests.RequestException as e:
            logger.error(f"请求行情数据异常: {str(e)}")
            return None
        except (ValueError, IndexError) as e:
            logger.error(f"解析行情数据异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取行情数据未知异常: {str(e)}")
            return None 