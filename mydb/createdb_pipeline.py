#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cybersec_rag_pipeline.py - 网络安全知识库构建Pipeline

功能：
- 程序化抓取网页/PDF（示例支持 MITRE ATT&CK、任意网页、直接 PDF 链接）
- 提取与清洗正文
- 分段（chunk）与重叠
- 自动生成元数据（source, url, title, date, tags (CVE/CWE/T\d+)）
- 批量上传到后端数据库（使用你的 test_api_20251015.py 风格接口）
"""

# ==================== 标准库导入 ====================
import re                # 正则表达式库，用于文本模式匹配（如提取CVE编号、日期等）
import os                # 操作系统接口，用于文件路径操作
import time              # 时间相关函数，用于延迟和时间戳生成
import json              # JSON数据处理
import hashlib           # 哈希算法库，用于生成文件唯一标识
import logging           # 日志记录库，用于输出程序运行信息
from typing import List, Dict, Tuple, Optional  # 类型注解，增强代码可读性
from urllib.parse import urlparse, urljoin      # URL解析工具，用于处理相对/绝对路径

# ==================== 第三方库导入 ====================
import requests          # HTTP请求库，用于发送网络请求下载网页和文件
from bs4 import BeautifulSoup  # HTML/XML解析库，用于从网页中提取文本内容

# PDF文本提取器（pdfminer.six库）- 用于从PDF文件中提取纯文本
from pdfminer.high_level import extract_text

# ==================== 配置区（修改为你的环境） ====================
BASE_URL = "http://10.1.0.220:9002/api"   # 后端API地址，与test_api_20251015.py保持一致
TOKEN = "e-1qa4tLR9N_AnEEBemwaiOBoyoRoFHr00W0Wb3Uk5tWE5ziWJiCHh7sM1b73T2s"  # 你的认证Token
# 向量相似度计算方式：L2(欧氏距离) 或 cosine(余弦相似度) 或 IP(内积)
METRIC_TYPE = "cosine"

# 批量上传时每批次的文件数量，避免单次请求过大
UPLOAD_BATCH = 10

# PDF文件临时下载目录（Windows系统使用临时目录）
PDF_TMP_DIR = os.path.join(os.getenv("TEMP", "."), "pdf_cache")
os.makedirs(PDF_TMP_DIR, exist_ok=True)  # 如果目录不存在则创建

# 日志配置：设置日志级别为INFO，格式包含时间、级别和消息
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# ==================== 工具函数 ====================

def safe_request_get(url, **kwargs):
    """
    安全的HTTP GET请求封装函数
    
    参数:
        url: 要请求的网址
        **kwargs: 其他requests.get()支持的参数
    
    返回:
        requests.Response对象，失败返回None
    
    功能说明:
        1. 自动添加User-Agent头，模拟浏览器访问（避免被反爬虫拦截）
        2. 设置20秒超时时间（避免长时间等待）
        3. 自动检查HTTP状态码，4xx/5xx会抛出异常
        4. 捕获所有异常并记录日志
    """
    # 从kwargs中取出headers参数，如果不存在则创建空字典
    headers = kwargs.pop("headers", {})
    # 如果headers中没有User-Agent，则设置默认值（模拟浏览器访问）
    headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; CyberSecRAG/1.0)")
    
    try:
        # 发送GET请求：headers指定请求头，timeout设置超时时间，**kwargs传递其他参数
        r = requests.get(url, headers=headers, timeout=20, **kwargs)
        # 检查响应状态码，如果是4xx或5xx会抛出HTTPError异常
        r.raise_for_status()
        return r
    except Exception as e:
        # 捕获所有异常（网络错误、超时、HTTP错误等），记录警告日志
        logging.warning(f"GET {url} 失败: {e}")
        return None

def download_pdf_to_text(url: str, local_tmp: str = None) -> str:
    """
    下载PDF文件并提取其中的文本内容
    
    参数:
        url: PDF文件的URL地址
        local_tmp: 临时文件存储目录，None时使用全局配置的PDF_TMP_DIR
    
    返回:
        提取的文本内容（字符串），失败返回空字符串
    
    工作流程:
        1. 下载PDF文件到本地临时目录
        2. 使用pdfminer.six库提取文本
        3. 返回提取的文本内容
    """
    if local_tmp is None:
        local_tmp = PDF_TMP_DIR  # 使用配置的临时目录
    
    logging.info(f"下载并提取 PDF: {url}")
    
    # stream=True: 流式下载，适合大文件，不会一次性加载到内存
    r = safe_request_get(url, stream=True)
    if not r:
        return ""
    
    # 解析URL，提取信息（这里主要用于日志记录）
    parsed = urlparse(url)
    
    # 使用SHA1哈希生成唯一文件名，避免文件名冲突
    # encode()将字符串转为字节，hexdigest()得到16进制哈希值
    fn = os.path.join(local_tmp, hashlib.sha1(url.encode()).hexdigest() + ".pdf")
    
    # 以二进制写入模式打开文件
    with open(fn, "wb") as f:
        # iter_content(): 迭代响应内容，每次读取16KB (1024*16字节)
        for chunk in r.iter_content(1024*16):
            if chunk:  # 过滤掉保持连接的空chunk
                f.write(chunk)
    
    try:
        # 使用pdfminer.six库提取PDF中的文本
        text = extract_text(fn)
        
        # 提取成功后删除临时文件，节省磁盘空间
        try:
            os.remove(fn)
        except:
            pass  # 删除失败不影响主流程
            
        return text
    except Exception as e:
        # PDF可能损坏、加密或格式不支持
        logging.warning(f"pdfminer 抽取失败: {e}")
        return ""

def html_to_text(html: str) -> Tuple[str, str]:
    """
    从HTML网页中提取标题和正文内容，自动过滤导航栏、广告等噪声
    
    参数:
        html: HTML源代码字符串
    
    返回:
        (title, text): 标题和正文的元组
    
    清洗策略:
        1. 提取网页标题
        2. 移除脚本、样式、导航、页脚等非正文元素
        3. 移除广告、面包屑等噪声内容
        4. 智能定位主要内容区域（<main>、<article>或文本最多的<div>）
        5. 清理多余空白字符
    """
    # BeautifulSoup解析HTML，html.parser是Python内置的解析器
    soup = BeautifulSoup(html, "html.parser")
    
    # 提取网页标题（<title>标签内容）
    title = (soup.title.string.strip() if soup.title and soup.title.string else "") or ""
    
    # 移除无用标签：脚本、样式、导航栏、页眉、页脚、侧边栏、表单
    # soup()等同于soup.find_all()，返回所有匹配的标签
    for s in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        s.decompose()  # decompose()从DOM树中完全删除该元素
    
    # 通过CSS选择器移除常见的噪声元素
    # . 表示class选择器，# 表示id选择器
    noise_selectors = ['.breadcrumb', '.nav', '.footer', '#footer', '.sidebar', 
                       '.ad', '.advert', '.cookie', '.menu', '.banner']
    for sel in noise_selectors:
        # select()使用CSS选择器查找元素
        for node in soup.select(sel):
            node.decompose()
    
    # 智能定位主要内容区域
    # 优先查找语义化标签 <main> 或 <article>
    main = soup.find("main") or soup.find("article")
    
    if not main:
        # 如果没有语义化标签，找文本内容最多的<div>或<section>
        candidates = soup.find_all(["div", "section"], recursive=True)
        if candidates:
            # max()找出文本长度最大的元素
            # key参数指定比较函数：获取元素的文本并计算长度
            main = max(candidates, key=lambda d: len(d.get_text(separator=" ", strip=True)) if d else 0)
        else:
            main = soup.body  # 降级方案：使用整个body
    
    # 提取文本：separator="\n"在标签间插入换行，strip=True去除首尾空白
    text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)
    
    # 正则表达式清理文本格式
    # \n{2,} 匹配2个或多个连续换行符，替换为2个换行（统一段落间距）
    text = re.sub(r'\n{2,}', '\n\n', text)
    # [ \t]{2,} 匹配2个或多个连续空格/制表符，替换为1个空格
    text = re.sub(r'[ \t]{2,}', ' ', text)
    
    return title, text

# ==================== 文本分割逻辑 ====================

def split_text_into_chunks(text: str,
                           chunk_size_chars: int = 2000,
                           chunk_overlap_chars: int = 200,
                           separators: List[str] = None) -> List[str]:
    """
    智能文本分割函数：将长文本分割成多个chunk，用于向量化存储
    
    参数:
        text: 待分割的原始文本
        chunk_size_chars: 每个chunk的目标字符数（建议800-4000，取决于embedding模型）
        chunk_overlap_chars: 相邻chunk之间的重叠字符数（保持上下文连贯性）
        separators: 分割符优先级列表（从左到右优先级降低）
    
    返回:
        分割后的文本块列表
    
    分割策略:
        1. 优先按段落（双换行）分割
        2. 合并小段落到目标大小
        3. 超长段落按固定大小切分
        4. 添加chunk间重叠，避免信息在边界丢失
    
    为什么需要chunk_overlap？
        - 如果某个概念正好跨越两个chunk的边界，没有重叠会导致检索时信息不完整
        - 重叠部分充当"缓冲区"，确保重要信息不会被切断
    """
    if separators is None:
        # 默认分隔符优先级：段落 > 行 > 中文句号 > 英文句号 > 问号 > 感叹号
        separators = ["\n\n", "\n", "。", ".", "?", "!"]
    
    # 第一步：按双换行（段落）分割文本
    # re.split()正则分割，\n{2,}匹配2个或更多换行符
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    
    chunks = []  # 最终的chunk列表
    cur = ""     # 当前正在构建的chunk
    
    # 第二步：将段落合并到接近chunk_size的大小
    for p in paragraphs:
        # 如果加入当前段落后不超过目标大小，则合并
        if len(cur) + len(p) + 1 <= chunk_size_chars:
            cur = (cur + "\n\n" + p).strip() if cur else p
        else:
            # 否则保存当前chunk，开始新chunk
            if cur:
                chunks.append(cur)
            
            # 处理超长段落：如果单个段落超过chunk_size，需要进一步切分
            if len(p) > chunk_size_chars:
                # 简单策略：按固定宽度滑动切分
                # range(start, stop, step): 从0开始，每次步进chunk_size_chars
                for i in range(0, len(p), chunk_size_chars):
                    chunks.append(p[i:i+chunk_size_chars])
                cur = ""
            else:
                cur = p  # 开始新chunk
    
    # 添加最后一个chunk
    if cur:
        chunks.append(cur)
    
    # 第三步：添加chunk间重叠（提升检索效果）
    if chunk_overlap_chars > 0:
        overlapped = []
        for i, c in enumerate(chunks):
            if i == 0:
                # 第一个chunk保持原样
                overlapped.append(c)
            else:
                # 从前一个chunk末尾取overlap_chars长度的文本
                prev = overlapped[-1]
                overlap = prev[-chunk_overlap_chars:] if len(prev) > chunk_overlap_chars else prev
                # 将重叠部分拼接到当前chunk前面
                merged = overlap + "\n\n" + c
                overlapped.append(merged)
        chunks = overlapped
    
    return chunks

# ==================== 元数据自动抽取 ====================

# 编译正则表达式模式（编译后可重复使用，提高效率）
# \b 表示单词边界，确保精确匹配
CVE_RE = re.compile(r'\bCVE-\d{4}-\d{4,7}\b', re.IGNORECASE)  # CVE编号：CVE-2021-12345
MITRE_ATTACK_RE = re.compile(r'\bT\d{4}\b')                   # MITRE ATT&CK技术ID：T1566
CWE_RE = re.compile(r'\bCWE-\d{1,5}\b', re.IGNORECASE)        # CWE编号：CWE-79
DATE_RE = re.compile(r'\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|20\d{2})\b')  # 日期：2021-01-15 或 2021

def generate_metadata(text: str, source_url: str, title: str = "") -> Dict:
    """
    从文本中自动提取元数据标签，用于后续的过滤检索
    
    参数:
        text: 文本内容
        source_url: 来源URL
        title: 标题（可选）
    
    返回:
        包含元数据的字典
    
    提取内容:
        - CVE编号: 漏洞标识符
        - MITRE ATT&CK技术ID: 攻击技术分类
        - CWE编号: 通用弱点枚举
        - 日期: 发布或更新时间
        - 分类标签: 根据关键词启发式判断（SQL注入、钓鱼、勒索软件等）
    """
    metadata = {}
    metadata['source_url'] = source_url
    # 如果没有标题，取文本前120字符作为标题（去除换行）
    metadata['title'] = title or (text[:120].replace("\n", " ") if text else "")
    
    # 提取CVE编号（常见漏洞与暴露）
    # finditer()返回所有匹配的迭代器，group(0)获取完整匹配
    cves = list(set([m.group(0).upper() for m in CVE_RE.finditer(text)]))
    if cves:
        metadata['cves'] = cves
    
    # 提取MITRE ATT&CK技术ID
    t_ids = list(set([m.group(0).upper() for m in MITRE_ATTACK_RE.finditer(text)]))
    if t_ids:
        metadata['mitre_techniques'] = t_ids
    
    # 提取CWE编号
    cwes = list(set([m.group(0).upper() for m in CWE_RE.finditer(text)]))
    if cwes:
        metadata['cwes'] = cwes
    
    # 提取日期/年份
    years = list(set([m.group(0) for m in DATE_RE.finditer(text)]))
    if years:
        metadata['dates'] = years
    
    # 基于关键词的启发式分类
    # re.search()在整个字符串中搜索匹配，re.I表示忽略大小写
    cats = []
    
    if re.search(r'\bsql injection|sql注入|sqlmap|sql盲注|union注入\b', text, re.I):
        cats.append('sql_injection')
    
    if re.search(r'\bxss|cross.?site.?script|跨站脚本\b', text, re.I):
        cats.append('xss')
    
    if re.search(r'\bphish(ing)?|钓鱼|网络钓鱼\b', text, re.I):
        cats.append('phishing')
    
    if re.search(r'\bransomware|勒索软件|勒索病毒\b', text, re.I):
        cats.append('ransomware')
    
    if re.search(r'\brce|remote code execution|远程代码执行\b', text, re.I):
        cats.append('rce')
    
    if re.search(r'\bddos|denial.?of.?service|拒绝服务\b', text, re.I):
        cats.append('ddos')
    
    if re.search(r'\bpenetration.?test|渗透测试|pentest\b', text, re.I):
        cats.append('penetration_testing')
    
    if re.search(r'\bmalware|恶意软件|木马|trojan\b', text, re.I):
        cats.append('malware')
    
    # 如果文本中包含CVE编号，标记为漏洞类
    if cves:
        cats.append('vulnerability')
    
    # 如果包含MITRE技术ID，标记为攻击技术类
    if t_ids:
        cats.append('attack_technique')
    
    # 去重并保存
    metadata['categories'] = list(set(cats))
    
    return metadata

# ==================== 后端数据库API交互 ====================

def create_database(metric_type: str = METRIC_TYPE) -> Tuple[str, str]:
    """
    调用后端API创建新的向量数据库
    
    参数:
        metric_type: 向量相似度度量方式 (L2/cosine/IP)
    
    返回:
        (数据库名称, 度量类型) 元组
    
    API说明:
        - 端点: POST /api/databases
        - 参数: database_name(数据库名), token(认证令牌), metric_type(度量方式)
        - 数据库命名规则: student_{组名}_{时间戳}
    """
    db_name = f"student_Group12_final"
    logging.info(f"创建数据库: {db_name}")
    
    # 发送POST请求，json参数自动将字典序列化为JSON并设置Content-Type
    resp = requests.post(
        f"{BASE_URL}/databases", 
        json={
            "database_name": db_name, 
            "token": TOKEN, 
            "metric_type": metric_type
        }
    )
    
    # 检查HTTP状态码，非2xx会抛出异常
    resp.raise_for_status()
    logging.info("创建数据库响应: %s", resp.json())
    
    return db_name, metric_type

def upload_chunks(db_name: str, chunks: List[Dict]) -> List[int]:
    """
    批量上传文本chunk到指定数据库
    
    参数:
        db_name: 目标数据库名称
        chunks: chunk列表，每个元素是字典 {'file': 文本内容, 'metadata': 元数据字典}
    
    返回:
        上传成功的file_id列表
    
    分批上传原因:
        - 避免单次请求体积过大导致超时
        - 提高上传稳定性，部分失败不影响整体
        - 后端可能有单次请求大小限制
    """
    file_ids = []
    
    # 分批上传：range(起始, 终止, 步长)
    # 例如：chunks有25个，UPLOAD_BATCH=10，则分3批：0-9, 10-19, 20-24
    for i in range(0, len(chunks), UPLOAD_BATCH):
        # 切片获取当前批次：i到i+UPLOAD_BATCH
        batch = chunks[i:i+UPLOAD_BATCH]
        
        # 构造请求体
        payload = {
            "files": batch,  # 文件列表
            "token": TOKEN   # 认证令牌
        }
        
        # POST请求上传文件
        # API端点: POST /api/databases/{db_name}/files
        resp = requests.post(f"{BASE_URL}/databases/{db_name}/files", json=payload)
        
        # 检查响应状态
        if resp.status_code != 200:
            logging.error("上传批次失败: %s %s", resp.status_code, resp.text)
            raise RuntimeError("上传失败")
        
        # 解析响应JSON
        j = resp.json()
        logging.info("上传批次 %d-%d 完成: %s", i, min(i+UPLOAD_BATCH, len(chunks))-1, j)
        
        # 收集返回的file_id
        # extend()将列表中的所有元素添加到file_ids
        file_ids.extend(j.get("file_ids", []))
        
        # 短暂延迟，给后端时间处理和持久化数据
        # 避免请求过快导致数据库未及时flush
        time.sleep(0.5)
    
    return file_ids

# ==================== 网站爬取函数（支持多个数据源） ====================

def crawl_mitre_attack(base_index_url="https://attack.mitre.org/techniques/enterprise/", max_pages=50):
    """
    爬取MITRE ATT&CK攻击技术知识库
    
    数据源介绍:
        MITRE ATT&CK是全球权威的网络攻击行为知识库，包含各种攻击技术、
        战术和程序的详细描述，被安全行业广泛采用作为威胁建模标准。
    
    参数:
        base_index_url: MITRE ATT&CK技术列表页URL
        max_pages: 最大爬取页面数（避免过度请求）
    
    返回:
        页面信息列表，每个元素包含 url, title, text, meta
    
    爬取策略:
        1. 先访问索引页，提取所有技术页面的链接
        2. 逐个访问技术页面，提取正文
        3. 自动去重，过滤低质量内容
        4. 遵守爬虫礼仪，每次请求间隔0.6秒
    
    注意事项:
        - 请遵守网站的robots.txt规则
        - 不要设置过高的max_pages，避免给服务器造成压力
        - MITRE页面结构可能变化，需要定期检查CSS选择器
    """
    results = []
    logging.info(f"开始爬取 MITRE ATT&CK: {base_index_url}")
    
    # 第一步：获取索引页
    idx_r = safe_request_get(base_index_url)
    if not idx_r:
        logging.warning("无法访问MITRE ATT&CK索引页")
        return results
    
    # 解析HTML
    soup = BeautifulSoup(idx_r.text, "html.parser")
    
    # 提取所有技术页面链接
    # CSS选择器: a[href^='/techniques/'] 匹配href以/techniques/开头的<a>标签
    for a in soup.select("a[href^='/techniques/']"):
        href = a.get('href')
        if not href or '/techniques/' not in href:
            continue
        
        # urljoin()将相对URL转换为绝对URL
        # 例如: /techniques/T1566 -> https://attack.mitre.org/techniques/T1566
        full = urljoin(base_index_url, href)
        
        # 去重：检查URL是否已存在
        if full in [r['url'] for r in results]:
            continue
        
        results.append({"url": full, "title": a.get_text(strip=True)})
    
    logging.info(f"从索引页提取到 {len(results)} 个技术页面链接")
    
    # 第二步：逐个访问技术页面，提取正文
    pages = []
    for item in results[:max_pages]:  # 限制爬取数量
        logging.info(f"正在爬取: {item['url']}")
        r = safe_request_get(item['url'])
        if not r:
            continue
        
        # 提取标题和正文
        title, text = html_to_text(r.text)
        
        # 过滤低质量内容：正文太短的页面可能是错误页或空页
        if len(text) < 200:
            logging.info("页面正文太短，跳过 %s", item['url'])
            continue
        
        # 生成元数据（自动提取CVE、技术ID等）
        meta = generate_metadata(text, item['url'], title)
        pages.append({"url": item['url'], "title": title, "text": text, "meta": meta})
        
        # 礼貌延迟：避免请求过快被服务器封禁
        time.sleep(0.6)
    
    logging.info(f"成功爬取 {len(pages)} 个MITRE ATT&CK页面")
    return pages

def crawl_generic_urls(urls: List[str]) -> List[Dict]:
    """
    通用URL爬取函数，支持网页和PDF文件
    
    参数:
        urls: URL列表，可以是HTML网页或PDF文件链接
    
    返回:
        爬取结果列表，每个元素包含 url, title, text, meta
    
    功能特点:
        - 自动识别PDF链接（通过.pdf后缀）
        - PDF使用pdfminer提取，网页使用BeautifulSoup解析
        - 自动过滤空内容和低质量页面
        - 为每个页面自动生成元数据标签
    
    使用场景:
        - 爬取安全厂商的漏洞公告页面
        - 下载安全报告PDF
        - 批量爬取技术博客文章
    """
    collected = []
    
    for u in urls:
        logging.info("正在处理: %s", u)
        
        # 判断是否为PDF文件（通过URL后缀）
        if u.lower().endswith(".pdf"):
            # PDF处理分支
            txt = download_pdf_to_text(u)
            if not txt:
                logging.warning(f"PDF提取失败或内容为空: {u}")
                continue
            
            # PDF通常没有HTML标题，提取文件名作为标题
            pdf_title = u.split('/')[-1].replace('.pdf', '')
            meta = generate_metadata(txt, u, title=pdf_title)
            collected.append({"url": u, "title": pdf_title, "text": txt, "meta": meta})
        else:
            # HTML网页处理分支
            r = safe_request_get(u)
            if not r:
                continue
            
            # 提取标题和正文
            title, text = html_to_text(r.text)
            
            # 过滤低质量内容
            if not text or len(text) < 50:
                logging.info("正文太短或为空，跳过: %s", u)
                continue
            
            # 生成元数据
            meta = generate_metadata(text, u, title)
            collected.append({"url": u, "title": title, "text": text, "meta": meta})
        
        # 延迟，避免请求过快
        time.sleep(0.4)
    
    logging.info(f"成功处理 {len(collected)}/{len(urls)} 个URL")
    return collected


def crawl_cwe_top25() -> List[Dict]:
    """
    爬取CWE Top 25最危险的软件弱点列表
    
    数据源介绍:
        CWE (Common Weakness Enumeration) 是由MITRE维护的软件安全弱点分类系统，
        Top 25列表展示了最常见和最危险的软件安全弱点。
    
    返回:
        弱点描述页面列表
    """
    base_url = "https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html"
    logging.info(f"开始爬取 CWE Top 25: {base_url}")
    
    pages = []
    r = safe_request_get(base_url)
    if not r:
        logging.warning("无法访问CWE Top 25页面")
        return pages
    
    # 提取主页内容
    title, text = html_to_text(r.text)
    if text and len(text) > 200:
        meta = generate_metadata(text, base_url, title)
        pages.append({"url": base_url, "title": title, "text": text, "meta": meta})
    
    logging.info(f"成功爬取CWE Top 25主页")
    return pages


def crawl_owasp_top10() -> List[Dict]:
    """
    爬取OWASP Top 10 Web应用安全风险
    
    数据源介绍:
        OWASP (Open Web Application Security Project) Top 10是Web应用安全领域
        最权威的风险列表，涵盖了最关键的Web安全威胁。
    
    返回:
        风险描述页面列表
    """
    # OWASP Top 10 2021版本
    urls = [
        "https://owasp.org/Top10/",
        "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
        "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/",
        "https://owasp.org/Top10/A03_2021-Injection/",
        "https://owasp.org/Top10/A04_2021-Insecure_Design/",
        "https://owasp.org/Top10/A05_2021-Security_Misconfiguration/",
        "https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/",
        "https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/",
        "https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/",
        "https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/",
        "https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/",
    ]
    
    logging.info("开始爬取 OWASP Top 10")
    return crawl_generic_urls(urls)

# ==================== 主流程Pipeline ====================

def pipeline_demo():
    """
    完整的知识库构建Pipeline演示
    
    执行流程:
        1. 创建向量数据库
        2. 从多个数据源爬取内容
        3. 文本分割和元数据提取
        4. 批量上传到数据库
        5. 测试搜索功能
    
    包含的数据源:
        - MITRE ATT&CK 攻击技术库
        - OWASP Top 10 Web安全风险
        - CWE Top 25 软件弱点
        - 自定义URL列表（厂商公告、PDF报告等）
    """
    logging.info("=" * 60)
    logging.info("开始网络安全知识库构建Pipeline")
    logging.info("=" * 60)
    
    # ========== 第一步：创建数据库 ==========
    logging.info("\n【步骤1】创建向量数据库")
    db_name, metric = create_database(metric_type=METRIC_TYPE)
    logging.info(f"✓ 数据库创建成功: {db_name} (metric={metric})")

    # ========== 第二步：爬取数据源 ==========
    logging.info("\n【步骤2】开始爬取数据源")
    
    # 2.1 爬取 MITRE ATT&CK （限制50页，避免过度请求）
    logging.info("\n>>> 数据源1: MITRE ATT&CK 攻击技术库")
    mitre_pages = crawl_mitre_attack(max_pages=30)
    logging.info(f"✓ 抓取到 {len(mitre_pages)} 个MITRE页面")

    # 2.2 爬取 OWASP Top 10
    logging.info("\n>>> 数据源2: OWASP Top 10 Web安全风险")
    owasp_pages = crawl_owasp_top10()
    logging.info(f"✓ 抓取到 {len(owasp_pages)} 个OWASP页面")
    
    # 2.3 爬取 CWE Top 25
    logging.info("\n>>> 数据源3: CWE Top 25 软件弱点")
    cwe_pages = crawl_cwe_top25()
    logging.info(f"✓ 抓取到 {len(cwe_pages)} 个CWE页面")

    # 2.4 自定义URL列表（你可以添加更多数据源）
    logging.info("\n>>> 数据源4: 自定义URL列表")
    extra_urls = [
        # ===== 推荐的中文安全资讯站点 =====
        # 注意：以下URL仅为示例，实际爬取时请检查网站的robots.txt并遵守爬虫规则
        
        # FreeBuf 技术文章示例（替换为具体文章URL）
        # "https://www.freebuf.com/articles/web/123456.html",
        
        # 安全客技术文章示例
        # "https://www.anquanke.com/post/id/123456",
        
        # ===== 厂商安全公告示例 =====
        # Microsoft 安全公告
        # "https://msrc.microsoft.com/update-guide/vulnerability/CVE-2021-XXXXX",
        
        # ===== PDF报告示例 =====
        # NIST 网络安全框架（如果可以直接访问PDF）
        # "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.04162018.pdf",
        
        # ===== 实际可用的公开资源 =====
        # NIST 计算机安全资源中心（主页，可以提取概念性内容）
        "https://csrc.nist.gov/",
        
        # US-CERT 网络安全提示
        "https://www.cisa.gov/news-events/cybersecurity-advisories",
    ]
    extra_pages = crawl_generic_urls(extra_urls)
    logging.info(f"✓ 抓取到 {len(extra_pages)} 个自定义页面")

    # 合并所有页面
    all_pages = mitre_pages + owasp_pages + cwe_pages + extra_pages
    logging.info(f"\n✓ 总计爬取 {len(all_pages)} 个页面")

    # ========== 第三步：文本分割与元数据生成 ==========
    logging.info("\n【步骤3】文本分割与元数据生成")
    upload_items = []
    
    # 遍历每个爬取的页面
    for p in all_pages:
        text = p["text"]
        title = p["title"]
        url = p["url"]
        meta_base = p.get("meta", {})
        
        # 将长文本分割成多个chunk
        # chunk_size_chars=1800: 每个chunk约1800字符（考虑到embedding模型的token限制）
        # chunk_overlap_chars=200: 相邻chunk重叠200字符，保持上下文连贯性
        chunks = split_text_into_chunks(text, chunk_size_chars=1800, chunk_overlap_chars=200)
        
        # 为每个chunk添加元数据
        for i, ch in enumerate(chunks):
            # 复制基础元数据（包含CVE、技术ID、分类等）
            meta = dict(meta_base)  # shallow copy避免修改原始数据
            
            # 添加chunk特有的元数据
            meta.update({
                "source_url": url,          # 来源URL
                "source_title": title,      # 来源标题
                "chunk_index": i,           # 当前chunk在原文中的位置
                "chunk_length": len(ch),    # chunk的字符数
                "total_chunks": len(chunks) # 该文档总chunk数
            })
            
            # 构造上传格式：{'file': 文本内容, 'metadata': 元数据}
            upload_items.append({"file": ch, "metadata": meta})
    
    logging.info(f"✓ 生成 {len(upload_items)} 个文本chunk（平均每页 {len(upload_items)/len(all_pages):.1f} 个chunk）")

    # ========== 第四步：批量上传到数据库 ==========
    logging.info("\n【步骤4】批量上传到向量数据库")
    file_ids = upload_chunks(db_name, upload_items)
    logging.info(f"✓ 上传完成，共 {len(file_ids)} 个文本块")

    # ========== 第五步：测试搜索功能 ==========
    logging.info("\n【步骤5】测试搜索功能")
    
    # 测试查询1：钓鱼邮件特征
    test_queries = [
        "phishing mail indicators",           # 钓鱼邮件指标
        "SQL注入攻击原理",                      # SQL注入
        "如何防御跨站脚本攻击",                 # XSS防御
        "远程代码执行漏洞",                     # RCE漏洞
    ]
    
    for query in test_queries[:2]:  # 只测试前2个查询
        logging.info(f"\n测试查询: '{query}'")
        payload = {
            "token": TOKEN, 
            "query": query, 
            "top_k": 3,              # 返回前3个最相关结果
            "metric_type": metric
        }
        
        try:
            resp = requests.post(f"{BASE_URL}/databases/{db_name}/search", json=payload)
            resp.raise_for_status()
            results = resp.json()
            
            # 显示搜索结果
            if "results" in results and results["results"]:
                for idx, item in enumerate(results["results"][:3], 1):
                    logging.info(f"  [{idx}] 相似度: {item.get('distance', 'N/A'):.4f}")
                    logging.info(f"      标题: {item.get('metadata', {}).get('source_title', 'N/A')[:50]}")
                    logging.info(f"      分类: {item.get('metadata', {}).get('categories', [])}")
            else:
                logging.info("  未找到相关结果")
        except Exception as e:
            logging.error(f"  搜索失败: {e}")
    
    logging.info("\n" + "=" * 60)
    logging.info("Pipeline执行完成！")
    logging.info(f"数据库名称: {db_name}")
    logging.info(f"总文档数: {len(all_pages)}")
    logging.info(f"总chunk数: {len(file_ids)}")
    logging.info("=" * 60)

    return db_name, file_ids

# ==================== 程序入口 ====================

if __name__ == "__main__":
    """
    程序主入口
    
    运行方式:
        python createdb_pipeline.py
    
    运行前准备:
        1. 确保已安装依赖: pip install requests beautifulsoup4 pdfminer.six
        2. 检查网络连接，确保可以访问目标网站
        3. 修改配置区的 TOKEN、USER_NAME、BASE_URL
        4. 根据需求调整爬取数量和数据源
    
    预期结果:
        - 创建一个新的向量数据库
        - 爬取并上传网络安全知识
        - 输出数据库名称和统计信息
    """
    try:
        logging.info("\n")
        logging.info("*" * 60)
        logging.info("     网络安全知识库构建 Pipeline")
        logging.info("*" * 60)
        logging.info(f"配置: BASE_URL={BASE_URL}")
        logging.info(f"配置: USER_NAME={USER_NAME}")
        logging.info(f"配置: METRIC_TYPE={METRIC_TYPE}")
        logging.info("*" * 60)
        
        # 执行主流程
        db, fids = pipeline_demo()
        
        # 输出最终结果
        logging.info("\n")
        logging.info("🎉 Pipeline执行成功！")
        logging.info(f"📊 数据库名称: {db}")
        logging.info(f"📊 上传文件数: {len(fids)}")
        logging.info(f"💡 后续可以使用此数据库进行RAG检索增强生成")
        logging.info(f"💡 在你的应用中使用数据库名: {db}")
        
    except KeyboardInterrupt:
        logging.warning("\n⚠️  用户中断执行")
    except Exception as e:
        logging.error(f"\n❌ Pipeline执行失败: {e}", exc_info=True)
        raise
