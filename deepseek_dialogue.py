import os
from openai import OpenAI

# 基本配置
_DEEPSEEK_BASE_URL = "https://llmapi.paratera.com"
_DEEPSEEK_MODEL    = os.getenv("DEEPSEEK_MODEL", "DeepSeek-V3.1")

_client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "sk-fc_Qf6bVyDypSplhVfWeTQ"),
    base_url=_DEEPSEEK_BASE_URL,
)

def dialogue(user_input: str,
             custom_prompt: str = "",
             temperature: float = 0.0,
             max_tokens: int = 256,
             model: str = None) -> dict:
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
