import subprocess
import time
import pyautogui
import pytesseract
from PIL import Image, ImageGrab
import re
import os
import platform
from datetime import datetime
import random
import psutil
import asyncio
import websockets
import json
import threading
from typing import Set

# 屏幕分辨率与BOLL截图坐标的映射配置
# 格式: "宽度x高度": {"x": x坐标, "y": y坐标, "width": 宽度, "height": 高度}
RESOLUTION_SCREENSHOT_CONFIG = {
    "2048x1280": {"x": 30, "y": 390, "width": 360, "height": 50},
    # 可以根据需要添加更多分辨率配置
    "5120x1440": {"x": 30, "y": 390, "width": 360, "height": 50},
    "1680x1050": {"x": 30, "y": 390, "width": 360, "height": 50},
}

# WebSocket配置
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8080
connected_clients: Set[websockets.WebSocketServerProtocol] = set()
latest_boll_data = {"UP": "--", "MB": "--", "DN": "--", "timestamp": ""}

def check_screen_recording_permission():
    """
    检查macOS屏幕录制权限
    """
    if platform.system() != 'Darwin':  # 非macOS系统
        return True
    
    try:
        # 尝试截取一个小区域的屏幕
        test_screenshot = ImageGrab.grab(bbox=(0, 0, 10, 10))
        if test_screenshot is None:
            return False
        
        # 检查截图是否为空或全黑
        pixels = list(test_screenshot.getdata())
        if all(pixel == (0, 0, 0) for pixel in pixels):
            return False
            
        return True
    except Exception as e:
        print(f"⚠️ 屏幕录制权限检查失败: {e}")
        return False

def prompt_screen_recording_permission():
    """
    提示用户授予屏幕录制权限
    """
    print("=" * 60)
    print("🚨 需要屏幕录制权限")
    print("=" * 60)
    print("程序需要屏幕录制权限才能正常工作。")
    print()
    print("请按照以下步骤授予权限：")
    print("1. 打开 系统偏好设置 > 安全性与隐私 > 隐私")
    print("2. 在左侧列表中选择 '屏幕录制'")
    print("3. 点击左下角的锁图标解锁设置")
    print("4. 勾选 'Terminal' 或 'Python' 或当前运行程序")
    print("5. 重新启动此程序")
    print()
    print("或者在终端中运行以下命令：")
    print("sudo tccutil reset ScreenCapture")
    print("然后重新运行程序并在弹出的权限请求中点击'允许'")
    print("=" * 60)
    
    input("按回车键退出程序...")
    exit(1)

def start_chrome():
    """
    启动 Chrome/Chromium 并使用项目目录下 chrome/ 作为用户数据目录
    自适应屏幕分辨率设置窗口大小和位置
    """
    project_dir = os.path.dirname(os.path.abspath(__file__))
    chrome_user_dir = os.path.join(project_dir, "chrome")
    os.makedirs(chrome_user_dir, exist_ok=True)

    # 获取屏幕分辨率
    screen_width, screen_height = pyautogui.size()
    
    # 计算Chrome窗口大小（占屏幕的90%，但最小1200x800）
    chrome_width = max(1500, 1500)
    chrome_height = max(800, 800)
    
    print(f"🖥️ 屏幕分辨率: {screen_width}x{screen_height}")
    print(f"🌐 Chrome窗口大小: {chrome_width}x{chrome_height}")

    system = platform.system()
    url = "https://www.binance.com/zh-CN/futures/BTCUSDT"

    if system == "Darwin":  # macOS
        subprocess.Popen([
            "open", "-na", "Google Chrome",
            "--args",
            f"--user-data-dir={chrome_user_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={chrome_width},{chrome_height}",  # 自适应窗口大小
            "--window-position=0,0",   # 设置窗口位置：左上角
            "--force-device-scale-factor=1",  # 强制缩放比例为1，避免高DPI问题
            url
        ])
    elif system == "Linux":  # Ubuntu / LXDE
        subprocess.Popen([
            "chromium-browser",  # 如果用的是 google-chrome，可以改成 google-chrome
            f"--user-data-dir={chrome_user_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={chrome_width},{chrome_height}",  # 自适应窗口大小
            "--window-position=0,0",   # 设置窗口位置：左上角
            "--force-device-scale-factor=1",  # 强制缩放比例为1，避免高DPI问题
            url
        ])
    else:
        raise OSError("不支持的系统: " + system)
    
    # 等待Chrome启动
    print("⏳ 等待Chrome启动...")
    time.sleep(3)
    
    # 强制移动Chrome窗口到左上角
    try:
        # 在macOS上使用AppleScript强制移动窗口
        if system == "Darwin":
            applescript = '''
            tell application "Google Chrome"
                activate
                set bounds of front window to {0, 0, %d, %d}
            end tell
            ''' % (chrome_width, chrome_height)
            subprocess.run(["osascript", "-e", applescript], check=True)
            print("✅ Chrome窗口已强制移动到左上角")
        else:
            # Linux系统使用wmctrl（如果可用）
            try:
                subprocess.run(["wmctrl", "-r", "Google Chrome", "-e", f"0,0,0,{chrome_width},{chrome_height}"], check=True)
                print("✅ Chrome窗口已强制移动到左上角")
            except FileNotFoundError:
                print("⚠️ wmctrl未安装，无法强制移动窗口位置")
    except Exception as e:
        print(f"⚠️ 移动窗口失败: {e}")
        print("🔄 将使用默认窗口位置")

def get_random_refresh_interval():
    """
    生成3-5分钟的随机刷新间隔（以秒为单位）
    """
    return random.randint(180, 300)  # 180秒(3分钟) 到 300秒(5分钟)

def refresh_page():
    """
    刷新当前页面（使用F5键）
    """
    try:
        pyautogui.press('f5')
        print("🔄 页面已刷新")
        return True
    except Exception as e:
        print(f"❌ 页面刷新失败: {e}")
        return False

def is_chrome_running():
    """
    检测Chrome浏览器进程是否正在运行
    返回: (bool, list) - (是否运行, Chrome浏览器进程列表)
    注意：只检测Chrome浏览器进程，不包括其他可能包含chrome关键字的进程
    """
    chrome_processes = []
    system = platform.system()
    current_pid = os.getpid()  # 获取当前Python进程PID
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                proc_name = proc_info['name'].lower() if proc_info['name'] else ""
                
                # 跳过当前Python进程
                if proc.pid == current_pid:
                    continue
                
                # 根据系统检测Chrome浏览器进程名
                is_chrome_browser = False
                
                if system == "Darwin":  # macOS
                    # 更精确的Chrome浏览器进程识别
                    if ('google chrome' in proc_name or 
                        proc_name == 'chrome' or 
                        proc_name.startswith('chrome ') or
                        'chromium' in proc_name):
                        # 进一步检查命令行参数确认是浏览器进程
                        cmdline = proc_info.get('cmdline', [])
                        if cmdline and any('chrome' in arg.lower() for arg in cmdline):
                            is_chrome_browser = True
                            
                elif system == "Linux":  # Ubuntu/Linux
                    if ('chromium' in proc_name or 
                        'google-chrome' in proc_name or 
                        proc_name == 'chrome' or
                        proc_name.startswith('chrome-')):
                        # 进一步检查命令行参数确认是浏览器进程
                        cmdline = proc_info.get('cmdline', [])
                        if cmdline and any('chrome' in arg.lower() for arg in cmdline):
                            is_chrome_browser = True
                
                if is_chrome_browser:
                    chrome_processes.append(proc)
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        return len(chrome_processes) > 0, chrome_processes
        
    except Exception as e:
        print(f"⚠️ 检测Chrome进程时出错: {e}")
        return False, []

def check_chrome_health():
    """
    检查Chrome进程健康状态
    返回: bool - Chrome是否健康运行
    """
    is_running, chrome_processes = is_chrome_running()
    
    if not is_running:
        print("❌ Chrome进程未运行")
        return False
    
    try:
        # 检查Chrome进程是否响应
        for proc in chrome_processes:
            try:
                # 检查进程状态
                if proc.status() == psutil.STATUS_ZOMBIE:
                    print(f"⚠️ 发现僵尸Chrome进程: PID {proc.pid}")
                    return False
                    
                # 检查CPU使用率（如果长时间100%可能卡死）
                cpu_percent = proc.cpu_percent(interval=1)
                if cpu_percent > 95:
                    print(f"⚠️ Chrome进程CPU使用率过高: {cpu_percent}%")
                    # 注意：这里不立即判断为不健康，因为可能是正常的高负载
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        print("✅ Chrome进程健康运行")
        return True
        
    except Exception as e:
        print(f"⚠️ 检查Chrome健康状态时出错: {e}")
        return False

def kill_chrome_processes():
    """
    强制终止所有Chrome浏览器进程
    注意：只终止Chrome浏览器进程，不影响其他进程（如WebSocket服务器）
    """
    is_running, chrome_processes = is_chrome_running()
    
    if not is_running:
        print("ℹ️ 没有发现Chrome进程")
        return True
    
    print(f"🔄 发现 {len(chrome_processes)} 个Chrome进程，正在终止...")
    
    # 获取当前Python进程的PID，确保不会误杀自己
    current_pid = os.getpid()
    
    for proc in chrome_processes:
        try:
            # 确保不会终止当前Python进程
            if proc.pid == current_pid:
                print(f"⚠️ 跳过当前Python进程: PID {proc.pid}")
                continue
                
            # 检查进程命令行，确保是Chrome浏览器进程
            try:
                cmdline = proc.cmdline()
                if cmdline and any('chrome' in arg.lower() for arg in cmdline):
                    # 进一步验证是否为Chrome浏览器进程
                    proc_name = proc.name().lower()
                    if 'chrome' in proc_name or 'chromium' in proc_name:
                        print(f"🔄 终止Chrome浏览器进程: PID {proc.pid}, 名称: {proc.name()}")
                        proc.terminate()  # 优雅终止
                        
                        # 等待进程终止
                        try:
                            proc.wait(timeout=5)  # 等待5秒
                        except psutil.TimeoutExpired:
                            print(f"⚠️ 进程 {proc.pid} 未响应，强制杀死")
                            proc.kill()  # 强制杀死
                    else:
                        print(f"⚠️ 跳过非Chrome浏览器进程: PID {proc.pid}, 名称: {proc.name()}")
                else:
                    print(f"⚠️ 跳过非Chrome进程: PID {proc.pid}")
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"⚠️ 无法访问进程信息: PID {proc.pid}")
                continue
                
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"⚠️ 无法终止进程 {proc.pid}: {e}")
            continue
    
    # 再次检查是否还有Chrome进程
    time.sleep(2)
    is_still_running, remaining_processes = is_chrome_running()
    
    if is_still_running:
        print(f"⚠️ 仍有 {len(remaining_processes)} 个Chrome进程未终止")
        return False
    else:
        print("✅ 所有Chrome浏览器进程已终止")
        return True

def restart_chrome_if_needed():
    """
    检查Chrome状态，如果需要则重启Chrome
    返回: bool - 是否成功重启或Chrome正常运行
    """
    print("🔍 检查Chrome运行状态...")
    
    # 检查Chrome是否健康运行
    if check_chrome_health():
        return True
    
    print("🔄 Chrome出现问题，准备重启...")
    
    # 终止现有Chrome进程
    if not kill_chrome_processes():
        print("❌ 无法完全终止Chrome进程")
        return False
    
    # 等待一段时间确保进程完全终止
    print("⏳ 等待进程完全终止...")
    time.sleep(3)
    
    # 重新启动Chrome
    try:
        print("🚀 重新启动Chrome...")
        start_chrome()
        
        # 等待Chrome启动
        print("⏳ 等待Chrome启动...")
        time.sleep(8)
        
        # 验证Chrome是否成功启动
        if check_chrome_health():
            print("✅ Chrome重启成功")
            return True
        else:
            print("❌ Chrome重启后仍然有问题")
            return False
            
    except Exception as e:
        print(f"❌ Chrome重启失败: {e}")
        return False

def extract_boll_values(image):
    """
    OCR 提取 UP/MB/DN 的值
    优化处理：修复逗号被识别为点号的问题，并确保数值格式一致性
    """
    # 使用更好的OCR配置
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,'
    text = pytesseract.image_to_string(image, lang="eng", config=custom_config)
    
    # 预处理文本：处理常见的OCR错误
    # 将可能被误识别的字符进行替换
    text = text.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
    
    # 改进的数字模式匹配，更精确地处理BOLL价格格式
    # BOLL价格通常格式为：120,308.1 或 120.308.1
    number_patterns = [
        r'\d{1,3}[,\.]\d{3}\.\d{1,3}',  # 如 120,308.1 或 120.308.1 (标准BOLL格式)
        r'\d{1,3}[,\.]\d{3}',           # 如 120,308 或 120.308 (无小数部分)
        r'\d+\.\d{1,3}',                # 如 308.1 (简单小数格式)
        r'\d+'                          # 纯整数
    ]
    
    all_numbers = []
    for pattern in number_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # 智能处理千位分隔符和小数点
            clean_number = process_number_format(match)
            
            try:
                num_value = float(clean_number)
                # 过滤掉明显不合理的值
                if 100000 <= num_value <= 200000:  # BOLL值通常在这个范围内
                    all_numbers.append(num_value)
            except ValueError:
                continue
    
    # 去重并排序
    unique_numbers = sorted(list(set(all_numbers)), reverse=True)
    
    if len(unique_numbers) >= 3:
        # 通常UP > MB > DN，所以按降序排列后取前三个
        # 标准化数值格式：统一保留1位小数
        return {
            "UP": round(unique_numbers[0], 1),
            "MB": round(unique_numbers[1], 1), 
            "DN": round(unique_numbers[2], 1)
        }
    
    return {"error": f"未识别出足够的数值: {unique_numbers}, 原始文本: {repr(text)}"}


def process_number_format(number_str):
    """
    智能处理数字格式，正确识别千位分隔符和小数点
    
    Args:
        number_str: 原始数字字符串，如 "120.308.1" 或 "120,308.1"
    
    Returns:
        str: 清理后的数字字符串，如 "120308.1"
    """
    # 如果字符串中同时包含逗号和点号
    if ',' in number_str and '.' in number_str:
        # 找到最后一个点号的位置
        last_dot_pos = number_str.rfind('.')
        # 检查最后一个点号后面的数字长度
        decimal_part = number_str[last_dot_pos + 1:]
        
        if len(decimal_part) <= 3 and decimal_part.isdigit():
            # 最后的点号很可能是小数点
            integer_part = number_str[:last_dot_pos].replace(',', '').replace('.', '')
            return f"{integer_part}.{decimal_part}"
        else:
            # 所有的点号和逗号都是千位分隔符
            return number_str.replace(',', '').replace('.', '')
    
    # 如果只有点号，需要判断是千位分隔符还是小数点
    elif '.' in number_str and ',' not in number_str:
        # 计算点号的数量
        dot_count = number_str.count('.')
        
        if dot_count == 1:
            # 只有一个点号，检查后面的数字长度
            parts = number_str.split('.')
            if len(parts) == 2 and len(parts[1]) <= 3 and parts[1].isdigit():
                # 很可能是小数点
                return number_str
            else:
                # 很可能是千位分隔符
                return number_str.replace('.', '')
        else:
            # 多个点号，最后一个可能是小数点
            last_dot_pos = number_str.rfind('.')
            decimal_part = number_str[last_dot_pos + 1:]
            
            if len(decimal_part) <= 3 and decimal_part.isdigit():
                # 最后的点号是小数点
                integer_part = number_str[:last_dot_pos].replace('.', '')
                return f"{integer_part}.{decimal_part}"
            else:
                # 所有点号都是千位分隔符
                return number_str.replace('.', '')
    
    # 如果只有逗号，都是千位分隔符
    elif ',' in number_str and '.' not in number_str:
        return number_str.replace(',', '')
    
    # 如果既没有逗号也没有点号，直接返回
    else:
        return number_str

def validate_and_format_boll_values(result):
    """
    验证和格式化BOLL数值，确保数据一致性
    
    Args:
        result: 包含UP、MB、DN键的字典
        
    Returns:
        格式化后的结果字典，所有数值保留1位小数
    """
    formatted_result = {}
    
    for key in ["UP", "MB", "DN"]:
        if key in result:
            try:
                # 转换为浮点数并格式化为1位小数
                value = float(result[key])
                # 验证数值范围（BOLL值通常在100000-200000范围内）
                if 100000 <= value <= 200000:
                    formatted_result[key] = round(value, 1)
                else:
                    print(f"警告: {key}值 {value} 超出正常范围")
                    formatted_result[key] = round(value, 1)
            except (ValueError, TypeError):
                print(f"错误: 无法格式化{key}值: {result[key]}")
                formatted_result[key] = result[key]  # 保持原值
        else:
            formatted_result[key] = "N/A"
    
    return formatted_result
    
# 不用保存到 CSV 文件，直接通过 WebSocket 广播


async def handle_websocket_client(websocket, path):
    """
    处理WebSocket客户端连接
    
    Args:
        websocket: WebSocket连接对象
        path: 连接路径
    """
    print(f"🔗 新的WebSocket客户端连接: {websocket.remote_address}")
    connected_clients.add(websocket)
    
    try:
        # 发送当前最新的BOLL数据给新连接的客户端
        if latest_boll_data["timestamp"]:
            await websocket.send(json.dumps(latest_boll_data))
            print(f"📤 向新客户端发送最新BOLL数据: {latest_boll_data}")
        
        # 保持连接活跃，等待客户端断开
        async for message in websocket:
            # 可以处理客户端发送的消息（如果需要）
            print(f"📨 收到客户端消息: {message}")
            
    except websockets.exceptions.ConnectionClosed:
        print(f"🔌 WebSocket客户端断开连接: {websocket.remote_address}")
    except Exception as e:
        print(f"❌ WebSocket连接错误: {e}")
    finally:
        connected_clients.discard(websocket)
        print(f"🗑️ 移除客户端连接，当前连接数: {len(connected_clients)}")


async def broadcast_boll_data(boll_data):
    """
    向所有连接的WebSocket客户端广播BOLL数据
    
    Args:
        boll_data: 包含UP、MB、DN的BOLL数据字典
    """
    global latest_boll_data
    
    if not connected_clients:
        return
    
    # 更新最新数据
    latest_boll_data = {
        "UP": boll_data.get("UP", 0),
        "MB": boll_data.get("MB", 0), 
        "DN": boll_data.get("DN", 0),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 准备要发送的JSON数据
    message = json.dumps(latest_boll_data)
    
    # 向所有连接的客户端发送数据
    disconnected_clients = set()
    for client in connected_clients:
        try:
            await client.send(message)
        except websockets.exceptions.ConnectionClosed:
            disconnected_clients.add(client)
        except Exception as e:
            print(f"❌ 向客户端发送数据失败: {e}")
            disconnected_clients.add(client)
    
    # 移除断开的客户端
    for client in disconnected_clients:
        connected_clients.discard(client)
    
    if connected_clients:
        print(f"📡 BOLL数据已广播给 {len(connected_clients)} 个客户端")
        print(f"📤 广播内容: {{'UP': {latest_boll_data['UP']}, 'MB': {latest_boll_data['MB']}, 'DN': {latest_boll_data['DN']}, 'timestamp': '{latest_boll_data['timestamp']}'}}")
    else:
        print("📡 没有连接的WebSocket客户端，跳过广播")


def start_websocket_server():
    """
    启动WebSocket服务器（在单独线程中运行）
    """
    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def server_main():
            print(f"🚀 启动WebSocket服务器: ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
            server = await websockets.serve(
                handle_websocket_client, 
                WEBSOCKET_HOST, 
                WEBSOCKET_PORT
            )
            print(f"✅ WebSocket服务器已启动，等待客户端连接...")
            await server.wait_closed()
        
        try:
            loop.run_until_complete(server_main())
        except Exception as e:
            print(f"❌ WebSocket服务器启动失败: {e}")
    
    # 在单独线程中运行WebSocket服务器
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread


def broadcast_boll_data_sync(boll_data):
    """
    同步方式广播BOLL数据（从主线程调用）
    
    Args:
        boll_data: 包含UP、MB、DN的BOLL数据字典
    """
    if "error" in boll_data or boll_data.get('UP') == '--' or boll_data.get('MB') == '--' or boll_data.get('DN') == '--':
        return
    
    # 在新的事件循环中运行异步广播函数
    def run_broadcast():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(broadcast_boll_data(boll_data))
            loop.close()
        except Exception as e:
            print(f"❌ 广播BOLL数据失败: {e}")
    
    # 在单独线程中运行广播
    broadcast_thread = threading.Thread(target=run_broadcast, daemon=True)
    broadcast_thread.start()



def get_screenshot_region_by_resolution():
    """
    根据屏幕分辨率获取预配置的BOLL截图坐标
    如果当前分辨率有配置，直接返回；否则返回None，需要搜索BOLL位置
    """
    screen_width, screen_height = pyautogui.size()
    resolution_key = f"{screen_width}x{screen_height}"
    
    if resolution_key in RESOLUTION_SCREENSHOT_CONFIG:
        config = RESOLUTION_SCREENSHOT_CONFIG[resolution_key]
        print(f"✅ 使用预配置的截图坐标 ({resolution_key}): ({config['x']}, {config['y']}, {config['width']}, {config['height']})")
        return {
            'x': config['x'],
            'y': config['y'], 
            'width': config['width'],
            'height': config['height']
        }
    else:
        print(f"⚠️ 当前分辨率 {resolution_key} 没有预配置，需要搜索BOLL位置")
        return None

def main():
    # 检查屏幕录制权限
    print("🔍 检查屏幕录制权限...")
    if not check_screen_recording_permission():
        prompt_screen_recording_permission()
    print("✅ 屏幕录制权限正常")
    
    # 启动WebSocket服务器
    print("🌐 启动WebSocket服务器...")
    websocket_thread = start_websocket_server()
    time.sleep(2)  # 等待WebSocket服务器启动
    
    # 获取屏幕分辨率并检查预配置
    screen_width, screen_height = pyautogui.size()
    resolution_key = f"{screen_width}x{screen_height}"
    print(f"🖥️ 检测到屏幕分辨率: {resolution_key}")
    
    # 直接从预配置获取截图坐标
    screenshot_region = get_screenshot_region_by_resolution()
    if screenshot_region is None:
        print(f"❌ 错误：当前分辨率 {resolution_key} 没有预配置的BOLL截图坐标")
        print("请在 RESOLUTION_SCREENSHOT_CONFIG 中添加当前分辨率的配置")
        print("程序退出")
        return
    
    # 启动 Chrome
    start_chrome()
    print("⏳ 等待页面加载...")
    time.sleep(8)  # 等待页面加载完成

    # 获取项目目录路径
    project_dir = os.path.dirname(os.path.abspath(__file__))
    screenshot_path = os.path.join(project_dir, "latest_screenshot.png")

    # 初始化刷新计时器
    refresh_interval = get_random_refresh_interval()
    last_refresh_time = time.time()
    print(f"⏰ 下次页面刷新将在 {refresh_interval//60} 分 {refresh_interval%60} 秒后进行")
    print("🔍 Chrome监控策略: 页面刷新后检查 + 截图失败时检查")

    # 循环截图 OCR
    while True:
        current_time = time.time()
        
        # 检查是否需要刷新页面
        if current_time - last_refresh_time >= refresh_interval:
            refresh_page()
            time.sleep(3)  # 等待页面刷新完成
            
            # 页面刷新后立即检查Chrome健康状态
            print("🔍 页面刷新后检查Chrome状态...")
            if not restart_chrome_if_needed():
                print("❌ Chrome重启失败，程序将继续尝试...")
            
            # 重新设置下次刷新时间
            refresh_interval = get_random_refresh_interval()
            last_refresh_time = current_time
            print(f"⏰ 下次页面刷新将在 {refresh_interval//60} 分 {refresh_interval%60} 秒后进行")

        # 使用预配置的截图区域进行截图
        try:
            screenshot = pyautogui.screenshot(region=(
                screenshot_region['x'], 
                screenshot_region['y'], 
                screenshot_region['width'], 
                screenshot_region['height']
            ))
            
            if screenshot is None:
                print("❌ 截图失败：返回None，可能Chrome出现问题")
                # 立即检查Chrome状态
                if not restart_chrome_if_needed():
                    print("❌ Chrome重启失败")
                time.sleep(3)  # 等待Chrome重启
                continue
                
        except Exception as screenshot_error:
            print(f"❌ 截图失败: {screenshot_error}，可能Chrome出现问题")
            # 立即检查Chrome状态
            if not restart_chrome_if_needed():
                print("❌ Chrome重启失败")
            time.sleep(3)  # 等待Chrome重启
            continue

        # 保存截图到项目目录（覆盖保存）
        try:
            screenshot.save(screenshot_path)
        except Exception as save_error:
            print(f"⚠️ 保存截图失败: {save_error}")
        


        # OCR 提取
        try:
            result = extract_boll_values(screenshot)
            print("📷 识别结果:", result)
            
            # 通过WebSocket广播BOLL数据
            if "error" not in result and result.get('UP') != '--' and result.get('MB') != '--' and result.get('DN') != '--':
                broadcast_boll_data_sync(result)
                # 打印广播出去的BOLL值
                print(f"📡 \033[34m广播结果: {{'UP': {result['UP']}, 'MB': {result['MB']}, 'DN': {result['DN']}}}\033[0m")
            else:
                print(f"⚠️ 识别出错或数据无效，跳过WebSocket广播: {result}")
            
        except Exception as ocr_error:
            print(f"❌ OCR处理失败: {ocr_error}")
            result = {'UP': '--', 'MB': '--', 'DN': '--'}  # 使用安全的默认值，避免误触发交易

        # 每 1 秒执行一次
        time.sleep(1)

if __name__ == "__main__":
    main()