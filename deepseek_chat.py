#!/usr/bin/env python3
"""
DeepSeek 聊天模块
用于语音识别系统的AI回复功能
"""

import os   
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver

class DeepSeekChatModule:
    """DeepSeek 聊天模块 - 专为语音系统设计"""
    
    def __init__(self, 
                 api_key: str = None,
                 model_name: str = "deepseek-chat",
                 system_prompt: str = None,
                 max_history_length: int = 20,
                 auto_summarize_threshold: int = 50):
        """
        初始化 DeepSeek 聊天模块
        
        Args:
            api_key: DeepSeek API 密钥
            model_name: 模型名称
            system_prompt: 系统提示词
            max_history_length: 最大保留的对话轮数
            auto_summarize_threshold: 自动总结触发的对话轮数
        """
        # 从环境变量获取API密钥，如果没有传入的话
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        
        if not self.api_key:
            raise ValueError("❌ DeepSeek API密钥未设置！请设置环境变量 DEEPSEEK_API_KEY 或传入 api_key 参数")
        self.model_name = model_name
        self.max_history_length = max_history_length
        self.auto_summarize_threshold = auto_summarize_threshold
        self.conversation_count = 0
        self.conversation_summary = ""
        
        # 语音助手专用提示词
        self.system_prompt = system_prompt or """你是一个智能语音助手小云，具有以下特点：
1. 友善、专业且乐于助人
2. 回答简洁明了，适合语音交互（建议控制在30字以内，如果要求详细回答可以增加到200字以内）
3. 能够进行多轮对话，记住上下文
4. 优先使用中文回复，语言自然流畅
5. 如果不确定答案，会诚实地说不知道
6. 避免过于技术性的回答，用通俗易懂的语言

请根据用户的语音输入，提供简洁有帮助的回复。"""
        
        # 设置环境变量
        os.environ['DEEPSEEK_API_KEY'] = self.api_key
        
        # 可选：启用 LangSmith 监控
        langsmith_key = os.getenv('LANGCHAIN_API_KEY')
        if langsmith_key and os.getenv('LANGCHAIN_TRACING_V2', '').lower() == 'true':
            os.environ['LANGCHAIN_API_KEY'] = langsmith_key
            os.environ['LANGCHAIN_TRACING_V2'] = 'true'
            os.environ['LANGCHAIN_PROJECT'] = os.getenv('LANGCHAIN_PROJECT', 'voice-chat-assistant')
        
        # 初始化模型和图
        self._init_model()
        self._init_graph()
        
        # 对话线程ID
        self.thread_id = uuid.uuid4().hex
        
        print("✅ DeepSeek 语音聊天模块初始化完成")
        print(f"💭 对话管理: 最大保留 {max_history_length} 轮，每 {auto_summarize_threshold} 轮自动整理")
    
    def _init_model(self):
        """初始化 DeepSeek 模型"""
        try:
            self.model = ChatDeepSeek(model=self.model_name)
            print("✅ ChatDeepSeek 模型加载成功")
        except Exception as e:
            print(f"❌ 模型初始化失败: {e}")
            raise
    
    def _init_graph(self):
        """初始化 LangGraph 状态图"""
        def chatbot_node(state: MessagesState):
            """聊天机器人节点 - 带智能历史管理"""
            messages = state['messages']
            
            # 智能历史管理
            messages = self._manage_conversation_history(messages)
            
            # 如果没有系统消息，添加一个
            if not messages or not isinstance(messages[0], SystemMessage):
                system_content = self.system_prompt
                # 如果有对话摘要，添加到系统提示中
                if self.conversation_summary:
                    system_content += f"\n\n[对话历史摘要: {self.conversation_summary}]"
                messages = [SystemMessage(content=system_content)] + messages
            
            response = self.model.invoke(messages)
            return {'messages': [response]}
        
        # 构建状态图
        graph_builder = StateGraph(state_schema=MessagesState)
        graph_builder.add_node('chatbot', chatbot_node)
        graph_builder.add_edge(START, 'chatbot')
        graph_builder.add_edge('chatbot', END)
        
        # 编译图（使用内存保存器实现状态持久化）
        self.graph = graph_builder.compile(checkpointer=MemorySaver())
        print("✅ LangGraph 状态图构建完成")
    
    def get_ai_response(self, user_text: str) -> str:
        """
        获取AI回复（专为语音系统优化，带智能历史管理）
        
        Args:
            user_text: 用户语音识别的文本
            
        Returns:
            AI回复文本
        """
        try:
            config = {"configurable": {"thread_id": self.thread_id}}
            
            # 增加对话计数
            self.conversation_count += 1
            
            # 检查是否需要历史管理
            if self.conversation_count % self.auto_summarize_threshold == 0:
                print("🔄 对话记录较多，正在智能整理...")
                self._auto_summarize_history()
            
            # 调用AI获取回复
            result = self.graph.invoke(
                {'messages': [HumanMessage(content=user_text)]},
                config
            )
            
            ai_response = result['messages'][-1].content
            
            # 记录对话（内部统计，不显示日志）
            # 主要的对话日志由主程序管理
            
            # 显示对话统计
            if self.conversation_count % 10 == 0:
                print(f"💭 对话统计: 已进行 {self.conversation_count} 轮对话")
            
            return ai_response
            
        except Exception as e:
            error_msg = "抱歉，我现在遇到了一些问题，请稍后再试。"
            print(f"❌ AI回复生成失败: {e}")
            return error_msg
    
    def _manage_conversation_history(self, messages: List) -> List:
        """智能管理对话历史长度"""
        # 分离系统消息和对话消息
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        conversation_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        # 如果对话消息超过限制，保留最近的对话
        if len(conversation_messages) > self.max_history_length:
            print(f"📝 对话历史管理: 保留最近 {self.max_history_length} 轮对话")
            conversation_messages = conversation_messages[-self.max_history_length:]
        
        return system_messages + conversation_messages
    
    def _auto_summarize_history(self):
        """自动总结对话历史"""
        try:
            config = {"configurable": {"thread_id": self.thread_id}}
            state = self.graph.get_state(config)
            messages = state.values.get('messages', [])
            
            # 获取对话内容
            conversation_text = ""
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    conversation_text += f"用户: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    conversation_text += f"助手: {msg.content}\n"
            
            if conversation_text:
                # 生成对话摘要
                summary_prompt = f"""请简洁地总结以下对话的关键信息（50字以内）：

{conversation_text}

摘要:"""
                
                summary_response = self.model.invoke([HumanMessage(content=summary_prompt)])
                self.conversation_summary = summary_response.content.strip()
                
                print(f"📋 对话摘要已生成: {self.conversation_summary}")
                
                # 清理旧的对话历史，保留摘要
                self._cleanup_old_history()
                
        except Exception as e:
            print(f"⚠️ 对话摘要生成失败: {e}")
    
    def _cleanup_old_history(self):
        """清理旧的对话历史"""
        try:
            # 创建新的线程ID，但保留摘要信息
            old_thread_id = self.thread_id
            self.thread_id = uuid.uuid4().hex
            
            # 静默清理对话历史
            pass
            
        except Exception as e:
            # 静默处理清理失败
            pass
    
    def reset_conversation(self):
        """重置对话历史"""
        self.thread_id = uuid.uuid4().hex
        self.conversation_count = 0
        self.conversation_summary = ""
        print("🔄 对话历史已完全重置")
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        config = {"configurable": {"thread_id": self.thread_id}}
        
        try:
            state = self.graph.get_state(config)
            messages = state.values.get('messages', [])
            
            history = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    history.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    history.append({"role": "assistant", "content": msg.content})
            
            return history
        except:
            return []
    
    def save_conversation(self, filename: str = None) -> str:
        """保存对话到文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"voice_conversation_{timestamp}.json"
        
        history = self.get_conversation_history()
        
        conversation_data = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model_name,
            "thread_id": self.thread_id,
            "type": "voice_conversation",
            "history": history
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
        
            print(f"💾 对话已保存到: {filename}")
            return filename
        except Exception as e:
            print(f"❌ 保存对话失败: {e}")
            return ""
