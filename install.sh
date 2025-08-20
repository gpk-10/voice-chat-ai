#!/bin/bash

# 语音对话AI系统 - 依赖安装脚本
# 支持 Ubuntu/Debian/CentOS/Arch Linux

set -e  # 遇到错误立即退出

echo "🎙️ 语音对话AI系统 - 依赖安装"
echo "=================================="

# 检测操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
elif type lsb_release >/dev/null 2>&1; then
    OS=$(lsb_release -si)
    VER=$(lsb_release -sr)
else
    OS=$(uname -s)
    VER=$(uname -r)
fi

echo "📋 检测到系统: $OS $VER"

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python版本过低: $python_version (需要 >= $required_version)"
    exit 1
fi

echo "✅ Python版本: $python_version"

# 安装系统依赖
echo "📦 安装系统依赖..."

install_system_deps() {
    case $OS in
        "Ubuntu"* | "Debian"*)
            echo "🔧 使用 apt 安装系统依赖..."
            sudo apt update
            sudo apt install -y \
                python3-pip \
                python3-dev \
                python3-venv \
                portaudio19-dev \
                alsa-utils \
                libasound2-dev \
                pkg-config \
                ffmpeg \
                curl \
                wget
            ;;
        "CentOS"* | "Red Hat"* | "Fedora"*)
            echo "🔧 使用 yum/dnf 安装系统依赖..."
            if command -v dnf &> /dev/null; then
                PKG_MANAGER="dnf"
            else
                PKG_MANAGER="yum"
            fi
            
            sudo $PKG_MANAGER install -y \
                python3-pip \
                python3-devel \
                portaudio-devel \
                alsa-lib-devel \
                pkgconfig \
                ffmpeg \
                curl \
                wget
            ;;
        "Arch"*)
            echo "🔧 使用 pacman 安装系统依赖..."
            sudo pacman -Sy --noconfirm \
                python-pip \
                portaudio \
                alsa-lib \
                alsa-utils \
                pkgconf \
                ffmpeg \
                curl \
                wget
            ;;
        *)
            echo "⚠️ 未识别的系统，请手动安装以下依赖:"
            echo "   - Python 3.8+"
            echo "   - PortAudio development library"
            echo "   - ALSA development library"
            echo "   - FFmpeg"
            echo "   - pkg-config"
            ;;
    esac
}

install_system_deps

# 创建虚拟环境（可选）
read -p "🐍 是否创建Python虚拟环境？(推荐) [y/N]: " create_venv
if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "📁 创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ 虚拟环境已创建并激活"
    echo "💡 使用 'source venv/bin/activate' 激活环境"
    echo "💡 使用 'deactivate' 退出环境"
fi

# 升级pip
echo "⬆️ 升级pip..."
python3 -m pip install --upgrade pip

# 安装Python依赖
echo "📦 安装Python依赖包..."
pip3 install -r requirements.txt

# 验证关键依赖
echo "🔍 验证安装..."

check_package() {
    package=$1
    if python3 -c "import $package" 2>/dev/null; then
        echo "✅ $package"
    else
        echo "❌ $package 安装失败"
        return 1
    fi
}

echo "📋 检查关键依赖:"
check_package "sounddevice" || exit 1
check_package "numpy" || exit 1
check_package "webrtcvad" || exit 1
check_package "wave" || exit 1

# 检查可选依赖
echo "📋 检查可选依赖:"
check_package "funasr" && echo "   语音识别: SenseVoice ✅" || echo "   语音识别: SenseVoice ❌"

# 检查音频设备
echo "🎵 检查音频设备..."
python3 -c "
import sounddevice as sd
try:
    devices = sd.query_devices()
    input_devices = [d for d in devices if d['max_input_channels'] > 0]
    output_devices = [d for d in devices if d['max_output_channels'] > 0]
    print(f'✅ 找到 {len(input_devices)} 个输入设备')
    print(f'✅ 找到 {len(output_devices)} 个输出设备')
    if len(input_devices) == 0:
        print('⚠️ 警告: 未找到音频输入设备')
    if len(output_devices) == 0:
        print('⚠️ 警告: 未找到音频输出设备')
except Exception as e:
    print(f'❌ 音频设备检查失败: {e}')
"

# 配置指导
echo ""
echo "🎯 安装完成！"
echo "=================================="

echo "📖 详细说明请查看 README.md 设置配置文件"
echo ""

# 创建快速启动脚本
cat > start.sh << 'EOF'
#!/bin/bash
# 快速启动脚本

# 加载.env文件（如果存在）
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    echo "📄 已加载 .env 配置文件"
fi

# 检查API密钥
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "❌ 请先设置 DEEPSEEK_API_KEY"
    echo "   方式1: 在 .env 文件中添加 DEEPSEEK_API_KEY=your_key_here"
    echo "   方式2: export DEEPSEEK_API_KEY='your_api_key_here'"
    exit 1
fi

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "🐍 虚拟环境已激活"
fi

# 启动系统
echo "🚀 启动语音对话AI系统..."
python3 main.py "$@"
EOF

chmod +x start.sh

echo "✅ 已创建快速启动脚本: ./start.sh"
echo "💡 使用方法: ./start.sh