# api_client.py

import requests
import time
from typing import Dict, List, Optional, Any
from config import config

class APIClient:
    """DART平台API客户端类"""
    
    def __init__(self):
        self.base_url = config.BASE_URL
        self.token = config.TOKEN
        self.timeout = config.REQUEST_TIMEOUT
        self.max_retries = config.MAX_RETRIES
        
    def _make_request(self, url: str, payload: Dict, method: str = "POST") -> Dict:
        """
        Args:
            url: 请求URL
            payload: 请求数据
            method: 请求方法
            
        Returns:
            响应数据字典
        """
        headers = {"Content-Type": "application/json"}
        
        for attempt in range(self.max_retries):
            try:
                if method.upper() == "POST":
                    response = requests.post(
                        url, 
                        json=payload, 
                        headers=headers, 
                        timeout=self.timeout
                    )
                else:
                    response = requests.get(
                        url,
                        params=payload,
                        timeout=self.timeout
                    )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    return {
                        "status": "error",
                        "message": "Token无效或缺失，请检查配置"
                    }
                elif response.status_code == 404:
                    return {
                        "status": "error", 
                        "message": "资源未找到，请检查数据库名称"
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"HTTP错误: {response.status_code}",
                        "details": response.text
                    }
                    
            except requests.exceptions.Timeout:
                print(f"请求超时，尝试 {attempt + 1}/{self.max_retries}")
                if attempt == self.max_retries - 1:
                    return {
                        "status": "error",
                        "message": "请求超时，请检查网络连接"
                    }
                time.sleep(1)  # 等待1秒后重试
                
            except requests.exceptions.ConnectionError:
                print(f"连接错误，尝试 {attempt + 1}/{self.max_retries}")
                if attempt == self.max_retries - 1:
                    return {
                        "status": "error",
                        "message": "网络连接错误，请检查BASE_URL配置"
                    }
                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                return {
                    "status": "error",
                    "message": f"请求异常: {str(e)}"
                }
            except ValueError as e:
                return {
                    "status": "error",
                    "message": f"响应解析失败: {str(e)}"
                }
        
        return {
            "status": "error",
            "message": "所有重试尝试均失败"
        }
    
    def dialogue(self, 
                 user_input: str, 
                 custom_prompt: str = None,
                 temperature: float = None,
                 max_tokens: int = None) -> Dict[str, Any]:
        """
        与大模型对话
        
        Args:
            user_input: 用户输入的查询内容
            custom_prompt: 自定义提示词
            temperature: 控制生成文本的随机性 (0-1)
            max_tokens: 限制生成的响应最大字数
            use_security_template: 是否使用安全模板
            
        Returns:
            对话响应字典
        """
        
        # 构建请求payload
        payload = {
            "token": self.token,
            "user_input": user_input,
            "temperature": temperature or config.MODEL_TEMPERATURE,
            "max_tokens": max_tokens or config.MODEL_MAX_TOKENS
        }
        
        # 添加自定义提示词
        if custom_prompt:
            payload["custom_prompt"] = custom_prompt
        
        url = self.base_url + config.ENDPOINTS["dialogue"]
        
        print(f"对话请求: user_input='{user_input[:50]}...'")
        if custom_prompt:
            print(f"  使用自定义提示词: {len(custom_prompt)} 字符")
        
        result = self._make_request(url, payload)
        
        # 返回大模型回答
        if result.get("status") == "error":
            return result
        else:
            return {
                "status": "success",
                "response": result.get("response", ""),
                "user_input": user_input
            }
    
    def test_connection(self) -> bool:
        """
        测试API连接是否正常
        
        Returns:
            连接是否成功
        """
        test_payload = {
            "user_input": "你好，请回复'连接正常'",
            "token": self.token,
            "max_tokens": 10
        }
        
        url = self.base_url + config.ENDPOINTS["dialogue"]
        result = self._make_request(url, test_payload)
        
        if result.get("status") == "success":
            print("API连接测试成功")
            return True
        else:
            print(f"API连接测试失败: {result.get('message')}")
            return False

api_client = APIClient()

def search(query: str, **kwargs) -> Dict[str, Any]:
    return api_client.search(query, **kwargs)

def dialogue(user_input: str, **kwargs) -> Dict[str, Any]:
    return api_client.dialogue(user_input, **kwargs)

def test_connection() -> bool:
    return api_client.test_connection()


# 使用示例
if __name__ == "__main__":
    if test_connection():
        print("\n=== 测试对话功能 ===")
        dialogue_result = dialogue("介绍一下御坂美琴")
        if dialogue_result["status"] == "success":
            print(f"AI回答: {dialogue_result['response']}")
    else:
        print("请检查配置和网络连接")