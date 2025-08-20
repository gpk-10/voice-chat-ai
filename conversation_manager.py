#!/usr/bin/env python3
"""
对话记录管理器
管理录制文件和TTS文件的一一对应关系
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

class ConversationManager:
    """对话记录管理器 - 管理完整的对话链路"""
    
    def __init__(self, 
                 conversation_dir: str = "conversation_records",
                 max_conversations: int = 100):
        """
        初始化对话记录管理器
        
        Args:
            conversation_dir: 对话记录目录
            max_conversations: 最大保留对话数量
        """
        self.conversation_dir = Path(conversation_dir)
        self.conversation_dir.mkdir(exist_ok=True)
        self.max_conversations = max_conversations
        
        # 对话记录索引文件
        self.index_file = self.conversation_dir / "conversation_index.json"
        self.conversation_index = self._load_index()
        
        # 当前对话ID计数器
        self.conversation_counter = self._get_next_conversation_id()
        
        print(f"💬 对话记录管理器初始化完成")
        print(f"📁 对话记录目录: {self.conversation_dir.absolute()}")
        print(f"📊 当前对话记录: {len(self.conversation_index)} / {self.max_conversations}")
    
    def _load_index(self) -> Dict:
        """加载对话索引"""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载对话索引失败: {e}")
        return {}
    
    def _save_index(self):
        """保存对话索引"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存对话索引失败: {e}")
    
    def _get_next_conversation_id(self) -> int:
        """获取下一个对话ID"""
        if not self.conversation_index:
            return 1
        
        # 从现有对话中找到最大ID
        max_id = 0
        for conv_id in self.conversation_index.keys():
            try:
                id_num = int(conv_id.split('_')[1])
                max_id = max(max_id, id_num)
            except:
                continue
        
        return max_id + 1
    
    def _cleanup_old_conversations(self):
        """清理旧的对话记录"""
        if len(self.conversation_index) <= self.max_conversations:
            return
        
        # 按创建时间排序，删除最旧的对话
        sorted_conversations = sorted(
            self.conversation_index.items(),
            key=lambda x: x[1].get('created', 0)
        )
        
        conversations_to_remove = len(self.conversation_index) - self.max_conversations
        for i in range(conversations_to_remove):
            conv_id, conv_info = sorted_conversations[i]
            
            try:
                # 删除对话记录（但保留音频文件，因为它们有自己的缓存管理）
                del self.conversation_index[conv_id]
                # 静默删除对话记录
            except Exception as e:
                # 静默处理删除失败
                pass
        
        self._save_index()
        # 静默完成清理
    
    def create_conversation_record(self, 
                                 user_text: str, 
                                 ai_response: str,
                                 recording_file: str = None,
                                 tts_file: str = None) -> str:
        """
        创建对话记录
        
        Args:
            user_text: 用户语音识别文本
            ai_response: AI回复文本
            recording_file: 录制文件路径
            tts_file: TTS文件路径
            
        Returns:
            对话ID
        """
        conversation_id = f"conv_{self.conversation_counter}"
        timestamp = time.time()
        
        # 创建对话记录
        conversation_record = {
            'conversation_id': conversation_id,
            'created': timestamp,
            'formatted_time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
            'user_text': user_text,
            'ai_response': ai_response,
            'recording_file': recording_file,
            'tts_file': tts_file,
            'complete': False  # 标记对话是否完整（包含TTS）
        }
        
        # 保存到索引
        self.conversation_index[conversation_id] = conversation_record
        
        # 清理旧记录
        self._cleanup_old_conversations()
        self._save_index()
        
        # 递增计数器
        self.conversation_counter += 1
        
        print(f"📝 创建对话记录 ({conversation_id})")
        return conversation_id
    
    def update_conversation_tts(self, conversation_id: str, tts_file: str):
        """更新对话记录的TTS文件"""
        if conversation_id in self.conversation_index:
            self.conversation_index[conversation_id]['tts_file'] = tts_file
            self.conversation_index[conversation_id]['complete'] = True
            self._save_index()
            print(f" -> {Path(tts_file).name}")
        else:
            print(f"⚠️ 对话记录不存在: {conversation_id}")
    
    def update_conversation_tts_silent(self, conversation_id: str, tts_file: str):
        """静默更新对话记录的TTS文件（不打印日志）"""
        if conversation_id in self.conversation_index:
            self.conversation_index[conversation_id]['tts_file'] = tts_file
            self.conversation_index[conversation_id]['complete'] = True
            self._save_index()
        # 不存在时也保持静默
    
    def get_conversation_record(self, conversation_id: str) -> Optional[Dict]:
        """获取对话记录"""
        return self.conversation_index.get(conversation_id)
    
    def find_conversations_by_text(self, search_text: str) -> List[Dict]:
        """根据文本搜索对话记录"""
        results = []
        search_text_lower = search_text.lower()
        
        for conv_id, conv_info in self.conversation_index.items():
            user_text = conv_info.get('user_text', '').lower()
            ai_response = conv_info.get('ai_response', '').lower()
            
            if search_text_lower in user_text or search_text_lower in ai_response:
                results.append(conv_info)
        
        # 按时间排序（最新的在前）
        results.sort(key=lambda x: x.get('created', 0), reverse=True)
        return results
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """获取最近的对话记录"""
        conversations = list(self.conversation_index.values())
        conversations.sort(key=lambda x: x.get('created', 0), reverse=True)
        return conversations[:limit]
    
    def get_conversation_stats(self) -> Dict:
        """获取对话统计信息"""
        total_conversations = len(self.conversation_index)
        complete_conversations = sum(1 for conv in self.conversation_index.values() 
                                   if conv.get('complete', False))
        
        # 计算平均对话长度
        user_texts = [conv.get('user_text', '') for conv in self.conversation_index.values()]
        ai_responses = [conv.get('ai_response', '') for conv in self.conversation_index.values()]
        
        avg_user_length = sum(len(text) for text in user_texts) / len(user_texts) if user_texts else 0
        avg_ai_length = sum(len(text) for text in ai_responses) / len(ai_responses) if ai_responses else 0
        
        return {
            'total_conversations': total_conversations,
            'complete_conversations': complete_conversations,
            'completion_rate': complete_conversations / total_conversations if total_conversations > 0 else 0,
            'avg_user_text_length': round(avg_user_length, 1),
            'avg_ai_response_length': round(avg_ai_length, 1)
        }
    
    def export_conversations(self, format: str = 'json') -> str:
        """导出对话记录"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        if format == 'json':
            export_file = self.conversation_dir / f"export_{timestamp}.json"
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_index, f, ensure_ascii=False, indent=2)
        
        elif format == 'txt':
            export_file = self.conversation_dir / f"export_{timestamp}.txt"
            with open(export_file, 'w', encoding='utf-8') as f:
                f.write("对话记录导出\n")
                f.write("=" * 50 + "\n\n")
                
                # 按时间排序
                conversations = sorted(
                    self.conversation_index.values(),
                    key=lambda x: x.get('created', 0)
                )
                
                for conv in conversations:
                    f.write(f"时间: {conv.get('formatted_time', '未知')}\n")
                    f.write(f"用户: {conv.get('user_text', '未识别')}\n")
                    f.write(f"AI: {conv.get('ai_response', '无回复')}\n")
                    f.write(f"录制文件: {conv.get('recording_file', '无')}\n")
                    f.write(f"TTS文件: {conv.get('tts_file', '无')}\n")
                    f.write("-" * 30 + "\n\n")
        
        print(f"📤 对话记录已导出: {export_file}")
        return str(export_file)
    
    def verify_file_links(self) -> Dict:
        """验证文件链接的完整性"""
        results = {
            'total_conversations': len(self.conversation_index),
            'missing_recording_files': 0,
            'missing_tts_files': 0,
            'complete_conversations': 0
        }
        
        for conv_info in self.conversation_index.values():
            recording_file = conv_info.get('recording_file')
            tts_file = conv_info.get('tts_file')
            
            recording_exists = recording_file and Path(recording_file).exists()
            tts_exists = tts_file and Path(tts_file).exists()
            
            if not recording_exists and recording_file:
                results['missing_recording_files'] += 1
            
            if not tts_exists and tts_file:
                results['missing_tts_files'] += 1
            
            if recording_exists and tts_exists:
                results['complete_conversations'] += 1
        
        return results
