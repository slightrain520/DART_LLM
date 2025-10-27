# guard.py 模块说明

## validate_user_input

**功能：**  
校验用户输入是否合法，检测是否包含敏感词或长度超限。

**参数：**  
- `user_input`：用户输入字符串。

**返回：**  
- `True`：输入合法；  
- `False`：包含敏感词或超过长度限制。

---

## validate_prompt

**功能：**  
检测最终生成的 prompt 是否包含潜在的危险内容（如 SQL 注入等）。

**参数：**  
- `final_prompt`：完整 prompt 字符串。

**返回：**  
- `True`：安全；  
- `False`：检测到潜在风险模式。

---

## prompt_builder

### build_prompt

**功能：**  
组合系统提示词、上下文和用户输入，生成最终的模型 prompt。

**参数：**  
- `user_input`：用户输入内容。  
- `context`：上下文或补充说明。  
- `system_prompt`：系统初始提示词。

**返回：**  
- `final_prompt`：完整的 prompt 字符串，可直接传入 LLM。
