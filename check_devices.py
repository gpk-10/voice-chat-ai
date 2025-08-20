#!/usr/bin/env python3
"""
音频设备检测工具
帮助用户查找和测试音频设备
"""

import sounddevice as sd
import numpy as np
import sys
import time
from pathlib import Path

def print_separator(title=""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*20} {title} {'='*20}")
    else:
        print("="*60)

def list_all_devices():
    """列出所有音频设备"""
    print_separator("所有音频设备")
    
    try:
        devices = sd.query_devices()
        
        print(f"{'ID':<4} {'名称':<30} {'类型':<8} {'声道':<8} {'采样率'}")
        print("-" * 60)
        
        for i, device in enumerate(devices):
            device_type = ""
            if device['max_input_channels'] > 0:
                device_type += "输入 "
            if device['max_output_channels'] > 0:
                device_type += "输出"
            
            channels = f"{device['max_input_channels']}/{device['max_output_channels']}"
            sample_rate = int(device['default_samplerate'])
            
            print(f"{i:<4} {device['name'][:30]:<30} {device_type:<8} {channels:<8} {sample_rate}")
            
    except Exception as e:
        print(f"❌ 设备列举失败: {e}")
        return False
    
    return True

def list_input_devices():
    """列出输入设备"""
    print_separator("可用输入设备 (麦克风)")
    
    try:
        devices = sd.query_devices()
        input_devices = []
        
        # 获取默认输入设备ID
        default_input_id = sd.default.device[0]
        
        print(f"{'ID':<4} {'名称':<60} {'声道数':<8} {'采样率'}")
        print("-" * 80)
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append((i, device))
                sample_rate = int(device['default_samplerate'])
                
                # 标识默认设备
                default_mark = " [默认]" if i == default_input_id else ""
                device_name = device['name'] + default_mark
                
                # 显示完整设备名称，不截断
                if len(device_name) > 60:
                    print(f"{i:<4} {device_name}")
                    print(f"{'':>4} {'':>60} {device['max_input_channels']:<8} {sample_rate}")
                else:
                    print(f"{i:<4} {device_name:<60} {device['max_input_channels']:<8} {sample_rate}")
        
        return input_devices
        
    except Exception as e:
        print(f"❌ 输入设备列举失败: {e}")
        return []

def list_output_devices():
    """列出输出设备"""
    print_separator("可用输出设备 (扬声器)")
    
    try:
        devices = sd.query_devices()
        output_devices = []
        
        # 获取默认输出设备ID
        default_output_id = sd.default.device[1]
        
        print(f"{'ID':<4} {'名称':<60} {'声道数':<8} {'采样率'}")
        print("-" * 80)
        
        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                output_devices.append((i, device))
                sample_rate = int(device['default_samplerate'])
                
                # 标识默认设备
                default_mark = " [默认]" if i == default_output_id else ""
                device_name = device['name'] + default_mark
                
                # 显示完整设备名称，不截断
                if len(device_name) > 60:
                    print(f"{i:<4} {device_name}")
                    print(f"{'':>4} {'':>60} {device['max_output_channels']:<8} {sample_rate}")
                else:
                    print(f"{i:<4} {device_name:<60} {device['max_output_channels']:<8} {sample_rate}")
        
        return output_devices
        
    except Exception as e:
        print(f"❌ 输出设备列举失败: {e}")
        return []

def test_recording(device_id, duration=3):
    """测试录音功能"""
    print(f"\n🎤 测试设备 {device_id} 录音功能...")
    print(f"📝 将录制 {duration} 秒音频，请对着麦克风说话...")
    
    try:
        # 开始录音
        print("🔴 开始录音...")
        audio_data = sd.rec(
            int(16000 * duration), 
            samplerate=16000, 
            channels=2, 
            device=device_id,
            dtype=np.float32
        )
        sd.wait()  # 等待录音完成
        
        # 分析音频
        max_amplitude = np.max(np.abs(audio_data))
        rms_amplitude = np.sqrt(np.mean(audio_data**2))
        
        print(f"✅ 录音完成")
        print(f"📊 最大幅度: {max_amplitude:.4f}")
        print(f"📊 RMS幅度: {rms_amplitude:.4f}")
        
        if max_amplitude > 0.001:
            print("🎉 设备工作正常，检测到音频信号")
            return True
        else:
            print("⚠️ 未检测到音频信号，请检查:")
            print("   - 麦克风是否连接")
            print("   - 音量设置是否正确")
            print("   - 是否选择了正确的设备")
            return False
            
    except Exception as e:
        print(f"❌ 录音测试失败: {e}")
        return False

def test_playback(device_id):
    """测试播放功能"""
    print(f"\n🔊 测试设备 {device_id} 播放功能...")
    
    try:
        # 生成测试音频 (1kHz正弦波)
        duration = 2  # 秒
        sample_rate = 16000
        frequency = 1000  # Hz
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        # 转换为立体声
        stereo_audio = np.column_stack((audio_data, audio_data))
        
        print("🔊 播放测试音频 (1kHz正弦波)...")
        sd.play(stereo_audio, samplerate=sample_rate, device=device_id)
        sd.wait()
        
        print("✅ 播放完成")
        return True
        
    except Exception as e:
        print(f"❌ 播放测试失败: {e}")
        return False

def find_device_by_name(keyword):
    """根据关键词查找设备"""
    print(f"\n🔍 查找包含 '{keyword}' 的设备...")
    
    try:
        devices = sd.query_devices()
        found_devices = []
        
        for i, device in enumerate(devices):
            if keyword.lower() in device['name'].lower():
                found_devices.append((i, device))
                device_type = ""
                if device['max_input_channels'] > 0:
                    device_type += "输入 "
                if device['max_output_channels'] > 0:
                    device_type += "输出"
                
                print(f"✅ 找到设备 {i}: {device['name']} ({device_type})")
        
        if not found_devices:
            print(f"❌ 未找到包含 '{keyword}' 的设备")
            
        return found_devices
        
    except Exception as e:
        print(f"❌ 设备搜索失败: {e}")
        return []

def generate_config_suggestions(input_device_id, output_device_id):
    """生成配置建议"""
    print_separator("配置建议")
    
    try:
        devices = sd.query_devices()
        input_device = devices[input_device_id]
        output_device = devices[output_device_id]
        
        print("📋 基于测试结果的配置建议:")
        print("")
        
        # 基本配置
        print("🔧 基本启动命令:")
        print(f"python3 main.py --device-id {input_device_id} --playback-device-id {output_device_id}")
        print("")
        
        # 按名称配置
        input_name_keyword = input_device['name'].split()[0]
        print("🔧 按设备名称启动 (推荐):")
        print(f"python3 main.py --device-name \"{input_name_keyword}\"")
        print("")
        
        # 高级配置
        print("🔧 高级配置选项:")
        if input_device['max_input_channels'] == 1:
            print("   # 单声道设备")
            print(f"   python3 main.py --device-id {input_device_id} --playback-device-id {output_device_id}")
        else:
            print("   # 立体声设备")
            print(f"   python3 main.py --device-id {input_device_id} --playback-device-id {output_device_id}")
        
        # ALSA配置 (Linux)
        if sys.platform.startswith('linux'):
            print("\n🔧 ALSA硬件配置:")
            print("   # 查找ALSA设备ID")
            print("   arecord -l")
            print("   aplay -l")
            print("   # 如果是hw:X,Y格式，使用:")
            print("   python3 main.py --tts-device \"hw:X,Y\"")
            
    except Exception as e:
        print(f"❌ 配置建议生成失败: {e}")

def interactive_device_test():
    """交互式设备测试"""
    print("🎯 交互式音频设备测试")
    print_separator()
    
    # 列出输入设备
    input_devices = list_input_devices()
    if not input_devices:
        print("❌ 未找到输入设备")
        return
    
    # 选择输入设备
    valid_ids = [str(device[0]) for device in input_devices]
    while True:
        try:
            choice = input(f"\n📝 请选择输入设备ID ({', '.join(valid_ids)}, 或按回车跳过): ").strip()
            if not choice:
                break
            
            device_id = int(choice)
            # 查找对应的设备
            selected_device = None
            for orig_id, device in input_devices:
                if orig_id == device_id:
                    selected_device = (orig_id, device)
                    break
            
            if selected_device:
                selected_input = selected_device[0]
                print(f"✅ 已选择输入设备: {selected_device[1]['name']}")
                
                # 测试录音
                if test_recording(selected_input):
                    break
                else:
                    continue
            else:
                print(f"❌ 无效的设备ID，请选择: {', '.join(valid_ids)}")
                
        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n👋 用户取消操作")
            return
    
    # 列出输出设备
    output_devices = list_output_devices()
    if not output_devices:
        print("❌ 未找到输出设备")
        return
    
    # 选择输出设备
    valid_output_ids = [str(device[0]) for device in output_devices]
    while True:
        try:
            choice = input(f"\n📝 请选择输出设备ID ({', '.join(valid_output_ids)}, 或按回车跳过): ").strip()
            if not choice:
                break
                
            device_id = int(choice)
            # 查找对应的设备
            selected_output_device = None
            for orig_id, device in output_devices:
                if orig_id == device_id:
                    selected_output_device = (orig_id, device)
                    break
            
            if selected_output_device:
                selected_output = selected_output_device[0]
                print(f"✅ 已选择输出设备: {selected_output_device[1]['name']}")
                
                # 测试播放
                if test_playback(selected_output):
                    # 生成配置建议
                    generate_config_suggestions(selected_input, selected_output)
                    break
                else:
                    continue
            else:
                print(f"❌ 无效的设备ID，请选择: {', '.join(valid_output_ids)}")
                
        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n👋 用户取消操作")
            return

def show_default_devices():
    """显示系统默认设备信息"""
    print_separator("系统默认设备")
    
    try:
        devices = sd.query_devices()
        default_input_id = sd.default.device[0]
        default_output_id = sd.default.device[1]
        
        print("📥 默认输入设备 (录音):")
        if 0 <= default_input_id < len(devices):
            input_dev = devices[default_input_id]
            print(f"   ID: {default_input_id}")
            print(f"   名称: {input_dev['name']}")
            print(f"   声道数: {input_dev['max_input_channels']}")
            print(f"   采样率: {int(input_dev['default_samplerate'])} Hz")
        else:
            print("   ❌ 无法获取默认输入设备")
        
        print("\n📤 默认输出设备 (播放):")
        if 0 <= default_output_id < len(devices):
            output_dev = devices[default_output_id]
            print(f"   ID: {default_output_id}")
            print(f"   名称: {output_dev['name']}")
            print(f"   声道数: {output_dev['max_output_channels']}")
            print(f"   采样率: {int(output_dev['default_samplerate'])} Hz")
        else:
            print("   ❌ 无法获取默认输出设备")
            
        print(f"\n💡 在 .env 中设置 DEFAULT_DEVICE_NAME=default 即可自动选择默认设备")
        
    except Exception as e:
        print(f"❌ 获取默认设备失败: {e}")

def main():
    """主程序"""
    print("🎙️ 语音对话AI系统 - 音频设备检测工具")
    print("======================================")
    
    if len(sys.argv) > 1:
        # 命令行模式
        if sys.argv[1] == "list":
            list_all_devices()
        elif sys.argv[1] == "input":
            list_input_devices()
        elif sys.argv[1] == "output":
            list_output_devices()
        elif sys.argv[1] == "find" and len(sys.argv) > 2:
            find_device_by_name(sys.argv[2])
        elif sys.argv[1] == "test" and len(sys.argv) > 2:
            device_id = int(sys.argv[2])
            test_recording(device_id)
        else:
            print("用法:")
            print("  python3 check_devices.py list          # 列出所有设备")
            print("  python3 check_devices.py input         # 列出输入设备")
            print("  python3 check_devices.py output        # 列出输出设备")
            print("  python3 check_devices.py find <关键词>  # 查找设备")
            print("  python3 check_devices.py test <设备ID> # 测试设备")
            print("  python3 check_devices.py               # 交互式测试")
    else:
        # 交互式模式
        try:
            # 首先显示默认设备信息
            show_default_devices()
            interactive_device_test()
        except KeyboardInterrupt:
            print("\n\n👋 检测工具已退出")

if __name__ == "__main__":
    main()
