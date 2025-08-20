# 🎙️ 语音对话AI系统

基于DeepSeek的实时语音对话系统，支持语音输入、AI回复和TTS播报的完整语音交互体验。

## ✨ 主要特性

- 🎤 **实时语音录制** - 支持VAD语音活动检测，自动识别说话开始和结束
- 🔍 **高精度语音识别** - 基于SenseVoice模型，支持中文语音识别
- 🤖 **智能AI对话** - 集成DeepSeek API，支持上下文对话和自动摘要
- 🔊 **自然语音播报** - 使用Edge-TTS合成，支持多种播放方式
- 💾 **完整会话管理** - 自动保存录音文件、识别结果和对话记录
- ⚡ **高性能设计** - 多线程异步处理，低延迟语音交互
- 🛡️ **智能缓存管理** - 自动管理音频缓存，支持历史回放

## 📁 项目结构

```
voice-chat-ai/
├── 📄 核心文件
│   ├── main.py                    # 主程序入口，系统协调器
│   ├── audio_recorder.py          # 音频录制模块，VAD检测和ASR队列
│   ├── speech_recognizer.py       # SenseVoice语音识别模块
│   ├── deepseek_chat.py           # DeepSeek AI对话模块，LangGraph实现
│   ├── tts_processor.py           # Edge-TTS语音合成模块
│   ├── vad_processor.py           # WebRTC VAD语音活动检测
│   ├── audio_device.py            # 音频设备管理和检测
│   └── conversation_manager.py    # 对话记录管理，会话持久化
│
├── 📋 配置文件
│   ├── requirements.txt          # Python依赖包列表
│   ├── env.example               # 环境变量模板文件
│   └── .env                      # 实际环境变量配置 (用户创建)
│
├── 🛠️ 工具脚本
│   ├── install.sh               # 自动化安装脚本
│   ├── start.sh                 # 快速启动脚本 (install.sh生成)
│   └── check_devices.py         # 音频设备检测和测试工具
│
├── 📚 文档
│   └── README.md               # 项目说明文档 (本文件)
│
└── 📂 运行时目录 (自动创建)
    ├── venv/                   # Python虚拟环境 (执行安装脚本自动创建)
    ├── recording_cache/        # 录音文件缓存 (自动清理)
    ├── tts_cache/              # TTS音频缓存 (自动清理)
    └── conversations/          # 对话记录存储
```

## 🚀 快速开始

### 环境要求

- **Python**: 3.8+
- **操作系统**: Linux / Windows
- **音频设备**: 支持16kHz采样率的麦克风和扬声器
- **网络**: 稳定的互联网连接（用于AI API和TTS服务）

### 1. 克隆项目

```bash
# 克隆项目到本地
git clone https://github.com/gpk-10/voice-chat-ai.git
cd voice-chat-ai
```

### 2. 安装依赖

**Linux (推荐)**:
```bash
# 自动安装
chmod +x install.sh
./install.sh

# 手动安装
sudo apt-get install alsa-utils libasound2-dev portaudio19-dev ffmpeg python3-dev python3-pip
pip install -r requirements.txt
```

**Windows**:
```bash
# 安装Python依赖
pip install -r requirements.txt
```

### 3. 配置API密钥

```bash
# 方式1: 环境变量
export DEEPSEEK_API_KEY="your_api_key_here"

# 方式2: 配置文件 
cp env.example .env
# 编辑 .env 文件，填入API密钥
```

### 4. 配置音频设备

**Linux**:
```bash
# 查看可用设备
python check_devices.py

# 在 .env 中配置设备
DEFAULT_DEVICE_NAME=你的麦克风名称
DEFAULT_TTS_DEVICE=hw:1,0
```

**Windows**:
```bash
# 查看可用设备
python check_devices.py

# 在 .env 中配置设备ID
DEFAULT_DEVICE_NAME=你的麦克风名称
DEFAULT_TTS_DEVICE=你的扬声器名称
```

### 5. 运行系统

```bash
# 直接运行
python main.py

# 或使用启动脚本 (Linux)
chmod +x start.sh
./start.sh
```

## 📝 环境变量配置

创建 `.env` 文件或设置环境变量：

```bash
# 必需配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 音频设备配置
DEFAULT_DEVICE_NAME=ES7210              # 麦克风设备名称
DEFAULT_TTS_DEVICE=hw:1,0               # TTS播放设备 (Linux)

# 可选配置
DEBUG=false                             # 调试模式
MAX_HISTORY=20                          # 最大对话历史
SILENCE_TIMEOUT=2.0                     # 静音超时(秒)
MIN_SPEECH_DURATION=0.5                 # 最小语音时长(秒)
DISABLE_TTS=false                       # 禁用TTS
```

## 🔧 设备适配指南

### Linux 音频设备

1. **查看ALSA设备**:
```bash
arecord -l    # 查看录音设备
aplay -l      # 查看播放设备
```

2. **设备格式**:
- 录音设备: `hw:卡号,设备号` (如 `hw:1,0`)
- 播放设备: `hw:卡号,设备号` (如 `hw:1,0`)

### Windows 音频设备

1. **查看设备**: 运行 `python check_devices.py`
2. **设备格式**: 使用设备完整名称或ID号

## 🚀 使用说明

1. 启动系统后，系统会自动初始化各个模块
2. 看到 "系统已就绪，请开始说话..." 后即可开始对话
3. 直接对着麦克风说话，系统会自动检测语音开始和结束
4. AI回复会通过TTS播放，播放完成后自动恢复录制
5. 按 `Ctrl+C` 停止系统

## 📋 系统要求

**最低配置**:
- CPU: 2核心以上
- 内存: 4GB RAM
- 存储: 2GB可用空间
- 网络: 10Mbps以上带宽

**推荐配置**:
- CPU: 4核心以上
- 内存: 8GB RAM
- 存储: 5GB可用空间
- 音频: 专业声卡或USB音频接口

## 🐛 常见问题

**Q: 无法识别音频设备？**
A: 运行 `python check_devices.py` 检查设备，确保设备名称或ID正确

**Q: 语音识别不准确？**
A: 检查麦克风位置，确保环境安静，调整 `MIN_SPEECH_DURATION` 参数

**Q: TTS播放失败？**
A: 检查网络连接，或在 `.env` 中设置 `DISABLE_TTS=true` 禁用TTS

**Q: AI回复慢或失败？**
A: 检查DeepSeek API密钥和网络连接，确保API额度充足
