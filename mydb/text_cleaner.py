"""
文本清洗和质量优化模块（改进版）
用于提升爬取内容的质量，改善RAG检索效果
"""

import re
from typing import List, Dict, Tuple
from collections import Counter


class TextCleaner:
    """文本清洗器，用于清理网页爬取的内容"""
    
    def __init__(self):
        """初始化文本清洗器"""
        # 定义需要移除的无意义模式
        self.noise_patterns = [
            r'-{3,}',  # 连续的横线（3个或以上）
            r'={3,}',  # 连续的等号
            r'_{3,}',  # 连续的下划线
            r'\*{3,}',  # 连续的星号
            r'\.{3,}',  # 连续的句点（3个以上，保留省略号...）
            r'\s{3,}',  # 连续的空白字符（3个或以上）
            r'[\r\n]{3,}',  # 连续的换行符（3个或以上）
        ]
        
        # 编译正则表达式以提高性能
        self.compiled_patterns = [re.compile(p) for p in self.noise_patterns]
        
    def remove_noise_characters(self, text: str) -> str:
        """
        移除文本中的无意义字符和重复符号
        
        Args:
            text: 原始文本
            
        Returns:
            清洗后的文本
        """
        if not text:
            return ""
        
        # 移除连续的无意义字符
        cleaned = text
        for pattern in self.compiled_patterns:
            cleaned = pattern.sub(' ', cleaned)
        
        # 移除HTML实体残留
        cleaned = re.sub(r'&[a-zA-Z]+;', ' ', cleaned)
        cleaned = re.sub(r'&#\d+;', ' ', cleaned)
        
        # 移除特殊的Unicode字符（如零宽字符）
        cleaned = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', cleaned)
        
        # 规范化空白字符
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)  # 多个空格/制表符 -> 单个空格
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)  # 多个空行 -> 双换行
        
        # 移除行首行尾空白
        lines = [line.strip() for line in cleaned.split('\n')]
        cleaned = '\n'.join(line for line in lines if line)
        
        return cleaned.strip()
    
    def remove_navigation_and_footer(self, text: str) -> str:
        """
        移除常见的导航栏、页脚等无关内容
        
        Args:
            text: 原始文本
            
        Returns:
            清洗后的文本
        """
        # 移除常见的导航和页脚关键词
        noise_keywords = [
            r'(?i)copyright\s+©.*?\d{4}',
            r'(?i)all rights reserved',
            r'(?i)privacy policy',
            r'(?i)terms of service',
            r'(?i)cookie policy',
            r'(?i)subscribe to.*?newsletter',
            r'(?i)follow us on',
            r'(?i)share this.*?:',
        ]
        
        cleaned = text
        for keyword in noise_keywords:
            cleaned = re.sub(keyword, '', cleaned)
        
        return cleaned
    
    def extract_meaningful_sentences(self, text: str, min_length: int = 20) -> str:
        """
        提取有意义的句子，过滤过短或无意义的行
        
        Args:
            text: 原始文本
            min_length: 最小句子长度（字符数）
            
        Returns:
            清洗后的文本
        """
        # 按句子分割（支持中英文）
        sentences = re.split(r'[。！？\n.!?]+', text)
        
        meaningful_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            
            # 过滤条件
            if len(sentence) < min_length:
                continue
            
            # 检查是否包含足够的字母或汉字（排除纯符号行）
            alpha_count = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', sentence))
            if alpha_count < min_length * 0.5:  # 至少50%是有意义字符
                continue
            
            meaningful_sentences.append(sentence)
        
        return '. '.join(meaningful_sentences) if meaningful_sentences else text
    
    def deduplicate_lines(self, text: str) -> str:
        """
        去除重复或高度相似的行（常见于导航栏重复）
        
        Args:
            text: 原始文本
            
        Returns:
            去重后的文本
        """
        lines = text.split('\n')
        unique_lines = []
        seen_lines = set()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 简单去重：完全相同的行
            if line in seen_lines:
                continue
            
            seen_lines.add(line)
            unique_lines.append(line)
        
        return '\n'.join(unique_lines)
    
    def clean_text(self, text: str, aggressive: bool = False) -> str:
        """
        完整的文本清洗流程
        
        Args:
            text: 原始文本
            aggressive: 是否使用激进清洗（会移除更多内容，但可能误删有用信息）
            
        Returns:
            清洗后的文本
        """
        if not text or len(text.strip()) < 50:
            return ""
        
        # 第一步：移除无意义字符
        cleaned = self.remove_noise_characters(text)
        
        # 第二步：移除导航和页脚
        cleaned = self.remove_navigation_and_footer(cleaned)
        
        # 第三步：去重
        cleaned = self.deduplicate_lines(cleaned)
        
        # 第四步（可选）：提取有意义的句子
        if aggressive:
            cleaned = self.extract_meaningful_sentences(cleaned, min_length=30)
        
        return cleaned.strip()


class ContentQualityEvaluator:
    """内容质量评估器，用于过滤低质量文本（改进版）"""
    
    def __init__(self):
        """初始化质量评估器"""
        # 网络安全领域的关键词（用于判断相关性）
        self.security_keywords = [
            # 英文关键词
            'security', 'attack', 'vulnerability', 'exploit', 'malware', 
            'encryption', 'authentication', 'authorization', 'firewall',
            'intrusion', 'threat', 'risk', 'breach', 'phishing', 'ransomware',
            'sql injection', 'xss', 'csrf', 'ddos', 'penetration', 'hacker',
            'cyber', 'network', 'protocol', 'cryptography', 'ssl', 'tls',
            'password', 'access control', 'backdoor', 'trojan', 'worm',
            
            # 中文关键词
            '安全', '攻击', '漏洞', '威胁', '恶意', '加密', '认证', '授权',
            '防火墙', '入侵', '风险', '泄露', '钓鱼', '勒索', '注入',
            '跨站', '渗透', '黑客', '网络', '协议', '密码', '访问控制',
            '后门', '木马', '蠕虫', '病毒',
        ]
    
    def calculate_quality_score(self, text: str) -> Dict[str, float]:
        """
        计算文本质量分数（改进版 - 更严格的评分标准）
        
        Args:
            text: 待评估的文本
            
        Returns:
            质量评分字典，包含多个维度的分数
        """
        if not text:
            return {
                'overall': 0.0,
                'length': 0.0,
                'relevance': 0.0,
                'readability': 0.0,
                'information_density': 0.0
            }
        
        scores = {}
        
        # 1. 长度分数（100-2000字符为最佳）
        length = len(text)
        if length < 50:
            scores['length'] = 0.0
        elif length < 100:
            scores['length'] = 0.3
        elif 100 <= length <= 2000:
            scores['length'] = 1.0
        elif 2000 < length <= 5000:
            scores['length'] = 0.8
        else:
            scores['length'] = 0.6
        
        # 2. 相关性分数（包含安全关键词的比例）- 改进版
        text_lower = text.lower()
        keyword_count = sum(1 for kw in self.security_keywords if kw in text_lower)
        
        # 更严格的相关性评分
        if keyword_count == 0:
            scores['relevance'] = 0.0  # 没有关键词直接0分
        elif keyword_count == 1:
            scores['relevance'] = 0.2  # 只有1个关键词给20%
        elif keyword_count == 2:
            scores['relevance'] = 0.4  # 2个关键词给40%
        elif keyword_count == 3:
            scores['relevance'] = 0.6  # 3个关键词给60%
        elif keyword_count == 4:
            scores['relevance'] = 0.8  # 4个关键词给80%
        else:
            scores['relevance'] = 1.0  # 5个及以上给满分
        
        # 3. 可读性分数（字母/汉字占比）
        meaningful_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
        if length > 0:
            scores['readability'] = meaningful_chars / length
        else:
            scores['readability'] = 0.0
        
        # 4. 信息密度（句子平均长度，避免过短或过长）
        sentences = re.split(r'[。！？.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
            # 理想句子长度：20-100字符
            if 20 <= avg_sentence_length <= 100:
                scores['information_density'] = 1.0
            elif avg_sentence_length < 20:
                scores['information_density'] = avg_sentence_length / 20
            else:
                scores['information_density'] = max(0.5, 100 / avg_sentence_length)
        else:
            scores['information_density'] = 0.0
        
        # 5. 综合分数（改进版 - 更高的相关性权重，并设置相关性门槛）
        # 策略：如果相关性太低，即使其他维度好也不行
        if scores['relevance'] < 0.2:
            # 相关性低于20%，综合分数最高只能是0.3
            scores['overall'] = min(0.3, (
                scores['length'] * 0.15 +
                scores['relevance'] * 0.6 +  # 提高相关性权重到60%
                scores['readability'] * 0.15 +
                scores['information_density'] * 0.1
            ))
        else:
            # 正常计算
            scores['overall'] = (
                scores['length'] * 0.15 +
                scores['relevance'] * 0.6 +  # 提高相关性权重到60%
                scores['readability'] * 0.15 +
                scores['information_density'] * 0.1
            )
        
        return scores
    
    def is_high_quality(self, text: str, threshold: float = 0.5) -> bool:
        """
        判断文本是否为高质量（改进版 - 增加相关性硬性要求）
        
        Args:
            text: 待评估的文本
            threshold: 质量阈值（0-1）
            
        Returns:
            是否为高质量文本
        """
        scores = self.calculate_quality_score(text)
        
        # 硬性要求：相关性必须 >= 0.2（至少有1个安全关键词）
        if scores['relevance'] < 0.2:
            return False
        
        # 综合分数达标
        return scores['overall'] >= threshold


def clean_and_evaluate(text: str, aggressive: bool = False) -> Tuple[str, Dict[str, float], bool]:
    """
    便捷函数：清洗文本并评估质量
    
    Args:
        text: 原始文本
        aggressive: 是否使用激进清洗
        
    Returns:
        (清洗后的文本, 质量评分, 是否高质量)
    """
    cleaner = TextCleaner()
    evaluator = ContentQualityEvaluator()
    
    cleaned_text = cleaner.clean_text(text, aggressive=aggressive)
    quality_scores = evaluator.calculate_quality_score(cleaned_text)
    is_high_quality = evaluator.is_high_quality(cleaned_text, threshold=0.5)
    
    return cleaned_text, quality_scores, is_high_quality


# 测试代码
if __name__ == "__main__":
    import sys
    import io
    
    # 设置UTF-8输出（Windows兼容）
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # 测试样例：包含大量噪音的文本
    test_text = """
    =====================================
    Navigation Menu | Home | About | Contact
    =====================================
    
    SQL Injection Attacks
    
    --------------------
    --------------------
    --------------------
    
    SQL injection is a code injection technique that might destroy your database.
    SQL injection is one of the most common web hacking techniques.
    SQL injection is the placement of malicious code in SQL statements, via web page input.
    
    How to Prevent SQL Injection:
    - Use parameterized queries
    - Validate user input
    - Use stored procedures
    
    
    
    Copyright 2024 All Rights Reserved | Privacy Policy | Terms of Service
    Follow us on: Twitter Facebook LinkedIn
    """
    
    print("原始文本:")
    print("=" * 60)
    print(test_text)
    print("\n")
    
    # 清洗文本
    cleaned, scores, is_hq = clean_and_evaluate(test_text, aggressive=False)
    
    print("清洗后的文本:")
    print("=" * 60)
    print(cleaned)
    print("\n")
    
    print("质量评分:")
    print("=" * 60)
    for key, value in scores.items():
        print(f"{key:25s}: {value:.4f}")
    print(f"\n是否高质量: {is_hq}")

