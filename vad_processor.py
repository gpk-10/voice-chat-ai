#!/usr/bin/env python3
"""
VAD (Voice Activity Detection) 处理模块
"""

import webrtcvad
import numpy as np

class VADProcessor:
    def __init__(self, vad_mode=1, samplerate=16000, channels=2):
        """
        初始化VAD处理器
        
        Args:
            vad_mode: VAD模式 (0-3, 数字越大越敏感)
            samplerate: 采样率
            channels: 声道数
        """
        self.vad_mode = vad_mode
        self.samplerate = samplerate
        self.channels = channels
        
        # 初始化 WebRTC VAD
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(self.vad_mode)
        
        print(f'🎯 VAD初始化完成: 模式={vad_mode}, 采样率={samplerate}Hz, 声道={channels}')
    
    def stereo_to_mono(self, stereo_data):
        """将双声道音频转换为单声道 - 修复音质问题"""
        try:
            audio_array = np.frombuffer(stereo_data, dtype=np.int16)
            if self.channels == 2:
                # 重塑为双声道数组 [左, 右, 左, 右, ...]
                stereo_array = audio_array.reshape(-1, 2)
                # 只取左声道，避免平均造成的音质损失
                mono_array = stereo_array[:, 0]  # 取左声道
            else:
                mono_array = audio_array
            return mono_array.tobytes()
        except Exception as e:
            print(f"❌ 双声道转单声道失败: {e}")
            return stereo_data
    
    def check_vad_activity(self, audio_data):
        """
        检测VAD活动 - 改善稳定性
        
        Args:
            audio_data: 音频数据 (bytes)
            
        Returns:
            tuple: (是否检测到语音, 语音块数, 总块数)
        """
        try:
            # 双声道转单声道用于VAD检测
            mono_data = self.stereo_to_mono(audio_data)
            
            # 检查数据长度
            if len(mono_data) < 640:  # 至少20ms的数据
                return False, 0, 0
            
            # 将音频数据分块检测，设置有效激活率rate=50%
            num, rate = 0, 0.5
            step = int(self.samplerate * 0.02) * 2  # 20ms 块大小 * 2字节(int16)
            
            # 确保步长不为0
            if step <= 0:
                step = 640  # 默认640字节 (20ms @ 16kHz，安全后备值)
            
            total_chunks = len(mono_data) // step
            if total_chunks == 0:
                return False, 0, 0
                
            flag_rate = max(1, round(rate * total_chunks))  # 至少需要1个块

            for i in range(0, len(mono_data), step):
                chunk = mono_data[i:i + step]
                if len(chunk) == step:
                    try:
                        if self.vad.is_speech(chunk, sample_rate=self.samplerate):
                            num += 1
                    except Exception:
                        # VAD检测失败时跳过该块，静默处理保证稳定性
                        continue

            is_speech = num >= flag_rate
            
            return is_speech, num, total_chunks
            
        except Exception as e:
            print(f"❌ VAD检测错误: {e}")
            return False, 0, 0
    
    def calculate_audio_amplitude(self, audio_data):
        """计算音频幅度"""
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        max_amplitude = np.max(np.abs(audio_array))
        normalized_amplitude = max_amplitude / 32768.0
        return normalized_amplitude
