# config.py

import os
import sys
from typing import Dict, List, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv 未安装，将使用默认配置或环境变量")
    pass

class Config:
    """配置管理类"""
    
    # 项目名称
    PROJECT_NAME = "DART_LLM"

    # 是否输出配置信息
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # API基础URL
    BASE_URL = os.getenv("DART_BASE_URL", "http://10.1.0.220:9002/api")
    
    # 用户认证Token
    TOKEN = os.getenv("DART_API_TOKEN", "your_default_token_here")
    
    # 默认数据库名称
    DATABASE_NAME = os.getenv("DATABASE_NAME", "common_dataset")
    
    # 温度参数
    MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.1"))
    
    # 最大生成长度
    MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "500"))
    
    # 输入长度限制
    MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "1000"))
    
    # 请求超时时间（秒）
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # 最大重试次数
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    
    # 重试间隔（秒）
    RETRY_DELAY = float(os.getenv("RETRY_DELAY", "1.0"))
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # API端点
    ENDPOINTS = {
        "dialogue": "/dialogue",
        "search": "/databases/{database_name}/search",
        "upload": "/databases/{database_name}/files",
        "databases": "/databases",
        "files": "/databases/{database_name}/files"
    }
    
    # 验证配置
    @classmethod
    def validate_config(cls):
        """验证配置的完整性"""
        errors = []
        
        if not cls.TOKEN or cls.TOKEN == "your_default_token_here":
            errors.append("❌ 请设置 DART_API_TOKEN 环境变量")
        
        if not cls.BASE_URL:
            errors.append("❌ BASE_URL 不能为空")
        
        if cls.MODEL_TEMPERATURE < 0 or cls.MODEL_TEMPERATURE > 1:
            errors.append("❌ MODEL_TEMPERATURE 应该在 0-1 范围内")
        
        if cls.MAX_INPUT_LENGTH <= 0:
            errors.append("❌ MAX_INPUT_LENGTH 应该大于 0")
        
        return errors
    
    @classmethod
    def print_config_summary(cls):
        """打印配置摘要"""
        print("=" * 50)
        print("📋 配置摘要")
        print("=" * 50)
        print(f"项目名称: {cls.PROJECT_NAME}")
        print(f"API地址: {cls.BASE_URL}")
        print(f"数据库: {cls.DATABASE_NAME}")
        print(f"模型参数: temperature={cls.MODEL_TEMPERATURE}, max_tokens={cls.MODEL_MAX_TOKENS}")
        print(f"系统配置: 超时={cls.REQUEST_TIMEOUT}s, 重试={cls.MAX_RETRIES}次")
        
        # 检查Token是否已设置
        if cls.TOKEN and cls.TOKEN != "your_default_token_here":
            print(f"Token状态: ✅ 已设置")
        else:
            print("Token状态: ❌ 未设置")
        
        print("=" * 50)

config = Config()

def setup_environment():
    """环境设置函数"""
    
    # 验证配置
    errors = config.validate_config()
    if errors:
        print("🚨 配置错误:")
        for error in errors:
            print(f"  {error}")
        print("\n💡 解决方案:")
        print("  1. 创建 .env 文件并设置 DART_API_TOKEN")
        print("  2. 或设置环境变量: export DART_API_TOKEN=your_token")
        print("  3. 检查其他配置参数")
        return False
    
    if config.DEBUG:
        config.print_config_summary()
    
    return True

# 初始化时进行环境设置
if __name__ == "__main__":
    print("🔧 初始化配置...")
    if setup_environment():
        print("✅ 配置初始化成功")
    else:
        print("❌ 配置初始化失败")
        sys.exit(1)