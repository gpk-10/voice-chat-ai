#!/usr/bin/env python3
"""
音频录制和处理模块
"""

import sounddevice as sd
import numpy as np
import threading
import time
import queue
import hashlib
import json
from pathlib import Path
from vad_processor import VADProcessor
from speech_recognizer import SpeechRecognizer

class AudioRecorder:
    def __init__(self, 
                 audio_device_id=0,
                 samplerate=16000,
                 channels=2,
                 blocksize=1024,
                 silence_timeout=1.5,
                 min_speech_duration=0.5,
                 enable_asr=True,
                 asr_queue_size=20,
                 save_recordings=True,
                 recording_cache_dir="recording_cache",
                 max_cache_files=50,
                 device="cpu"):
        """
        初始化音频录制器
        
        Args:
            audio_device_id: 音频设备ID
            samplerate: 采样率
            channels: 声道数
            blocksize: 音频块大小
            silence_timeout: 静音超时时间(秒)
            min_speech_duration: 最小语音时长(秒)
            enable_asr: 启用语音识别
            asr_queue_size: ASR队列大小
            save_recordings: 是否保存录制文件 (新增)
            recording_cache_dir: 录制缓存目录 (新增)
            max_cache_files: 最大缓存文件数量 (新增)
            device: AI模型运行设备 (cpu/cuda:0/auto)
        """
        # 音频参数
        self.audio_device_id = audio_device_id
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = blocksize
        self.silence_timeout = silence_timeout
        self.min_speech_duration = min_speech_duration
        self.enable_asr = enable_asr
        self.asr_queue_size = asr_queue_size
        self.save_recordings = save_recordings
        self.max_cache_files = max_cache_files
        
        # 录制缓存管理
        self.recording_cache_dir = Path(recording_cache_dir)
        self.recording_cache_dir.mkdir(exist_ok=True)
        self.recording_cache_index_file = self.recording_cache_dir / "recording_index.json"
        self.recording_cache_index = self._load_recording_cache_index()
        
        # 状态变量
        self.recording_active = True
        self.is_paused = False  # 暂停状态
        self.audio_stream = None  # 音频流引用
        self.audio_buffer = []
        self.last_active_time = time.time()
        
        # 线程锁
        self._buffer_lock = threading.Lock()  # 保护音频缓冲区的线程锁
        
        # 录制统计
        self.recording_stats = {
            'total_recordings': 0,
            'successful_recognitions': 0,
            'failed_recognitions': 0,
            'short_recordings': 0,
            'cached_files': len(self.recording_cache_index)
        }
        
        # 语音录制状态
        self.speech_segments = []
        self.is_recording_speech = False
        self.speech_start_time = None
        self.is_processing = False
        self.actual_speech_duration = 0.0
        
        # 控制待机状态显示
        self.show_standby_status = True
        
        # 连续语音检测计数器 (减少误触发)
        self.consecutive_speech_count = 0
        self.speech_confirmation_threshold = 2  # 需要连续2次检测到语音才开始录制
        
        # 初始化VAD处理器 (模式1: 不太敏感，减少误触发)
        self.vad_processor = VADProcessor(
            vad_mode=1, 
            samplerate=samplerate, 
            channels=channels
        )
        
        # 初始化语音识别器
        self.speech_recognizer = None
        if enable_asr:
            self.speech_recognizer = SpeechRecognizer(samplerate=samplerate, device=device)
            if not self.speech_recognizer.is_model_loaded():
                self.enable_asr = False
        
        # ASR队列管理
        self.asr_queue = queue.Queue(maxsize=asr_queue_size)
        self.asr_consumer_active = True
        self.asr_stats = {
            'queued': 0,
            'processed': 0,
            'dropped': 0
        }
        
        # 回调函数
        self.on_speech_detected = None
        self.on_silence_detected = None
        self.on_recognition_result = None
        
        # 启动时清理缓存，确保文件数量在限制内
        if len(self.recording_cache_index) > self.max_cache_files:
            self._cleanup_recording_cache()
        
        print('✅ 音频录制器初始化完成')
        print(f'📁 录制缓存目录: {self.recording_cache_dir.absolute()}')
        print(f'📊 当前缓存文件: {len(self.recording_cache_index)} / {self.max_cache_files}')
    
    def _load_recording_cache_index(self):
        """加载录制缓存索引"""
        try:
            if self.recording_cache_index_file.exists():
                with open(self.recording_cache_index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载录制缓存索引失败: {e}")
        return {}
    
    def _save_recording_cache_index(self):
        """保存录制缓存索引"""
        try:
            with open(self.recording_cache_index_file, 'w', encoding='utf-8') as f:
                json.dump(self.recording_cache_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存录制缓存索引失败: {e}")
    
    def _get_recording_hash(self, audio_data: bytes) -> str:
        """生成录制音频的哈希值"""
        # 使用音频数据的MD5哈希作为唯一标识
        return hashlib.md5(audio_data).hexdigest()
    
    def _cleanup_recording_cache(self):
        """清理录制缓存，保持在最大数量限制内"""
        if len(self.recording_cache_index) <= self.max_cache_files:
            return
        
        # 按创建时间排序，删除最旧的文件
        sorted_items = sorted(
            self.recording_cache_index.items(),
            key=lambda x: x[1].get('created', 0)
        )
        
        files_to_remove = len(self.recording_cache_index) - self.max_cache_files
        for i in range(files_to_remove):
            hash_key, file_info = sorted_items[i]
            file_path = self.recording_cache_dir / file_info['filename']
            
            try:
                if file_path.exists():
                    file_path.unlink()
                    # 静默删除旧录制
                    pass
                del self.recording_cache_index[hash_key]
            except Exception as e:
                # 静默处理删除失败
                pass
        
        self._save_recording_cache_index()
        # 静默完成清理
    
    def _save_recording_file(self, audio_data: bytes, recognized_text: str = None) -> str:
        """保存录制文件并返回文件路径"""
        if not self.save_recordings:
            return None
            
        try:
            # 生成哈希和文件名
            audio_hash = self._get_recording_hash(audio_data)
            timestamp = int(time.time())
            filename = f"rec_{timestamp}_{audio_hash[:8]}.wav"
            file_path = self.recording_cache_dir / filename
            
            # 保存WAV文件
            if self.speech_recognizer:
                self.speech_recognizer.save_wav_file(str(file_path), audio_data)
            
            # 计算实际音频时长（包含静音段）
            actual_duration = len(audio_data) / (self.samplerate * 2)  # 总时长（包含静音）
            
            # 更新缓存索引
            self.recording_cache_index[audio_hash] = {
                'filename': filename,
                'created': timestamp,
                'text': recognized_text or "未识别",
                'duration': actual_duration,  # 实际录制时长（包含静音）
                'speech_duration': getattr(self, 'actual_speech_duration', 0),  # 纯语音时长
                'size': len(audio_data),
                'recognition_success': recognized_text is not None,
                'contains_silence': True  # 标记包含静音段
            }
            
            # 清理旧缓存
            self._cleanup_recording_cache()
            self._save_recording_cache_index()
            
            # 更新统计
            self.recording_stats['total_recordings'] += 1
            if recognized_text:
                self.recording_stats['successful_recognitions'] += 1
            self.recording_stats['cached_files'] = len(self.recording_cache_index)
            
            # 录制文件信息将在录制完成时显示
            return str(file_path)
            
        except Exception as e:
            print(f"❌ 保存录制文件失败: {e}")
            return None
    
    def get_recording_stats(self) -> dict:
        """获取录制统计信息"""
        return self.recording_stats.copy()
    
    def find_recording_by_text(self, text: str) -> list:
        """根据识别文本查找录制文件"""
        results = []
        for hash_key, file_info in self.recording_cache_index.items():
            if text.lower() in file_info.get('text', '').lower():
                file_path = self.recording_cache_dir / file_info['filename']
                if file_path.exists():
                    results.append({
                        'hash': hash_key,
                        'file_path': str(file_path),
                        'text': file_info['text'],
                        'created': file_info['created'],
                        'duration': file_info.get('duration', 0)
                    })
        return results
    
    def set_callbacks(self, on_speech=None, on_silence=None, on_recognition=None):
        """设置回调函数"""
        self.on_speech_detected = on_speech
        self.on_silence_detected = on_silence
        self.on_recognition_result = on_recognition
    
    def audio_callback(self, indata, frames, time_info, status):
        """音频数据回调函数"""
        if status:
            print(f"⚠️ 音频状态警告: {status}")
        
        # 如果暂停，清空缓冲区并返回，不处理音频数据
        if self.is_paused:
            with self._buffer_lock:
                self.audio_buffer.clear()
            return
        
        if self.recording_active:
            try:
                # 正确的音频格式转换方式 - 避免音质损失
                # 确保输入数据是正确的格式
                if indata.ndim == 1:
                    # 单声道数据，扩展为双声道
                    audio_array = np.column_stack((indata, indata))
                else:
                    audio_array = indata
                
                # 限制范围到[-1, 1]然后转换为int16，避免溢出和音质损失
                audio_clipped = np.clip(audio_array, -1.0, 1.0)
                audio_data = (audio_clipped * 32767).astype(np.int16).tobytes()
                
                # 添加到缓冲区
                self.audio_buffer.append(audio_data)
                
                # 每0.3秒检测一次VAD
                buffer_duration = len(self.audio_buffer) * self.blocksize / self.samplerate
                if buffer_duration >= 0.3:
                    self.process_audio_buffer()
            
            except Exception as e:
                print(f"❌ 音频回调处理错误: {e}")
    
    def process_audio_buffer(self):
        """处理音频缓冲区"""
        # 如果暂停，不处理音频缓冲区
        if self.is_paused:
            return
            
        # 拼接音频数据并检测VAD
        with self._buffer_lock:
            raw_audio = b''.join(self.audio_buffer)
        
        # 转换为单声道（用于保存录制文件）
        if self.channels == 1:
            mono_audio = raw_audio
        else:
            mono_audio = self.vad_processor.stereo_to_mono(raw_audio)
        
        vad_result, speech_chunks, total_chunks = self.vad_processor.check_vad_activity(raw_audio)
        
        # 计算音频幅度
        amplitude = self.vad_processor.calculate_audio_amplitude(raw_audio)
        
        # 获取当前时间
        current_time = time.time()
        
        # 增加幅度阈值过滤，减少误触发 (调整这个值来控制敏感度)
        amplitude_threshold = 0.1  # 幅度阈值，低于此值的音频不会触发录制（可配置参数）
        
        if vad_result and amplitude > amplitude_threshold:
            self.consecutive_speech_count += 1
            
            # 如果还没开始录制语音，需要连续检测到语音才开始录制
            if not self.is_recording_speech:
                if self.consecutive_speech_count >= self.speech_confirmation_threshold:
                    self.is_recording_speech = True
                    self.speech_start_time = current_time
                    self.speech_segments = []
                    self.actual_speech_duration = 0.0
                    self.show_standby_status = False  # 停止显示待机状态
                    print(f"\r\n🔴 开始录制语音段", flush=True)
                else:
                    return  # 还未确认，不开始录制
            
            # 录制过程中不显示实时状态
            self.last_active_time = current_time
            
            # 添加原始双声道音频段到语音录制（保持原始音质）
            self.speech_segments.append(raw_audio)
            self.actual_speech_duration += 0.3
            
            # 调用回调函数
            if self.on_speech_detected:
                self.on_speech_detected(amplitude, speech_chunks, total_chunks)
        else:
            # 重置连续语音计数器
            self.consecutive_speech_count = 0
            
            # 只在未录制时显示待机状态
            if not self.is_recording_speech and self.show_standby_status:
                print(f"\r🔇 待机中 - 幅度: {amplitude:.4f}, 语音块: {speech_chunks}/{total_chunks}                    ", end="", flush=True)
            
            # 静音时也添加音频段，保持完整的录制上下文
            if self.is_recording_speech:
                self.speech_segments.append(raw_audio)  # 添加静音段到录制（保持原始双声道）
                # 注意：静音段不增加actual_speech_duration，但会增加总录制时长
            
            # 调用回调函数
            if self.on_silence_detected:
                self.on_silence_detected(amplitude, speech_chunks, total_chunks)
        
        # 检查是否需要结束录制
        if (self.is_recording_speech and 
            current_time - self.last_active_time > self.silence_timeout and 
            not self.is_processing):
            
            # 检查实际语音长度是否满足最小要求
            if self.actual_speech_duration >= self.min_speech_duration:
                # 录制完成，立即暂停录制，避免在识别和AI处理期间继续录制
                self.is_paused = True
                self.show_standby_status = False
                self.process_speech_segments()
            else:
                # 短语音统计
                self.recording_stats['short_recordings'] += 1
                print(f"\r\n⏭️ 语音过短 [{self.actual_speech_duration:.1f}s/{self.min_speech_duration}s] 已跳过")
                print("-" * 50)  # 分割线
                self.speech_segments.clear()
            
            self.is_recording_speech = False
            self.speech_start_time = None
            self.actual_speech_duration = 0.0
            # 注意：如果刚才成功录制了，现在是暂停状态，show_standby_status应该为False
            # 如果是短语音跳过，show_standby_status应该为True
            if not self.is_paused:  # 如果没有暂停（短语音情况），恢复待机状态显示
                self.show_standby_status = True
        
        # 处理完成后清空缓冲区
        with self._buffer_lock:
            self.audio_buffer.clear()  # 使用clear()更安全
    
    def process_speech_segments(self):
        """处理和保存语音段"""
        if not self.speech_segments or self.is_processing:
            return
        
        self.is_processing = True
        
        try:
            # 合并所有语音段
            combined_audio = b''.join(self.speech_segments)
            
            # 转换为单声道
            mono_audio = self.vad_processor.stereo_to_mono(combined_audio)
            
            # 计算音频信息
            audio_length = len(mono_audio) / (self.samplerate * 2)  # 2字节per sample
            
            # 如果启用语音识别，加入队列进行识别
            if self.enable_asr and self.speech_recognizer:
                try:
                    audio_item = (mono_audio, audio_length, self.actual_speech_duration)
                    self.asr_queue.put_nowait(audio_item)
                    
                    self.asr_stats['queued'] += 1
                    queue_size = self.asr_queue.qsize()
                    
                    # 音频段已加入队列（内部调试信息，不显示）
                    
                except queue.Full:
                    self.asr_stats['dropped'] += 1
                    print(f"⚠️ ASR队列已满，丢弃当前音频段 (时长: {audio_length:.1f}s)")
            else:
                # 保存文件用于调试
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"speech_vad_{timestamp}.wav"
                self.speech_recognizer.save_wav_file(filename, mono_audio)
                print(f"💾 语音文件已保存: {filename} (时长: {audio_length:.1f}s)")
            
            # 清空语音段缓存
            self.speech_segments.clear()
            
        except Exception as e:
            print(f"❌ 处理语音段失败: {e}")
        finally:
            self.is_processing = False
    
    def asr_consumer_worker(self):
        """ASR消费者线程"""
        # ASR消费者线程开始工作
        
        while self.asr_consumer_active:
            try:
                audio_item = self.asr_queue.get(timeout=1.0)
                
                if audio_item is None:  # 结束信号
                    break
                
                audio_data, audio_length, actual_speech_duration = audio_item
                
                self.asr_stats['processed'] += 1
                queue_size = self.asr_queue.qsize()
                
                # 不显示识别中状态，保持简洁
                
                # 执行语音识别
                recognized_text = self.speech_recognizer.recognize_from_memory(audio_data)
                
                # 保存录制文件（与识别结果关联）
                recording_file = self._save_recording_file(audio_data, recognized_text)
                
                # 显示录制文件保存结果
                if recording_file:
                    from pathlib import Path
                    filename = Path(recording_file).name
                    if recognized_text and recognized_text.strip():
                        # 识别成功，显示录制完成和识别结果
                        print(f"\r⏹️ 录制完成 ({audio_length:.1f}s) -> {filename}")
                        print(f"🎙️ 语音识别: {recognized_text}")
                    else:
                        # 识别失败
                        self.recording_stats['failed_recognitions'] += 1
                        print(f"\r❌ 识别失败 -> {filename} ({audio_length:.1f}s)")
                        print("⚠️ 语音识别失败，但已保存录制文件以供调试")
                        print("-" * 50)  # 分割线
                        # 识别失败时恢复录制
                        self._ensure_recording_resumed()
                
                # 调用识别结果回调，传递录制文件路径
                if recognized_text and recognized_text.strip() and self.on_recognition_result:
                    # 如果回调函数支持录制文件参数，传递它
                    try:
                        # 尝试传递额外参数
                        self.on_recognition_result(recognized_text, recording_file=recording_file)
                    except TypeError:
                        # 如果不支持额外参数，使用原始方式
                        self.on_recognition_result(recognized_text)
                
                self.asr_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ ASR消费者线程错误: {e}")
                # ASR异常时恢复录制
                self._ensure_recording_resumed()
                # 检查是否是关键错误
                if "memory" in str(e).lower() or "model" in str(e).lower():
                    print("🚨 检测到关键错误，停止ASR处理")
                    self.asr_consumer_active = False
                    break
                time.sleep(0.5)
        
        # ASR消费者线程结束
    
    def pause_recording(self):
        """暂停录制（保持音频流，但停止处理）"""
        if not self.is_paused:
            self.is_paused = True
            self.show_standby_status = False  # TTS播放期间不显示待机状态
            # 暂停录制（内部操作，不显示日志）
    
    def resume_recording(self):
        """恢复录制"""
        if self.is_paused:
            self.is_paused = False
            self.show_standby_status = True  # 恢复待机状态显示
            # 恢复录制（内部操作，不显示日志）
    
    def _ensure_recording_resumed(self):
        """确保录制已恢复 - 内部方法，用于识别失败等情况"""
        if self.is_paused:
            self.resume_recording()
    
    def start_recording(self):
        """开始录制"""
        try:
            # 开始音频VAD监听
            
            # 启动ASR消费者线程
            if self.enable_asr:
                self.asr_thread = threading.Thread(target=self.asr_consumer_worker)
                self.asr_thread.daemon = True
                self.asr_thread.start()
                # ASR消费者线程启动完成
            
            # 使用sounddevice进行音频监听
            self.audio_stream = sd.InputStream(
                device=self.audio_device_id,
                channels=self.channels,
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                dtype=np.float32,
                callback=self.audio_callback
            )
            
            with self.audio_stream:
                # 持续监听
                while self.recording_active:
                    time.sleep(0.1)
            
        except Exception as e:
            print(f'❌ 音频VAD监听错误: {e}')
    
    def stop_recording(self):
        """停止录制"""
        self.recording_active = False
        # VAD监听停止
        
        # 安全关闭音频流
        if hasattr(self, 'audio_stream') and self.audio_stream is not None:
            try:
                self.audio_stream.close()
                self.audio_stream = None
            except Exception as e:
                print(f"⚠️ 关闭音频流失败: {e}")
        
        if self.enable_asr and hasattr(self, 'asr_queue'):
            self.asr_consumer_active = False
            try:
                # 发送停止信号到ASR队列
                self.asr_queue.put_nowait(None)
                # 等待ASR线程结束
                if hasattr(self, 'asr_thread') and self.asr_thread.is_alive():
                    self.asr_thread.join(timeout=2.0)  # 最多等待2秒
            except queue.Full:
                print("⚠️ ASR队列已满，强制停止")
            except Exception as e:
                print(f"⚠️ 停止ASR线程失败: {e}")
