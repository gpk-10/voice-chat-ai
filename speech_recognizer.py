#!/usr/bin/env python3
"""
语音识别模块
"""

import tempfile
import time
import wave
from funasr import AutoModel

class SpeechRecognizer:
    def __init__(self, model_dir="iic/SenseVoiceSmall", 
                 samplerate=16000, device="cpu"):
        """
        初始化语音识别器
        
        Args:
            model_dir: 模型目录路径
            samplerate: 采样率
            device: 运行设备 (cpu/cuda)
        """
        self.model_dir = model_dir
        self.samplerate = samplerate
        
        # 设备检测和设置
        if device == "auto":
            import torch
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
            print(f"🔍 自动检测设备: {self.device}")
        else:
            self.device = device
            
        self.model_sensevoice = None
        
        self.init_model()
    
    def init_model(self):
        """初始化SenseVoice语音识别模型"""
        try:
            print(f'🔍 初始化 SenseVoice 模型 (设备: {self.device})...')
            self.model_sensevoice = AutoModel(
                model=self.model_dir, 
                trust_remote_code=True, 
                device=self.device
            )
            print(f'✅ SenseVoice模型加载成功 (设备: {self.device})')
            return True
        except Exception as e:
            print(f'❌ SenseVoice模型加载失败: {e}')
            self.model_sensevoice = None
            return False
    
    def save_wav_file(self, filename, audio_data):
        """将音频数据保存为WAV文件"""
        try:
            with wave.open(filename, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位
                wav_file.setframerate(self.samplerate)
                wav_file.writeframes(audio_data)
        except Exception as e:
            print(f"❌ WAV文件写入失败: {e}")
            raise
    
    def recognize_from_memory(self, audio_data):
        """
        从内存中的音频数据进行语音识别
        
        Args:
            audio_data: 音频数据 (bytes)
            
        Returns:
            str: 识别结果文本，失败返回None
        """
        try:
            if self.model_sensevoice is None:
                print("SenseVoice模型未加载，跳过语音识别")
                return None
            
            # 使用临时文件进行识别（自动清理）
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as temp_file:
                # 写入音频数据到临时文件
                self.save_wav_file(temp_file.name, audio_data)
                
                # 使用SenseVoice进行识别
                res = self.model_sensevoice.generate(
                    input=temp_file.name,
                    cache={},
                    language="zn",  # 中文
                    use_itn=False,
                    disable_pbar=True,  # 禁用进度条
                    disable_log=True,   # 禁用日志
                )
                
                # 提取识别结果文本
                if res and len(res) > 0:
                    recognized_text = res[0]['text'].split(">")[-1].strip()
                    
                    if recognized_text:
                        return recognized_text
                    else:
                        return None
                else:
                    print("⚠️ 识别返回结果为空")
                    return None
            
        except Exception as e:
            print(f"❌ 语音识别失败: {e}")
            # 检查是否是模型加载问题
            if "model" in str(e).lower() and self.model_sensevoice is not None:
                print("🔄 尝试重新初始化语音识别模型...")
                try:
                    self.init_model()
                except:
                    print("❌ 模型重新初始化失败")
            return None
    
    def is_model_loaded(self):
        """检查模型是否已加载"""
        return self.model_sensevoice is not None
