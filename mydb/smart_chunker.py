"""
智能文本分块模块
改进原有的简单字符切分，采用语义感知的分块策略
"""

import re
from typing import List, Dict, Tuple
from hashlib import md5


class SmartChunker:
    """智能文本分块器，基于语义边界进行分块"""
    
    def __init__(
        self, 
        chunk_size: int = 1500,
        chunk_overlap: int = 150,
        min_chunk_size: int = 100
    ):
        """
        初始化智能分块器
        
        Args:
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 块之间的重叠大小
            min_chunk_size: 最小块大小，小于此值的块会被丢弃或合并
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
    def split_by_semantic_boundaries(self, text: str) -> List[str]:
        """
        基于语义边界分割文本（段落、句子）
        
        Args:
            text: 待分割的文本
            
        Returns:
            分割后的文本块列表
        """
        if not text or len(text) < self.min_chunk_size:
            return []
        
        # 第一步：按段落分割（双换行或多个换行）
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            # 如果当前段落本身就很长，需要进一步分割
            if len(para) > self.chunk_size * 1.5:
                # 如果当前chunk有内容，先保存
                if current_chunk and len(current_chunk) >= self.min_chunk_size:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # 将长段落按句子分割
                sentences = self._split_into_sentences(para)
                temp_chunk = ""
                
                for sentence in sentences:
                    if len(temp_chunk) + len(sentence) <= self.chunk_size:
                        temp_chunk += sentence + " "
                    else:
                        if temp_chunk and len(temp_chunk) >= self.min_chunk_size:
                            chunks.append(temp_chunk.strip())
                        temp_chunk = sentence + " "
                
                if temp_chunk and len(temp_chunk) >= self.min_chunk_size:
                    current_chunk = temp_chunk
                    
            # 如果加上这个段落不会超过chunk_size
            elif len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += para + "\n\n"
            
            # 如果会超过，保存当前chunk，开始新chunk
            else:
                if current_chunk and len(current_chunk) >= self.min_chunk_size:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        # 保存最后一个chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        将文本分割成句子（支持中英文）
        
        Args:
            text: 待分割的文本
            
        Returns:
            句子列表
        """
        # 使用正则表达式分割句子（支持中英文标点）
        # 保留标点符号
        sentences = re.split(r'([。！？.!?]+)', text)
        
        # 重新组合句子和标点
        result = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i].strip()
            punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
            if sentence:
                result.append(sentence + punctuation)
        
        # 处理最后一个元素（如果没有标点）
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())
        
        return result
    
    def add_overlap(self, chunks: List[str]) -> List[str]:
        """
        在相邻chunk之间添加重叠内容，保持上下文连贯性
        
        Args:
            chunks: 原始chunk列表
            
        Returns:
            添加重叠后的chunk列表
        """
        if not chunks or self.chunk_overlap == 0:
            return chunks
        
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                # 第一个chunk不需要添加前置重叠
                overlapped_chunks.append(chunk)
            else:
                # 从前一个chunk的末尾提取overlap内容
                prev_chunk = chunks[i - 1]
                overlap_text = prev_chunk[-self.chunk_overlap:] if len(prev_chunk) > self.chunk_overlap else prev_chunk
                
                # 尝试在句子边界处截断overlap
                overlap_text = self._truncate_at_sentence_boundary(overlap_text)
                
                # 合并overlap和当前chunk
                overlapped_chunks.append(overlap_text + " " + chunk)
        
        return overlapped_chunks
    
    def _truncate_at_sentence_boundary(self, text: str) -> str:
        """
        在句子边界处截断文本
        
        Args:
            text: 待截断的文本
            
        Returns:
            截断后的文本
        """
        # 查找最后一个句子结束符
        sentence_ends = ['。', '！', '？', '.', '!', '?']
        last_pos = -1
        
        for end_char in sentence_ends:
            pos = text.rfind(end_char)
            if pos > last_pos:
                last_pos = pos
        
        # 如果找到句子结束符，在其后截断
        if last_pos > len(text) // 2:  # 至少保留一半内容
            return text[:last_pos + 1]
        
        return text
    
    def deduplicate_chunks(self, chunks: List[str]) -> List[str]:
        """
        去除完全重复或高度相似的chunk
        
        Args:
            chunks: 原始chunk列表
            
        Returns:
            去重后的chunk列表
        """
        if not chunks:
            return []
        
        unique_chunks = []
        seen_hashes = set()
        
        for chunk in chunks:
            # 使用MD5哈希快速检测完全重复
            chunk_hash = md5(chunk.encode('utf-8')).hexdigest()
            
            if chunk_hash not in seen_hashes:
                seen_hashes.add(chunk_hash)
                unique_chunks.append(chunk)
        
        return unique_chunks
    
    def chunk_text(self, text: str, deduplicate: bool = True) -> List[str]:
        """
        完整的智能分块流程
        
        Args:
            text: 待分块的文本
            deduplicate: 是否去重
            
        Returns:
            分块后的文本列表
        """
        if not text or len(text) < self.min_chunk_size:
            return []
        
        # 第一步：基于语义边界分割
        chunks = self.split_by_semantic_boundaries(text)
        
        # 第二步：添加重叠
        chunks = self.add_overlap(chunks)
        
        # 第三步：去重
        if deduplicate:
            chunks = self.deduplicate_chunks(chunks)
        
        # 第四步：过滤过小的chunk
        chunks = [c for c in chunks if len(c) >= self.min_chunk_size]
        
        return chunks


def compare_chunking_methods(text: str):
    """
    比较原始方法和智能方法的分块效果
    
    Args:
        text: 测试文本
    """
    print("=" * 80)
    print("原始方法（简单字符切分）:")
    print("=" * 80)
    
    # 原始方法：简单按字符数切分
    chunk_size = 500
    overlap = 50
    simple_chunks = []
    
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if len(chunk) >= 100:
            simple_chunks.append(chunk)
    
    print(f"生成chunk数量: {len(simple_chunks)}")
    for i, chunk in enumerate(simple_chunks[:3], 1):
        print(f"\nChunk {i} (长度: {len(chunk)}):")
        print(chunk[:200] + "..." if len(chunk) > 200 else chunk)
    
    print("\n" + "=" * 80)
    print("智能方法（语义感知分块）:")
    print("=" * 80)
    
    # 智能方法
    chunker = SmartChunker(chunk_size=500, chunk_overlap=50, min_chunk_size=100)
    smart_chunks = chunker.chunk_text(text)
    
    print(f"生成chunk数量: {len(smart_chunks)}")
    for i, chunk in enumerate(smart_chunks[:3], 1):
        print(f"\nChunk {i} (长度: {len(chunk)}):")
        print(chunk[:200] + "..." if len(chunk) > 200 else chunk)
    
    print("\n" + "=" * 80)
    print("对比总结:")
    print("=" * 80)
    print(f"原始方法: {len(simple_chunks)} 个chunk")
    print(f"智能方法: {len(smart_chunks)} 个chunk")
    print(f"优化率: {(1 - len(smart_chunks) / len(simple_chunks)) * 100:.1f}%")


# 测试代码
if __name__ == "__main__":
    test_text = """
    SQL Injection Attacks and Defense
    
    SQL injection is a code injection technique used to attack data-driven applications. 
    Malicious SQL statements are inserted into an entry field for execution.
    
    Common Types of SQL Injection:
    
    In-band SQLi is the most common type of SQL injection attack. It occurs when an attacker 
    is able to use the same communication channel to both launch the attack and gather results.
    
    Error-based SQLi relies on error messages thrown by the database server to obtain information 
    about the structure of the database. In some cases, error-based SQL injection alone is enough 
    for an attacker to enumerate an entire database.
    
    Union-based SQLi leverages the UNION SQL operator to combine the results of two or more 
    SELECT statements into a single result which is then returned as part of the HTTP response.
    
    Prevention Techniques:
    
    Use parameterized queries (prepared statements). This is the most effective way to prevent 
    SQL injection attacks. Parameterized queries force the developer to first define all the 
    SQL code, and then pass in each parameter to the query later.
    
    Use stored procedures. While stored procedures are not always safe from SQL injection, 
    certain standard stored procedure programming constructs have the same effect as the use 
    of parameterized queries when implemented safely.
    
    Validate input. Input validation can be used as a secondary defense against SQL injection. 
    However, it should not be relied upon as the primary defense.
    """
    
    print("测试文本长度:", len(test_text), "字符\n")
    compare_chunking_methods(test_text)

