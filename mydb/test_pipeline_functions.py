#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 createdb_pipeline.py 中的核心函数

运行方式:
    python test_pipeline_functions.py
"""

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# 测试函数导入
try:
    from createdb_pipeline import (
        html_to_text,
        split_text_into_chunks,
        generate_metadata,
    )
    print("✓ 所有函数导入成功")
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    exit(1)


def test_html_to_text():
    """测试HTML文本提取"""
    print("\n【测试1】HTML文本提取")
    
    html = """
    <html>
    <head><title>测试页面</title></head>
    <body>
        <nav>导航栏</nav>
        <main>
            <h1>SQL注入攻击</h1>
            <p>SQL注入是一种常见的Web安全漏洞，攻击者通过在用户输入的数据中注入恶意的SQL代码。</p>
            <p>CVE-2021-12345是一个典型的SQL注入漏洞案例。</p>
        </main>
        <footer>页脚</footer>
    </body>
    </html>
    """
    
    title, text = html_to_text(html)
    
    assert title == "测试页面", f"标题提取失败: {title}"
    assert "SQL注入攻击" in text, "正文内容缺失"
    assert "导航栏" not in text, "噪声过滤失败"
    assert "页脚" not in text, "噪声过滤失败"
    
    print(f"✓ 标题: {title}")
    print(f"✓ 正文长度: {len(text)} 字符")
    print(f"✓ HTML提取测试通过")


def test_split_text():
    """测试文本分割"""
    print("\n【测试2】文本分割")
    
    # 生成一段长文本
    text = "这是测试文本。" * 200  # 约2000字符
    
    chunks = split_text_into_chunks(
        text, 
        chunk_size_chars=500, 
        chunk_overlap_chars=50
    )
    
    assert len(chunks) > 1, "应该生成多个chunk"
    assert all(len(c) > 0 for c in chunks), "chunk不应为空"
    
    # 检查重叠
    if len(chunks) > 1:
        overlap_exists = chunks[0][-50:] in chunks[1]
        assert overlap_exists, "chunk间应该有重叠"
    
    print(f"✓ 原文长度: {len(text)} 字符")
    print(f"✓ 生成chunk数: {len(chunks)}")
    print(f"✓ 第一个chunk长度: {len(chunks[0])} 字符")
    print(f"✓ 文本分割测试通过")


def test_generate_metadata():
    """测试元数据提取"""
    print("\n【测试3】元数据提取")
    
    text = """
    CVE-2021-44228 Log4Shell漏洞分析
    
    这是一个严重的远程代码执行漏洞，影响Apache Log4j库。
    该漏洞被分配为CVE-2021-44228，CVSS评分为10.0。
    攻击者可以通过JNDI注入实现远程代码执行（RCE）。
    
    MITRE ATT&CK技术编号: T1190 (利用面向公众的应用程序)
    CWE编号: CWE-502 (不可信数据的反序列化)
    
    发现日期: 2021-12-09
    """
    
    meta = generate_metadata(text, url="https://example.com/cve-2021-44228", title="Log4Shell")
    
    # 验证提取结果
    assert 'CVE-2021-44228' in meta.get('cves', []), "CVE提取失败"
    assert 'T1190' in meta.get('mitre_techniques', []), "MITRE技术ID提取失败"
    assert 'CWE-502' in meta.get('cwes', []), "CWE提取失败"
    assert 'rce' in meta.get('categories', []), "分类标签提取失败"
    assert 'vulnerability' in meta.get('categories', []), "分类标签提取失败"
    
    print(f"✓ CVE编号: {meta.get('cves', [])}")
    print(f"✓ MITRE技术: {meta.get('mitre_techniques', [])}")
    print(f"✓ CWE编号: {meta.get('cwes', [])}")
    print(f"✓ 分类标签: {meta.get('categories', [])}")
    print(f"✓ 元数据提取测试通过")


def test_metadata_categories():
    """测试不同类型的分类识别"""
    print("\n【测试4】分类标签识别")
    
    test_cases = [
        ("SQL注入攻击是最常见的Web漏洞", ['sql_injection']),
        ("XSS跨站脚本攻击", ['xss']),
        ("钓鱼邮件识别技巧", ['phishing']),
        ("勒索软件防御指南", ['ransomware']),
        ("DDoS拒绝服务攻击", ['ddos']),
        ("渗透测试方法论", ['penetration_testing']),
        ("木马病毒分析", ['malware']),
    ]
    
    for text, expected_cats in test_cases:
        meta = generate_metadata(text, url="test", title="test")
        found = False
        for cat in expected_cats:
            if cat in meta.get('categories', []):
                found = True
                break
        assert found, f"未能识别分类: {expected_cats} in '{text}'"
        print(f"✓ '{text[:20]}...' -> {meta.get('categories', [])}")
    
    print(f"✓ 分类标签识别测试通过")


def test_chunk_metadata_integration():
    """测试完整的分割+元数据流程"""
    print("\n【测试5】完整流程集成测试")
    
    text = """
    CVE-2017-0144 EternalBlue漏洞分析
    
    EternalBlue是NSA开发的网络武器，利用Windows SMB协议漏洞。
    该漏洞被WannaCry勒索软件利用，造成全球范围的网络攻击。
    MITRE ATT&CK编号: T1210 (横向移动)
    """ * 10  # 重复生成长文本
    
    # 1. 生成元数据
    meta_base = generate_metadata(text, url="https://example.com", title="EternalBlue")
    
    # 2. 分割文本
    chunks = split_text_into_chunks(text, chunk_size_chars=800, chunk_overlap_chars=100)
    
    # 3. 为每个chunk添加元数据
    upload_items = []
    for i, chunk in enumerate(chunks):
        meta = dict(meta_base)
        meta.update({
            "chunk_index": i,
            "chunk_length": len(chunk),
            "total_chunks": len(chunks)
        })
        upload_items.append({"file": chunk, "metadata": meta})
    
    # 验证
    assert len(upload_items) == len(chunks), "上传项数量不匹配"
    assert all('file' in item for item in upload_items), "缺少file字段"
    assert all('metadata' in item for item in upload_items), "缺少metadata字段"
    assert upload_items[0]['metadata']['chunk_index'] == 0, "chunk索引错误"
    
    print(f"✓ 原文长度: {len(text)} 字符")
    print(f"✓ 生成chunks: {len(chunks)}")
    print(f"✓ 上传项数: {len(upload_items)}")
    print(f"✓ 第一个chunk元数据: {list(upload_items[0]['metadata'].keys())}")
    print(f"✓ 完整流程集成测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行Pipeline函数测试")
    print("=" * 60)
    
    tests = [
        test_html_to_text,
        test_split_text,
        test_generate_metadata,
        test_metadata_categories,
        test_chunk_metadata_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_func.__name__} 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__} 出错: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    if failed == 0:
        print("🎉 所有测试通过！代码功能正常。")
        return True
    else:
        print("⚠️  部分测试失败，请检查代码。")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

