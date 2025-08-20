#!/usr/bin/env python3
"""
主程序 - 语音对话AI系统
集成语音识别 + DeepSeek AI回复
"""

import os
import argparse
import time
import threading
import asyncio
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()
from pathlib import Path
from audio_device import AudioDeviceManager
from audio_recorder import AudioRecorder
from deepseek_chat import DeepSeekChatModule
from tts_processor import TTSProcessor
from conversation_manager import ConversationManager

class VoiceChatSystem:
    def __init__(self, args):
        self.has_exception = False  # 跟踪是否发生异常
        """初始化语音对话AI系统"""
        self.args = args
        
        # 初始化 DeepSeek AI 模块
        print("🤖 初始化 AI 聊天模块...")
        try:
            # 可配置的历史管理参数
            max_history = getattr(args, 'max_history', 20)
            auto_summarize = getattr(args, 'auto_summarize', 50)
            
            self.ai_chat = DeepSeekChatModule(
                max_history_length=max_history,
                auto_summarize_threshold=auto_summarize
            )
        except Exception as e:
            print(f"❌ AI 模块初始化失败: {e}")
            raise
        
        # 初始化对话记录管理器
        print("💬 初始化对话记录管理器...")
        self.conversation_manager = ConversationManager(max_conversations=20)  # 减少到20个对话记录
        
        # 初始化TTS模块（默认启用）
        self.tts_enabled = not getattr(args, 'disable_tts', False)
        self.tts = None
        if self.tts_enabled:
            print("🎵 初始化 TTS 语音播报...")
            try:
                tts_device = getattr(args, 'tts_device', 'hw:1,0')
                # 使用sounddevice播放，需要传递设备ID
                # 如果有指定播放设备ID，优先使用
                playback_device_id = getattr(args, 'playback_device_id', None)
                
                self.tts = TTSProcessor(
                    audio_device=tts_device,
                    audio_device_id=playback_device_id,
                    use_sounddevice=not getattr(args, 'use_aplay', False),  # 根据参数决定
                    max_cache_files=5  # 减少TTS缓存到5个文件
                )
                print(f"✅ TTS模块初始化成功")
            except Exception as e:
                print(f"⚠️ TTS 模块初始化失败: {e}")
                self.tts_enabled = False
        
        # 初始化录制设备管理器
        print("🎙️ 初始化录制设备...")
        self.device_manager = AudioDeviceManager(args.device_name)
        
        # 查找录制设备
        if args.device_id == -1:
            device_id = self.device_manager.find_target_device()
        else:
            device_id = args.device_id
        
        # 列出可用设备（debug级别）
        import os
        if os.getenv('DEBUG', '').lower() in ['true', '1', 'yes']:
            self.device_manager.list_audio_devices(device_id)
        
        # 录制设备初始化成功提示
        device_info = self.device_manager.get_device_info(device_id)
        if device_info:
            print(f"✅ 录制设备已就绪: {device_info['name']}")
        
        # 初始化音频录制器
        print("📼 初始化音频录制器...")
        self.recorder = AudioRecorder(
            audio_device_id=device_id,
            samplerate=16000,
            channels=2,
            blocksize=1024,
            silence_timeout=args.silence_timeout,
            min_speech_duration=args.min_duration,
            enable_asr=not args.disable_asr,
            asr_queue_size=args.queue_size,
            save_recordings=True,  # 启用录制文件保存
            recording_cache_dir="recording_cache",
            max_cache_files=5,  # 减少到5个文件，及时清理
            device=args.device  # 传递设备参数
        )
        
        # 设置回调函数
        self.recorder.set_callbacks(
            on_speech=self.on_speech_detected,
            on_silence=self.on_silence_detected,
            on_recognition=self.on_recognition_result
        )
        
        # 对话历史存储（线程安全）
        self.conversation_log = []
        self._conversation_lock = threading.Lock()  # 保护对话日志的线程锁
        
        # 显示系统配置
        print("📋 系统配置:")
        
        # 获取录制设备的hw名称
        device_info = self.device_manager.get_device_info(device_id)
        if device_info and 'hw:' in device_info['name']:
            # 提取hw设备名（如hw:1,1）
            import re
            hw_match = re.search(r'\((hw:\d+,\d+)\)', device_info['name'])
            hw_name = hw_match.group(1) if hw_match else f"hw:设备{device_id}"
        else:
            hw_name = f"hw:设备{device_id}"
        
        print(f"🎙️ 录制设备: {hw_name}")
        
        # 获取TTS播放设备信息
        if self.tts_enabled and self.tts:
            tts_device = getattr(args, 'tts_device', 'hw:1,0')
            print(f"🔊 播放设备: {tts_device}")
        
        print(f"🎯 VAD敏感度: 1 (共3级)")
        print(f"⏱️ 静音超时: {args.silence_timeout}秒")
        print(f"⏳ 最小时长: {args.min_duration}秒")
        # 显示AI模型设备信息
        if not args.disable_asr and self.recorder.speech_recognizer:
            actual_device = self.recorder.speech_recognizer.device
            print(f"🔍 语音识别: 启用 (设备: {actual_device})")
        else:
            print(f"🔍 语音识别: 禁用")
            
        print(f"🤖 AI对话: {'启用' if True else '禁用'}")
        print(f"🔊 语音播报: {'启用' if self.tts_enabled else '禁用'}")
        print('🚀 语音对话AI系统初始化完成')
    
    def on_speech_detected(self, amplitude, speech_chunks, total_chunks):
        """语音检测回调"""
        # 可以在这里添加自定义逻辑
        pass
    
    def on_silence_detected(self, amplitude, speech_chunks, total_chunks):
        """静音检测回调"""
        # 可以在这里添加自定义逻辑
        pass
    
    def on_recognition_result(self, text, recording_file=None):
        """语音识别结果回调 - 核心：语音转AI回复"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 语音识别结果已在ASR线程中显示
        # 录制已在录制完成时自动暂停
        
        # 🚀 使用线程处理AI对话和TTS，提高实时性
        def process_ai_response():
            try:
                print("🤖 AI思考中...")
                ai_response = self.ai_chat.get_ai_response(text)
                
                print(f"🤖 AI回复: {ai_response}")
                
                # 创建对话记录（先不包含TTS文件）
                conversation_id = self.conversation_manager.create_conversation_record(
                    user_text=text,
                    ai_response=ai_response,
                    recording_file=recording_file
                )
                
                # 记录完整对话（保持向后兼容）
                conversation_entry = {
                    'timestamp': timestamp,
                    'user_speech': text,
                    'ai_response': ai_response,
                    'conversation_id': conversation_id,
                    'recording_file': recording_file
                }
                with self._conversation_lock:
                    self.conversation_log.append(conversation_entry)
                
                # TTS语音播报（如果启用） - 同步顺序执行
                if self.tts_enabled and self.tts:
                    print("🔊 生成回复音频...", end="", flush=True)
                    try:
                        # 使用TTS的同步包装函数，避免事件循环冲突
                        from tts_processor import run_tts_async
                        # 录制已在录制完成时暂停
                        try:
                            # 获取TTS缓存文件路径
                            tts_file = run_tts_async(self.tts.speak(ai_response))
                            
                            # 更新对话记录的TTS文件，获取文件名
                            tts_filename = None
                            if conversation_id and hasattr(self.tts, '_get_cached_audio'):
                                # 尝试获取最近生成的TTS文件
                                cached_audio = self.tts._get_cached_audio(ai_response)
                                if cached_audio:
                                    self.conversation_manager.update_conversation_tts_silent(conversation_id, cached_audio)
                                    conversation_entry['tts_file'] = cached_audio
                                    from pathlib import Path
                                    tts_filename = Path(cached_audio).name
                            
                            # 显示TTS文件名
                            if tts_filename:
                                print(f" -> {tts_filename}")
                            
                            print("✅ 播放完成")
                            print("-" * 40)
                        finally:
                            # TTS完成后恢复录制
                            try:
                                if self.recorder:
                                    self.recorder.resume_recording()
                            except Exception as e:
                                print(f"⚠️ 恢复录制失败: {e}")
                    except Exception as e:
                        print(f"❌ TTS播报失败: {e}")
                        print("💬 AI回复（文字）: " + ai_response)
                        print("-" * 40)  # 分割线
                        # TTS失败时也要恢复录制
                        try:
                            if self.recorder:
                                self.recorder.resume_recording()
                        except Exception as e:
                            print(f"⚠️ 恢复录制失败: {e}")
                else:
                    # TTS未启用，直接恢复录制
                    try:
                        if self.recorder:
                            self.recorder.resume_recording()
                    except Exception as e:
                        print(f"⚠️ 恢复录制失败: {e}")
                
                # 对话记录已由conversation_manager统一管理
                
            except Exception as e:
                print(f"❌ AI回复生成失败: {e}")
                print("-" * 40)  # 分割线
                # AI回复失败时也要恢复录制
                try:
                    if self.recorder:
                        self.recorder.resume_recording()
                except Exception as resume_e:
                    print(f"⚠️ 恢复录制失败: {resume_e}")
        
        # 在新线程中处理AI对话，避免阻塞语音识别
        ai_thread = threading.Thread(target=process_ai_response, daemon=True)
        ai_thread.start()
    

    def start(self):
        """启动语音对话AI系统"""
        print("\n🚀 启动语音对话AI系统...")
        
        try:
            print("✅ 系统已就绪，请开始说话... (按 Ctrl+C 停止)")
            self.recorder.start_recording()
            
        except KeyboardInterrupt:
            print("\n📥 接收到停止信号 (Ctrl+C)")
            print("🛑 正在停止系统...")
        except Exception as e:
            self.has_exception = True
            print(f"❌ 程序异常: {e}")
            print("🛑 异常停止系统...")
            import traceback
            print(f"📋 详细错误信息:\n{traceback.format_exc()}")
        finally:
            self.stop()
    
    def stop(self):
        """停止系统"""
        try:
            if hasattr(self, 'recorder') and self.recorder:
                self.recorder.stop_recording()
        except Exception as e:
            print(f"⚠️ 停止录制器失败: {e}")
        
        # 显示统计信息
        print(f"\n📊 本次会话统计:")
        
        # 基本统计
        try:
            recording_stats = self.recorder.get_recording_stats() if hasattr(self, 'recorder') and self.recorder else {
                'successful_recognitions': 0, 'failed_recognitions': 0, 'short_recordings': 0
            }
            with self._conversation_lock if hasattr(self, '_conversation_lock') else threading.Lock():
                conversation_count = len(self.conversation_log) if hasattr(self, 'conversation_log') else 0
            print(f"💬 对话轮数: {conversation_count}轮")
            print(f"📊 识别统计: 成功{recording_stats['successful_recognitions']}次 | 失败{recording_stats['failed_recognitions']}次 | 过短{recording_stats['short_recordings']}次")
        except Exception as e:
            print(f"⚠️ 获取统计信息失败: {e}")
            print(f"💬 对话轮数: 0轮")
            print(f"📊 识别统计: 数据不可用")
        
        # 最近对话记录
        try:
            with self._conversation_lock if hasattr(self, '_conversation_lock') else threading.Lock():
                if hasattr(self, 'conversation_log') and self.conversation_log:
                    print(f"\n最近对话:")
                    for entry in self.conversation_log[-2:]:  # 显示最近2轮对话
                        user_text = entry['user_speech'][:30] + "..." if len(entry['user_speech']) > 30 else entry['user_speech']
                        ai_text = entry['ai_response'][:30] + "..." if len(entry['ai_response']) > 30 else entry['ai_response']
                        print(f"  👤 {user_text} → 🤖 {ai_text}")
        except Exception as e:
            print(f"⚠️ 显示对话记录失败: {e}")
        
        # 保存对话记录
        try:
            if hasattr(self, 'conversation_manager') and self.conversation_manager:
                export_file = self.conversation_manager.export_conversations('txt')
                print(f"\n📁 已保存至: {Path(export_file).name}")
            else:
                print(f"\n⚠️ 对话管理器不可用，跳过保存")
        except Exception as e:
            print(f"\n⚠️ 保存失败: {e}")
        
        # 对话记录已由conversation_manager统一管理和导出
        
        if self.has_exception:
            print("\n❌ 语音对话AI系统异常退出")
        else:
            print("\n✅ 语音对话AI系统已停止")

def main():
    parser = argparse.ArgumentParser(description='语音对话AI系统 - 语音输入直接对话DeepSeek')
    
    # 音频相关参数
    parser.add_argument('--device-id', type=int, default=-1, 
                       help='音频设备ID (-1为自动查找)')
    parser.add_argument('--device-name', default=os.getenv('DEFAULT_DEVICE_NAME', 'default'), 
                       help='目标设备名称')
    parser.add_argument('--silence-timeout', type=float, default=float(os.getenv('SILENCE_TIMEOUT', '1.5')), 
                       help='静音超时时间(秒)')
    parser.add_argument('--min-duration', type=float, default=float(os.getenv('MIN_SPEECH_DURATION', '0.5')), 
                       help='最小语音时长(秒)')
    parser.add_argument('--disable-asr', action='store_true', 
                       default=os.getenv('DISABLE_ASR', '').lower() in ['true', '1', 'yes'],
                       help='禁用语音识别（仅录音）')
    parser.add_argument('--queue-size', type=int, default=int(os.getenv('ASR_QUEUE_SIZE', '20')), 
                       help='ASR队列大小')
    
    # 对话管理参数
    parser.add_argument('--max-history', type=int, default=int(os.getenv('MAX_HISTORY', '20')),
                       help='最大保留的对话轮数')
    parser.add_argument('--auto-summarize', type=int, default=int(os.getenv('AUTO_SUMMARIZE', '50')),
                       help='自动总结触发的对话轮数')
    
    # TTS参数
    parser.add_argument('--disable-tts', action='store_true',
                       default=os.getenv('DISABLE_TTS', '').lower() in ['true', '1', 'yes'],
                       help='禁用TTS语音播报')
    parser.add_argument('--tts-device', default=os.getenv('DEFAULT_TTS_DEVICE', 'default'),
                       help='TTS音频播放设备 (默认: default)')
    parser.add_argument('--playback-device-id', type=int, default=None,
                       help='sounddevice播放设备ID (优先级高于tts-device)')
    parser.add_argument('--use-aplay', action='store_true',
                       default=os.getenv('USE_APLAY', '').lower() in ['true', '1', 'yes'],
                       help='强制使用aplay播放而非sounddevice')
    
    # AI模型参数
    parser.add_argument('--device', default=os.getenv('DEVICE', 'cpu'),
                       help='AI模型运行设备 (cpu/cuda:0/auto)')
    
    args = parser.parse_args()
    
    print("🎙️ 语音对话AI系统")
    print("=" * 50)
    print("🚀 功能: 语音输入 → AI回复 → 语音播报")
    print("🤖 AI助手: 小云 (基于DeepSeek)")
    print("🔍 语音识别: SenseVoice")
    print("🔊 语音播报: Edge-TTS合成")
    print("=" * 50)
    
    try:
        # 创建并启动语音对话AI系统
        system = VoiceChatSystem(args)
        system.start()
        
    except Exception as e:
        print(f"❌ 系统初始化失败: {e}")
        print("💡 请检查:")
        print("   1. DeepSeek API密钥是否有效")
        print("   2. 音频设备是否正常")
        print("   3. 依赖包是否完整安装")
        
        # 显示详细错误信息
        import traceback
        print(f"\n📋 详细错误信息:")
        print(traceback.format_exc())

if __name__ == '__main__':
    main()
