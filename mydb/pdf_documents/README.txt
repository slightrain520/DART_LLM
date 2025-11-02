PDF文档目录说明
================

这个目录用于存放需要处理的PDF文件（如法律法规、技术报告等）。

使用方法：
---------

1. 将PDF文件放入此目录
   例如：
   - 网络安全法.pdf
   - 数据安全法.pdf
   - 个人信息保护法.pdf
   - 等保2.0标准.pdf
   - 安全技术报告.pdf

2. 运行处理脚本：

   方法1 - 使用PDFProcessor：
   ```python
   from mydb.pdf_processor import PDFProcessor
   from mydb.createdb_pipeline import create_database
   
   # 创建数据库
   db_name, metric = create_database()
   
   # 初始化处理器
   processor = PDFProcessor(quality_threshold=0.3)
   
   # 批量处理此目录
   file_ids = processor.upload_pdf_directory_to_database(
       db_name=db_name,
       directory="d:/lhy/DART_LLM/mydb/pdf_documents",
       recursive=False,
       custom_metadata={
           'document_type': '法律法规',
           'source': 'local_files'
       }
   )
   
   print(f"处理完成: {len(file_ids)} 个chunk")
   ```

   方法2 - 使用增强版爬虫（自动处理此目录）：
   ```python
   from mydb.enhanced_crawler import run_enhanced_crawler_demo
   
   # 运行演示，会自动处理pdf_documents目录
   db_name, file_ids = run_enhanced_crawler_demo(test_mode=False)
   ```

推荐的PDF文件：
--------------

法律法规类：
- 《中华人民共和国网络安全法》
- 《中华人民共和国数据安全法》
- 《中华人民共和国个人信息保护法》
- 《关键信息基础设施安全保护条例》
- GB/T 22239-2019 网络安全等级保护基本要求

技术报告类：
- Verizon数据泄露调查报告（DBIR）
- SANS研究报告
- 厂商威胁情报报告
- NIST网络安全框架文档

注意事项：
---------
1. 确保PDF文件未加密
2. 扫描版PDF需要OCR处理（当前版本不支持）
3. 文件名建议使用中文或英文，避免特殊字符
4. 大文件（>50MB）可能处理较慢

获取PDF文件的途径：
-----------------
1. 中国人大网: http://www.npc.gov.cn/
2. 国家标准全文公开系统: http://openstd.samr.gov.cn/
3. 全国信息安全标准化技术委员会: https://www.tc260.org.cn/
4. NIST: https://csrc.nist.gov/publications


"criterions:
https://www.tc260.org.cn/upload/2025-06-30/1751257342816036759.pdf,
"
