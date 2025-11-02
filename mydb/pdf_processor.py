"""
PDF文件处理模块
提供PDF文件的智能分块和上传接口
"""

import os
import logging
from typing import List, Dict, Optional
from pdfminer.high_level import extract_text

from mydb.text_cleaner import TextCleaner, ContentQualityEvaluator
from mydb.smart_chunker import SmartChunker
from mydb.createdb_pipeline import generate_metadata, upload_chunks

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class PDFProcessor:
    """PDF文件处理器，支持智能分块和质量控制"""
    
    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 150,
        min_chunk_size: int = 100,
        quality_threshold: float = 0.3,
        aggressive_cleaning: bool = False
    ):
        """
        初始化PDF处理器
        
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
            'total_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'low_quality_files': 0,
            'total_chunks': 0,
            'filtered_chunks': 0,
            'final_chunks': 0
        }
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        从PDF文件中提取文本
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            提取的文本内容
        """
        try:
            text = extract_text(pdf_path)
            return text
        except Exception as e:
            logging.error(f"PDF文本提取失败 {pdf_path}: {e}")
            return ""
    
    def process_pdf(
        self,
        pdf_path: str,
        custom_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        处理单个PDF文件：提取、清洗、分块、质量评估
        
        Args:
            pdf_path: PDF文件路径
            custom_metadata: 自定义元数据（可选）
            
        Returns:
            处理后的chunk列表
        """
        self.stats['total_files'] += 1
        
        if not os.path.exists(pdf_path):
            logging.error(f"文件不存在: {pdf_path}")
            self.stats['failed_files'] += 1
            return []
        
        logging.info(f"处理PDF: {pdf_path}")
        
        try:
            # 第一步：提取文本
            text = self.extract_text_from_pdf(pdf_path)
            
            if not text or len(text) < 100:
                logging.warning(f"PDF内容过短: {pdf_path}")
                self.stats['failed_files'] += 1
                return []
            
            # 获取文件名作为标题
            title = os.path.basename(pdf_path).replace('.pdf', '')
            
            # 第二步：清洗文本
            cleaned_text = self.text_cleaner.clean_text(text, aggressive=self.aggressive_cleaning)
            
            if not cleaned_text:
                logging.warning(f"清洗后为空: {pdf_path}")
                self.stats['failed_files'] += 1
                return []
            
            # 第三步：质量评估
            quality_scores = self.quality_evaluator.calculate_quality_score(cleaned_text)
            
            if quality_scores['overall'] < self.quality_threshold:
                logging.info(f"质量不达标 (分数: {quality_scores['overall']:.2f}): {pdf_path}")
                self.stats['low_quality_files'] += 1
                return []
            
            # 第四步：智能分块
            chunks = self.chunker.chunk_text(cleaned_text, deduplicate=True)
            self.stats['total_chunks'] += len(chunks)
            
            if not chunks:
                logging.warning(f"分块后为空: {pdf_path}")
                self.stats['failed_files'] += 1
                return []
            
            # 第五步：为每个chunk生成元数据
            upload_items = []
            for i, chunk_text in enumerate(chunks):
                # 评估chunk质量
                chunk_quality = self.quality_evaluator.calculate_quality_score(chunk_text)
                
                # 过滤低质量chunk
                if chunk_quality['overall'] < self.quality_threshold:
                    self.stats['filtered_chunks'] += 1
                    continue
                
                # 生成基础元数据
                metadata = generate_metadata(chunk_text, pdf_path, title)
                
                # 添加PDF特有信息
                metadata['quality_score'] = round(chunk_quality['overall'], 4)
                metadata['chunk_index'] = i
                metadata['total_chunks'] = len(chunks)
                metadata['source_type'] = 'local_pdf'
                metadata['file_path'] = pdf_path
                metadata['file_name'] = os.path.basename(pdf_path)
                
                # 合并自定义元数据
                if custom_metadata:
                    metadata.update(custom_metadata)
                
                upload_items.append({
                    'file': chunk_text,
                    'metadata': metadata
                })
            
            self.stats['successful_files'] += 1
            self.stats['final_chunks'] += len(upload_items)
            
            logging.info(f"✓ PDF处理成功: {pdf_path} | 质量: {quality_scores['overall']:.2f} | "
                        f"Chunks: {len(upload_items)}/{len(chunks)}")
            
            return upload_items
            
        except Exception as e:
            logging.error(f"PDF处理失败 {pdf_path}: {e}")
            self.stats['failed_files'] += 1
            return []
    
    def process_pdf_batch(
        self,
        pdf_paths: List[str],
        custom_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        批量处理PDF文件列表
        
        Args:
            pdf_paths: PDF文件路径列表
            custom_metadata: 自定义元数据（应用于所有文件）
            
        Returns:
            所有chunk的列表
        """
        all_chunks = []
        
        for i, pdf_path in enumerate(pdf_paths, 1):
            logging.info(f"\n处理进度: {i}/{len(pdf_paths)}")
            chunks = self.process_pdf(pdf_path, custom_metadata)
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def process_pdf_directory(
        self,
        directory: str,
        recursive: bool = False,
        custom_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        批量处理目录中的所有PDF文件
        
        Args:
            directory: 目录路径
            recursive: 是否递归处理子目录
            custom_metadata: 自定义元数据（应用于所有文件）
            
        Returns:
            所有chunk的列表
        """
        if not os.path.exists(directory):
            logging.error(f"目录不存在: {directory}")
            return []
        
        pdf_files = []
        
        if recursive:
            # 递归查找所有PDF文件
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        pdf_files.append(os.path.join(root, file))
        else:
            # 只处理当前目录
            pdf_files = [
                os.path.join(directory, f)
                for f in os.listdir(directory)
                if f.lower().endswith('.pdf')
            ]
        
        logging.info(f"找到 {len(pdf_files)} 个PDF文件")
        
        return self.process_pdf_batch(pdf_files, custom_metadata)
    
    def upload_pdf_to_database(
        self,
        db_name: str,
        pdf_path: str,
        custom_metadata: Optional[Dict] = None
    ) -> List[int]:
        """
        处理PDF文件并上传到数据库（一站式接口）
        
        Args:
            db_name: 数据库名称
            pdf_path: PDF文件路径
            custom_metadata: 自定义元数据
            
        Returns:
            上传成功的file_id列表
        """
        # 处理PDF
        chunks = self.process_pdf(pdf_path, custom_metadata)
        
        if not chunks:
            logging.warning(f"没有可上传的内容: {pdf_path}")
            return []
        
        # 上传到数据库
        logging.info(f"上传到数据库: {db_name}")
        file_ids = upload_chunks(db_name, chunks)
        logging.info(f"✓ 上传完成，共 {len(file_ids)} 个chunk")
        
        return file_ids
    
    def upload_pdf_directory_to_database(
        self,
        db_name: str,
        directory: str,
        recursive: bool = False,
        custom_metadata: Optional[Dict] = None
    ) -> List[int]:
        """
        批量处理目录中的PDF并上传到数据库（一站式接口）
        
        Args:
            db_name: 数据库名称
            directory: 目录路径
            recursive: 是否递归处理子目录
            custom_metadata: 自定义元数据
            
        Returns:
            上传成功的file_id列表
        """
        # 处理目录中的所有PDF
        all_chunks = self.process_pdf_directory(directory, recursive, custom_metadata)
        
        if not all_chunks:
            logging.warning(f"没有可上传的内容: {directory}")
            return []
        
        # 上传到数据库
        logging.info(f"上传到数据库: {db_name}")
        file_ids = upload_chunks(db_name, all_chunks)
        logging.info(f"✓ 上传完成，共 {len(file_ids)} 个chunk")
        
        return file_ids
    
    def print_stats(self):
        """打印统计信息"""
        logging.info("\n" + "=" * 80)
        logging.info("PDF处理统计:")
        logging.info("=" * 80)
        logging.info(f"总文件数: {self.stats['total_files']}")
        logging.info(f"成功处理: {self.stats['successful_files']}")
        logging.info(f"失败文件: {self.stats['failed_files']}")
        logging.info(f"低质量文件: {self.stats['low_quality_files']}")
        logging.info(f"生成chunk总数: {self.stats['total_chunks']}")
        logging.info(f"过滤chunk数: {self.stats['filtered_chunks']}")
        logging.info(f"最终chunk数: {self.stats['final_chunks']}")
        
        if self.stats['total_files'] > 0:
            success_rate = self.stats['successful_files'] / self.stats['total_files'] * 100
            logging.info(f"成功率: {success_rate:.1f}%")
        
        if self.stats['total_chunks'] > 0:
            filter_rate = self.stats['filtered_chunks'] / self.stats['total_chunks'] * 100
            logging.info(f"过滤率: {filter_rate:.1f}%")
        
        logging.info("=" * 80)


# ===== 使用示例 =====

def example_single_pdf():
    """示例：处理单个PDF文件"""
    print("\n示例1: 处理单个PDF文件")
    print("=" * 60)
    
    # 初始化处理器
    processor = PDFProcessor(
        chunk_size=1500,
        chunk_overlap=150,
        quality_threshold=0.3
    )
    
    # 处理PDF文件
    pdf_path = "example.pdf"  # 替换为实际文件路径
    chunks = processor.process_pdf(
        pdf_path,
        custom_metadata={
            'document_type': '法律法规',
            'category': 'cybersecurity_law'
        }
    )
    
    print(f"处理结果: {len(chunks)} 个chunk")
    processor.print_stats()


def example_pdf_directory():
    """示例：批量处理目录中的PDF"""
    print("\n示例2: 批量处理PDF目录")
    print("=" * 60)
    
    processor = PDFProcessor(
        chunk_size=1500,
        chunk_overlap=150,
        quality_threshold=0.3
    )
    
    # 处理目录
    directory = "pdf_documents"  # 替换为实际目录路径
    chunks = processor.process_pdf_directory(
        directory,
        recursive=True,  # 递归处理子目录
        custom_metadata={
            'document_type': '法律法规',
            'source': 'local_files'
        }
    )
    
    print(f"处理结果: {len(chunks)} 个chunk")
    processor.print_stats()


def example_upload_to_database():
    """示例：处理PDF并上传到数据库"""
    print("\n示例3: 处理PDF并上传到数据库")
    print("=" * 60)
    
    processor = PDFProcessor(
        chunk_size=1500,
        chunk_overlap=150,
        quality_threshold=0.3
    )
    
    # 一站式处理和上传
    db_name = "student_Group12_1234567890"  # 替换为实际数据库名
    pdf_path = "example.pdf"  # 替换为实际文件路径
    
    file_ids = processor.upload_pdf_to_database(
        db_name,
        pdf_path,
        custom_metadata={
            'document_type': '法律法规',
            'category': 'cybersecurity_law'
        }
    )
    
    print(f"上传结果: {len(file_ids)} 个chunk")
    processor.print_stats()


def example_batch_upload():
    """示例：批量上传目录中的PDF到数据库"""
    print("\n示例4: 批量上传PDF目录到数据库")
    print("=" * 60)
    
    processor = PDFProcessor(
        chunk_size=1500,
        chunk_overlap=150,
        quality_threshold=0.3
    )
    
    # 批量处理和上传
    db_name = "student_Group12_1234567890"  # 替换为实际数据库名
    directory = "pdf_documents"  # 替换为实际目录路径
    
    file_ids = processor.upload_pdf_directory_to_database(
        db_name,
        directory,
        recursive=True,
        custom_metadata={
            'document_type': '法律法规',
            'source': 'local_files'
        }
    )
    
    print(f"上传结果: {len(file_ids)} 个chunk")
    processor.print_stats()


if __name__ == "__main__":
    print("=" * 60)
    print("PDF处理模块使用示例")
    print("=" * 60)
    
    print("\n请根据需要取消注释以下示例代码：")
    print("1. example_single_pdf()      - 处理单个PDF")
    print("2. example_pdf_directory()   - 批量处理目录")
    print("3. example_upload_to_database() - 上传单个PDF")
    print("4. example_batch_upload()    - 批量上传目录")
    
    # 取消注释以运行示例
    # example_single_pdf()
    # example_pdf_directory()
    # example_upload_to_database()
    # example_batch_upload()

