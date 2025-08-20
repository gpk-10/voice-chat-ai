#!/usr/bin/env python3
"""
音频设备管理模块
"""

import sounddevice as sd

class AudioDeviceManager:
    def __init__(self, target_device_name='ES7210'):
        self.target_device_name = target_device_name
        self.audio_device_id = -1
    
    def find_target_device(self):
        """自动查找目标音频设备，支持hw:X,Y格式"""
        try:
            import os
            import re
            debug_mode = os.getenv('DEBUG', '').lower() in ['true', '1', 'yes']
            
            if debug_mode:
                print(f"正在查找设备: '{self.target_device_name}'")
            
            # 如果指定了 default，直接使用系统默认设备
            if self.target_device_name.lower() == 'default':
                self.audio_device_id = sd.default.device[0]
                devices = sd.query_devices()
                default_dev = devices[self.audio_device_id]
                if debug_mode:
                    print(f"✅ 使用系统默认设备: ID {self.audio_device_id} - {default_dev['name']}")
                return self.audio_device_id
            
            # 检查是否是hw:X,Y格式
            hw_match = re.match(r'hw:(\d+),(\d+)', self.target_device_name)
            if hw_match:
                # Linux ALSA设备格式
                card_id, device_id = hw_match.groups()
                alsa_device_name = f"hw:{card_id},{device_id}"
                
                devices = sd.query_devices()
                for idx, dev in enumerate(devices):
                    # 查找包含hw:X,Y的设备名称
                    if (alsa_device_name in dev['name'] and 
                        dev['max_input_channels'] > 0):
                        self.audio_device_id = idx
                        if debug_mode:
                            print(f"✅ 找到ALSA设备: ID {idx} - {dev['name']}")
                        return idx
                
                # 如果精确匹配失败，尝试部分匹配
                for idx, dev in enumerate(devices):
                    if (f"card {card_id}" in dev['name'].lower() and 
                        dev['max_input_channels'] > 0):
                        self.audio_device_id = idx
                        if debug_mode:
                            print(f"✅ 找到声卡设备: ID {idx} - {dev['name']}")
                        return idx
            else:
                # 数字ID或设备名称
                if self.target_device_name.isdigit():
                    # 直接使用数字ID
                    device_id = int(self.target_device_name)
                    devices = sd.query_devices()
                    if 0 <= device_id < len(devices):
                        dev = devices[device_id]
                        if dev['max_input_channels'] > 0:
                            self.audio_device_id = device_id
                            if debug_mode:
                                print(f"✅ 使用指定设备ID: {device_id} - {dev['name']}")
                            return device_id
                else:
                    # 按名称搜索
                    devices = sd.query_devices()
                    for idx, dev in enumerate(devices):
                        if (self.target_device_name.lower() in dev['name'].lower() and 
                            dev['max_input_channels'] > 0):
                            self.audio_device_id = idx
                            if debug_mode:
                                print(f"✅ 找到目标设备: ID {idx} - {dev['name']}")
                            return idx
            
            # 如果没找到，使用默认设备
            self.audio_device_id = sd.default.device[0]
            devices = sd.query_devices()
            default_dev = devices[self.audio_device_id]
            if debug_mode:
                print(f"⚠️ 未找到目标设备，使用默认设备: {default_dev['name']}")
            return self.audio_device_id
            
        except Exception as e:
            print(f"❌ 查找音频设备失败: {e}")
            self.audio_device_id = 0
            return 0
    
    def list_audio_devices(self, current_device_id=None):
        """列出所有可用的输入音频设备"""
        try:
            import re
            print("=== 可用音频输入设备列表 ===")
            
            devices = sd.query_devices()
            input_count = 0
            
            for idx, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    input_count += 1
                    mark = "⭐" if self.target_device_name.lower() in dev['name'].lower() else "🎤"
                    current = " [当前选择]" if idx == current_device_id else ""
                    
                    # 提取hw:X,Y格式（如果存在）
                    hw_info = ""
                    hw_match = re.search(r'hw:(\d+),(\d+)', dev['name'])
                    if hw_match:
                        hw_info = f" (ALSA: {hw_match.group(0)})"
                    
                    print(f"{mark} 设备 {idx}: {dev['name']}{hw_info}{current}")
                    print(f"   - 输入声道: {dev['max_input_channels']}")
                    print(f"   - 采样率: {int(dev['default_samplerate'])} Hz")
                    if hw_match:
                        print(f"   - 配置格式: hw:{hw_match.group(1)},{hw_match.group(2)}")
            
            print(f"📊 共找到 {input_count} 个音频输入设备")
            return input_count
            
        except Exception as e:
            print(f"❌ 列出设备失败: {e}")
            return 0
    
    def get_device_info(self, device_id):
        """获取设备信息"""
        try:
            devices = sd.query_devices()
            if 0 <= device_id < len(devices):
                return devices[device_id]
            return None
        except Exception as e:
            print(f"❌ 获取设备信息失败: {e}")
            return None
