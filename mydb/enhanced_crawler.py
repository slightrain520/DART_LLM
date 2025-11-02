"""
增强版网络安全知识库爬取系统
集成改进的文本清洗、智能分块、PDF处理等功能
包含丰富的中英文数据源
"""

import sys
import os
import time
import logging
import requests
from typing import List, Dict, Tuple, Optional
from urllib.parse import urlparse, urljoin

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text
import hashlib

# 导入改进的模块
from mydb.text_cleaner import TextCleaner, ContentQualityEvaluator
from mydb.smart_chunker import SmartChunker
from mydb.createdb_pipeline import (
    BASE_URL, TOKEN, METRIC_TYPE,
    safe_request_get, generate_metadata,
    create_database, upload_chunks
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# PDF临时目录
PDF_TMP_DIR = os.path.join(os.getenv("TEMP", "."), "pdf_cache")
os.makedirs(PDF_TMP_DIR, exist_ok=True)


class EnhancedCrawler:
    """增强版爬虫，支持网页和PDF，集成文本清洗和质量控制"""
    
    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 150,
        min_chunk_size: int = 100,
        quality_threshold: float = 0.4,
        aggressive_cleaning: bool = False
    ):
        """
        初始化增强版爬虫
        
        Args:
            chunk_size: 目标chunk大小
            chunk_overlap: chunk重叠大小
            min_chunk_size: 最小chunk大小
            quality_threshold: 质量阈值（0-1）
            aggressive_cleaning: 是否使用激进清洗
        """
        self.text_cleaner = TextCleaner()
        self.quality_evaluator = ContentQualityEvaluator()
        self.chunker = SmartChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size
        )
        self.quality_threshold = quality_threshold
        self.aggressive_cleaning = aggressive_cleaning
        
        # 统计信息
        self.stats = {
            'total_urls': 0,
            'successful_pages': 0,
            'failed_pages': 0,
            'low_quality_pages': 0,
            'total_chunks': 0,
            'filtered_chunks': 0,
            'final_chunks': 0,
            'pdf_count': 0,
            'html_count': 0
        }
    
    def download_pdf_to_text(self, url: str) -> str:
        """
        下载PDF并提取文本
        
        Args:
            url: PDF文件URL
            
        Returns:
            提取的文本内容
        """
        logging.info(f"下载PDF: {url}")
        self.stats['pdf_count'] += 1
        
        r = safe_request_get(url, stream=True)
        if not r:
            return ""
        
        # 生成唯一文件名
        fn = os.path.join(PDF_TMP_DIR, hashlib.sha1(url.encode()).hexdigest() + ".pdf")
        
        # 下载文件
        with open(fn, "wb") as f:
            for chunk in r.iter_content(1024*16):
                if chunk:
                    f.write(chunk)
        
        try:
            # 提取文本
            text = extract_text(fn)
            
            # 删除临时文件
            try:
                os.remove(fn)
            except:
                pass
            
            return text
        except Exception as e:
            logging.warning(f"PDF提取失败: {e}")
            return ""
    
    def html_to_text(self, html: str) -> Tuple[str, str]:
        """
        从HTML中提取标题和正文（改进版）
        
        Args:
            html: HTML源代码
            
        Returns:
            (title, text) 元组
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # 提取标题
        title = (soup.title.string.strip() if soup.title and soup.title.string else "") or ""
        
        # 移除无用标签
        for s in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            s.decompose()
        
        # 移除噪声元素
        noise_selectors = [
            '.breadcrumb', '.nav', '.footer', '#footer', '.sidebar',
            '.ad', '.advert', '.cookie', '.menu', '.banner',
            '.social-share', '.comment', '.related-posts'
        ]
        for sel in noise_selectors:
            for node in soup.select(sel):
                node.decompose()
        
        # 智能定位主要内容
        main = soup.find("main") or soup.find("article")
        
        if not main:
            candidates = soup.find_all(["div", "section"], recursive=True)
            if candidates:
                main = max(candidates, key=lambda d: len(d.get_text(separator=" ", strip=True)) if d else 0)
            else:
                main = soup.body
        
        # 提取文本
        text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)
        
        return title, text
    
    def process_url(self, url: str) -> List[Dict]:
        """
        处理单个URL（网页或PDF）
        
        Args:
            url: 要处理的URL
            
        Returns:
            处理后的chunk列表
        """
        self.stats['total_urls'] += 1
        
        try:
            # 判断是否为PDF
            if url.lower().endswith('.pdf'):
                # 处理PDF
                text = self.download_pdf_to_text(url)
                title = url.split('/')[-1].replace('.pdf', '')
                
                if not text or len(text) < 100:
                    logging.warning(f"PDF内容过短: {url}")
                    self.stats['failed_pages'] += 1
                    return []
            else:
                # 处理HTML
                self.stats['html_count'] += 1
                response = safe_request_get(url)
                if not response:
                    logging.warning(f"爬取失败: {url}")
                    self.stats['failed_pages'] += 1
                    return []
                
                title, text = self.html_to_text(response.text)
                
                if not text or len(text) < 100:
                    logging.warning(f"文本过短: {url}")
                    self.stats['failed_pages'] += 1
                    return []
            
            # 清洗文本
            cleaned_text = self.text_cleaner.clean_text(text, aggressive=self.aggressive_cleaning)
            if not cleaned_text:
                logging.warning(f"清洗后为空: {url}")
                self.stats['failed_pages'] += 1
                return []
            
            # 质量评估
            quality_scores = self.quality_evaluator.calculate_quality_score(cleaned_text)
            if quality_scores['overall'] < self.quality_threshold:
                logging.info(f"质量不达标 (分数: {quality_scores['overall']:.2f}): {url}")
                self.stats['low_quality_pages'] += 1
                return []
            
            # 智能分块
            chunks = self.chunker.chunk_text(cleaned_text, deduplicate=True)
            self.stats['total_chunks'] += len(chunks)
            
            if not chunks:
                logging.warning(f"分块后为空: {url}")
                self.stats['failed_pages'] += 1
                return []
            
            # 为每个chunk生成元数据
            upload_items = []
            for i, chunk_text in enumerate(chunks):
                # 评估chunk质量
                chunk_quality = self.quality_evaluator.calculate_quality_score(chunk_text)
                
                # 过滤低质量chunk
                if chunk_quality['overall'] < self.quality_threshold:
                    self.stats['filtered_chunks'] += 1
                    continue
                
                # 生成元数据
                metadata = generate_metadata(chunk_text, url, title)
                
                # 添加额外信息
                metadata['quality_score'] = round(chunk_quality['overall'], 4)
                metadata['chunk_index'] = i
                metadata['total_chunks'] = len(chunks)
                metadata['source_type'] = 'pdf' if url.lower().endswith('.pdf') else 'html'
                
                upload_items.append({
                    'file': chunk_text,
                    'metadata': metadata
                })
            
            self.stats['successful_pages'] += 1
            self.stats['final_chunks'] += len(upload_items)
            
            logging.info(f"✓ 处理成功: {url} | 质量: {quality_scores['overall']:.2f} | "
                        f"Chunks: {len(upload_items)}/{len(chunks)}")
            
            return upload_items
            
        except Exception as e:
            logging.error(f"处理失败 {url}: {e}")
            self.stats['failed_pages'] += 1
            return []
    
    def process_urls(self, urls: List[str], delay: float = 1.0) -> List[Dict]:
        """
        批量处理URL列表
        
        Args:
            urls: URL列表
            delay: 请求间隔（秒）
            
        Returns:
            所有chunk的列表
        """
        all_chunks = []
        
        for i, url in enumerate(urls, 1):
            logging.info(f"\n处理进度: {i}/{len(urls)}")
            chunks = self.process_url(url)
            all_chunks.extend(chunks)
            
            # 避免请求过快
            if i < len(urls):  # 最后一个URL不需要延迟
                time.sleep(delay)
        
        return all_chunks
    
    def print_stats(self):
        """打印统计信息"""
        logging.info("\n" + "=" * 80)
        logging.info("处理统计:")
        logging.info("=" * 80)
        logging.info(f"总URL数: {self.stats['total_urls']}")
        logging.info(f"  - HTML页面: {self.stats['html_count']}")
        logging.info(f"  - PDF文件: {self.stats['pdf_count']}")
        logging.info(f"成功处理: {self.stats['successful_pages']}")
        logging.info(f"失败页面: {self.stats['failed_pages']}")
        logging.info(f"低质量页面: {self.stats['low_quality_pages']}")
        logging.info(f"生成chunk总数: {self.stats['total_chunks']}")
        logging.info(f"过滤chunk数: {self.stats['filtered_chunks']}")
        logging.info(f"最终chunk数: {self.stats['final_chunks']}")
        
        if self.stats['total_urls'] > 0:
            success_rate = self.stats['successful_pages'] / self.stats['total_urls'] * 100
            logging.info(f"成功率: {success_rate:.1f}%")
        
        if self.stats['total_chunks'] > 0:
            filter_rate = self.stats['filtered_chunks'] / self.stats['total_chunks'] * 100
            logging.info(f"过滤率: {filter_rate:.1f}%")
        
        logging.info("=" * 80)


def get_cybersecurity_urls() -> Dict[str, List[str]]:
    """
    获取网络安全相关的高质量数据源URL
    包含中英文网站
    
    Returns:
        按类别分组的URL字典
    """
    urls = {
        # ===== 国际权威标准和知识库 =====
        # 'standards': [
        #     # OWASP Top 10 (Web应用安全)
        #     "https://owasp.org/www-project-top-ten/",
        #     "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
        #     "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/",
        #     "https://owasp.org/Top10/A03_2021-Injection/",
            
        #     # MITRE ATT&CK (攻击技术)
        #     "https://attack.mitre.org/techniques/T1190/",  # Exploit Public-Facing Application
        #     "https://attack.mitre.org/techniques/T1059/",  # Command and Scripting Interpreter
        #     "https://attack.mitre.org/techniques/T1078/",  # Valid Accounts
        #     "https://attack.mitre.org/techniques/T1566/",  # Phishing
            
        #     # CWE (通用弱点枚举)
        #     "https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html",
        # ],
        
        # ===== 技术教程和实战 =====
        # 'tutorials': [
        #     # PortSwigger Web Security Academy
        #     "https://portswigger.net/web-security/sql-injection",
        #     "https://portswigger.net/web-security/cross-site-scripting",
        #     "https://portswigger.net/web-security/csrf",
        #     "https://portswigger.net/web-security/xxe",
            
        #     # OWASP Cheat Sheet
        #     "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html",
        #     "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html",
        # ],
        
        # # ===== 中文维基百科（网络安全相关） =====
        # 'wikipedia_zh': [
        #     "https://zh.wikipedia.org/wiki/SQL注入",
        #     "https://zh.wikipedia.org/wiki/跨網站指令碼",
        #     "https://zh.wikipedia.org/wiki/跨站请求伪造",
        #     "https://zh.wikipedia.org/wiki/拒绝服务攻击",
        #     "https://zh.wikipedia.org/wiki/钓鱼式攻击",
        #     "https://zh.wikipedia.org/wiki/勒索软件",
        #     "https://zh.wikipedia.org/wiki/防火墙",
        #     "https://zh.wikipedia.org/wiki/入侵检测系统",
        #     "https://zh.wikipedia.org/wiki/加密",
        #     "https://zh.wikipedia.org/wiki/数字签名",
        #     "https://zh.wikipedia.org/wiki/公开密钥加密",
        #     "https://zh.wikipedia.org/wiki/渗透测试",
        # ],
        
        # # ===== 英文维基百科（网络安全相关） =====
        # 'wikipedia_en': [
        #     "https://en.wikipedia.org/wiki/SQL_injection",
        #     "https://en.wikipedia.org/wiki/Cross-site_scripting",
        #     "https://en.wikipedia.org/wiki/Cross-site_request_forgery",
        #     "https://en.wikipedia.org/wiki/Denial-of-service_attack",
        #     "https://en.wikipedia.org/wiki/Phishing",
        #     "https://en.wikipedia.org/wiki/Ransomware",
        #     "https://en.wikipedia.org/wiki/Penetration_test",
        #     "https://en.wikipedia.org/wiki/Computer_security",
        # ],
        
        # ===== 中文安全资讯和技术博客 =====
        'chinese_blogs': [
            # 注意：这些URL需要根据实际情况选择具体文章
            # 这里提供一些主页和常见技术文章类型的示例
            
            # 先知社区（阿里云）- 需要替换为具体文章URL
            "https://xz.aliyun.com/",
            
            # 安全客 - 需要替换为具体文章URL
            "https://www.anquanke.com/",
            
            # FreeBuf - 需要替换为具体文章URL
            "https://www.freebuf.com/",
        ],
        
#         # ===== 政府和机构资源 =====
#         'government': [
#             # NIST 网络安全资源
#             "https://csrc.nist.gov/",
            
#             # US-CERT
#             "https://www.cisa.gov/news-events/cybersecurity-advisories",
#         ],
#         'laws': [
#             "http://www.npc.gov.cn/zgrdw/npc/xinwen/2016-11/07/content_2001605.htm",
#            "http://www.npc.gov.cn/c2/c30834/202106/t20210610_311888.html",
#            "http://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html",
#            "https://www.gov.cn/gongbao/content/2021/content_5636138.htm",

#         ],
#         'wikipedia': [
#     # 攻击技术
#     "https://zh.wikipedia.org/wiki/SQL注入",
#     "https://zh.wikipedia.org/wiki/跨網站指令碼",
#     "https://zh.wikipedia.org/wiki/跨站请求伪造",
#     "https://zh.wikipedia.org/wiki/缓冲区溢出",
#     "https://zh.wikipedia.org/wiki/拒绝服务攻击",
#     "https://zh.wikipedia.org/wiki/钓鱼式攻击",
#     "https://zh.wikipedia.org/wiki/中间人攻击",
#     "https://zh.wikipedia.org/wiki/会话劫持",
    
#     # 恶意软件
#     "https://zh.wikipedia.org/wiki/勒索软件",
#     "https://zh.wikipedia.org/wiki/特洛伊木马_(电脑)",
#     "https://zh.wikipedia.org/wiki/计算机病毒",
#     "https://zh.wikipedia.org/wiki/计算机蠕虫",
#     "https://zh.wikipedia.org/wiki/间谍软件",
#     "https://zh.wikipedia.org/wiki/Rootkit",
    
#     # 防御技术
#     "https://zh.wikipedia.org/wiki/防火墙",
#     "https://zh.wikipedia.org/wiki/入侵检测系统",
#     "https://zh.wikipedia.org/wiki/入侵预防系统",
#     "https://zh.wikipedia.org/wiki/虚拟专用网",
#     "https://zh.wikipedia.org/wiki/Web应用程序防火墙",
    
#     # 加密技术
#     "https://zh.wikipedia.org/wiki/加密",
#     "https://zh.wikipedia.org/wiki/公开密钥加密",
#     "https://zh.wikipedia.org/wiki/数字签名",
#     "https://zh.wikipedia.org/wiki/傳輸層安全性協定",
#     "https://zh.wikipedia.org/wiki/安全套接层",
    
#     # 安全概念
#     "https://zh.wikipedia.org/wiki/信息安全",
#     "https://zh.wikipedia.org/wiki/网络安全",
#     "https://zh.wikipedia.org/wiki/渗透测试",
#     "https://zh.wikipedia.org/wiki/漏洞扫描器",
#     "https://zh.wikipedia.org/wiki/社会工程学",
#     "https://zh.wikipedia.org/wiki/零日攻击",
# ]
    }
    
    return urls


def process_pdf_file(pdf_path: str, crawler: EnhancedCrawler) -> List[Dict]:
    """
    处理本地PDF文件
    
    Args:
        pdf_path: PDF文件路径
        crawler: 爬虫实例
        
    Returns:
        处理后的chunk列表
    """
    logging.info(f"处理本地PDF: {pdf_path}")
    
    try:
        # 提取文本
        text = extract_text(pdf_path)
        
        if not text or len(text) < 100:
            logging.warning(f"PDF内容过短: {pdf_path}")
            return []
        
        # 获取文件名作为标题
        title = os.path.basename(pdf_path).replace('.pdf', '')
        
        # 清洗文本
        cleaned_text = crawler.text_cleaner.clean_text(text, aggressive=crawler.aggressive_cleaning)
        if not cleaned_text:
            logging.warning(f"清洗后为空: {pdf_path}")
            return []
        
        # 质量评估
        quality_scores = crawler.quality_evaluator.calculate_quality_score(cleaned_text)
        if quality_scores['overall'] < crawler.quality_threshold:
            logging.info(f"质量不达标 (分数: {quality_scores['overall']:.2f}): {pdf_path}")
            return []
        
        # 智能分块
        chunks = crawler.chunker.chunk_text(cleaned_text, deduplicate=True)
        
        if not chunks:
            logging.warning(f"分块后为空: {pdf_path}")
            return []
        
        # 为每个chunk生成元数据
        upload_items = []
        for i, chunk_text in enumerate(chunks):
            # 评估chunk质量
            chunk_quality = crawler.quality_evaluator.calculate_quality_score(chunk_text)
            
            # 过滤低质量chunk
            if chunk_quality['overall'] < crawler.quality_threshold:
                continue
            
            # 生成元数据
            metadata = generate_metadata(chunk_text, pdf_path, title)
            
            # 添加额外信息
            metadata['quality_score'] = round(chunk_quality['overall'], 4)
            metadata['chunk_index'] = i
            metadata['total_chunks'] = len(chunks)
            metadata['source_type'] = 'local_pdf'
            metadata['file_path'] = pdf_path
            
            upload_items.append({
                'file': chunk_text,
                'metadata': metadata
            })
        
        logging.info(f"✓ PDF处理成功: {pdf_path} | 质量: {quality_scores['overall']:.2f} | "
                    f"Chunks: {len(upload_items)}/{len(chunks)}")
        
        return upload_items
        
    except Exception as e:
        logging.error(f"PDF处理失败 {pdf_path}: {e}")
        return []


def process_pdf_directory(pdf_dir: str, crawler: EnhancedCrawler) -> List[Dict]:
    """
    批量处理目录中的所有PDF文件
    
    Args:
        pdf_dir: PDF文件目录
        crawler: 爬虫实例
        
    Returns:
        所有chunk的列表
    """
    all_chunks = []
    
    if not os.path.exists(pdf_dir):
        logging.warning(f"目录不存在: {pdf_dir}")
        return all_chunks
    
    # 获取所有PDF文件
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    
    logging.info(f"找到 {len(pdf_files)} 个PDF文件")
    
    for i, pdf_file in enumerate(pdf_files, 1):
        logging.info(f"\n处理PDF进度: {i}/{len(pdf_files)}")
        pdf_path = os.path.join(pdf_dir, pdf_file)
        chunks = process_pdf_file(pdf_path, crawler)
        all_chunks.extend(chunks)
    
    return all_chunks


def run_enhanced_crawler_demo(test_mode: bool = True):
    """
    运行增强版爬虫演示
    
    Args:
        test_mode: 是否为测试模式（只爬取少量页面）
    """
    logging.info("=" * 80)
    logging.info("增强版网络安全知识库构建系统")
    logging.info("=" * 80)
    
    # 第一步：数据库,使用final作为最终版本
    logging.info("\n【步骤1】设置向量数据库")
    #最终创建的数据库为：student_Group12_final，使用cosine相似度
    db_name = "student_Group12_final"
    metric = "cosine"
    logging.info(f"✓ 数据库设置成功: {db_name} (metric={metric})")
    
    # 第二步：初始化爬虫
    logging.info("\n【步骤2】初始化增强版爬虫")
    crawler = EnhancedCrawler(
        chunk_size=1500,
        chunk_overlap=150,
        min_chunk_size=100,
        quality_threshold=0.4, 
        aggressive_cleaning=False
    )
    
    # 第三步：准备URL列表
    logging.info("\n【步骤3】准备数据源")
    url_groups = get_cybersecurity_urls()
    
    # 测试模式：每个类别只取少量URL
    if test_mode:
        logging.info("⚠️ 测试模式：每个类别只爬取前2个URL")
        test_urls = []
        for category, urls in url_groups.items():
            test_urls.extend(urls[:2])  # 每个类别取2个
            logging.info(f"  - {category}: {min(2, len(urls))} 个URL")
        urls_to_crawl = test_urls
    else:
        # 完整模式：爬取所有URL
        urls_to_crawl = []
        for category, urls in url_groups.items():
            urls_to_crawl.extend(urls)
            logging.info(f"  - {category}: {len(urls)} 个URL")
    
    logging.info(f"\n总计准备爬取: {len(urls_to_crawl)} 个URL")
    
    # 第四步：爬取网页
    logging.info("\n【步骤4】开始爬取网页")
    all_chunks = crawler.process_urls(urls_to_crawl, delay=1.0)
    
    # 第五步：处理本地PDF（如果有）
    logging.info("\n【步骤5】处理本地PDF文件")
    pdf_dir = os.path.join(os.path.dirname(__file__), "pdf_documents")
    
    if os.path.exists(pdf_dir):
        pdf_chunks = process_pdf_directory(pdf_dir, crawler)
        all_chunks.extend(pdf_chunks)
        logging.info(f"✓ PDF处理完成，新增 {len(pdf_chunks)} 个chunk")
    else:
        logging.info(f"ℹ️ PDF目录不存在: {pdf_dir}")
        logging.info(f"   如需处理PDF，请创建该目录并放入PDF文件")
    
    # 第六步：打印统计
    crawler.print_stats()
    
    # 第七步：上传到数据库
    if all_chunks:
        logging.info("\n【步骤6】上传到向量数据库")
        file_ids = upload_chunks(db_name, all_chunks)
        logging.info(f"✓ 上传完成，共 {len(file_ids)} 个文本块")
    else:
        logging.warning("没有可上传的内容！")
        return None, []
    
    # 第八步：测试搜索
    logging.info("\n【步骤7】测试搜索功能")
    test_queries = [
        "SQL注入攻击原理和防御方法",
        "跨站脚本XSS攻击",
        "phishing attack indicators",
        "如何进行渗透测试",
    ]
    
    for query in test_queries[:2]:  # 只测试前2个
        logging.info(f"\n测试查询: {query}")
        payload = {
            "token": TOKEN,
            "query": query,
            "top_k": 3,
            "metric_type": metric,
            "score_threshold": 0.0
        }
        
        try:
            resp = requests.post(f"{BASE_URL}/databases/{db_name}/search", json=payload)
            if resp.status_code == 200:
                results = resp.json().get("files", [])
                logging.info(f"  返回 {len(results)} 个结果")
                for i, r in enumerate(results[:2], 1):
                    score = r.get("score", 0)
                    quality = r.get("metadata", {}).get("quality_score", "N/A")
                    source_type = r.get("metadata", {}).get("source_type", "N/A")
                    preview = r.get("text", "")[:80]
                    logging.info(f"  [{i}] 相似度: {score:.4f} | 质量: {quality} | 类型: {source_type}")
                    logging.info(f"      预览: {preview}...")
            else:
                logging.error(f"  搜索失败: {resp.status_code}")
        except Exception as e:
            logging.error(f"  搜索失败: {e}")
    
    logging.info("\n" + "=" * 80)
    logging.info("🎉 增强版爬虫执行完成！")
    logging.info(f"📊 数据库名称: {db_name}")
    logging.info(f"📊 最终chunk数: {len(file_ids)}")
    logging.info("=" * 80)
    
    return db_name, file_ids


if __name__ == "__main__":
    try:
        # 运行演示（测试模式）
        db_name, file_ids = run_enhanced_crawler_demo(test_mode=False)
        
        if db_name:
            print("\n" + "=" * 80)
            print("✅ 系统执行成功！")
            print(f"数据库名称: {db_name}")
            print(f"上传文件数: {len(file_ids)}")
            print("\n💡 使用建议:")
            print(f"1. 在应用中使用数据库名: '{db_name}'")
            print("=" * 80)
        else:
            print("\n❌ 系统执行失败，请检查日志")
            
    except KeyboardInterrupt:
        logging.warning("\n⚠️ 用户中断执行")
    except Exception as e:
        logging.error(f"\n❌ 系统执行失败: {e}", exc_info=True)
        raise

