# Conversation 模块接口文档

## 概述

`conversation.py` 提供了会话管理功能，包括：
- `Conversation` 类：管理单个会话的对话历史
- `ConversationManager` 类：管理多个会话
- 全局 `conversation_manager` 实例：可直接导入使用

---

## Conversation 类

### 初始化
```python
def __init__(self, session_id: Optional[str] = None)
```
- **参数**：
  - `session_id`：可选，会话ID。若不提供则自动生成UUID
- **属性**：
  - `session_id`：唯一会话标识
  - `create_time`：会话创建时间
  - `update_time`：最后更新时间
  - `messages`：对话历史列表
  - `max_history_len`：最大保留对话轮数（默认10轮）

### 方法

#### `add_message`
添加消息到对话历史
```python
def add_message(self, role: str, content: str, **kwargs) -> None
```
- **参数**：
  - `role`：角色，可选 `user`/`assistant`/`system`
  - `content`：消息内容
  - `**kwargs`：额外信息（如 `citations`、`context_used` 等）

#### `get_context`
生成对话上下文文本
```python
def get_context(self, include_system: bool = False) -> str
```
- **参数**：
  - `include_system`：是否包含system角色的消息
- **返回**：格式化后的上下文文本

#### `get_history`
获取完整的对话历史
```python
def get_history(self) -> List[Dict[str, Any]]
```
- **返回**：消息列表的副本

#### `clear_history`
清空对话历史
```python
def clear_history(self) -> None
```

#### `to_dict`
将会话信息转换为字典
```python
def to_dict(self) -> Dict[str, Any]
```
- **返回**：包含会话基本信息的字典

---

## ConversationManager 类

### 初始化
```python
def __init__(self)
```
- **属性**：
  - `conversations`：字典，key为session_id，value为Conversation实例

### 方法

#### `create_conversation`
创建新会话
```python
def create_conversation(self) -> str
```
- **返回**：新会话的session_id

#### `create_conversation_with_id`
使用指定ID创建会话
```python
def create_conversation_with_id(self, session_id: str) -> bool
```
- **参数**：
  - `session_id`：指定的会话ID
- **返回**：创建成功返回True，ID已存在返回False

#### `get_conversation`
获取会话实例
```python
def get_conversation(self, session_id: str) -> Optional[Conversation]
```
- **参数**：
  - `session_id`：会话ID
- **返回**：Conversation实例，不存在则返回None

#### `add_message_to_conversation`
向指定会话添加消息
```python
def add_message_to_conversation(
    self,
    session_id: str,
    role: str,
    content: str,
    **kwargs
) -> bool
```
- **参数**：
  - `session_id`：会话ID
  - `role`：消息角色
  - `content`：消息内容
  - `**kwargs`：额外信息
- **返回**：成功返回True，会话不存在返回False

#### `get_conversation_context`
获取指定会话的上下文文本
```python
def get_conversation_context(
    self,
    session_id: str,
    include_system: bool = False
) -> str
```
- **参数**：
  - `session_id`：会话ID
  - `include_system`：是否包含system消息
- **返回**：格式化后的上下文文本，会话不存在时返回提示信息

#### `list_conversations`
列出所有会话的基本信息
```python
def list_conversations(self) -> List[Dict[str, Any]]
```
- **返回**：包含各会话基本信息的字典列表

#### `delete_conversation`
删除指定会话
```python
def delete_conversation(self, session_id: str) -> bool
```
- **返回**：删除成功返回True，会话不存在返回False

#### `clear_all_conversations`
删除所有会话
```python
def clear_all_conversations(self) -> None
```

---

## 全局实例

### `conversation_manager`
可直接导入使用的全局会话管理器实例
```python
from conversation import conversation_manager
```

---

## 使用示例

```python
# 导入全局管理器
from conversation import conversation_manager

# 1. 创建会话
session_id = conversation_manager.create_conversation()

# 2. 添加消息
conversation_manager.add_message_to_conversation(
    session_id=session_id,
    role="user",
    content="你好"
)

# 3. 获取上下文
context = conversation_manager.get_conversation_context(session_id)

# 4. 列出所有会话
sessions = conversation_manager.list_conversations()

# 5. 删除会话
conversation_manager.delete_conversation(session_id)
```

---

## 注意事项

- 对话历史长度限制：默认保留最新10轮对话（每轮包含user和assistant各一条）
- 时间戳格式：`%Y-%m-%d %H:%M:%S`