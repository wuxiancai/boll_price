#!/usr/bin/env bash
set -e

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_BIN="python3"

echo "🚀 开始部署 boll_ocr_cross.py"

# -------- 检查系统类型 --------
OS="$(uname -s)"
echo "🔍 检测系统: $OS"

# -------- 检查 Python --------
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装 Python3"
    exit 1
fi

# -------- 创建虚拟环境 --------
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 创建虚拟环境..."
    $PYTHON_BIN -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# -------- 升级 pip --------
pip install --upgrade pip

# -------- 安装 Python 依赖 --------
pip install -r requirements.txt
pip install tesseract-ocr
# -------- 检查/安装 Chrome --------
if [[ "$OS" == "Darwin" ]]; then
    # macOS
    if ! command -v /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome &> /dev/null; then
        echo "🔧 未检测到 Chrome，使用 brew 安装..."
        if ! command -v brew &> /dev/null; then
            echo "❌ 未安装 Homebrew，请先安装 Homebrew"
            exit 1
        fi
        brew install --cask google-chrome
    else
        echo "✅ Chrome 已安装"
    fi
else
    # Ubuntu
    if ! command -v google-chrome &> /dev/null; then
        echo "🔧 未检测到 Chrome，开始安装..."
        sudo apt-get update
        sudo apt-get install -y wget gnupg unzip xvfb fonts-liberation libappindicator3-1 \
            libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 \
            libnspr4 libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils
        wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb
        sudo apt-get install -y /tmp/chrome.deb || sudo dpkg -i /tmp/chrome.deb
        rm /tmp/chrome.deb
    else
        echo "✅ Chrome 已安装"
    fi
fi

# -------- 安装 Playwright 浏览器驱动 --------
playwright install chromium

# -------- 运行程序 --------
echo "🚀 启动 boll_ocr_cross.py..."
python "$PROJECT_DIR/boll_ocr_cross.py"