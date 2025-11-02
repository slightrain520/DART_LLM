将论文给出的QA数据集上传到数据库的格式：
```json
{
    'file': '问题：What is sniff mode?\n\n答案：Sniff mode is a way of capturing network traffic on a network interface by setting the interface to receive all packets on the network, regardless of their destination.',
    
    'metadata': {
        'qid': 'C-1',
        'question': 'What is sniff mode?',
        'answer': 'Sniff mode is a way of capturing network traffic on a network interface by setting the interface to receive all packets on the network, regardless of their destination.',
        'method': 'Zero-shot',
        'entities': 'Sniff Mode',
        'relations': '',
        'source_file': 'QA_zeropara.json',
        'data_type': 'qa_pair',
        'source': 'AISECKG-QA-Dataset',
        'language': 'en'
    }
}
```

正在检索: what is sniff mode?
============================================================

提取的上下文：
------------------------------------------------------------    
[文档1] (相似度: 0.7704)
问题：What is sniff mode?

答案：Sniff mode is a way of capturing network traffic on a network interface by setting the interface to receive all packets on the network, regardless of their destination.

[文档2] (相似度: 0.7687)
问题：What is Sniff mode?

答案：Sniff mode is a feature in some network security tools that allows the tool to capture and analyze network traffic.       

[文档3] (相似度: 0.7624)
问题：What is sniff mode?

答案：Sniff mode is a network monitoring mode that allows packets to be captured and analyzed in real-time.

[文档4] (相似度: 0.7393)
问题：Why is sniff mode useful?

答案：Sniff mode can be useful for network troubleshooting, network security analysis, and other purposes.

[文档5] (相似度: 0.7249)
问题：How can Sniff mode be used to detect malicious activity?  

答案：Sniff mode can be used to detect malicious activity by analyzing network traffic for known attack signatures, identifying anomalies in traffic patterns, and monitoring for suspicious behavior.
