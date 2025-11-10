# main.py 
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
from conversation import conversation_manager
from guard import validate_llm_output

# 初始化Flask应用
app = Flask(__name__)
CORS(app)  # 允许所有跨域请求

# 初始化环境（只执行一次）
ENV_SETUP_COMPLETED = False
if not ENV_SETUP_COMPLETED:
    setup_environment()
    ENV_SETUP_COMPLETED = True


def process_query(user_query: str, conversation_context: str = "") -> Dict[str, Any]:
    """处理用户查询的核心逻辑"""
    
    # 1. 校验用户输入合法性
    if not validate_user_input(user_query):
        return {
            "status": "error",
            "message": "用户输入不合法（包含敏感词或长度超限）"
        }
    
    try:
        # 2. RAG检索（获取上下文）- 使用配置文件中的参数
        context_text, filtered_results, citations = extract_context(
            query=user_query,
            base_url=config.BASE_URL,
            db_name=config.DATABASE_NAME,
            token=config.TOKEN,
            max_context_length=config.RAG_MAX_CONTEXT_LENGTH,
            top_k=config.RAG_TOP_K,
            score_threshold=config.RAG_SCORE_THRESHOLD,
            metric_type=config.RAG_METRIC_TYPE
        )
        print("context_text: ", context_text)
        
        # 3. 构建Prompt
        final_prompt = build_prompt(
            user_input=user_query,
            context=f"对话历史：\n{conversation_context}\n\n知识库上下文：\n{context_text}"
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
        
        # 5. 调用 LLM 获取回答 ...
        raw_answer = llm_response["response"]

        # 6. 对输出做安全审计
        # from guard import validate_llm_output  # 与 validate_user_input/validate_prompt 同文件
        if not validate_llm_output(raw_answer):
            return {
                "status": "error",
                "message": "输出内容经安全审计判定为不安全，已拦截"
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
    data = request.get_json()
    user_query = data.get('query', '').strip()
    session_id = data.get('session_id')  # 获取前端传递的session_id
    print("session_id: ", session_id)
    # 仅在session_id为空时创建新会话，否则验证是否存在
    if not session_id:
        session_id = conversation_manager.create_conversation()
    else:
        # 检查会话是否存在，不存在则用指定ID创建
        if not conversation_manager.get_conversation(session_id):
            # 尝试用指定ID创建会话
            if not conversation_manager.create_conversation_with_id(session_id):
                # 极端情况：ID冲突时使用自动生成ID
                session_id = conversation_manager.create_conversation()
    
    if not user_query:
        return jsonify({
            "status": "error",
            "message": "请输入有效的查询内容",
            "session_id": session_id  # 返回新创建的会话ID
        })
    
    # 获取该会话的历史上下文
    conversation_context = conversation_manager.get_conversation_context(session_id)
    print("对话历史：", conversation_context)
    # 处理查询（核心逻辑不变，新增 conversation_context 传入）
    # result = process_query(user_query, conversation_context)
    result = process_query(user_query, conversation_context=conversation_context)
    
    # 将用户查询和AI回答添加到会话历史
    # print("result:", result)
    if result["status"] == "success":
        # print("添加消息！")
        # 添加用户消息
        conversation_manager.add_message_to_conversation(
            session_id=session_id,
            role="user",
            content=user_query
        )
        # 添加AI消息（含引用信息）
        conversation_manager.add_message_to_conversation(
            session_id=session_id,
            role="assistant",
            content=result["answer"],
            citations=result.get("citations", {})
        )
    
    # 返回结果时附带 session_id
    result["session_id"] = session_id
    return jsonify(result)

# 获取会话列表（供前端展示历史会话）
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    return jsonify({
        "status": "success",
        "conversations": conversation_manager.list_conversations()
    })

# 删除指定会话
@app.route('/api/conversations/<session_id>', methods=['DELETE'])
def delete_conversation(session_id):
    success = conversation_manager.delete_conversation(session_id)
    return jsonify({
        "status": "success" if success else "error",
        "message": "会话删除成功" if success else "会话不存在"
    })

# 获取当前配置信息
@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        "status": "success",
        "config": {
            "base_url": config.BASE_URL,
            "database_name": config.DATABASE_NAME,
            "model_temperature": config.MODEL_TEMPERATURE,
            "model_max_tokens": config.MODEL_MAX_TOKENS,
            "token_status": "已设置" if config.TOKEN and config.TOKEN != "your_default_token_here" else "未设置"
        }
    })

# 测试接口
@app.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({
        "status": "success",
        "message": "API服务正常运行中"
    })


# 启动服务
if __name__ == "__main__":
    # 测试API连接
    print("测试API连接...")
    if not test_connection():
        sys.exit(1)
    
    # 启动Flask服务（默认端口5000，允许外部访问）
    print("API服务启动中...")
    app.run(host='0.0.0.0', port=5000, debug=True)