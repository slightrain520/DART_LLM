### 接口说明:
#### RAG部分：
主要功能函数为```extract_context```,输入参数有最大上下文长度,搜索最相似文档数量,相似度阈值，搜索评估类型等，返回有整理后的上下文,结果列表和引用列表,详见如下说明:
```python
def extract_context(
    query: str,
    base_url: str = "http://10.1.0.220:9002/api",
    db_name: str = "common_dataset",# 默认使用共享数据库
    token: str = "token_common",
    max_context_length: int = 2000,
    top_k: int = 5,
    score_threshold: float = 0.5,
    metric_type: str = "cosine"
) -> Tuple[str, List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    """
    这是主要的对外接口函数，完成完整的RAG检索流程：
    1. 调用后端搜索接口
    2. 提取和整理上下文
    3. 生成引用信息
    
    Args:
        query: 用户查询文本
        base_url: API基础URL
        db_name: 数据库名称
        token: 访问令牌
        max_context_length: 最大上下文长度
        top_k: 返回的最相似文档数量
        
    Returns:
        (context_text, filtered_results, citations):
            - context_text: 提取的上下文，会列出检索到的相关文档、相似度，并智能截断，建议给LLM使用
            - filtered_results: 详细结果，包含引用ID，文件ID，相似度，内容预览，方便用户查看检索内容
            - citations: 引用信息字典，包含文件ID，相似度和description（类似参考文献列表）
            
    Example:
        >>> context, results, citations = extract_context(
        ...     query="什么是网络安全？",#用户输入的查询
        ...     max_context_length=1500,# 最大上下文长度，从配置文件读取
        ...     top_k=3# 返回的最相似文档数量
        ... )
        >>> print(context)
        >>> print(citations)
    """
```
使用时直接导入data_processor模块，使用该函数即可。可优化的地方有：**可以使用config中的统一配置来设置函数中的默认参数**。可以考虑修改。

现在遇到的问题：后端search接口的metric_type目前只支持cosine，使用L2后会报错：
```
500 Server Error: Internal Server Error for url: http://10.1.0.220:9002/api/databases/common_dataset/search
```