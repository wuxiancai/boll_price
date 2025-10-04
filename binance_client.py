"""
币安合约API客户端
用于获取币安合约账户的各种信息
"""

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
import logging
from datetime import datetime
from binance_config import get_api_config, validate_api_config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BinanceFuturesClient:
    """币安合约账户信息客户端"""
    
    def __init__(self):
        """
        初始化币安合约客户端
        """
        if not validate_api_config('futures'):
            raise ValueError("合约API配置无效，请检查API密钥")
        
        config = get_api_config('futures')
        self.client = Client(
            api_key=config['api_key'],
            api_secret=config['api_secret'],
            requests_params={'timeout': config['timeout']}
        )
        
        # 测试连接
        self._test_connection()
    
    def _test_connection(self):
        """
        测试API连接是否正常
        """
        try:
            # 获取服务器时间来测试连接
            server_time = self.client.get_server_time()
            logger.info(f"币安合约API连接成功，服务器时间: {datetime.fromtimestamp(server_time['serverTime']/1000)}")
        except Exception as e:
            logger.error(f"币安合约API连接失败: {e}")
            raise
    
    def get_futures_account_info(self):
        """
        获取合约账户基本信息
        
        Returns:
            dict: 合约账户信息
        """
        try:
            account_info = self.client.futures_account()
            
            return {
                'total_wallet_balance': float(account_info.get('totalWalletBalance', 0)),
                'total_unrealized_pnl': float(account_info.get('totalUnrealizedPnL', 0)),
                'total_margin_balance': float(account_info.get('totalMarginBalance', 0)),
                'total_position_initial_margin': float(account_info.get('totalPositionInitialMargin', 0)),
                'total_open_order_initial_margin': float(account_info.get('totalOpenOrderInitialMargin', 0)),
                'available_balance': float(account_info.get('availableBalance', 0)),
                'max_withdraw_amount': float(account_info.get('maxWithdrawAmount', 0)),
                'can_trade': account_info.get('canTrade', False),
                'can_deposit': account_info.get('canDeposit', False),
                'can_withdraw': account_info.get('canWithdraw', False),
                'update_time': datetime.fromtimestamp(account_info.get('updateTime', 0)/1000).strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"获取合约账户信息失败: {e}")
            return None
    
    def get_futures_balances(self, show_zero=False):
        """
        获取合约账户余额
        
        Args:
            show_zero (bool): 是否显示余额为0的资产
        
        Returns:
            list: 余额信息列表
        """
        try:
            account_info = self.client.futures_account()
            assets = account_info.get('assets', [])
            
            balances = []
            for asset in assets:
                wallet_balance = float(asset.get('walletBalance', 0))
                unrealized_pnl = float(asset.get('unrealizedPnL', 0))
                margin_balance = float(asset.get('marginBalance', 0))
                
                if not show_zero and wallet_balance == 0 and unrealized_pnl == 0:
                    continue
                
                balances.append({
                    'asset': asset.get('asset'),
                    'wallet_balance': wallet_balance,
                    'unrealized_pnl': unrealized_pnl,
                    'margin_balance': margin_balance,
                    'available_balance': float(asset.get('availableBalance', 0)),
                    'position_initial_margin': float(asset.get('positionInitialMargin', 0)),
                    'open_order_initial_margin': float(asset.get('openOrderInitialMargin', 0)),
                    'max_withdraw_amount': float(asset.get('maxWithdrawAmount', 0))
                })
            
            return balances
        except Exception as e:
            logger.error(f"获取合约余额失败: {e}")
            return []
    
    def get_futures_positions(self):
        """
        获取合约持仓信息
        
        Returns:
            list: 持仓信息列表
        """
        try:
            positions = self.client.futures_position_information()
            
            active_positions = []
            for position in positions:
                position_amt = float(position.get('positionAmt', 0))
                if position_amt != 0:  # 只显示有持仓的合约
                    active_positions.append({
                        'symbol': position.get('symbol'),
                        'position_amt': position_amt,
                        'entry_price': float(position.get('entryPrice', 0)),
                        'mark_price': float(position.get('markPrice', 0)),
                        'unrealized_pnl': float(position.get('unRealizedProfit', 0)),
                        'percentage': float(position.get('percentage', 0)),
                        'position_side': position.get('positionSide'),
                        'isolated': position.get('isolated'),
                        'notional': float(position.get('notional', 0)),
                        'isolated_wallet': float(position.get('isolatedWallet', 0)),
                        'update_time': datetime.fromtimestamp(int(position.get('updateTime', 0))/1000).strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            return active_positions
        except Exception as e:
            logger.error(f"获取合约持仓失败: {e}")
            return []
    
    def get_futures_open_orders(self):
        """
        获取合约当前挂单
        
        Returns:
            list: 挂单信息列表
        """
        try:
            orders = self.client.futures_get_open_orders()
            
            formatted_orders = []
            for order in orders:
                formatted_orders.append({
                    'symbol': order.get('symbol'),
                    'order_id': order.get('orderId'),
                    'side': order.get('side'),
                    'type': order.get('type'),
                    'quantity': float(order.get('origQty', 0)),
                    'price': float(order.get('price', 0)),
                    'stop_price': float(order.get('stopPrice', 0)),
                    'status': order.get('status'),
                    'time_in_force': order.get('timeInForce'),
                    'position_side': order.get('positionSide'),
                    'reduce_only': order.get('reduceOnly'),
                    'close_position': order.get('closePosition'),
                    'time': datetime.fromtimestamp(int(order.get('time', 0))/1000).strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': datetime.fromtimestamp(int(order.get('updateTime', 0))/1000).strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return formatted_orders
        except Exception as e:
            logger.error(f"获取合约挂单失败: {e}")
            return []
    
    def get_futures_recent_trades(self, symbol=None, limit=10):
        """
        获取合约最近交易记录
        
        Args:
            symbol (str): 交易对符号，如果为None则获取所有
            limit (int): 返回记录数量限制
        
        Returns:
            list: 交易记录列表
        """
        try:
            if symbol:
                trades = self.client.futures_account_trades(symbol=symbol, limit=limit)
            else:
                # 获取所有交易记录（最近的）
                trades = self.client.futures_account_trades(limit=limit)
            
            formatted_trades = []
            for trade in trades:
                formatted_trades.append({
                    'symbol': trade.get('symbol'),
                    'trade_id': trade.get('id'),
                    'order_id': trade.get('orderId'),
                    'side': trade.get('side'),
                    'quantity': float(trade.get('qty', 0)),
                    'price': float(trade.get('price', 0)),
                    'quote_qty': float(trade.get('quoteQty', 0)),
                    'commission': float(trade.get('commission', 0)),
                    'commission_asset': trade.get('commissionAsset'),
                    'realized_pnl': float(trade.get('realizedPnl', 0)),
                    'position_side': trade.get('positionSide'),
                    'buyer': trade.get('buyer'),
                    'maker': trade.get('maker'),
                    'time': datetime.fromtimestamp(int(trade.get('time', 0))/1000).strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return formatted_trades
        except Exception as e:
            logger.error(f"获取合约交易记录失败: {e}")
            return []
    
    def get_futures_24hr_ticker(self, limit=10):
        """
        获取合约24小时价格变动统计
        
        Args:
            limit (int): 返回数量限制
        
        Returns:
            list: 24小时统计数据列表
        """
        try:
            tickers = self.client.futures_ticker()
            
            # 按成交量排序，取前N个
            sorted_tickers = sorted(tickers, key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
            
            formatted_tickers = []
            for ticker in sorted_tickers[:limit]:
                formatted_tickers.append({
                    'symbol': ticker.get('symbol'),
                    'price': float(ticker.get('lastPrice', 0)),
                    'price_change': float(ticker.get('priceChange', 0)),
                    'price_change_percent': float(ticker.get('priceChangePercent', 0)),
                    'high_price': float(ticker.get('highPrice', 0)),
                    'low_price': float(ticker.get('lowPrice', 0)),
                    'volume': float(ticker.get('volume', 0)),
                    'quote_volume': float(ticker.get('quoteVolume', 0)),
                    'open_price': float(ticker.get('openPrice', 0)),
                    'prev_close_price': float(ticker.get('prevClosePrice', 0)),
                    'weighted_avg_price': float(ticker.get('weightedAvgPrice', 0)),
                    'count': int(ticker.get('count', 0))
                })
            
            return formatted_tickers
        except Exception as e:
            logger.error(f"获取合约24小时统计失败: {e}")
            return []
    
    def get_futures_income_history(self, limit=10):
        """
        获取合约收益历史
        
        Args:
            limit (int): 返回记录数量限制
        
        Returns:
            list: 收益历史列表
        """
        try:
            income_history = self.client.futures_income_history(limit=limit)
            
            formatted_income = []
            for income in income_history:
                formatted_income.append({
                    'symbol': income.get('symbol'),
                    'income_type': income.get('incomeType'),
                    'income': float(income.get('income', 0)),
                    'asset': income.get('asset'),
                    'info': income.get('info'),
                    'time': datetime.fromtimestamp(int(income.get('time', 0))/1000).strftime('%Y-%m-%d %H:%M:%S'),
                    'tran_id': income.get('tranId'),
                    'trade_id': income.get('tradeId')
                })
            
            return formatted_income
        except Exception as e:
            logger.error(f"获取合约收益历史失败: {e}")
            return []
    
    def get_all_futures_data(self):
        """
        获取所有合约账户数据
        
        Returns:
            dict: 包含所有数据的字典
        """
        try:
            return {
                'account_info': self.get_futures_account_info(),
                'balances': self.get_futures_balances(),
                'positions': self.get_futures_positions(),
                'open_orders': self.get_futures_open_orders(),
                'recent_trades': self.get_futures_recent_trades(limit=10),
                'market_tickers': self.get_futures_24hr_ticker(limit=10),
                'income_history': self.get_futures_income_history(limit=10)
            }
        except Exception as e:
            logger.error(f"获取所有合约数据失败: {e}")
            return None