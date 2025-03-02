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
            stock_code: 股票代码，如果是4位代码，认为是港股，会自动加前缀'hk0'
            
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
        # 如果是港股，4位代码，增加前缀
        if len(stock_code) == 4:
            logger.info(f"检测到港股代码：{stock_code}，转换为：hk0{stock_code}")
            stock_code = f"hk0{stock_code}"
        
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
                
            # 预处理成交量字段，去除空白和逗号
            volume_str = data[6].strip().replace(",", "")
            try:
                volume = int(float(volume_str))
            except Exception as e:
                logger.error(f"成交量转换错误，原始数据: '{data[6]}', 错误: {e}")
                return None
                
            # 根据 full_code 判断是否为港股，港股的价格取自 data[2]，否则取 data[3]
            price = float(data[2]) if full_code.startswith('hk') else float(data[3])
            
            # 构建返回数据
            quote = {
                'code': stock_code,
                'name': data[1],
                'price': price,
                'pre_close': float(data[4]),
                'open': float(data[5]),
                'volume': volume,
                'amount': float(data[37]) if data[37] != '' else 0,
                'high': float(data[33]),
                'low': float(data[34]),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'market': 'HK' if full_code.startswith('hk') else 'A股'
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

    def get_stock_name(self, stock_code: str) -> str:
        """
        根据股票代码获取股票名称
        
        Args:
            stock_code: 股票代码
            
        Returns:
            str: 股票名称，如果获取失败则返回股票代码
        """
        try:
            # 尝试从实时行情中获取股票名称
            quote_data = self.get_real_time_quote(stock_code)
            if quote_data and 'name' in quote_data:
                return quote_data['name']
            
            # 如果实时行情中没有，尝试从本地缓存中获取
            if hasattr(self, '_stock_name_cache') and stock_code in self._stock_name_cache:
                return self._stock_name_cache[stock_code]
            
            # 都没有则返回股票代码
            return stock_code
        except Exception as e:
            logger.warning(f"获取股票名称失败 - 股票代码: {stock_code}, 错误: {str(e)}")
            return stock_code 