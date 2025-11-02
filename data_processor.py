"""
数据处理模块 - 对搜索结果进行二次整理
包括：
1. extract_context() - 提炼上下文，选取相关文件，控制长度
2. files_to_citations() - 生成引用编号/链接，便于答案引用
"""
import requests
from typing import List, Dict, Tuple, Any
TOKEN = "e-1qa4tLR9N_AnEEBemwaiOBoyoRoFHr00W0Wb3Uk5tWE5ziWJiCHh7sM1b73T2s"
DBNAME = "student_Group12_final"
METRIC_TYPE = "cosine"
class DataProcessor:
    """数据处理器，用于处理RAG检索结果"""
    
    def __init__(self, max_context_length: int = 2000, top_k: int = 10):
        """
        初始化数据处理器
        
        Args:
            max_context_length: 最大上下文长度（字符数）
            top_k: 选取的最相关文件数量，默认为10
        """
        self.max_context_length = max_context_length
        self.top_k = top_k
    
    def search_knowledge_base(
        self, 
        query: str, 
        base_url: str = "http://10.1.0.220:9002/api",
        db_name: str = "common_dataset",
        token: str = "token_common",
        top_k: int = None,
        metric_type: str = "cosine",
        score_threshold: float = 0.0

    ) -> Dict[str, Any]:
        """
        调用后端搜索接口，从知识库中检索相关文档
        
        Args:
            query: 用户查询文本
            base_url: API基础URL
            db_name: 数据库名称（默认使用共享数据库）
            token: 访问令牌
            top_k: 返回的最相似文档数量
            metric_type: 相似度度量类型
            score_threshold: 相似度阈值,默认为0.5
            
        Returns:
            搜索结果字典，包含相关文档列表
        """
        if top_k is None:
            top_k = self.top_k

            
        search_url = f"{base_url}/databases/{db_name}/search"
        payload = {
            "token": token,
            "query": query,
            "top_k": top_k,
            "metric_type": metric_type,
            "score_threshold": score_threshold
        }
        
        try:
            response = requests.post(search_url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"搜索请求失败: {e}")
            return {"results": []}
    
    def process_context(
        self, 
        search_results: Dict[str, Any],
        max_length: int = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        从搜索结果中整理上下文，选取相关文件内容并控制长度
        
        Args:
            search_results: 后端搜索接口返回的结果
            max_length: 最大上下文长度（可选，默认使用初始化时的配置）
            
        Returns:
            (context_text, filtered_results): 
                - context_text: 整理后的上下文文本,智能截断
                - filtered_results: 筛选和处理后的结果列表,包含引用的文件信息和内容预览
        """
        if max_length is None:
            max_length = self.max_context_length# 调用时未显示指定则启用默认值
        
        # 获取搜索结果列表
        #此处搜索结果为json列表，search_results.json()["files"]
        results = search_results.get("files", [])
        
        if not results:
            return "", []
        
        # 按相似度分数排序（分数越高越相似）
        sorted_results = sorted(
            results, 
            key=lambda x: x.get("score", 0), 
            reverse=True
        )
        
        # 选取top_k个最相关的结果
        top_results = sorted_results[:self.top_k]
        
        # 构建上下文文本
        context_parts = []
        filtered_results = []
        current_length = 0
        
        for idx, result in enumerate(top_results, 1):
            # 提取文件内容和元数据
            file_content = result.get("text", "")
            file_id = result.get("file_id", "unknown")
            score = result.get("score", 0)
            metadata = result.get("metadata", {})
            
            # 如果已经达到最大长度，停止添加
            if current_length >= max_length:
                break
            
            # 计算可用空间
            available_space = max_length - current_length
            
            # 截断文本以适应剩余空间
            if len(file_content) > available_space:
                # 保留完整的句子，避免在句子中间截断
                truncated_content = self._smart_truncate(file_content, available_space)
            else:
                truncated_content = file_content
            
            # 构建带引用编号的上下文片段
            context_piece = f"[文档{idx}] (相似度: {score:.4f})\n{truncated_content}\n"
            context_parts.append(context_piece)
            
            # 记录筛选后的结果,List(Dict)
            filtered_results.append({
                "citation_id": idx,
                "file_id": file_id,
                "content": truncated_content,
                "score": score,
                "metadata": metadata
            })
            
            current_length += len(context_piece)
        
        # 合并所有上下文片段
        context_text = "\n".join(context_parts)
        
        return context_text, filtered_results
    
    def _smart_truncate(self, text: str, max_length: int) -> str:
        """
        智能截断文本，尽量保持句子完整性
        
        Args:
            text: 待截断的文本
            max_length: 最大长度
            
        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        
        # 在最大长度附近寻找句子结束标记
        truncated = text[:max_length]
        
        # 句子结束符
        sentence_ends = ['。', '！', '？', '.', '!', '?', '\n']
        
        # 从后向前查找最近的句子结束符
        last_end_pos = -1
        for end_char in sentence_ends:
            pos = truncated.rfind(end_char)
            if pos > last_end_pos:
                last_end_pos = pos
        
        # 如果找到句子结束符且位置合理（至少保留一半内容）
        if last_end_pos > max_length // 2:
            return truncated[:last_end_pos + 1]
        
        # 否则直接截断并添加省略号
        return truncated + "..."
    
    def files_to_citations(
        self, 
        filtered_results: List[Dict[str, Any]]
    ) -> Dict[int, Dict[str, Any]]:
        """
        生成引用编号和文件信息的映射，便于在答案中引用
        
        Args:
            filtered_results: extract_context返回的筛选结果列表
            
        Returns:
            引用字典，格式为 {citation_id: {file_id, score, metadata, ...}}
        """
        citations = {}
        
        for result in filtered_results:
            citation_id = result.get("citation_id")
            citations[citation_id] = {
                "file_id": result.get("file_id"),
                "score": result.get("score"),
                "metadata": result.get("metadata", {}),
                "content_preview": result.get("content")[:100] + "..." 
                    if len(result.get("content", "")) > 100 else result.get("content", "")
            }
        
        return citations
    
    def format_citations_for_display(
        self, 
        citations: Dict[int, Dict[str, Any]]
    ) -> str:
        """
        格式化引用信息，用于显示给用户
        
        Args:
            citations: 引用字典
            
        Returns:
            格式化后的引用文本
        """
        if not citations:
            return ""
        
        citation_lines = ["\n\n📚 参考文档："]
        
        for citation_id, info in sorted(citations.items()):
            file_id = info.get("file_id", "unknown")
            score = info.get("score", 0)
            metadata = info.get("metadata", {})
            description = metadata.get("description", "无描述")
            
            citation_line = f"[{citation_id}] 文件ID: {file_id} | 相似度: {score:.4f} | {description}"
            citation_lines.append(citation_line)
        
        return "\n".join(citation_lines)


def extract_context(
    query: str,
    base_url: str = "http://10.1.0.220:9002/api",
    db_name: str = "common_dataset",# 默认使用共享数据库
    token: str = "token_common",
    max_context_length: int = 2000,
    top_k: int = 5,
    score_threshold: float = 0.0,
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
    # 创建数据处理器,使用指定的最大上下文长度和top_k
    processor = DataProcessor(max_context_length=max_context_length, top_k=top_k)
    
    # 1. 调用搜索接口
    search_results = processor.search_knowledge_base(
        query=query,
        base_url=base_url,
        db_name=db_name,
        token=token,
        top_k=top_k,
        score_threshold=score_threshold,
        metric_type=metric_type
    )
    
    # 2. 提取上下文
    context_text, filtered_results = processor.process_context(search_results)
    
    # 3. 生成引用信息
    citations = processor.files_to_citations(filtered_results)
    
    return context_text, filtered_results, citations


# 测试代码
if __name__ == "__main__":
    # 测试RAG检索功能
    test_query = "钓鱼邮件"
    
    print(f"正在检索: {test_query}")
    print("=" * 60)
    
    context, results, citations = extract_context(
        query=test_query,
        max_context_length=1500,
        top_k=5,
        score_threshold=0.2,
        metric_type=METRIC_TYPE,
        db_name = DBNAME,
        token=TOKEN
    )
    
    print("\n提取的上下文：")
    print("-" * 60)
    print(context)
    
    print("\n\n引用信息：")
    print("-" * 60)
    processor = DataProcessor()
    print(processor.format_citations_for_display(citations))
    
    print("\n\n详细结果：")
    print("-" * 60)
    for result in results:
        print(f"引用ID: {result['citation_id']}")
        print(f"文件ID: {result['file_id']}")
        print(f"相似度: {result['score']:.4f}")
        print(f"内容预览: {result['content']}...")
        print("-" * 40)
