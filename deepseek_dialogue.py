# api_client.py
import os
from openai import OpenAI

# 基本配置
_DEEPSEEK_BASE_URL = "https://llmapi.paratera.com"
_DEEPSEEK_MODEL    = os.getenv("DEEPSEEK_MODEL", "DeepSeek-V3.1")  # 也可用 deepseek-reasoner

_client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "sk-fc_Qf6bVyDypSplhVfWeTQ"),   # 必填
    base_url=_DEEPSEEK_BASE_URL,                      # DeepSeek 兼容 OpenAI SDK
)

def dialogue(user_input: str,
             custom_prompt: str = "",
             temperature: float = 0.0,
             max_tokens: int = 256,
             model: str = None) -> dict:
    """
    用 DeepSeek Chat Completions 完成一次对话调用。
    保持与你原来上层调用的签名/字段一致：
      - user_input: 你要审核的文本（放到 user role）
      - custom_prompt: 作为 system 提示词
    返回：
      {"status":"success","response": "..."} 或 {"status":"error","message": "..."}
    """
    try:
        messages = []
        if custom_prompt:
            messages.append({"role": "system", "content": custom_prompt})
        messages.append({"role": "user", "content": user_input})

        resp = _client.chat.completions.create(
            model=model or _DEEPSEEK_MODEL,   # deepseek-chat | deepseek-reasoner
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,                      # 需要流式可改 True，注意解析方式不同
        )
        # OpenAI SDK 返回对象，取首个 choice
        content = (resp.choices[0].message.content or "").strip()
        return {"status": "success", "response": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}
