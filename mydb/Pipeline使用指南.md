# 网络安全知识库构建 Pipeline 使用指南

本指南详细说明如何使用 `createdb_pipeline.py` 构建网络安全攻防知识库。

---

## 📋 目录
1. [环境准备](#环境准备)
2. [快速开始](#快速开始)
3. [配置说明](#配置说明)
4. [核心功能介绍](#核心功能介绍)
5. [常见问题](#常见问题)
6. [进阶使用](#进阶使用)

---

## 🔧 环境准备

### 1. Python环境要求
- Python 3.7 或更高版本
- 推荐使用 Python 3.8+

### 2. 安装依赖库

```bash
# 方式1: 使用 requirements.txt (如果有)
pip install -r requirements.txt

# 方式2: 手动安装核心依赖
pip install requests beautifulsoup4 pdfminer.six
```

**依赖库说明**:
- `requests`: HTTP请求库，用于下载网页和文件
- `beautifulsoup4`: HTML解析库，用于提取网页内容
- `pdfminer.six`: PDF文本提取库，用于处理PDF文档

### 3. 网络连接
- 确保可以访问互联网
- 如果在公司网络，可能需要配置代理

### 4. API配置
- 获取后端API的访问Token
- 确认后端服务器地址（BASE_URL）

---

## 🚀 快速开始

### 第一步：配置参数

打开 `createdb_pipeline.py`，修改配置区：

```python
# ==================== 配置区 ====================
BASE_URL = "http://10.1.0.220:9002/api"   # 修改为你的后端地址
TOKEN = "你的Token"                        # 替换为你的认证Token
USER_NAME = "Group12"                     # 替换为你的组名
METRIC_TYPE = "L2"                        # 向量相似度计算方式
```

### 第二步：运行程序

```bash
python createdb_pipeline.py
```

### 第三步：查看结果

程序会输出如下信息：
```
============================================================
开始网络安全知识库构建Pipeline
============================================================

【步骤1】创建向量数据库
✓ 数据库创建成功: student_Group12_1730123456 (metric=L2)

【步骤2】开始爬取数据源
>>> 数据源1: MITRE ATT&CK 攻击技术库
✓ 抓取到 30 个MITRE页面

>>> 数据源2: OWASP Top 10 Web安全风险
✓ 抓取到 11 个OWASP页面

【步骤3】文本分割与元数据生成
✓ 生成 150 个文本chunk

【步骤4】批量上传到向量数据库
✓ 上传完成，共 150 个文本块

【步骤5】测试搜索功能
测试查询: 'phishing mail indicators'
  [1] 相似度: 0.3254
      标题: T1566 - Phishing
      分类: ['phishing', 'attack_technique']

🎉 Pipeline执行完成！
📊 数据库名称: student_Group12_1730123456
📊 上传文件数: 150
💡 后续可以使用此数据库进行RAG检索增强生成
```

---

## ⚙️ 配置说明

### 核心配置参数

| 参数 | 说明 | 默认值 | 推荐值 |
|------|------|--------|--------|
| `BASE_URL` | 后端API地址 | `http://10.1.0.220:9002/api` | 根据实际情况 |
| `TOKEN` | 认证令牌 | 需要设置 | 从管理员获取 |
| `USER_NAME` | 用户/组名 | `Group12` | 你的组名 |
| `METRIC_TYPE` | 向量距离度量 | `L2` | `L2` 或 `cosine` |
| `UPLOAD_BATCH` | 批量上传大小 | `10` | 10-50 |
| `PDF_TMP_DIR` | PDF临时目录 | 系统临时目录 | 默认即可 |

### METRIC_TYPE 说明

- **L2**: 欧氏距离，适合大多数场景
- **cosine**: 余弦相似度，适合文本长度差异大的场景
- **IP**: 内积，较少使用

---

## 🧩 核心功能介绍

### 1. 网页爬取 (`safe_request_get`)

**功能**: 安全地发送HTTP GET请求

**特点**:
- 自动添加User-Agent（避免被识别为爬虫）
- 20秒超时保护
- 自动错误处理和日志记录

**示例**:
```python
response = safe_request_get("https://example.com")
if response:
    print(response.text)
```

### 2. PDF文本提取 (`download_pdf_to_text`)

**功能**: 下载PDF并提取纯文本

**支持**:
- 流式下载，支持大文件
- 自动生成临时文件名（SHA1哈希）
- 提取后自动清理临时文件

**示例**:
```python
text = download_pdf_to_text("https://example.com/report.pdf")
print(text[:500])  # 打印前500字符
```

### 3. HTML内容提取 (`html_to_text`)

**功能**: 从HTML中提取标题和正文

**清洗策略**:
- 移除脚本、样式、导航栏
- 移除广告和噪声元素
- 智能定位主内容区域
- 清理多余空白字符

**示例**:
```python
html = "<html><head><title>示例</title></head><body>内容</body></html>"
title, text = html_to_text(html)
print(f"标题: {title}, 内容: {text}")
```

### 4. 文本分割 (`split_text_into_chunks`)

**功能**: 将长文本分割成多个chunk

**参数**:
- `chunk_size_chars`: 每个chunk的字符数（推荐1800）
- `chunk_overlap_chars`: 重叠字符数（推荐200）

**为什么需要分割？**
- Embedding模型有输入长度限制（通常512-8192 tokens）
- 更小的chunk提高检索精度
- 重叠部分防止信息在边界丢失

**示例**:
```python
text = "很长的文本..." * 1000
chunks = split_text_into_chunks(text, chunk_size_chars=1800, chunk_overlap_chars=200)
print(f"分割成 {len(chunks)} 个chunk")
```

### 5. 元数据提取 (`generate_metadata`)

**功能**: 自动从文本中提取元数据标签

**提取内容**:
- CVE编号: `CVE-2021-44228`
- MITRE ATT&CK ID: `T1566`
- CWE编号: `CWE-79`
- 日期: `2021-12-10`
- 分类标签: SQL注入、XSS、钓鱼等

**示例**:
```python
text = "CVE-2021-44228是Log4Shell漏洞，属于T1190攻击技术。"
meta = generate_metadata(text, url="https://example.com", title="Log4Shell")
print(meta)
# 输出: {'cves': ['CVE-2021-44228'], 'mitre_techniques': ['T1190'], ...}
```

### 6. 数据库操作

#### 创建数据库 (`create_database`)
```python
db_name, metric = create_database(metric_type="L2")
print(f"数据库名: {db_name}")
```

#### 批量上传 (`upload_chunks`)
```python
chunks = [
    {"file": "文本内容1", "metadata": {"title": "标题1"}},
    {"file": "文本内容2", "metadata": {"title": "标题2"}},
]
file_ids = upload_chunks(db_name, chunks)
print(f"上传了 {len(file_ids)} 个文件")
```

### 7. 爬虫函数

#### MITRE ATT&CK (`crawl_mitre_attack`)
```python
pages = crawl_mitre_attack(max_pages=50)
```

#### OWASP Top 10 (`crawl_owasp_top10`)
```python
pages = crawl_owasp_top10()
```

#### 通用爬虫 (`crawl_generic_urls`)
```python
urls = [
    "https://www.freebuf.com/articles/web/123456.html",
    "https://example.com/security-report.pdf",
]
pages = crawl_generic_urls(urls)
```

---

## ❓ 常见问题

### Q1: 运行时提示"ModuleNotFoundError"

**问题**: 缺少依赖库

**解决**:
```bash
pip install requests beautifulsoup4 pdfminer.six
```

### Q2: 爬取时提示"GET https://xxx 失败"

**可能原因**:
1. 网络连接问题
2. 目标网站不可访问
3. 被反爬虫拦截

**解决**:
1. 检查网络连接
2. 尝试在浏览器中访问该URL
3. 增加请求延迟 `time.sleep(1)`
4. 检查是否需要代理

### Q3: PDF提取失败

**可能原因**:
1. PDF文件损坏
2. PDF是扫描版（图片）
3. PDF有密码保护

**解决**:
1. 在浏览器中确认PDF可以打开
2. 扫描版PDF需要OCR技术
3. 密码保护的PDF需要先解密

### Q4: 上传时提示"401 Unauthorized"

**问题**: Token无效或过期

**解决**:
1. 检查TOKEN是否正确
2. 联系管理员获取新Token

### Q5: 爬取速度很慢

**原因**: 为了遵守爬虫礼仪，代码中设置了延迟

**调整**:
```python
# 在爬虫函数中修改延迟时间
time.sleep(0.3)  # 从0.6秒改为0.3秒（不推荐太小）
```

### Q6: 内存占用过高

**原因**: 一次性加载太多页面到内存

**解决**:
1. 减少 `max_pages` 参数
2. 分批次运行
3. 增加机器内存

---

## 🎓 进阶使用

### 自定义数据源

#### 方式1: 添加URL列表
在 `pipeline_demo()` 函数中的 `extra_urls` 添加：

```python
extra_urls = [
    "https://www.freebuf.com/articles/web/123456.html",
    "https://www.anquanke.com/post/id/234567",
    "https://example.com/security-report.pdf",
]
```

#### 方式2: 编写新的爬虫函数

```python
def crawl_your_site():
    """自定义爬虫函数"""
    urls = ["https://your-site.com/page1", "https://your-site.com/page2"]
    return crawl_generic_urls(urls)

# 在 pipeline_demo() 中调用
your_pages = crawl_your_site()
all_pages = mitre_pages + owasp_pages + your_pages
```

### 调整Chunk大小

根据你的embedding模型调整：

```python
# 示例：如果你的模型支持更长的输入
chunks = split_text_into_chunks(
    text, 
    chunk_size_chars=3000,      # 增加到3000字符
    chunk_overlap_chars=300     # 增加重叠到300字符
)
```

**推荐配置**:
- 短文本模型 (512 tokens): `chunk_size_chars=800`
- 中等模型 (2048 tokens): `chunk_size_chars=1800` (默认)
- 长文本模型 (8192 tokens): `chunk_size_chars=6000`

### 增量更新

如果想定期更新数据库：

```python
# 1. 使用现有数据库（不创建新的）
db_name = "student_Group12_existing_db"

# 2. 只爬取新内容
new_urls = ["https://new-article.com"]
new_pages = crawl_generic_urls(new_urls)

# 3. 处理并上传
# ... (后续步骤与pipeline_demo相同)
```

### 过滤和筛选

#### 按分类过滤
```python
# 只保留包含SQL注入的内容
filtered_pages = [
    p for p in all_pages 
    if 'sql_injection' in p.get('meta', {}).get('categories', [])
]
```

#### 按长度过滤
```python
# 只保留长度大于1000字符的页面
filtered_pages = [p for p in all_pages if len(p['text']) > 1000]
```

### 并行爬取（进阶）

使用多线程加速爬取：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def crawl_with_thread_pool(urls, max_workers=5):
    """并行爬取多个URL"""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(safe_request_get, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                response = future.result()
                if response:
                    title, text = html_to_text(response.text)
                    results.append({"url": url, "title": title, "text": text})
            except Exception as e:
                logging.error(f"爬取失败 {url}: {e}")
    return results
```

**注意**: 并行爬取时要更加注意请求频率，避免被封禁。

---

## 📊 性能优化建议

### 1. 合理设置爬取数量
- 初学者: 30-50页（快速测试）
- 中级: 100-200页（实用规模）
- 高级: 500+页（生产环境）

### 2. 批量上传大小
- 小文件 (<1KB): `UPLOAD_BATCH = 50`
- 中等文件 (1-10KB): `UPLOAD_BATCH = 20` (默认10)
- 大文件 (>10KB): `UPLOAD_BATCH = 5`

### 3. 请求延迟
- 国际站点: 1-2秒
- 国内站点: 0.5-1秒
- 本地测试: 0.1-0.3秒

### 4. 内存管理
```python
# 分批处理，避免一次性加载所有页面
def process_in_batches(pages, batch_size=100):
    for i in range(0, len(pages), batch_size):
        batch = pages[i:i+batch_size]
        # 处理batch
        yield batch
```

---

## 🔒 安全与合规

### 爬虫礼仪
1. **遵守 robots.txt**: 检查网站是否允许爬取
2. **请求频率**: 不要过快，建议0.5-1秒/请求
3. **User-Agent**: 标识你的爬虫身份
4. **错误处理**: 不要无限重试

### 法律合规
1. **个人使用**: 用于学习和研究
2. **商业使用**: 需要获得网站授权
3. **版权尊重**: 不要侵犯内容版权
4. **隐私保护**: 不要爬取个人隐私信息

### 代码中的合规措施
```python
# 1. User-Agent 标识
headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; CyberSecRAG/1.0)")

# 2. 请求延迟
time.sleep(0.6)  # 礼貌等待

# 3. 错误处理
try:
    response = requests.get(url, timeout=20)
except Exception as e:
    logging.warning(f"请求失败: {e}")
    return None
```

---

## 📞 获取帮助

如果遇到问题:
1. 检查本文档的"常见问题"部分
2. 查看代码中的详细注释
3. 阅读 `数据源推荐.md` 了解数据源
4. 检查后端API文档

---

## 🎯 下一步

完成Pipeline后:
1. **测试搜索**: 使用不同查询测试检索效果
2. **评估质量**: 检查返回结果的相关性
3. **优化调整**: 根据效果调整chunk大小、数据源
4. **集成应用**: 将数据库集成到你的RAG应用中

**集成示例**:
```python
# 在你的RAG应用中使用构建好的数据库
import requests

def rag_query(user_question, db_name):
    # 1. 检索相关文档
    search_response = requests.post(
        f"{BASE_URL}/databases/{db_name}/search",
        json={
            "token": TOKEN,
            "query": user_question,
            "top_k": 5,
            "metric_type": "L2"
        }
    )
    
    results = search_response.json()["results"]
    
    # 2. 构造prompt
    context = "\n\n".join([r["file"] for r in results])
    prompt = f"基于以下参考资料回答问题:\n\n{context}\n\n问题: {user_question}"
    
    # 3. 调用LLM生成答案
    # ... (使用你的LLM API)
    
    return answer
```

祝你构建成功！🎉

