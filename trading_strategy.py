"""
BOLL自动交易策略模块
基于BOLL指标的自动交易策略实现
"""

import logging
import time
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Callable
from binance_client import BinanceFuturesClient
from binance.exceptions import BinanceAPIException
from binance_config import get_trading_config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingState(Enum):
    """交易状态枚举"""
    WAITING = "等待开仓"
    BREAKTHROUGH_UP_WAITING = "突破UP,等待跌破UP"
    HOLDING_SHORT = "持仓SHORT"
    BREAKTHROUGH_UP_AGAIN_WAITING = "再次突破UP,已止损SHORT,等待跌破UP"
    BELOW_MB_WAITING = "跌破中轨,等待价格突破中轨或者跌破DN"
    HOLDING_LONG = "持有LONG"
    BELOW_DN_WAITING = "跌破DN,等待价格反弹到DN"
    ABOVE_MB_WAITING = "突破中轨,等待价格继续突破UP或者跌破中轨"

class PositionSide(Enum):
    """持仓方向"""
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"

class TradingEngine:
    """
    BOLL自动交易引擎
    实现基于BOLL指标的自动交易策略
    """
    
    def __init__(self, symbol: str = None, interval: str = None):
        """
        初始化交易引擎
        
        Args:
            symbol: 交易对符号（默认从配置文件读取）
            interval: K线时间间隔（默认从配置文件读取）
        """
        # 获取交易配置
        self.trading_config = get_trading_config()
        
        # 使用传入参数或配置文件默认值
        self.symbol = symbol or self.trading_config['symbol']
        self.interval = interval or self.trading_config['kline_interval']
        self.client = BinanceFuturesClient()
        
        # 交易状态
        self.current_state = TradingState.WAITING
        self.position_side = PositionSide.NONE
        self.position_size = 0.0
        self.entry_price = 0.0
        
        # 价格数据
        self.current_price = 0.0
        self.last_close_price = 0.0
        self.boll_up = 0.0
        self.boll_mb = 0.0
        self.boll_dn = 0.0
        
        # 控制参数
        self.is_running = False
        self.monitoring_thread = None
        self.update_interval = 60  # 更新间隔（秒）
        
        # 回调函数
        self.state_change_callback: Optional[Callable] = None
        self.trade_callback: Optional[Callable] = None
        
        # 日志存储
        self.trading_logs = []
        self.max_logs = 100
        
        
        # 交易参数（从配置文件读取）
        self.position_ratio = self.trading_config['position_ratio']  # 开仓金额比例（70%）
        self.leverage = self.trading_config['leverage']              # 杠杆倍数（10X）
        self.fee_rate = self.trading_config['fee_rate']              # 手续费率（0.05%）
        self.boll_period = self.trading_config['boll_period']        # BOLL周期（20）
        self.boll_std_dev = self.trading_config['boll_std_dev']      # BOLL标准差（2）
        

        
        logger.info(f"交易引擎初始化完成: {symbol} {interval}")
        self.add_log(f"交易引擎初始化完成: {symbol} {interval}", "info")
        
        # 启动时检测持仓状态
        self.check_startup_position()
    
    def check_startup_position(self):
        """
        启动时检测当前持仓状态并记录到交易状态日志
        """
        try:
            logger.info("🔍 正在检测启动时的持仓状态...")
            self.add_log("🔍 正在检测启动时的持仓状态...", "info")
            
            # 获取当前持仓信息
            position_info = self.client.get_position_info(self.symbol)
            
            if position_info and position_info.get('position_amt', 0) != 0:
                position_amt = float(position_info['position_amt'])
                entry_price = float(position_info['entry_price'])
                unrealized_pnl = float(position_info.get('unrealized_pnl', 0))
                
                # 确定持仓方向
                if position_amt > 0:
                    self.position_side = PositionSide.LONG
                    self.current_state = TradingState.HOLDING_LONG
                    position_msg = f"📈 检测到现有持仓: LONG {abs(position_amt):.4f} {self.symbol}"
                elif position_amt < 0:
                    self.position_side = PositionSide.SHORT
                    self.current_state = TradingState.HOLDING_SHORT
                    position_msg = f"📉 检测到现有持仓: SHORT {abs(position_amt):.4f} {self.symbol}"
                
                self.position_size = abs(position_amt)
                self.entry_price = entry_price
                
                # 记录详细持仓信息
                detail_msg = f"   ├─ 入场价格: {entry_price:.4f} USDT"
                pnl_msg = f"   ├─ 未实现盈亏: {unrealized_pnl:.4f} USDT"
                state_msg = f"   └─ 当前状态: {self.current_state.value}"
                
                logger.info(position_msg)
                self.add_log(position_msg, "success")
                self.add_log(detail_msg, "info")
                self.add_log(pnl_msg, "info" if unrealized_pnl >= 0 else "warning")
                self.add_log(state_msg, "info")
                
            else:
                # 无持仓
                self.position_side = PositionSide.NONE
                self.current_state = TradingState.WAITING
                self.position_size = 0.0
                self.entry_price = 0.0
                
                no_position_msg = f"🔄 当前无持仓，等待开仓机会"
                state_msg = f"   └─ 当前状态: {self.current_state.value}"
                
                logger.info(no_position_msg)
                self.add_log(no_position_msg, "info")
                self.add_log(state_msg, "info")
                
        except Exception as e:
            error_msg = f"❌ 检测启动持仓状态失败: {e}"
            logger.error(error_msg)
            self.add_log(error_msg, "error")
            
            # 默认设置为等待状态
            self.position_side = PositionSide.NONE
            self.current_state = TradingState.WAITING
            self.add_log("⚠️ 使用默认状态: 等待开仓", "warning")
    
    def set_callbacks(self, state_change_callback: Callable = None, trade_callback: Callable = None):
        """
        设置回调函数
        
        Args:
            state_change_callback: 状态变化回调函数
            trade_callback: 交易回调函数
        """
        self.state_change_callback = state_change_callback
        self.trade_callback = trade_callback
    
    def add_log(self, message: str, log_type: str = "info"):
        """
        添加交易日志
        
        Args:
            message: 日志消息
            log_type: 日志类型 (info, warning, error, success)
        """
        log_entry = {
            'timestamp': datetime.now(),
            'message': message,
            'type': log_type
        }
        
        self.trading_logs.append(log_entry)
        
        # 保持日志数量在限制内
        if len(self.trading_logs) > self.max_logs:
            self.trading_logs = self.trading_logs[-self.max_logs:]
    
    def get_logs(self) -> list:
        """
        获取交易日志
        
        Returns:
            交易日志列表
        """
        return self.trading_logs.copy()
    
    def clear_logs(self):
        """
        清空交易日志
        """
        self.trading_logs.clear()
        logger.info("交易日志已清空")
    

    
    def calculate_safe_position_size(self, current_price):
        """
        计算安全的仓位大小
        
        Args:
            current_price: 当前价格
            
        Returns:
            安全的仓位大小
        """
        try:
            # 获取账户余额
            balance_info = self.client.get_futures_account_balance()
            if not balance_info:
                logger.warning("无法获取账户余额信息")
                return 0.0
            
            # 获取USDT余额
            usdt_balance = 0.0
            for asset in balance_info:
                if asset['asset'] == 'USDT':
                    usdt_balance = float(asset['balance'])
                    break
            
            if usdt_balance <= 0:
                logger.warning("USDT余额不足")
                return 0.0
            
            # 计算开仓金额（余额的指定比例）
            position_value = usdt_balance * self.position_ratio
            
            # 计算数量（考虑杠杆）
            quantity = (position_value * self.leverage) / current_price
            
            logger.info(f"计算仓位: 余额={usdt_balance:.2f} USDT, 开仓比例={self.position_ratio*100}%, 杠杆={self.leverage}X, 数量={quantity:.6f}")
            
            return quantity
            
        except Exception as e:
            logger.error(f"计算安全仓位大小错误: {e}")
            return 0.0
    

    
    def update_market_data(self):
        """
        更新市场数据
        获取最新的K线数据和BOLL指标
        """
        try:
            # 先测试API连接
            try:
                server_time = self.client.client.get_server_time()
                logger.debug(f"API连接正常，服务器时间: {datetime.fromtimestamp(server_time['serverTime']/1000)}")
            except Exception as conn_e:
                logger.error(f"API连接测试失败: {conn_e}")
                return False
            
            # 获取K线数据和BOLL指标
            data = self.client.get_klines_with_boll(self.symbol, self.interval, 50)
            
            if data and 'klines' in data and 'boll' in data:
                klines = data['klines']
                boll = data['boll']
                
                if klines and boll:
                    # 获取最新收盘价
                    latest_kline = klines[-1]
                    self.last_close_price = float(latest_kline['close'])
                    
                    # 获取BOLL指标 - 修复数据结构访问错误
                    # boll是字典格式: {'upper': [values], 'middle': [values], 'lower': [values]}
                    if isinstance(boll, dict) and 'upper' in boll and 'middle' in boll and 'lower' in boll:
                        upper_values = boll['upper']
                        middle_values = boll['middle']
                        lower_values = boll['lower']
                        
                        # 确保有足够的数据且最后一个值不为None
                        if (len(upper_values) > 0 and len(middle_values) > 0 and len(lower_values) > 0 and
                            upper_values[-1] is not None and middle_values[-1] is not None and lower_values[-1] is not None):
                            
                            self.boll_up = float(upper_values[-1])
                            self.boll_mb = float(middle_values[-1])
                            self.boll_dn = float(lower_values[-1])
                            
                            logger.info(f"市场数据更新: 收盘价={self.last_close_price}, UP={self.boll_up}, MB={self.boll_mb}, DN={self.boll_dn}")
                            return True
                        else:
                            logger.warning(f"BOLL指标数据无效: upper={len(upper_values) if upper_values else 0}, middle={len(middle_values) if middle_values else 0}, lower={len(lower_values) if lower_values else 0}")
                            logger.warning(f"最后一个BOLL值: UP={upper_values[-1] if upper_values else None}, MB={middle_values[-1] if middle_values else None}, DN={lower_values[-1] if lower_values else None}")
                            return False
                    else:
                        logger.warning(f"BOLL数据格式错误: {type(boll)}, 内容: {boll}")
                        return False
                else:
                    logger.warning(f"获取的K线或BOLL数据为空: klines={len(klines) if klines else 0}, boll={boll}")
                    return False
            else:
                logger.warning(f"API返回数据格式错误: {data}")
                return False
            
        except BinanceAPIException as e:
            logger.error(f"币安API错误: 错误代码={e.code}, 错误信息={e.message}")
            return False
        except KeyError as e:
            logger.error(f"数据结构访问错误: 缺少键 {e}，可能是BOLL数据格式不正确")
            logger.error(f"当前数据结构: {data if 'data' in locals() else 'data变量不存在'}")
            return False
        except IndexError as e:
            logger.error(f"数据索引错误: {e}，可能是K线或BOLL数据为空")
            return False
        except (TypeError, ValueError) as e:
            logger.error(f"数据类型或值错误: {e}，可能是数据格式不正确")
            return False
        except Exception as e:
            logger.error(f"更新市场数据错误: {type(e).__name__}: {e}")
            logger.error(f"错误详情: {str(e)}")
            # 添加调试信息
            if 'data' in locals():
                logger.error(f"API返回数据: {data}")
            return False
    
    def change_state(self, new_state: TradingState, reason: str = ""):
        """
        改变交易状态
        
        Args:
            new_state: 新状态
            reason: 状态变化原因
        """
        old_state = self.current_state
        self.current_state = new_state
        
        # 根据状态类型选择不同的日志级别和图标
        if "突破" in new_state.value:
            log_msg = f"🚀 突破状态: {new_state.value}"
            log_type = "warning"
        elif "持仓" in new_state.value or "持有" in new_state.value:
            log_msg = f"💼 持仓状态: {new_state.value}"
            log_type = "success"
        elif "等待" in new_state.value:
            log_msg = f"⏳ 等待状态: {new_state.value}"
            log_type = "info"
        else:
            log_msg = f"🔄 状态变化: {old_state.value} → {new_state.value}"
            log_type = "info"
        
        if reason:
            log_msg += f" (原因: {reason})"
        
        logger.info(log_msg)
        self.add_log(log_msg, log_type)
        
        # 调用状态变化回调
        if self.state_change_callback:
            try:
                self.state_change_callback(old_state, new_state, reason)
            except Exception as e:
                logger.error(f"状态变化回调错误: {e}")
                self.add_log(f"状态变化回调错误: {e}", "error")
    
    def execute_trade(self, side: str, action: str, reason: str = ""):
        """
        执行交易操作
        
        Args:
            side: 交易方向 (BUY/SELL)
            action: 交易动作 (开仓/平仓/止损/止盈)
            reason: 交易原因
        """
        try:

            
            trade_info = {
                'timestamp': datetime.now(),
                'symbol': self.symbol,
                'side': side,
                'action': action,
                'price': self.last_close_price,
                'reason': reason,
                'state': self.current_state.value
            }
            
            logger.info(f"准备执行交易: {action} {side} {self.symbol} @ {self.last_close_price} (原因: {reason})")
            self.add_log(f"准备执行交易: {action} {side} {self.symbol} @ {self.last_close_price} (原因: {reason})", "info")
            
            # 计算交易数量
            if action == "开仓":
                # 使用安全仓位计算方法
                quantity = self.calculate_safe_position_size(self.last_close_price)
                if quantity <= 0:
                    logger.warning("计算的安全仓位大小为0，跳过交易")
                    self.add_log("计算的安全仓位大小为0，跳过交易", "warning")
                    return False
            else:
                # 平仓时使用当前持仓数量
                position_info = self.client.get_position_info(self.symbol)
                if position_info:
                    quantity = abs(position_info['position_amt'])
                else:
                    logger.warning("没有找到持仓信息，跳过平仓操作")
                    self.add_log("没有找到持仓信息，跳过平仓操作", "warning")
                    return False
            
            # 执行真实交易
            order_result = None
            
            if action == "开仓":
                if side == "BUY":
                    # 开多仓
                    order_result = self.client.open_long_position(self.symbol, quantity)
                    self.position_side = PositionSide.LONG
                else:
                    # 开空仓
                    order_result = self.client.open_short_position(self.symbol, quantity)
                    self.position_side = PositionSide.SHORT
                
                self.entry_price = self.last_close_price
                self.position_size = quantity
                
            elif action in ["平仓", "止损", "止盈"]:
                if self.position_side == PositionSide.LONG:
                    # 平多仓
                    order_result = self.client.close_long_position(self.symbol, quantity)
                elif self.position_side == PositionSide.SHORT:
                    # 平空仓
                    order_result = self.client.close_short_position(self.symbol, quantity)
                
                self.position_side = PositionSide.NONE
                self.position_size = 0.0
                self.entry_price = 0.0
            
            if order_result:
                trade_info['order_id'] = order_result.get('orderId')
                trade_info['quantity'] = quantity
                trade_info['status'] = 'SUCCESS'
                success_msg = f"交易执行成功: 订单ID {order_result.get('orderId')}"
                logger.info(success_msg)
                self.add_log(success_msg, "success")
                

                
            else:
                trade_info['status'] = 'FAILED'
                error_msg = "交易执行失败"
                logger.error(error_msg)
                self.add_log(error_msg, "error")
                return False
            
            # 调用交易回调
            if self.trade_callback:
                try:
                    self.trade_callback(trade_info)
                except Exception as e:
                    logger.error(f"交易回调错误: {e}")
                    self.add_log(f"交易回调错误: {e}", "error")
            
            return True
            
        except Exception as e:
            error_msg = f"执行交易错误: {e}"
            logger.error(error_msg)
            self.add_log(error_msg, "error")
            trade_info['status'] = 'ERROR'
            trade_info['error'] = str(e)
            
            # 调用交易回调报告错误
            if self.trade_callback:
                try:
                    self.trade_callback(trade_info)
                except Exception as callback_e:
                    logger.error(f"交易回调错误: {callback_e}")
            
            return False
    
    def process_trading_logic(self):
        """
        处理交易逻辑
        根据当前状态和价格变化执行相应的交易策略
        """
        try:
            close_price = self.last_close_price
            
            # 记录BOLL突破事件
            self.check_boll_breakthrough(close_price)
            
            # 根据当前状态执行相应逻辑
            if self.current_state == TradingState.WAITING:
                # 等待开仓状态：监控价格突破UP
                if close_price > self.boll_up:
                    breakthrough_msg = f"📈 价格突破BOLL上轨: {close_price:.4f} > {self.boll_up:.4f}"
                    self.add_log(breakthrough_msg, "warning")
                    self.change_state(TradingState.BREAKTHROUGH_UP_WAITING, "K线收盘到BOLL UP之上")
            
            elif self.current_state == TradingState.BREAKTHROUGH_UP_WAITING:
                # 突破UP等待状态：等待跌破UP开SHORT
                if close_price < self.boll_up:
                    fallback_msg = f"📉 价格跌破BOLL上轨: {close_price:.4f} < {self.boll_up:.4f}"
                    self.add_log(fallback_msg, "warning")
                    self.execute_trade("SELL", "开仓", "收盘价格跌破UP")
                    self.change_state(TradingState.HOLDING_SHORT, "开SHORT成功")
            
            elif self.current_state == TradingState.HOLDING_SHORT:
                # 持仓SHORT状态
                if close_price > self.boll_up:
                    # 情况A: 价格重新突破UP，止损
                    breakthrough_again_msg = f"⚠️ 价格重新突破BOLL上轨: {close_price:.4f} > {self.boll_up:.4f}"
                    self.add_log(breakthrough_again_msg, "error")
                    self.execute_trade("BUY", "止损", "K线价格收盘到UP之上")
                    self.change_state(TradingState.BREAKTHROUGH_UP_AGAIN_WAITING, "再次突破UP，已止损SHORT")
                elif close_price < self.boll_mb:
                    # 情况B: 价格跌破中轨
                    below_mb_msg = f"📉 价格跌破BOLL中轨: {close_price:.4f} < {self.boll_mb:.4f}"
                    self.add_log(below_mb_msg, "success")
                    self.change_state(TradingState.BELOW_MB_WAITING, "K线收盘价格跌破BOLL中轨")
            
            elif self.current_state == TradingState.BREAKTHROUGH_UP_AGAIN_WAITING:
                # 再次突破UP后等待状态
                if close_price < self.boll_up:
                    fallback_again_msg = f"📉 价格再次跌破BOLL上轨: {close_price:.4f} < {self.boll_up:.4f}"
                    self.add_log(fallback_again_msg, "warning")
                    self.execute_trade("SELL", "开仓", "K线收盘价跌破UP")
                    self.change_state(TradingState.HOLDING_SHORT, "再开SHORT成功")
            
            elif self.current_state == TradingState.BELOW_MB_WAITING:
                # 跌破中轨等待状态
                if close_price > self.boll_mb:
                    # 情况1: 突破中轨，止盈SHORT并开LONG
                    above_mb_msg = f"📈 价格突破BOLL中轨: {close_price:.4f} > {self.boll_mb:.4f}"
                    self.add_log(above_mb_msg, "success")
                    self.execute_trade("BUY", "止盈", "K线收盘价格突破BOLL中轨")
                    self.execute_trade("BUY", "开仓", "立即开LONG")
                    self.change_state(TradingState.HOLDING_LONG, "已止盈SHORT，持有LONG")
                elif close_price < self.boll_dn:
                    # 情况2: 跌破DN
                    below_dn_msg = f"📉 价格跌破BOLL下轨: {close_price:.4f} < {self.boll_dn:.4f}"
                    self.add_log(below_dn_msg, "warning")
                    self.change_state(TradingState.BELOW_DN_WAITING, "K线收盘价格跌破DN")
            
            elif self.current_state == TradingState.HOLDING_LONG:
                # 持仓LONG状态
                if close_price < self.boll_mb:
                    # 收盘价跌破中轨，止损
                    below_mb_long_msg = f"⚠️ 价格跌破BOLL中轨: {close_price:.4f} < {self.boll_mb:.4f}"
                    self.add_log(below_mb_long_msg, "error")
                    self.execute_trade("SELL", "止损", "收盘价跌破中轨")
                    self.change_state(TradingState.WAITING, "已止损LONG")
                elif close_price > self.boll_up:
                    # 收盘价突破UP
                    above_up_long_msg = f"📈 价格突破BOLL上轨: {close_price:.4f} > {self.boll_up:.4f}"
                    self.add_log(above_up_long_msg, "success")
                    self.change_state(TradingState.BREAKTHROUGH_UP_WAITING, "收盘价格突破UP")
                    self.execute_trade("SELL", "止盈", "收盘价突破UP")
                    self.execute_trade("SELL", "开仓", "立即开SHORT")
                    self.change_state(TradingState.HOLDING_SHORT, "持有SHORT")
            
            elif self.current_state == TradingState.BELOW_DN_WAITING:
                # 跌破DN等待状态
                if close_price > self.boll_dn:
                    above_dn_msg = f"📈 价格反弹至BOLL下轨之上: {close_price:.4f} > {self.boll_dn:.4f}"
                    self.add_log(above_dn_msg, "success")
                    self.execute_trade("BUY", "止盈", "K线收盘价格大于DN")
                    self.execute_trade("BUY", "开仓", "立即开LONG")
                    self.change_state(TradingState.HOLDING_LONG, "持有LONG")
            
            elif self.current_state == TradingState.ABOVE_MB_WAITING:
                # 突破中轨等待状态
                if close_price > self.boll_up:
                    # 继续突破UP
                    continue_up_msg = f"📈 价格继续突破BOLL上轨: {close_price:.4f} > {self.boll_up:.4f}"
                    self.add_log(continue_up_msg, "warning")
                    self.change_state(TradingState.BREAKTHROUGH_UP_WAITING, "K线收盘价继续突破UP")
                elif close_price < self.boll_mb:
                    # 跌破中轨，止盈LONG并开SHORT
                    below_mb_again_msg = f"📉 价格跌破BOLL中轨: {close_price:.4f} < {self.boll_mb:.4f}"
                    self.add_log(below_mb_again_msg, "success")
                    self.execute_trade("SELL", "止盈", "K线收盘价跌破中轨价格")
                    self.execute_trade("SELL", "开仓", "立即开SHORT")
                    self.change_state(TradingState.HOLDING_SHORT, "已平仓止盈，持有SHORT")
            
        except Exception as e:
            error_msg = f"❌ 处理交易逻辑错误: {e}"
            logger.error(error_msg)
            self.add_log(error_msg, "error")
    
    def check_boll_breakthrough(self, current_price: float):
        """
        检查BOLL突破事件并记录日志
        
        Args:
            current_price: 当前价格
        """
        try:
            # 检查是否有BOLL数据
            if self.boll_up == 0 or self.boll_mb == 0 or self.boll_dn == 0:
                return
            
            # 计算价格相对于BOLL轨道的位置
            if current_price > self.boll_up:
                position_msg = f"📊 价格位置: 上轨之上 ({current_price:.4f} > {self.boll_up:.4f})"
                if not hasattr(self, '_last_boll_position') or self._last_boll_position != 'above_up':
                    self.add_log(position_msg, "warning")
                    self._last_boll_position = 'above_up'
            elif current_price < self.boll_dn:
                position_msg = f"📊 价格位置: 下轨之下 ({current_price:.4f} < {self.boll_dn:.4f})"
                if not hasattr(self, '_last_boll_position') or self._last_boll_position != 'below_dn':
                    self.add_log(position_msg, "warning")
                    self._last_boll_position = 'below_dn'
            elif self.boll_dn <= current_price <= self.boll_mb:
                position_msg = f"📊 价格位置: 下轨与中轨之间 ({self.boll_dn:.4f} ≤ {current_price:.4f} ≤ {self.boll_mb:.4f})"
                if not hasattr(self, '_last_boll_position') or self._last_boll_position != 'between_dn_mb':
                    self.add_log(position_msg, "info")
                    self._last_boll_position = 'between_dn_mb'
            elif self.boll_mb <= current_price <= self.boll_up:
                position_msg = f"📊 价格位置: 中轨与上轨之间 ({self.boll_mb:.4f} ≤ {current_price:.4f} ≤ {self.boll_up:.4f})"
                if not hasattr(self, '_last_boll_position') or self._last_boll_position != 'between_mb_up':
                    self.add_log(position_msg, "info")
                    self._last_boll_position = 'between_mb_up'
                    
        except Exception as e:
            logger.error(f"检查BOLL突破事件错误: {e}")

    def monitoring_loop(self):
        """
        监控循环
        持续监控市场数据并执行交易逻辑
        """
        logger.info("🔄 开始监控循环")
        self.add_log("🔄 开始监控循环", "info")
        
        last_state = None
        last_position_side = None
        
        while self.is_running:
            try:
                # 更新市场数据
                if self.update_market_data():
                    # 检查状态变化
                    if last_state != self.current_state:
                        if last_state is not None:
                            state_change_msg = f"🔄 状态变化: {last_state.value} → {self.current_state.value}"
                            logger.info(state_change_msg)
                            self.add_log(state_change_msg, "warning")
                        last_state = self.current_state
                    
                    # 检查持仓变化
                    current_position_side = self.position_side
                    if last_position_side != current_position_side:
                        if current_position_side == PositionSide.SHORT:
                            position_msg = "📉 持有SHORT"
                            self.add_log(position_msg, "success")
                        elif current_position_side == PositionSide.LONG:
                            position_msg = "📈 持有LONG"
                            self.add_log(position_msg, "success")
                        elif current_position_side == PositionSide.NONE:
                            position_msg = "🔄 无持仓"
                            self.add_log(position_msg, "info")
                        last_position_side = current_position_side
                    
                    # 记录当前状态信息（每5次循环记录一次，避免日志过多）
                    if hasattr(self, '_loop_count'):
                        self._loop_count += 1
                    else:
                        self._loop_count = 1
                    
                    if self._loop_count % 5 == 0:
                        status_msg = f"📊 当前状态: {self.current_state.value}, 价格: {self.last_close_price:.4f}, UP: {self.boll_up:.4f}, MB: {self.boll_mb:.4f}, DN: {self.boll_dn:.4f}"
                        logger.info(status_msg)
                        self.add_log(status_msg, "info")
                    
                    # 处理交易逻辑
                    self.process_trading_logic()
                
                # 等待下次更新
                time.sleep(self.update_interval)
                
            except Exception as e:
                error_msg = f"❌ 监控循环错误: {e}"
                logger.error(error_msg)
                self.add_log(error_msg, "error")
                time.sleep(5)  # 错误后短暂等待
    
    def start(self):
        """
        启动自动交易策略
        """
        if self.is_running:
            warning_msg = "⚠️ 交易策略已在运行中"
            logger.warning(warning_msg)
            self.add_log(warning_msg, "warning")
            return False
        
        try:
            self.is_running = True
            self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            success_msg = f"🚀 自动交易策略已启动 - 交易对: {self.symbol}, 时间间隔: {self.interval}"
            logger.info(success_msg)
            self.add_log(success_msg, "success")
            return True
            
        except Exception as e:
            error_msg = f"❌ 启动交易策略错误: {e}"
            logger.error(error_msg)
            self.add_log(error_msg, "error")
            self.is_running = False
            return False
    
    def stop(self):
        """
        停止自动交易策略
        """
        if not self.is_running:
            warning_msg = "⚠️ 交易策略未在运行"
            logger.warning(warning_msg)
            self.add_log(warning_msg, "warning")
            return False
        
        try:
            self.is_running = False
            
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5)
            
            success_msg = "🛑 自动交易策略已停止"
            logger.info(success_msg)
            self.add_log(success_msg, "success")
            return True
            
        except Exception as e:
            error_msg = f"❌ 停止交易策略错误: {e}"
            logger.error(error_msg)
            self.add_log(error_msg, "error")
            return False

    def get_status(self) -> Dict:
        """
        获取当前状态信息
        
        Returns:
            包含当前状态的字典
        """
        return {
            'is_running': self.is_running,
            'current_state': self.current_state.value,
            'position_side': self.position_side.value,
            'position_size': self.position_size,
            'entry_price': self.entry_price,
            'current_price': self.last_close_price,
            'boll_up': self.boll_up,
            'boll_mb': self.boll_mb,
            'boll_dn': self.boll_dn,
            'symbol': self.symbol,
            'interval': self.interval
        }

# 全局交易引擎实例
trading_engine = None

def get_trading_engine() -> TradingEngine:
    """
    获取全局交易引擎实例
    
    Returns:
        TradingEngine实例
    """
    global trading_engine
    if trading_engine is None:
        trading_engine = TradingEngine()
    return trading_engine