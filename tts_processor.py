#!/usr/bin/env python3
"""
TTS处理器模块 - 智能文本转语音

基于Edge-TTS的高质量语音合成，优化为零延迟播放：
- Edge-TTS默认输出: 48kHz、16位、双声道 WAV
- 零延迟策略: 直接播放原始输出，无需格式转换
- 高音质播放: 保持48kHz采样率的最佳音质
"""

import asyncio
import tempfile
import os
import time
import re
import subprocess
import hashlib
import json
from typing import List, Dict, Optional
import threading
import queue
from pathlib import Path
import wave
import numpy as np

try:
    import edge_tts
    import sounddevice as sd
    
    # 禁用pygame的欢迎信息
    import os
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
    import pygame
    
    TTS_AVAILABLE = True
    pass  # Edge-TTS 可用
except ImportError as e:
    TTS_AVAILABLE = False
    print(f"❌ TTS依赖不可用: {e}")
    print("   请安装: pip install edge-tts pygame sounddevice")

class TTSProcessor:
    """智能TTS处理器 - 带音频缓存"""
    
    def __init__(self, 
                 voice: str = "zh-CN-XiaoxiaoNeural",
                 rate: str = "+0%",
                 volume: str = "+0%",
                 strategy: str = "auto",
                 audio_device_id: int = None,
                 audio_device: str = "hw:0,0",
                 cache_dir: str = "tts_cache",
                 max_cache_files: int = 20,
                 use_sounddevice: bool = True):
        """
        初始化TTS处理器
        
        Args:
            voice: 语音音色
            rate: 语速 (-50% 到 +100%)
            volume: 音量 (-50% 到 +100%)
            strategy: 合成策略 (auto/immediate/chunked/streaming)
            audio_device_id: sounddevice设备ID (优先使用)
            audio_device: ALSA设备名 (备选)
            cache_dir: 音频缓存目录
            max_cache_files: 最大缓存文件数量
            use_sounddevice: 是否使用sounddevice播放 (新增)
        """
        if not TTS_AVAILABLE:
            raise ImportError("请先安装TTS依赖: pip install edge-tts pygame sounddevice")
        
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.strategy = strategy
        self.max_cache_files = max_cache_files
        self.use_sounddevice = use_sounddevice
        self.audio_device_id = audio_device_id
        self.target_device = audio_device
        
        # 音频缓存管理
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_index_file = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_cache_index()
        
        # 配置播放设备
        self._configure_playback_device()
        
        # 语音队列和控制
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.stop_playing = threading.Event()
        
        # 启动时清理缓存，确保文件数量在限制内
        if len(self.cache_index) > self.max_cache_files:
            self._cleanup_cache()
        
        # TTS处理器初始化完成
        print(f"🎵 TTS缓存目录: {self.cache_dir.absolute()}")
        print(f"📂 当前缓存文件: {len(self.cache_index)} / {self.max_cache_files}")
        # 播放设备信息在_configure_playback_device中显示
    
    def _configure_playback_device(self):
        """配置播放设备"""
        if self.use_sounddevice:
            try:
                # 如果没有指定设备ID，尝试从ALSA设备名解析
                if self.audio_device_id is None and self.target_device:
                    self.audio_device_id = self._parse_device_id_from_alsa(self.target_device)
                
                # 验证设备是否可用
                if self.audio_device_id is not None:
                    devices = sd.query_devices()
                    if self.audio_device_id < len(devices):
                        device_info = devices[self.audio_device_id]
                        if device_info['max_output_channels'] > 0:
                            print(f"🔊 播放设备: {device_info['name']}")
                            return
                        else:
                            print(f"⚠️ 设备{self.audio_device_id}无输出通道，回退到默认")
                            self.audio_device_id = None
                
                # 使用默认输出设备
                if self.audio_device_id is None:
                    self.audio_device_id = sd.default.device[1]  # 默认输出设备
                    devices = sd.query_devices()
                    device_name = devices[self.audio_device_id]['name']
                    print(f"🔊 播放设备: {device_name} (默认)")
                    
            except Exception as e:
                print(f"⚠️ sounddevice设备配置失败: {e}")
                self.use_sounddevice = False
                self._setup_fallback_player()
        else:
            self._setup_fallback_player()
    
    def _parse_device_id_from_alsa(self, alsa_device):
        """从ALSA设备名解析sounddevice设备ID"""
        try:
            # 如果是 default，返回系统默认输出设备
            if alsa_device.lower() == 'default':
                return sd.default.device[1]  # 默认输出设备
            
            # 解析 hw:1,0 格式
            if alsa_device.startswith('hw:'):
                parts = alsa_device.split(':')[1].split(',')
                card_num = int(parts[0])
                
                # 查找对应的sounddevice设备
                devices = sd.query_devices()
                for idx, device in enumerate(devices):
                    if f"card {card_num}" in device['name'].lower() and device['max_output_channels'] > 0:
                        return idx
            
            # 如果是数字ID
            if alsa_device.isdigit():
                device_id = int(alsa_device)
                devices = sd.query_devices()
                if 0 <= device_id < len(devices) and devices[device_id]['max_output_channels'] > 0:
                    return device_id
                    
            # 按设备名称搜索
            devices = sd.query_devices()
            for idx, device in enumerate(devices):
                if alsa_device.lower() in device['name'].lower() and device['max_output_channels'] > 0:
                    return idx
                    
        except:
            pass
        return None
    
    def _setup_fallback_player(self):
        """设置备选播放器"""
        # 使用系统播放器作为备选
        self.use_system_player = True
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        except pygame.error as e:
            print(f"⚠️ pygame初始化失败: {e}")
            print("✅ 将使用aplay作为播放器")
    
    def _load_cache_index(self) -> Dict:
        """加载缓存索引"""
        try:
            if self.cache_index_file.exists():
                with open(self.cache_index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载缓存索引失败: {e}")
        return {}
    
    def _save_cache_index(self):
        """保存缓存索引"""
        try:
            with open(self.cache_index_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存缓存索引失败: {e}")
    
    def _get_text_hash(self, text: str) -> str:
        """生成文本的哈希值作为缓存键"""
        # 包含语音参数以确保唯一性
        cache_key = f"{text}|{self.voice}|{self.rate}|{self.volume}"
        return hashlib.md5(cache_key.encode('utf-8')).hexdigest()
    
    def _cleanup_cache(self):
        """清理旧的缓存文件，保持在最大数量限制内"""
        if len(self.cache_index) <= self.max_cache_files:
            return
        
        # 按访问时间排序，删除最旧的文件
        sorted_items = sorted(
            self.cache_index.items(), 
            key=lambda x: x[1].get('last_access', 0)
        )
        
        files_to_remove = len(self.cache_index) - self.max_cache_files
        for i in range(files_to_remove):
            hash_key, file_info = sorted_items[i]
            file_path = self.cache_dir / file_info['filename']
            
            try:
                if file_path.exists():
                    file_path.unlink()
                    # 静默删除旧缓存
                del self.cache_index[hash_key]
            except Exception as e:
                # 静默处理删除失败
                pass
        
        self._save_cache_index()
        # 静默完成清理
    
    def _get_cached_audio(self, text: str) -> Optional[str]:
        """获取缓存的音频文件路径"""
        text_hash = self._get_text_hash(text)
        
        if text_hash in self.cache_index:
            file_info = self.cache_index[text_hash]
            file_path = self.cache_dir / file_info['filename']
            
            if file_path.exists():
                # 更新访问时间
                self.cache_index[text_hash]['last_access'] = time.time()
                self._save_cache_index()
                # 使用缓存音频
                return str(file_path)
            else:
                # 文件不存在，从索引中移除
                del self.cache_index[text_hash]
                self._save_cache_index()
        
        return None
    
    def _cache_audio(self, text: str, audio_path: str) -> str:
        """将音频文件添加到缓存"""
        text_hash = self._get_text_hash(text)
        timestamp = int(time.time())
        filename = f"tts_{timestamp}_{text_hash[:8]}.wav"
        cached_path = self.cache_dir / filename
        
        try:
            # 复制文件到缓存目录
            import shutil
            shutil.copy2(audio_path, cached_path)
            
            # 更新缓存索引
            self.cache_index[text_hash] = {
                'text': text[:50],  # 保存前50个字符用于显示
                'filename': filename,
                'created': timestamp,
                'last_access': timestamp,
                'voice': self.voice,
                'rate': self.rate,
                'volume': self.volume
            }
            
            # 清理旧缓存
            self._cleanup_cache()
            self._save_cache_index()
            
            # 音频已缓存（内部调试信息，不显示）
            return str(cached_path)
            
        except Exception as e:
            print(f"⚠️ 缓存音频失败: {e}")
            return audio_path
    
    def _analyze_text_strategy(self, text: str) -> str:
        """分析文本并决定合成策略 - 统一使用完整合成"""
        # 不再分割，统一使用完整合成保证语音连贯性
        return "immediate"
    
    def _split_text_semantic(self, text: str) -> List[str]:
        """智能语义分割"""
        # 清理文本
        text = text.strip()
        if not text:
            return []
        
        chunks = []
        
        # 1. 按强制分割符分割
        sentences = re.split(r'[。！？]', text)
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            # 2. 按逗号和语义词分割
            parts = re.split(r'[，；]|但是|然而|另外|首先|其次|最后|因此|所以', sentence)
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                
                # 3. 长度保护分割
                if len(part) > 25:
                    # 按词语边界分割长句
                    words = part.split()
                    current_chunk = ""
                    
                    for word in words:
                        if len(current_chunk + word) <= 20:
                            current_chunk += word
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = word
                    
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                else:
                    chunks.append(part)
        
        # 过滤空块和过短块
        chunks = [chunk for chunk in chunks if len(chunk.strip()) >= 2]
        
        return chunks
    
    async def _synthesize_chunk(self, text: str) -> Optional[str]:
        """合成单个文本块 - 带缓存支持"""
        # 首先检查缓存
        cached_path = self._get_cached_audio(text)
        if cached_path:
            return cached_path
        
        try:
            # 创建临时文件用于合成
            import time
            import os
            temp_path = os.path.join(tempfile.gettempdir(), f"tts_temp_{int(time.time()*1000)}.wav")
            
            # Edge-TTS合成 - 流式转换为设备兼容格式
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, volume=self.volume)
            
            # 使用ffmpeg转换为与语音识别一致的格式（16kHz双声道）
            import subprocess
            # 使用16kHz双声道，与语音识别设备参数保持一致，避免冲突
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'mp3',     # Edge-TTS默认输出MP3
                '-i', 'pipe:0',  # 从stdin读取
                '-ac', '2',      # 双声道
                '-ar', '16000',  # 16kHz采样率（与语音识别一致）
                '-f', 'wav',     # 输出WAV格式
                '-acodec', 'pcm_s16le',  # 16位PCM
                temp_path
            ]
            
            # 启动ffmpeg进程
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 流式传输音频数据
            try:
                audio_data = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]
                
                # 发送音频数据到ffmpeg
                stdout, stderr = ffmpeg_process.communicate(input=audio_data)
                
                if ffmpeg_process.returncode != 0:
                    print(f"❌ ffmpeg转换失败: {stderr.decode()}")
                    raise Exception("音频转换失败")
                
                # 确保文件完全写入完成
                import time
                time.sleep(0.1)  # 等待文件系统同步
                    
            except Exception as e:
                print(f"❌ Edge-TTS音频合成失败: {e}")
                ffmpeg_process.terminate()
                raise e
            
            # 验证生成的WAV文件
            try:
                import wave
                with wave.open(temp_path, 'rb') as w:
                    # 验证格式正确性
                    rate = w.getframerate()
                    channels = w.getnchannels()
                    sampwidth = w.getsampwidth()
                    # 生成音频
                    
                    # 检查文件是否为空
                    frames = w.getnframes()
                    if frames == 0:
                        print("❌ 生成的音频文件为空")
                        return None
                        
            except Exception as e:
                print(f"❌ 音频文件验证失败: {e}")
                return None
            
            # 将临时文件添加到缓存并返回缓存路径
            cached_path = self._cache_audio(text, temp_path)
            
            # 删除临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return cached_path
            
        except Exception as e:
            print(f"❌ 合成失败: {e}")
            return None
    
    def _load_wav_file(self, file_path: str):
        """加载WAV文件为numpy数组"""
        try:
            with wave.open(file_path, 'rb') as wav_file:
                frames = wav_file.readframes(-1)
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sampwidth = wav_file.getsampwidth()
                
                # 转换为numpy数组
                if sampwidth == 1:
                    dtype = np.uint8
                elif sampwidth == 2:
                    dtype = np.int16
                elif sampwidth == 4:
                    dtype = np.int32
                else:
                    raise ValueError(f"不支持的位深度: {sampwidth}")
                
                audio_data = np.frombuffer(frames, dtype=dtype)
                
                # 处理多声道
                if channels > 1:
                    audio_data = audio_data.reshape(-1, channels)
                
                # 转换为float32格式 (-1.0 到 1.0)
                if sampwidth == 1:
                    audio_data = (audio_data.astype(np.float32) - 128) / 128.0
                elif sampwidth == 2:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                elif sampwidth == 4:
                    audio_data = audio_data.astype(np.float32) / 2147483648.0
                
                return audio_data, sample_rate, channels
                
        except Exception as e:
            print(f"❌ 加载WAV文件失败: {e}")
            return None, None, None
    
    def _play_audio_file(self, file_path: str):
        """
        播放音频文件
        
        优先使用sounddevice，备选aplay/pygame
        """
        try:
            if self.use_sounddevice:
                # 使用sounddevice播放
                audio_data, sample_rate, channels = self._load_wav_file(file_path)
                
                if audio_data is not None:
                    # sounddevice播放
                    
                    # 播放音频
                    sd.play(audio_data, samplerate=sample_rate, device=self.audio_device_id)
                    sd.wait()  # 等待播放完成
                    
                    # sounddevice播放完成
                    return
                else:
                    print("⚠️ WAV文件加载失败，回退到备选播放器")
                    
            # 备选方案：使用aplay或pygame
            if hasattr(self, 'use_system_player') and self.use_system_player:
                # 使用aplay播放
                try:
                    # 优先使用plughw设备，自动处理格式转换
                    plug_device = self.target_device.replace('hw:', 'plughw:')
                    cmd_plug = ['aplay', '-D', plug_device, file_path]
                    result = subprocess.run(cmd_plug, capture_output=True, timeout=30)
                    
                    if result.returncode == 0:
                        # aplay播放完成
                        return
                    else:
                        # 备选：尝试原始hw设备
                        cmd_hw = ['aplay', '-D', self.target_device, file_path]
                        result_hw = subprocess.run(cmd_hw, capture_output=True, timeout=30)
                        if result_hw.returncode == 0:
                            # aplay播放完成
                            return
                        else:
                            print(f"❌ aplay播放失败: {result_hw.stderr.decode()}")
                        
                except subprocess.TimeoutExpired:
                    print(f"⚠️ aplay播放超时")
                except Exception as e:
                    print(f"⚠️ aplay播放错误: {e}")
            
            # 最后备选：pygame播放
            try:
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                
                # 等待播放完成
                while pygame.mixer.music.get_busy():
                    if self.stop_playing.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.1)
                # pygame播放完成
                
            except Exception as e:
                print(f"❌ pygame播放失败: {e}")
            
        except Exception as e:
            print(f"❌ 播放失败: {e}")
    
    def _audio_player_thread(self):
        """音频播放线程"""
        while True:
            try:
                audio_file = self.audio_queue.get(timeout=1.0)
                if audio_file is None:  # 结束信号
                    break
                
                self._play_audio_file(audio_file)
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 播放线程错误: {e}")
    
    async def speak_immediate(self, text: str):
        """立即合成策略 - 适用于短文本"""
        print(f"🔊 立即合成: {text}")
        
        audio_file = await self._synthesize_chunk(text)
        if audio_file:
            self._play_audio_file(audio_file)
    
    async def speak_chunked(self, text: str):
        """分块合成策略 - 适用于中等长度文本"""
        chunks = self._split_text_semantic(text)
        print(f"🔊 分块合成: {len(chunks)} 个片段")
        
        for i, chunk in enumerate(chunks):
            print(f"   片段 {i+1}: {chunk}")
            
            audio_file = await self._synthesize_chunk(chunk)
            if audio_file:
                self._play_audio_file(audio_file)
                # 片段间短暂停顿
                time.sleep(0.2)
    
    async def speak_streaming(self, text: str):
        """流式合成策略 - 适用于长文本"""
        chunks = self._split_text_semantic(text)
        print(f"🔊 流式合成: {len(chunks)} 个片段")
        
        # 启动播放线程
        if not self.is_playing:
            self.is_playing = True
            self.stop_playing.clear()
            player_thread = threading.Thread(target=self._audio_player_thread)
            player_thread.daemon = True
            player_thread.start()
        
        # 并行合成和播放
        for i, chunk in enumerate(chunks):
            print(f"   流式片段 {i+1}: {chunk}")
            
            audio_file = await self._synthesize_chunk(chunk)
            if audio_file:
                self.audio_queue.put(audio_file)
    
    async def speak(self, text: str, strategy: Optional[str] = None):
        """
        完整语音合成 - 保证语音连贯性
        
        Args:
            text: 要合成的文本
            strategy: 合成策略（现在统一使用完整合成）
        """
        if not text or not text.strip():
            return
        
        text = text.strip()
        
        # 静默TTS处理，减少日志噪音
        start_time = time.time()
        
        try:
            audio_file = await self._synthesize_chunk(text)
            if audio_file:
                self._play_audio_file(audio_file)
        
        except Exception as e:
            print(f"❌ TTS处理失败: {e}")
        
        # 静默完成，不显示处理时间
        elapsed_time = time.time() - start_time
    
    def stop(self):
        """停止TTS播放"""
        self.stop_playing.set()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except:
            pass  # 静默处理mixer未初始化的错误
        
        # 清空队列（不删除缓存文件）
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                break
        
        print("🛑 TTS播放已停止")
    
    def clear_cache(self):
        """清空音频缓存"""
        try:
            # 删除所有缓存文件
            for file_path in self.cache_dir.glob("*.wav"):
                file_path.unlink()
            
            # 清空索引
            self.cache_index.clear()
            self._save_cache_index()
            
            # 静默清空音频缓存
            pass
        except Exception as e:
            # 静默处理清空失败
            pass
    
    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        total_size = 0
        file_count = 0
        
        for file_path in self.cache_dir.glob("*.wav"):
            if file_path.exists():
                total_size += file_path.stat().st_size
                file_count += 1
        
        return {
            "file_count": file_count,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "cache_dir": str(self.cache_dir.absolute()),
            "max_files": self.max_cache_files
        }
    
    def get_available_voices(self) -> List[str]:
        """获取可用的语音列表"""
        try:
            # 常用中文语音
            chinese_voices = [
                "zh-CN-XiaoxiaoNeural",  # 晓晓 (女)
                "zh-CN-YunxiNeural",     # 云希 (男)
                "zh-CN-YunyangNeural",   # 云扬 (男)
                "zh-CN-XiaochenNeural",  # 晓辰 (女)
                "zh-CN-XiaohanNeural",   # 晓涵 (女)
                "zh-CN-XiaomengNeural",  # 晓梦 (女)
                "zh-CN-XiaomoNeural",    # 晓墨 (女)
                "zh-CN-XiaoqiuNeural",   # 晓秋 (女)
                "zh-CN-XiaoruiNeural",   # 晓睿 (女)
                "zh-CN-XiaoshuangNeural",# 晓双 (女)
                "zh-CN-XiaoxuanNeural",  # 晓萱 (女)
                "zh-CN-XiaoyanNeural",   # 晓颜 (女)
                "zh-CN-XiaoyouNeural",   # 晓悠 (女)
                "zh-CN-XiaozhenNeural",  # 晓甄 (女)
            ]
            return chinese_voices
        except:
            return ["zh-CN-XiaoxiaoNeural"]

# 异步包装函数
def run_tts_async(coro):
    """运行异步TTS函数的辅助函数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


