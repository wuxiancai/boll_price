"""
数据库操作模块
用于存储和管理K线数据
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class KlineDatabase:
    """K线数据库操作类"""
    
    def __init__(self, db_path: str = 'db.db'):
        """
        初始化数据库连接
        
        Args:
            db_path (str): 数据库文件路径
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建K线数据表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS klines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        interval_type TEXT NOT NULL,
                        open_time INTEGER NOT NULL,
                        close_time INTEGER NOT NULL,
                        open_price REAL NOT NULL,
                        high_price REAL NOT NULL,
                        low_price REAL NOT NULL,
                        close_price REAL NOT NULL,
                        volume REAL NOT NULL,
                        quote_volume REAL NOT NULL,
                        trades_count INTEGER NOT NULL,
                        taker_buy_base_volume REAL NOT NULL,
                        taker_buy_quote_volume REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, interval_type, open_time)
                    )
                ''')
                
                # 创建BOLL指标数据表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS boll_indicators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        interval_type TEXT NOT NULL,
                        open_time INTEGER NOT NULL,
                        upper_band REAL,
                        middle_band REAL,
                        lower_band REAL,
                        period INTEGER DEFAULT 20,
                        std_dev REAL DEFAULT 2.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, interval_type, open_time, period, std_dev)
                    )
                ''')
                
                # 创建索引提高查询性能
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_klines_symbol_interval_time 
                    ON klines(symbol, interval_type, open_time)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_boll_symbol_interval_time 
                    ON boll_indicators(symbol, interval_type, open_time)
                ''')
                
                conn.commit()
                logger.info("数据库表初始化完成")
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def save_klines(self, klines_data: List[Dict], symbol: str, interval: str) -> int:
        """
        保存K线数据到数据库
        
        Args:
            klines_data (List[Dict]): K线数据列表
            symbol (str): 交易对
            interval (str): 时间间隔
            
        Returns:
            int: 保存的记录数
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                saved_count = 0
                for kline in klines_data:
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO klines (
                                symbol, interval_type, open_time, close_time,
                                open_price, high_price, low_price, close_price,
                                volume, quote_volume, trades_count,
                                taker_buy_base_volume, taker_buy_quote_volume
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            symbol, interval, kline['open_time'], kline['close_time'],
                            kline['open'], kline['high'], kline['low'], kline['close'],
                            kline['volume'], kline['quote_volume'], kline['trades_count'],
                            kline['taker_buy_base_volume'], kline['taker_buy_quote_volume']
                        ))
                        saved_count += 1
                    except sqlite3.IntegrityError:
                        # 数据已存在，跳过
                        pass
                
                conn.commit()
                logger.info(f"保存了 {saved_count} 条K线数据到数据库")
                return saved_count
                
        except Exception as e:
            logger.error(f"保存K线数据失败: {e}")
            raise
    
    def get_klines(self, symbol: str, interval: str, limit: int = 50) -> List[Dict]:
        """
        从数据库获取K线数据
        
        Args:
            symbol (str): 交易对
            interval (str): 时间间隔
            limit (int): 获取数量
            
        Returns:
            List[Dict]: K线数据列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT open_time, close_time, open_price, high_price, 
                           low_price, close_price, volume, quote_volume,
                           trades_count, taker_buy_base_volume, taker_buy_quote_volume
                    FROM klines 
                    WHERE symbol = ? AND interval_type = ?
                    ORDER BY open_time DESC
                    LIMIT ?
                ''', (symbol, interval, limit))
                
                rows = cursor.fetchall()
                
                klines = []
                for row in rows:
                    klines.append({
                        'open_time': row[0],
                        'close_time': row[1],
                        'open': row[2],
                        'high': row[3],
                        'low': row[4],
                        'close': row[5],
                        'volume': row[6],
                        'quote_volume': row[7],
                        'trades_count': row[8],
                        'taker_buy_base_volume': row[9],
                        'taker_buy_quote_volume': row[10]
                    })
                
                # 按时间正序返回
                klines.reverse()
                return klines
                
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []
    
    def save_boll_indicators(self, boll_data: Dict, symbol: str, interval: str, 
                           klines: List[Dict], period: int = 20, std_dev: float = 2.0) -> int:
        """
        保存BOLL指标数据到数据库
        
        Args:
            boll_data (Dict): BOLL指标数据
            symbol (str): 交易对
            interval (str): 时间间隔
            klines (List[Dict]): 对应的K线数据
            period (int): BOLL周期
            std_dev (float): 标准差倍数
            
        Returns:
            int: 保存的记录数
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                saved_count = 0
                for i, kline in enumerate(klines):
                    if (i < len(boll_data['upper']) and 
                        boll_data['upper'][i] is not None):
                        
                        try:
                            cursor.execute('''
                                INSERT OR REPLACE INTO boll_indicators (
                                    symbol, interval_type, open_time, upper_band,
                                    middle_band, lower_band, period, std_dev
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                symbol, interval, kline['open_time'],
                                boll_data['upper'][i], boll_data['middle'][i],
                                boll_data['lower'][i], period, std_dev
                            ))
                            saved_count += 1
                        except sqlite3.IntegrityError:
                            # 数据已存在，跳过
                            pass
                
                conn.commit()
                logger.info(f"保存了 {saved_count} 条BOLL指标数据到数据库")
                return saved_count
                
        except Exception as e:
            logger.error(f"保存BOLL指标数据失败: {e}")
            raise
    
    def get_boll_indicators(self, symbol: str, interval: str, limit: int = 50) -> Dict:
        """
        从数据库获取BOLL指标数据
        
        Args:
            symbol (str): 交易对
            interval (str): 时间间隔
            limit (int): 获取数量
            
        Returns:
            Dict: BOLL指标数据
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT open_time, upper_band, middle_band, lower_band
                    FROM boll_indicators 
                    WHERE symbol = ? AND interval_type = ?
                    ORDER BY open_time DESC
                    LIMIT ?
                ''', (symbol, interval, limit))
                
                rows = cursor.fetchall()
                
                # 按时间正序排列
                rows.reverse()
                
                return {
                    'upper': [row[1] for row in rows],
                    'middle': [row[2] for row in rows],
                    'lower': [row[3] for row in rows]
                }
                
        except Exception as e:
            logger.error(f"获取BOLL指标数据失败: {e}")
            return {'upper': [], 'middle': [], 'lower': []}
    
    def save_kline_data(self, symbol: str, interval: str, timestamp: int, 
                       open_price: float, high_price: float, low_price: float, 
                       close_price: float, volume: float) -> bool:
        """
        保存单条K线数据到数据库
        
        Args:
            symbol (str): 交易对
            interval (str): 时间间隔
            timestamp (int): 时间戳
            open_price (float): 开盘价
            high_price (float): 最高价
            low_price (float): 最低价
            close_price (float): 收盘价
            volume (float): 成交量
            
        Returns:
            bool: 保存是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO klines (
                        symbol, interval_type, open_time, close_time,
                        open_price, high_price, low_price, close_price,
                        volume, quote_volume, trades_count,
                        taker_buy_base_volume, taker_buy_quote_volume
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0)
                ''', (
                    symbol, interval, timestamp, timestamp + 60000,  # 假设1分钟间隔
                    open_price, high_price, low_price, close_price, volume
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"保存K线数据失败: {e}")
            return False

    def save_boll_indicator(self, symbol: str, interval: str, timestamp: int,
                           upper_band: float, middle_band: float, lower_band: float,
                           period: int = 20, std_dev: float = 2.0) -> bool:
        """
        保存单条BOLL指标数据到数据库
        
        Args:
            symbol (str): 交易对
            interval (str): 时间间隔
            timestamp (int): 时间戳
            upper_band (float): 上轨
            middle_band (float): 中轨
            lower_band (float): 下轨
            period (int): 周期
            std_dev (float): 标准差倍数
            
        Returns:
            bool: 保存是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO boll_indicators (
                        symbol, interval_type, open_time, upper_band,
                        middle_band, lower_band, period, std_dev
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, interval, timestamp, upper_band,
                    middle_band, lower_band, period, std_dev
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"保存BOLL指标数据失败: {e}")
            return False

    def get_data_count(self, symbol: str, interval: str) -> int:
        """
        获取数据库中指定交易对和时间间隔的数据数量
        
        Args:
            symbol (str): 交易对
            interval (str): 时间间隔
            
        Returns:
            int: 数据数量
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT COUNT(*) FROM klines 
                    WHERE symbol = ? AND interval_type = ?
                ''', (symbol, interval))
                
                return cursor.fetchone()[0]
                
        except Exception as e:
            logger.error(f"获取数据数量失败: {e}")
            return 0