# main.py（添加API服务代码）
import sys
from typing import Dict, Any
from flask import Flask, request, jsonify
from flask_cors import CORS  # 解决跨域问题
from config import config, setup_environment
from guard import validate_user_input, validate_prompt
from prompt_builder import build_prompt
from data_processor import extract_context
from api_client import dialogue, test_connection
from data_processor import DataProcessor

# 初始化Flask应用
app = Flask(__name__)
CORS(app)  # 允许所有跨域请求（生产环境可限制来源）

# 初始化环境（只执行一次）
ENV_SETUP_COMPLETED = False
if not ENV_SETUP_COMPLETED:
    setup_environment()
    ENV_SETUP_COMPLETED = True


def process_query(user_query: str) -> Dict[str, Any]:
    """处理用户查询的核心逻辑（复用原main函数逻辑）"""
    # 1. 校验用户输入合法性
    if not validate_user_input(user_query):
        return {
            "status": "error",
            "message": "用户输入不合法（包含敏感词或长度超限）"
        }
    
    try:
        # 2. RAG检索（获取上下文）
        context_text, filtered_results, citations = extract_context(
            query=user_query,
            max_context_length=1500,
            top_k=8,
            score_threshold=0.69,
            metric_type="cosine"
        )
        
        # 3. 构建Prompt
        final_prompt = build_prompt(
            user_input=user_query,
            context=context_text
        )
        
        # 4. 校验Prompt安全性
        if not validate_prompt(final_prompt):
            return {
                "status": "error",
                "message": "生成的Prompt包含潜在危险内容，已拦截"
            }
        
        # 5. 调用LLM获取回答
        llm_response = dialogue(
            user_input=user_query,
            custom_prompt=final_prompt,
            temperature=config.MODEL_TEMPERATURE,
            max_tokens=config.MODEL_MAX_TOKENS
        )
        
        if llm_response["status"] != "success":
            return {
                "status": "error",
                "message": f"大模型调用失败：{llm_response.get('message', '未知错误')}"
            }
        
        # 6. 格式化引用信息
        processor = DataProcessor()
        formatted_citations = processor.format_citations_for_display(citations)
        
        return {
            "status": "success",
            "user_query": user_query,
            "answer": llm_response["response"] + formatted_citations,
            "citations": citations,
            "context_used": context_text
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"系统运行异常：{str(e)}"
        }


# 定义API接口（前端调用此接口）
@app.route('/api/chat', methods=['POST'])
def chat_api():
    """接收前端请求，返回AI回答"""
    # 1. 获取前端发送的JSON数据
    data = request.get_json()
    user_query = data.get('query', '').strip()
    
    # 2. 校验输入
    if not user_query:
        return jsonify({
            "status": "error",
            "message": "请输入有效的查询内容"
        })
    
    # 3. 处理查询并返回结果
    result = process_query(user_query)
    return jsonify(result)  # 返回JSON格式响应


# 测试接口（可选）
@app.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({
        "status": "success",
        "message": "API服务正常运行中"
    })


# 启动服务
if __name__ == "__main__":
    # 测试API连接
    print("📡 测试API连接...")
    if not test_connection():
        sys.exit(1)
    
    # 启动Flask服务（默认端口5000，允许外部访问）
    print("🚀 API服务启动中...")
    app.run(host='0.0.0.0', port=5000, debug=True)