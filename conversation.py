# conversation.py
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

class Conversation:
    """会话管理类，维护单一会话的多轮对话上下文"""
    
    def __init__(self, session_id: Optional[str] = None):
        """
        初始化会话
        Args:
            session_id: 会话ID（可选，未提供则自动生成）
        """
        self.session_id = session_id or str(uuid.uuid4())  # 唯一会话标识
        self.create_time = datetime.now()  # 会话创建时间
        self.update_time = datetime.now()  # 最后更新时间
        self.messages: List[Dict[str, Any]] = []  # 对话历史列表
        self.max_history_len = 10  # 最大保留对话轮数
    
    def add_message(self, role: str, content: str, **kwargs) -> None:
        """
        添加消息到对话历史
        Args:
            role: 角色（user/assistant/system）
            content: 消息内容
            **kwargs: 额外信息（如citations、context_used等）
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **kwargs
        }
        self.messages.append(message)
        self.update_time = datetime.now()
        
        # 限制对话历史长度（只保留最新的max_history_len轮）
        if len(self.messages) > self.max_history_len * 2:  # 每轮包含user+assistant，故×2
            self.messages = self.messages[-self.max_history_len * 2:]
    
    def get_context(self, include_system: bool = False) -> str:
        """
        生成对话上下文文本（供LLM参考多轮对话）
        Args:
            include_system: 是否包含system角色的消息
        Returns:
            格式化后的上下文文本
        """
        context_parts = []
        for msg in self.messages:
            if not include_system and msg["role"] == "system":
                continue
            # 格式化消息（角色+时间+内容）
            context_parts.append(
                f"【{msg['role']}】{msg['timestamp']}\n{msg['content']}"
            )
        return "\n\n".join(context_parts) if context_parts else "无历史对话"
    
    def get_history(self) -> List[Dict[str, Any]]:
        """获取完整的对话历史（含元数据）"""
        return self.messages.copy()
    
    def clear_history(self) -> None:
        """清空对话历史（保留会话ID和时间戳）"""
        self.messages = []
        self.update_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """将会话信息转换为字典（便于序列化存储）"""
        return {
            "session_id": self.session_id,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "update_time": self.update_time.strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": len(self.messages),
            "max_history_len": self.max_history_len
        }


class ConversationManager:
    """会话管理器，管理多个会话实例（内存存储）"""
    
    def __init__(self):
        self.conversations: Dict[str, Conversation] = {}  # key: session_id, value: Conversation
    
    def create_conversation(self) -> str:
        """创建新会话，返回会话ID"""
        conversation = Conversation()
        self.conversations[conversation.session_id] = conversation
        return conversation.session_id
    
    def create_conversation_with_id(self, session_id: str) -> bool:
        """
        使用指定的会话ID创建会话（如果ID不存在）
        返回值：创建成功返回True，ID已存在返回False
        """
        if session_id in self.conversations:
            return False  # ID已存在，创建失败
        self.conversations[session_id] = Conversation(session_id=session_id)
        return True
    
    def get_conversation(self, session_id: str) -> Optional[Conversation]:
        """根据会话ID获取会话实例（不存在则返回None）"""
        return self.conversations.get(session_id)
    
    def add_message_to_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs
    ) -> bool:
        """
        向指定会话添加消息
        Args:
            session_id: 会话ID
            role: 角色（user/assistant/system）
            content: 消息内容
            **kwargs: 额外信息
        Returns:
            成功添加返回True，会话不存在返回False
        """
        conversation = self.get_conversation(session_id)
        if not conversation:
            return False
        conversation.add_message(role, content, **kwargs)
        return True
    
    def get_conversation_context(
        self,
        session_id: str,
        include_system: bool = False
    ) -> str:
        """获取指定会话的上下文文本"""
        conversation = self.get_conversation(session_id)
        if not conversation:
            return "无此会话的历史对话"
        return conversation.get_context(include_system)
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """列出所有会话的基本信息（用于前端历史记录展示）"""
        return [conv.to_dict() for conv in self.conversations.values()]
    
    def delete_conversation(self, session_id: str) -> bool:
        """删除指定会话"""
        if session_id in self.conversations:
            del self.conversations[session_id]
            return True
        return False
    
    def clear_all_conversations(self) -> None:
        """删除所有会话"""
        self.conversations.clear()


# 全局会话管理器实例（供其他模块直接导入使用）
conversation_manager = ConversationManager()


# 使用示例
if __name__ == "__main__":
    # 1. 创建新会话
    session_id = conversation_manager.create_conversation()
    print(f"创建新会话：{session_id}")
    
    # 2. 添加用户消息
    conversation_manager.add_message_to_conversation(
        session_id=session_id,
        role="user",
        content="什么是SQL注入？"
    )
    
    # 3. 添加AI回复（模拟）
    conversation_manager.add_message_to_conversation(
        session_id=session_id,
        role="assistant",
        content="SQL注入是一种常见的Web安全漏洞...",
        citations={"1": "网络安全知识库v2.1"}
    )
    
    # 4. 获取对话上下文
    context = conversation_manager.get_conversation_context(session_id)
    print("\n对话上下文：")
    print(context)
    
    # 5. 列出所有会话
    print("\n所有会话：")
    for conv in conversation_manager.list_conversations():
        print(conv)
    
    # 6. 删除会话
    conversation_manager.delete_conversation(session_id)
    print(f"\n删除会话 {session_id}：{'成功' if session_id not in conversation_manager.conversations else '失败'}")