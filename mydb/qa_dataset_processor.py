"""
基于知识图谱的问答数据集处理器
从JSON格式的QA数据集中提取高质量问答对，上传到向量数据库
"""

import sys
import os
import json
import logging
from typing import List, Dict, Optional

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mydb.createdb_pipeline import (
    BASE_URL, TOKEN, METRIC_TYPE,
    create_database, upload_chunks
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class QADatasetProcessor:
    """问答数据集处理器"""
    
    def __init__(self, include_question_in_text: bool = True):
        """
        初始化处理器
        
        Args:
            include_question_in_text: 是否在文本中包含问题（有助于语义检索）
        """
        self.include_question_in_text = include_question_in_text
        self.stats = {
            'total_qa_pairs': 0,
            'processed_qa_pairs': 0,
            'skipped_qa_pairs': 0,
            'by_method': {},
            'by_file': {}
        }
    
    def load_json_file(self, file_path: str) -> List[Dict]:
        """
        加载JSON文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            QA对象列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                logging.warning(f"文件格式不正确: {file_path}")
                return []
            
            logging.info(f"✓ 加载成功: {file_path} | 包含 {len(data)} 个QA对")
            return data
            
        except Exception as e:
            logging.error(f"加载失败 {file_path}: {e}")
            return []
    
    def process_qa_item(self, qa_item: Dict, source_file: str) -> Optional[Dict]:
        """
        处理单个QA项
        
        Args:
            qa_item: QA数据项
            source_file: 源文件名
            
        Returns:
            处理后的上传项，如果无效则返回None
        """
        try:
            # 提取必要字段
            qid = qa_item.get('QID', '')
            question = qa_item.get('Question', '').strip()
            answer = qa_item.get('Answer', '').strip()
            method = qa_item.get('Method', '')
            entities = qa_item.get('Entity', [])
            relations = qa_item.get('Relation', [])
            ontology = qa_item.get('Ontology', [])
            
            # 验证必要字段
            if not question or not answer:
                logging.debug(f"跳过无效QA对: {qid}")
                self.stats['skipped_qa_pairs'] += 1
                return None
            
            # 构建文本内容
            if self.include_question_in_text:
                # 方式1: Question + Answer（更好的语义检索）
                text_content = f"问题：{question}\n\n答案：{answer}"
            else:
                # 方式2: 仅Answer
                text_content = answer
            
            # 统计方法类型
            if method:
                self.stats['by_method'][method] = self.stats['by_method'].get(method, 0) + 1
            
            # 构建元数据
            metadata = {
                'qid': qid,
                'question': question,
                'answer': answer,
                'method': method,
                'entities': ','.join(entities) if entities else '',
                'relations': ','.join(relations) if relations else '',
                'source_file': source_file,
                'data_type': 'qa_pair',
                'source': 'AISECKG-QA-Dataset',
                'language': 'en',  # 当前数据集为英文
            }
            
            # 添加本体信息（如果有）
            if ontology:
                # 将本体三元组转换为可读字符串
                ontology_str = '; '.join([f"{t[0]}-{t[1]}-{t[2]}" for t in ontology if len(t) == 3])
                metadata['ontology'] = ontology_str
            
            self.stats['processed_qa_pairs'] += 1
            
            return {
                'file': text_content,
                'metadata': metadata
            }
            
        except Exception as e:
            logging.error(f"处理QA项失败: {e}")
            self.stats['skipped_qa_pairs'] += 1
            return None
    
    def process_json_file(self, file_path: str) -> List[Dict]:
        """
        处理单个JSON文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            处理后的上传项列表
        """
        # 加载数据
        qa_list = self.load_json_file(file_path)
        if not qa_list:
            return []
        
        # 获取文件名
        file_name = os.path.basename(file_path)
        self.stats['by_file'][file_name] = len(qa_list)
        self.stats['total_qa_pairs'] += len(qa_list)
        
        # 处理每个QA对
        upload_items = []
        for qa_item in qa_list:
            item = self.process_qa_item(qa_item, file_name)
            if item:
                upload_items.append(item)
        
        logging.info(f"✓ 文件处理完成: {file_name} | 有效QA对: {len(upload_items)}/{len(qa_list)}")
        
        return upload_items
    
    def process_directory(self, directory: str, file_pattern: str = "*.json") -> List[Dict]:
        """
        处理目录中的所有JSON文件
        
        Args:
            directory: 目录路径
            file_pattern: 文件匹配模式
            
        Returns:
            所有处理后的上传项列表
        """
        all_items = []
        
        if not os.path.exists(directory):
            logging.error(f"目录不存在: {directory}")
            return all_items
        
        # 获取所有JSON文件
        json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
        
        if not json_files:
            logging.warning(f"目录中没有JSON文件: {directory}")
            return all_items
        
        logging.info(f"\n找到 {len(json_files)} 个JSON文件:")
        for f in json_files:
            logging.info(f"  - {f}")
        
        # 处理每个文件
        for i, json_file in enumerate(json_files, 1):
            logging.info(f"\n【{i}/{len(json_files)}】处理文件: {json_file}")
            file_path = os.path.join(directory, json_file)
            items = self.process_json_file(file_path)
            all_items.extend(items)
        
        return all_items
    
    def print_stats(self):
        """打印统计信息"""
        logging.info("\n" + "=" * 80)
        logging.info("QA数据集处理统计")
        logging.info("=" * 80)
        logging.info(f"总QA对数: {self.stats['total_qa_pairs']}")
        logging.info(f"成功处理: {self.stats['processed_qa_pairs']}")
        logging.info(f"跳过数量: {self.stats['skipped_qa_pairs']}")
        
        if self.stats['by_file']:
            logging.info("\n按文件统计:")
            for file_name, count in self.stats['by_file'].items():
                logging.info(f"  - {file_name}: {count} 对")
        
        if self.stats['by_method']:
            logging.info("\n按方法统计:")
            for method, count in self.stats['by_method'].items():
                logging.info(f"  - {method}: {count} 对")
        
        if self.stats['total_qa_pairs'] > 0:
            success_rate = self.stats['processed_qa_pairs'] / self.stats['total_qa_pairs'] * 100
            logging.info(f"\n处理成功率: {success_rate:.1f}%")
        
        logging.info("=" * 80)


def run_qa_dataset_upload(
    data_directory: str,
    db_name: str = "student_Group12_qa_final",
    metric: str = "cosine",
    include_question: bool = True
):
    """
    运行QA数据集上传流程
    
    Args:
        data_directory: QA数据集目录
        db_name: 数据库名称
        metric: 相似度度量方式
        include_question: 是否在文本中包含问题
    """
    logging.info("=" * 80)
    logging.info("基于知识图谱的QA数据集上传系统")
    logging.info("=" * 80)
    
    # 第一步：初始化处理器
    logging.info("\n【步骤1】初始化QA数据集处理器")
    processor = QADatasetProcessor(include_question_in_text=include_question)
    logging.info(f"✓ 处理器设置: 文本{'包含'if include_question else '不包含'}问题部分")
    
    # 第二步：处理数据集
    logging.info("\n【步骤2】处理QA数据集文件")
    logging.info(f"数据目录: {data_directory}")
    
    all_items = processor.process_directory(data_directory)
    
    if not all_items:
        logging.error("❌ 没有处理到任何有效的QA对！")
        return None, []
    
    # 第三步：打印统计
    processor.print_stats()
    
    # 第四步：创建/使用数据库
    logging.info("\n【步骤3】准备向量数据库")
    logging.info(f"数据库名称: {db_name}")
    logging.info(f"相似度度量: {metric}")
    
    # 第五步：上传数据
    logging.info("\n【步骤4】上传QA数据到向量数据库")
    logging.info(f"准备上传 {len(all_items)} 个QA对...")
    
    try:
        file_ids = upload_chunks(db_name, all_items)
        logging.info(f"✓ 上传完成！共上传 {len(file_ids)} 个QA对")
    except Exception as e:
        logging.error(f"❌ 上传失败: {e}")
        return None, []
    
    # 第六步：总结
    logging.info("\n" + "=" * 80)
    logging.info("🎉 QA数据集上传完成！")
    logging.info("=" * 80)
    logging.info(f"📊 数据库名称: {db_name}")
    logging.info(f"📊 上传QA对数: {len(file_ids)}")
    logging.info(f"📊 数据来源: AISECKG-QA-Dataset")
    logging.info("=" * 80)
    
    return db_name, file_ids


def main():
    """主函数"""
    # 配置参数
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_directory = os.path.join(current_dir, "All_data_files")
    
    # 数据库名称（使用最终版本数据库）
    db_name = "student_Group12_final"
    
    # 相似度度量（与原数据库保持一致）
    metric = "cosine"
    
    # 是否在文本中包含问题（建议为True，有助于语义检索）
    include_question = True
    
    logging.info("配置信息:")
    logging.info(f"  数据目录: {data_directory}")
    logging.info(f"  数据库名: {db_name}")
    logging.info(f"  相似度度量: {metric}")
    logging.info(f"  包含问题: {include_question}")
    
    # 运行上传流程
    db_name_result, file_ids = run_qa_dataset_upload(
        data_directory=data_directory,
        db_name=db_name,
        metric=metric,
        include_question=include_question
    )
    
    if db_name_result:
        print("\n" + "=" * 80)
        print("✅ QA数据集上传成功！")
        print(f"数据库名称: {db_name_result}")
        print(f"上传QA对数: {len(file_ids)}")
        print("\n💡 使用建议:")
        print(f"1. 在RAG系统中使用数据库: '{db_name_result}'")
        print("2. 这些QA对基于知识图谱生成，质量较高")
        print("3. 包含三种方法: Zero-shot, Ontology-based, In-Context Learning")
        print("=" * 80)
    else:
        print("\n❌ QA数据集上传失败，请检查日志")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("\n⚠️ 用户中断执行")
    except Exception as e:
        logging.error(f"\n❌ 执行失败: {e}", exc_info=True)
        raise

