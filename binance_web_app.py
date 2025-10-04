"""
币安合约账户信息Web应用
提供Web界面展示币安合约账户的各种信息
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from binance_client import BinanceFuturesClient
from trading_strategy import get_trading_engine
from binance_config import get_trading_config
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局客户端实例
binance_client = None

def init_binance_client():
    """初始化币安合约客户端"""
    global binance_client
    try:
        binance_client = BinanceFuturesClient()
        logger.info("币安合约客户端初始化成功")
        return True
    except Exception as e:
        logger.error(f"币安合约客户端初始化失败: {e}")
        return False

@app.route('/')
def index():
    """
    主页面
    """
    # 获取交易策略配置
    config = get_trading_config()
    return render_template('index.html', config=config)

@app.route('/api/account/info')
def get_account_info():
    """
    获取合约账户基本信息API
    """
    try:
        if not binance_client:
            return jsonify({'error': '币安客户端未初始化'}), 500
        
        account_info = binance_client.get_futures_account_info()
        if account_info:
            return jsonify({
                'success': True,
                'data': account_info,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': '获取合约账户信息失败'}), 500
            
    except Exception as e:
        logger.error(f"获取合约账户信息API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/account/balances')
def get_balances():
    """
    获取合约账户余额API
    """
    try:
        if not binance_client:
            return jsonify({'error': '币安客户端未初始化'}), 500
        
        show_zero = request.args.get('show_zero', 'false').lower() == 'true'
        balances = binance_client.get_futures_balances(show_zero=show_zero)
        
        return jsonify({
            'success': True,
            'data': balances,
            'count': len(balances),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取合约余额API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/account/orders')
def get_open_orders():
    """
    获取合约当前挂单API
    """
    try:
        if not binance_client:
            return jsonify({'error': '币安客户端未初始化'}), 500
        
        orders = binance_client.get_futures_open_orders()
        
        return jsonify({
            'success': True,
            'data': orders,
            'count': len(orders),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取合约挂单API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/account/trades')
def get_recent_trades():
    """
    获取合约最近交易记录API
    """
    try:
        if not binance_client:
            return jsonify({'error': '币安客户端未初始化'}), 500
        
        limit = int(request.args.get('limit', 10))
        symbol = request.args.get('symbol', None)
        
        trades = binance_client.get_futures_recent_trades(symbol=symbol, limit=limit)
        
        return jsonify({
            'success': True,
            'data': trades,
            'count': len(trades),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取合约交易记录API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/market/tickers')
def get_market_tickers():
    """
    获取合约24小时行情API
    """
    try:
        if not binance_client:
            return jsonify({'error': '币安客户端未初始化'}), 500
        
        limit = int(request.args.get('limit', 10))
        tickers = binance_client.get_futures_24hr_ticker(limit=limit)
        
        return jsonify({
            'success': True,
            'data': tickers,
            'count': len(tickers),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取合约行情API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/account/positions')
def get_positions():
    """
    获取合约持仓信息API
    """
    try:
        if not binance_client:
            return jsonify({'error': '币安客户端未初始化'}), 500
        
        positions = binance_client.get_futures_positions()
        
        return jsonify({
            'success': True,
            'data': positions,
            'count': len(positions),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取合约持仓API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/account/income')
def get_income_history():
    """
    获取合约收益历史API
    """
    try:
        if not binance_client:
            return jsonify({'error': '币安客户端未初始化'}), 500
        
        limit = int(request.args.get('limit', 10))
        income = binance_client.get_futures_income_history(limit=limit)
        
        return jsonify({
            'success': True,
            'data': income,
            'count': len(income),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取合约收益历史API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/market/klines')
def get_klines():
    """
    获取K线数据和BOLL指标API
    """
    try:
        if not binance_client:
            return jsonify({'error': '币安客户端未初始化'}), 500
        
        # 获取请求参数
        symbol = request.args.get('symbol', 'BTCUSDT')
        interval = request.args.get('interval', '15m')
        limit = int(request.args.get('limit', 50))
        
        # 第一步：从币安API获取50根K线数据并存储到数据库
        klines = binance_client.get_klines(symbol=symbol, interval=interval, limit=limit)
        
        if not klines:
            return jsonify({'error': '获取K线数据失败'}), 500
        
        # 第三步：计算BOLL指标并存储到数据库（使用配置参数）
        trading_config = get_trading_config()
        boll_data = binance_client.calculate_boll(
            klines, symbol, interval, 
            period=trading_config['boll_period'], 
            std_dev=trading_config['boll_std_dev']
        )
        
        # 组合数据用于前端显示
        chart_data = []
        for i, kline in enumerate(klines):
            chart_data.append({
                'timestamp': kline['timestamp'],
                'open': kline['open'],
                'high': kline['high'],
                'low': kline['low'],
                'close': kline['close'],
                'volume': kline['volume'],
                'upper': boll_data['upper'][i] if i < len(boll_data['upper']) else None,
                'middle': boll_data['middle'][i] if i < len(boll_data['middle']) else None,
                'lower': boll_data['lower'][i] if i < len(boll_data['lower']) else None
            })
        
        return jsonify({
            'success': True,
            'data': {
                'klines': chart_data,
                'boll': boll_data
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取K线数据API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/all')
def get_all_data():
    """
    获取所有合约账户数据API
    """
    try:
        if not binance_client:
            return jsonify({'error': '客户端未初始化'}), 500
        
        all_data = binance_client.get_all_futures_data()
        
        if all_data:
            return jsonify({
                'success': True,
                'data': all_data,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': '获取合约数据失败'}), 500
            
    except Exception as e:
        logger.error(f"获取所有合约数据API错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def get_api_status():
    """
    获取API状态
    """
    try:
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'client_initialized': binance_client is not None
        })
    except Exception as e:
        logger.error(f"获取API状态失败: {e}")
        return jsonify({'error': str(e)}), 500

# 交易策略相关API
@app.route('/api/trading/status')
def get_trading_status():
    """
    获取交易策略状态
    """
    try:
        trading_engine = get_trading_engine()
        status = trading_engine.get_status()
        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        logger.error(f"获取交易策略状态失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trading/start', methods=['POST'])
def start_trading():
    """
    启动自动交易策略
    """
    try:
        trading_engine = get_trading_engine()
        
        # 设置回调函数
        def state_change_callback(old_state, new_state, reason):
            logger.info(f"策略状态变化: {old_state.value} -> {new_state.value} ({reason})")
        
        def trade_callback(trade_info):
            logger.info(f"交易执行: {trade_info}")
        
        trading_engine.set_callbacks(state_change_callback, trade_callback)
        
        if trading_engine.start():
            return jsonify({
                'status': 'success',
                'message': '自动交易策略已启动'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '启动自动交易策略失败'
            }), 500
            
    except Exception as e:
        logger.error(f"启动交易策略失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trading/stop', methods=['POST'])
def stop_trading():
    """
    停止自动交易策略
    """
    try:
        trading_engine = get_trading_engine()
        
        if trading_engine.stop():
            return jsonify({
                'status': 'success',
                'message': '自动交易策略已停止'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '停止自动交易策略失败'
            }), 500
            
    except Exception as e:
        logger.error(f"停止交易策略失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trading/config', methods=['GET', 'POST'])
def trading_config():
    """
    获取或设置交易策略配置
    """
    try:
        trading_engine = get_trading_engine()
        
        if request.method == 'GET':
            # 获取当前配置
            config = {
                'symbol': trading_engine.symbol,
                'interval': trading_engine.interval,
                'update_interval': trading_engine.update_interval
            }
            return jsonify({
                'status': 'success',
                'data': config
            })
        
        elif request.method == 'POST':
            # 更新配置
            data = request.get_json()
            
            if 'symbol' in data:
                trading_engine.symbol = data['symbol']
            if 'interval' in data:
                trading_engine.interval = data['interval']
            if 'update_interval' in data:
                trading_engine.update_interval = data['update_interval']
            
            return jsonify({
                'status': 'success',
                'message': '交易策略配置已更新'
            })
            
    except Exception as e:
        logger.error(f"交易策略配置操作失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trading/logs', methods=['GET'])
def trading_logs():
    """
    获取交易日志
    """
    try:
        trading_engine = get_trading_engine()
        logs = trading_engine.get_logs()
        
        return jsonify({
            'success': True,
            'data': logs
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取日志失败: {str(e)}'
        })

@app.route('/api/trading/logs', methods=['DELETE'])
def clear_trading_logs():
    """
    清空交易日志
    """
    try:
        trading_engine = get_trading_engine()
        trading_engine.clear_logs()
        
        return jsonify({
            'success': True,
            'message': '日志已清空'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'清空日志失败: {str(e)}'
        })





@app.errorhandler(404)
def not_found(error):
    """
    404错误处理
    """
    return jsonify({'error': '页面未找到'}), 404

@app.errorhandler(500)
def internal_error(error):
    """
    500错误处理
    """
    return jsonify({'error': '服务器内部错误'}), 500

def auto_start_trading():
    """
    自动启动交易策略
    """
    try:
        trading_engine = get_trading_engine()
        if trading_engine:
            trading_engine.start()
            logger.info("🚀 交易策略已自动启动")
            print("🚀 交易策略已自动启动")
        else:
            logger.error("❌ 交易引擎初始化失败")
            print("❌ 交易引擎初始化失败")
    except Exception as e:
        logger.error(f"❌ 自动启动交易策略失败: {e}")
        print(f"❌ 自动启动交易策略失败: {e}")

if __name__ == '__main__':
    # 初始化币安客户端
    if init_binance_client():
        print("🚀 币安账户信息Web应用启动中...")
        print("📱 访问地址: http://localhost:9998")
        print("📊 API文档:")
        print("  - 合约账户信息: /api/account/info")
        print("  - 合约账户余额: /api/account/balances")
        print("  - 合约持仓信息: /api/account/positions")
        print("  - 合约当前挂单: /api/account/orders")
        print("  - 合约交易记录: /api/account/trades")
        print("  - 合约收益历史: /api/account/income")
        print("  - 合约市场行情: /api/market/tickers")
        print("  - K线数据和BOLL指标: /api/market/klines")
        print("  - 所有数据: /api/account/all")
        print("  - API状态: /api/status")
        
        # 自动启动交易策略
        auto_start_trading()
        
        # 启动Flask应用
        app.run(host='0.0.0.0', port=9999, debug=True)
    else:
        print("❌ 币安客户端初始化失败，无法启动Web应用")
        print("请检查API密钥配置")