#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT Story Maker - 本地RAG系统
使用 Qwen3 + ChromaDB 为创作项目提供智能文档检索

依赖安装：
pip install chromadb ollama-python markdown pyyaml
"""

from rag_base import BaseRAGSystem, DocumentChunk
from pathlib import Path
from typing import List, Dict, Any, Optional


class StoryRAGSystem(BaseRAGSystem):
    """故事创作RAG系统"""
    
    def __init__(self, 
                 project_root: Optional[str] = None,
                 config_path: Optional[str] = None):
        """
        初始化RAG系统
        
        Args:
            project_root: 项目根目录（可选，使用配置文件）
            config_path: 配置文件路径
        """
        super().__init__(project_root, config_path)
    
    
    def index_documents(self, force_reindex: bool = False, 
                        parallel_workers: Optional[int] = None, 
                        embedding_batch_size: Optional[int] = None):
        """
        索引所有文档
        
        Args:
            force_reindex: 强制重建索引
            parallel_workers: 并行处理线程数（可选，使用配置文件默认值）
            embedding_batch_size: embedding生成的批次大小（可选，使用配置文件默认值）
        """
        # 使用配置文件默认值
        if parallel_workers is None:
            parallel_workers = self.config.get("document_processing.parallel_workers", 8)
        if embedding_batch_size is None:
            embedding_batch_size = self.config.get("document_processing.embedding_batch_size", 20)
        
        collection_name = self.config.get("vectordb.collection_name", "story_knowledge")
        
        if force_reindex:
            # 强制重建时删除现有数据
            try:
                self.chroma_client.delete_collection(collection_name)
                print("已删除现有索引数据")
            except:
                pass
            # 重新创建collection
            self.collection = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "GPT Story Maker knowledge base"}
            )
        elif self.collection.count() > 0:
            print(f"数据库已存在 {self.collection.count()} 个文档，使用 force_reindex=True 强制重建")
            return
        
        print("开始索引文档...")
        all_chunks = []
        
        # 收集所有markdown文件，过滤掉不需要的路径
        md_files = list(self.project_root.glob("**/*.md"))
        
        # 获取忽略模式
        ignore_patterns = self.config.get("system.ignore_patterns", [])
        
        filtered_files = []
        for file_path in md_files:
            # 检查文件名
            if file_path.name.startswith('.'):
                continue
            
            # 检查路径中是否包含忽略模式
            path_str = str(file_path)
            should_ignore = False
            for pattern in ignore_patterns:
                if pattern in path_str:
                    should_ignore = True
                    break
            
            if not should_ignore:
                filtered_files.append(file_path)
        
        for file_path in filtered_files:
                
            print(f"处理文件: {file_path}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 根据文件类型选择切片策略
                file_type = self._get_file_type(file_path)
                doc_types = self.config.get("document_processing.doc_types", {})
                
                chunk_strategy = "by_paragraph"  # 默认策略
                if file_type in doc_types:
                    chunk_strategy = doc_types[file_type].get("chunk_strategy", "by_paragraph")
                
                if chunk_strategy == "by_section":
                    chunks = self.chunk_by_section(content, file_path)
                else:
                    chunks = self.chunk_by_paragraph(content, file_path)
                
                all_chunks.extend(chunks)
                
            except Exception as e:
                print(f"处理文件 {file_path} 失败: {e}")
        
        if not all_chunks:
            print("未找到任何文档内容")
            return
        
        print(f"共生成 {len(all_chunks)} 个文档切片")
        
        # 批量获取embeddings并存储（并行处理）
        print(f"生成向量并存储...（并行线程数: {parallel_workers}）")
        storage_batch_size = self.config.get("document_processing.storage_batch_size", 50)
        
        for i in range(0, len(all_chunks), storage_batch_size):
            batch = all_chunks[i:i+storage_batch_size]
            
            # 准备批次数据
            ids = [chunk.chunk_id for chunk in batch]
            contents = [chunk.content for chunk in batch]
            metadatas = [chunk.metadata for chunk in batch]
            
            print(f"正在处理存储批次 {i//storage_batch_size + 1}/{(len(all_chunks) + storage_batch_size - 1)//storage_batch_size}")
            
            # 使用基类的模型接口获取embeddings
            embeddings = self.model_interface.get_embeddings_batch(contents, batch_size=embedding_batch_size)
            
            # 存储到ChromaDB
            try:
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=contents,
                    metadatas=metadatas
                )
                print(f"✅ 已存储 {min(i+storage_batch_size, len(all_chunks))}/{len(all_chunks)} 个切片")
            except Exception as e:
                print(f"❌ 存储批次失败: {e}")
        
        print(f"索引完成！共索引 {len(all_chunks)} 个文档切片")
    
    # 搜索方法继承自基类，使用 rerank 功能
    


def main():
    """CLI接口示例"""
    import sys
    import os
    
    # 强制UTF-8编码
    if sys.platform == "win32":
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        import codecs
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
    
    import argparse
    
    parser = argparse.ArgumentParser(description="GPT Story Maker RAG System")
    parser.add_argument("--index", action="store_true", help="重建索引")
    parser.add_argument("--query", type=str, help="搜索查询")
    parser.add_argument("--character", type=str, help="搜索角色信息")
    parser.add_argument("--top-k", type=int, default=5, help="返回结果数量")
    parser.add_argument("--parallel-workers", type=int, default=4, help="并行处理线程数")
    parser.add_argument("--debug", action="store_true", help="显示调试信息")
    parser.add_argument("--list-docs", action="store_true", help="列出所有已索引的文档")
    
    args = parser.parse_args()
    
    # 初始化系统
    rag = StoryRAGSystem()
    
    if args.index:
        rag.index_documents(force_reindex=True, parallel_workers=args.parallel_workers)
        return
    
    if args.list_docs:
        print(f"\n=== 已索引文档统计 ===")
        print(f"总文档数: {rag.collection.count()}")
        
        # 获取所有文档的元数据
        all_docs = rag.collection.get()
        file_counts = {}
        
        for metadata in all_docs['metadatas']:
            file_path = metadata['file_path']
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
        
        print("\n各文件切片数量:")
        for file_path, count in sorted(file_counts.items()):
            print(f"  {file_path}: {count} 个切片")
        return
    
    def print_search_results(results, title):
        """统一的结果打印函数"""
        print(f"\n=== {title} ===")
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            content = result['content']
            
            print(f"\n{i}. 来源: {metadata['file_path']}")
            print(f"   类型: {metadata.get('file_type', 'N/A')}")
            print(f"   标题: {metadata.get('section_title', 'N/A')}")
            
            # 显示行号信息（如果有）
            if 'start_line' in metadata and 'end_line' in metadata:
                print(f"   位置: 第{metadata['start_line']}-{metadata['end_line']}行")
            
            # 显示相关度分数（优先使用rerank分数）
            if result.get('rerank_score') is not None:
                print(f"   相关度: {result['rerank_score']:.3f} (rerank)")
            elif result.get('final_score') is not None:
                print(f"   相关度: {result['final_score']:.3f} (final)")
            elif result.get('distance') is not None:
                similarity = 1 - result['distance']
                print(f"   相关度: {similarity:.3f} (vector)")
            
            print(f"   内容: {content}")
            if len(content) > 1000:
                print(f"   [内容较长，已完整显示 {len(content)} 字符]")
    
    if args.character:
        results = rag.search_character(args.character, args.top_k)
        print_search_results(results, f"{args.character} 相关信息")
    
    elif args.query:
        results = rag.search(args.query, args.top_k)
        print_search_results(results, f"搜索: {args.query}")
    
    else:
        print("请指定操作: --index, --query 或 --character")
        print("示例:")
        print("  python story_rag_system.py --index")
        print("  python story_rag_system.py --query '小一的病娇特征'")
        print("  python story_rag_system.py --character '林晚晚-1'")


if __name__ == "__main__":
    main()