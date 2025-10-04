"""
币安API配置文件
包含API密钥和基础配置信息
"""

# 币安API配置
BINANCE_API_KEY = "yHEbiLZVNTpX81Vc6UYPJpIsPFa6P461R1OVHHq7JcLs60B4GPcVSEq7Chw8OCGG"
BINANCE_SECRET_KEY = "gwbbkf4uCPTJbMH6M3QZFJ4qtkqqzasg28vVZb20nkWwe7kDCZsSRSMjidHCb3Th"

# 币安API基础URL（现货交易）
BINANCE_SPOT_BASE_URL = "https://api.binance.com"

# 币安合约API基础URL
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"

# 测试网配置（如果需要使用测试网）
TESTNET_API_KEY = ""
TESTNET_SECRET_KEY = ""
TESTNET_SPOT_BASE_URL = "https://testnet.binance.vision"
TESTNET_FUTURES_BASE_URL = "https://testnet.binancefuture.com"

# 是否使用测试网
USE_TESTNET = False

# API请求超时设置（秒）
REQUEST_TIMEOUT = 30

# ==================== 交易策略配置 ====================
# 默认交易币对
DEFAULT_SYMBOL = "BTCUSDT"

# 默认K线周期
DEFAULT_KLINE_INTERVAL = "15m"

# 默认开仓金额比例（总钱包余额的百分比）
DEFAULT_POSITION_RATIO = 0.70  # 70%

# 默认杠杆倍数
DEFAULT_LEVERAGE = 10

# 默认手续费率
DEFAULT_FEE_RATE = 0.0005  # 0.05%

# BOLL策略参数
BOLL_PERIOD = 20  # BOLL指标周期
BOLL_STD_DEV = 2  # 标准差倍数

# 交易策略配置函数
def get_trading_config():
    """
    获取交易策略配置
    
    Returns:
        dict: 交易策略配置字典
    """
    return {
        'symbol': DEFAULT_SYMBOL,
        'kline_interval': DEFAULT_KLINE_INTERVAL,
        'position_ratio': DEFAULT_POSITION_RATIO,
        'leverage': DEFAULT_LEVERAGE,
        'fee_rate': DEFAULT_FEE_RATE,
        'boll_period': BOLL_PERIOD,
        'boll_std_dev': BOLL_STD_DEV
    }

# 获取API配置的函数
def get_api_config(api_type='futures'):
    """
    获取当前使用的API配置
    
    Args:
        api_type (str): API类型，'spot'为现货，'futures'为合约
    
    Returns:
        dict: 包含API密钥和基础URL的配置字典
    """
    if USE_TESTNET:
        base_url = TESTNET_FUTURES_BASE_URL if api_type == 'futures' else TESTNET_SPOT_BASE_URL
        return {
            'api_key': TESTNET_API_KEY,
            'api_secret': TESTNET_SECRET_KEY,
            'base_url': base_url,
            'timeout': REQUEST_TIMEOUT,
            'api_type': api_type
        }
    else:
        base_url = BINANCE_FUTURES_BASE_URL if api_type == 'futures' else BINANCE_SPOT_BASE_URL
        return {
            'api_key': BINANCE_API_KEY,
            'api_secret': BINANCE_SECRET_KEY,
            'base_url': base_url,
            'timeout': REQUEST_TIMEOUT,
            'api_type': api_type
        }

# 验证API配置是否完整
def validate_api_config(api_type='futures'):
    """
    验证API配置是否完整
    
    Args:
        api_type (str): API类型，'spot'为现货，'futures'为合约
    
    Returns:
        bool: 配置是否有效
    """
    config = get_api_config(api_type)
    return bool(config['api_key'] and config['api_secret'])