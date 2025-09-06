#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# 强制UTF-8编码
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
"""
GPT Story Maker - 本地RAG系统
使用 Ollama + ChromaDB 为创作项目提供智能文档检索

依赖安装：
pip install chromadb ollama-python markdown
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings
import ollama
import markdown


@dataclass
class DocumentChunk:
    """文档切片数据结构"""
    content: str
    metadata: Dict[str, Any]
    chunk_id: str


class StoryRAGSystem:
    """故事创作RAG系统"""
    
    def __init__(self, 
                 project_root: str = ".",
                 db_path: str = "./chroma_db",
                 embedding_model: str = "nomic-embed-text"):
        """
        初始化RAG系统
        
        Args:
            project_root: 项目根目录
            db_path: ChromaDB存储路径  
            embedding_model: Ollama embedding模型名称
        """
        self.project_root = Path(project_root)
        self.db_path = db_path
        self.embedding_model = embedding_model
        
        # 初始化ChromaDB客户端
        self.chroma_client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 创建或获取collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="story_knowledge",
            metadata={"description": "GPT Story Maker knowledge base"}
        )
        
        # 文档类型配置
        self.doc_types = {
            "设定": {
                "path_patterns": ["设定/*.md"],
                "chunk_strategy": "by_section",
                "priority": 1
            },
            "章节": {
                "path_patterns": ["Vol*/*.md"],
                "chunk_strategy": "by_paragraph", 
                "priority": 2
            },
            "支线": {
                "path_patterns": ["设定/跨卷支线剧情设计/*.md"],
                "chunk_strategy": "by_section",
                "priority": 1
            }
        }
    
    def get_embedding(self, text: str) -> List[float]:
        """获取单个文本向量"""
        response = ollama.embed(
            model=self.embedding_model,
            input=text
        )
        if "embeddings" in response:
            return response["embeddings"][0]
        elif "embedding" in response:
            return response["embedding"]
        else:
            raise ValueError("Unexpected response format from embedding API")
    
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """批量获取文本向量，支持并行处理"""
        import concurrent.futures
        import threading
        
        all_embeddings = []
        
        # 分批处理，每批并行
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            print(f"正在处理批次 {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}，包含 {len(batch_texts)} 个文档...")
            
            # 并行处理当前批次
            max_workers = min(self._parallel_workers, len(batch_texts))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_text = {
                    executor.submit(self.get_embedding, text): idx 
                    for idx, text in enumerate(batch_texts)
                }
                
                # 收集结果，保持原有顺序
                batch_embeddings = [None] * len(batch_texts)
                for future in concurrent.futures.as_completed(future_to_text):
                    idx = future_to_text[future]
                    try:
                        embedding = future.result()
                        batch_embeddings[idx] = embedding
                    except Exception as e:
                        print(f"批次中第 {idx} 个文档embedding失败: {e}")
                        # 使用零向量作为fallback
                        batch_embeddings[idx] = [0.0] * 768
            
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def chunk_by_section(self, content: str, file_path: str) -> List[DocumentChunk]:
        """按章节标题切片 - 保持完整章节内容"""
        lines = content.split('\n')
        chunks = []
        current_section = None
        section_lines = []
        section_start = 0
        
        for i, line in enumerate(lines):
            if line.startswith('## ') and not line.startswith('### '):  # 只匹配二级标题
                # 保存前一个章节
                if current_section and section_lines:
                    section_content = '\n'.join(section_lines).strip()
                    if section_content:
                        chunk_id = self._generate_chunk_id(file_path, len(chunks), current_section)
                        
                        chunks.append(DocumentChunk(
                            content=section_content,
                            metadata={
                                "file_path": str(file_path),
                                "chunk_type": "section",
                                "section_title": current_section,
                                "chunk_index": len(chunks),
                                "start_line": section_start + 1,
                                "end_line": i,
                                "file_type": self._get_file_type(file_path)
                            },
                            chunk_id=chunk_id
                        ))
                
                # 开始新章节
                current_section = line[3:].strip()  # 去掉 "## "
                section_lines = [line]
                section_start = i
            else:
                # 添加到当前章节
                if current_section is not None:
                    section_lines.append(line)
        
        # 处理最后一个章节
        if current_section and section_lines:
            section_content = '\n'.join(section_lines).strip()
            if section_content:
                chunk_id = self._generate_chunk_id(file_path, len(chunks), current_section)
                
                chunks.append(DocumentChunk(
                    content=section_content,
                    metadata={
                        "file_path": str(file_path),
                        "chunk_type": "section",
                        "section_title": current_section,
                        "chunk_index": len(chunks),
                        "start_line": section_start + 1,
                        "end_line": len(lines),
                        "file_type": self._get_file_type(file_path)
                    },
                    chunk_id=chunk_id
                ))
        
        return chunks
    
    def chunk_by_paragraph(self, content: str, file_path: str) -> List[DocumentChunk]:
        """按段落切片（适合章节内容）"""
        chunks = []
        lines = content.split('\n')
        
        # 先按章节分割
        sections = re.split(r'\n(?=#{1,3}\s)', content)
        
        current_line = 1
        for section_idx, section in enumerate(sections):
            if not section.strip():
                current_line += section.count('\n') + 1
                continue
                
            # 提取章节标题
            title_match = re.match(r'^(#{1,3})\s*(.+)', section)
            section_title = title_match.group(2) if title_match else f"Section {section_idx+1}"
            section_start_line = current_line
            
            # 章节内容按段落分割（保留对话和描述的完整性）
            paragraphs = re.split(r'\n\s*\n', section)
            
            para_start_line = section_start_line
            for para_idx, para in enumerate(paragraphs):
                if len(para.strip()) < 50:  # 提高最小长度要求，避免太短的切片
                    para_start_line += para.count('\n') + 2  # +2 for paragraph separator
                    continue
                
                # 计算段落的行号范围
                para_end_line = para_start_line + para.count('\n')
                
                # 增加上下文：包含前后段落的部分内容
                enhanced_content = self._add_context(para, paragraphs, para_idx)
                
                chunk_id = self._generate_chunk_id(file_path, section_idx * 100 + para_idx, f"{section_title}_para{para_idx}")
                
                chunks.append(DocumentChunk(
                    content=enhanced_content,
                    metadata={
                        "file_path": str(file_path),
                        "chunk_type": "paragraph",
                        "section_title": section_title,
                        "paragraph_index": para_idx,
                        "chunk_index": section_idx * 100 + para_idx,
                        "start_line": para_start_line,
                        "end_line": para_end_line,
                        "file_type": self._get_file_type(file_path)
                    },
                    chunk_id=chunk_id
                ))
                
                para_start_line = para_end_line + 2  # +2 for paragraph separator
            
            current_line += section.count('\n') + 1
        
        return chunks
    
    def _generate_chunk_id(self, file_path: str, index: int, title: str) -> str:
        """生成chunk唯一ID"""
        content = f"{file_path}_{index}_{title}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _add_context(self, main_para: str, all_paragraphs: list, para_idx: int, context_chars: int = 200) -> str:
        """为段落添加上下文信息"""
        result = main_para.strip()
        
        # 添加前文上下文
        if para_idx > 0:
            prev_para = all_paragraphs[para_idx - 1].strip()
            if prev_para:
                prev_context = prev_para[-context_chars:] if len(prev_para) > context_chars else prev_para
                result = f"[上文]...{prev_context}\n\n{result}"
        
        # 添加后文上下文
        if para_idx < len(all_paragraphs) - 1:
            next_para = all_paragraphs[para_idx + 1].strip()
            if next_para:
                next_context = next_para[:context_chars] if len(next_para) > context_chars else next_para
                result = f"{result}\n\n[下文]{next_context}..."
        
        return result
    
    def _get_file_type(self, file_path: str) -> str:
        """判断文件类型"""
        path_str = str(file_path)
        if "设定" in path_str:
            if "跨卷支线" in path_str:
                return "支线"
            return "设定"
        elif any(vol in path_str for vol in ["Vol1", "Vol2", "Vol3", "Vol4", "Vol5"]):
            return "章节"
        return "其他"
    
    def index_documents(self, force_reindex: bool = False, parallel_workers: int = 8, embedding_batch_size: int = 20):
        """
        索引所有文档
        
        Args:
            force_reindex: 强制重建索引
            parallel_workers: 并行处理线程数
            embedding_batch_size: embedding生成的批次大小
        """
        if force_reindex:
            # 强制重建时删除现有数据
            try:
                self.chroma_client.delete_collection("story_knowledge")
                print("已删除现有索引数据")
            except:
                pass
            # 重新创建collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="story_knowledge",
                metadata={"description": "GPT Story Maker knowledge base"}
            )
        elif self.collection.count() > 0:
            print(f"数据库已存在 {self.collection.count()} 个文档，使用 force_reindex=True 强制重建")
            return
        
        print("开始索引文档...")
        all_chunks = []
        
        # 收集所有markdown文件，过滤掉不需要的路径
        md_files = list(self.project_root.glob("**/*.md"))
        
        # 忽略列表
        ignore_patterns = [
            ".venv",
            ".env", 
            "venv",
            "env",
            "__pycache__",
            ".git",
            "node_modules",
            "site-packages",
            "dist-info",
            ".uv"
        ]
        
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
                if file_type in ["设定", "支线"]:
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
        storage_batch_size = 50  # ChromaDB存储批次大小
        
        for i in range(0, len(all_chunks), storage_batch_size):
            batch = all_chunks[i:i+storage_batch_size]
            
            # 准备批次数据
            ids = [chunk.chunk_id for chunk in batch]
            contents = [chunk.content for chunk in batch]
            metadatas = [chunk.metadata for chunk in batch]
            
            print(f"正在处理存储批次 {i//storage_batch_size + 1}/{(len(all_chunks) + storage_batch_size - 1)//storage_batch_size}")
            
            # 并行获取embeddings
            self._parallel_workers = parallel_workers
            embeddings = self.get_embeddings_batch(contents, batch_size=embedding_batch_size)
            
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
    
    def search(self, query: str, top_k: int = 5, filter_type: Optional[str] = None) -> List[Dict]:
        """搜索相关文档"""
        try:
            query_embedding = self.get_embedding(query)
            
            # 构建过滤条件
            where_clause = {}
            if filter_type:
                where_clause["file_type"] = filter_type
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause if where_clause else None
            )
            
            # 格式化结果
            formatted_results = []
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    
    def search_character(self, character_name: str, top_k: int = 3) -> List[Dict]:
        """搜索特定角色相关信息"""
        # 扩展搜索词汇，包含更多变体
        character_variants = []
        
        # 根据常见人格命名模式生成搜索变体
        if character_name in ["小一", "1号", "林晚晚-1"]:
            character_variants = ["小一", "林晚晚-1", "病娇", "收藏家", "恋爱游戏"]
        elif character_name in ["小二", "2号", "林晚晚-2"]:
            character_variants = ["小二", "林晚晚-2", "吃货", "美食家", "消化器"]
        elif character_name in ["小七", "7号", "林晚晚-7"]:
            character_variants = ["小七", "林晚晚-7", "数学家", "计算姬", "公式女王"]
        elif character_name in ["小二十一", "21号", "林晚晚-21"]:
            character_variants = ["小二十一", "林晚晚-21", "二十一号", "幼态"]
        elif character_name in ["小三十五", "35号", "林晚晚-35"]:
            character_variants = ["小三十五", "林晚晚-35", "三十五号", "律师"]
        elif character_name in ["小四十二", "42号", "林晚晚-42"]:
            character_variants = ["小四十二", "林晚晚-42", "四十二号", "答案守护者"]
        else:
            character_variants = [character_name]
        
        all_results = []
        
        # 使用所有变体进行搜索
        for variant in character_variants:
            queries = [
                f"{variant} 人格设定 性格特点",
                f"{variant} 能力 出场",
                f"{variant} 对话风格 台词"
            ]
            
            for query in queries:
                results = self.search(query, top_k=3, filter_type="设定")
                all_results.extend(results)
        
        # 去重并按相关性排序
        seen_ids = set()
        unique_results = []
        for result in all_results:
            content_hash = hashlib.md5(result['content'].encode()).hexdigest()
            if content_hash not in seen_ids:
                seen_ids.add(content_hash)
                unique_results.append(result)
        
        # 优先显示包含人格图鉴的结果
        priority_results = []
        other_results = []
        
        for result in unique_results:
            if "人格图鉴" in result['metadata']['file_path']:
                priority_results.append(result)
            else:
                other_results.append(result)
        
        # 合并结果，优先级结果在前
        final_results = priority_results + other_results
        return final_results[:top_k]
    
    def search_plot_thread(self, thread_keyword: str, top_k: int = 5) -> List[Dict]:
        """搜索剧情线索"""
        return self.search(
            f"{thread_keyword} 伏笔 剧情",
            top_k=top_k,
            filter_type="设定"
        )
    
    def get_context_for_chapter(self, volume: int, chapter: int) -> Dict[str, List[Dict]]:
        """获取特定章节的上下文信息"""
        context = {
            "当前章节": [],
            "相关人物": [],
            "剧情线索": []
        }
        
        # 获取当前章节内容
        chapter_query = f"Vol{volume} ch{chapter:02d}"
        context["当前章节"] = self.search(chapter_query, top_k=1, filter_type="章节")
        
        # 如果找到了章节内容，基于内容搜索相关信息
        if context["当前章节"]:
            chapter_content = context["当前章节"][0]['content']
            
            # 提取人物名称（简单启发式）
            character_mentions = re.findall(r'(小[一二三四五六七八九十]+|林晚晚|系统009)', chapter_content)
            for char in set(character_mentions):
                char_info = self.search_character(char, top_k=1)
                context["相关人物"].extend(char_info)
        
        return context


def main():
    """CLI接口示例"""
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
    
    if args.character:
        results = rag.search_character(args.character, args.top_k)
        print(f"\n=== {args.character} 相关信息 ===")
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            content = result['content']
            
            print(f"\n{i}. 来源: {metadata['file_path']}")
            print(f"   标题: {metadata.get('section_title', 'N/A')}")
            
            # 显示行号信息（如果有）
            if 'start_line' in metadata and 'end_line' in metadata:
                print(f"   位置: 第{metadata['start_line']}-{metadata['end_line']}行")
            
            # 显示相似度分数（如果有）
            if result.get('distance') is not None:
                similarity = 1 - result['distance']
                print(f"   相关度: {similarity:.3f}")
            
            print(f"   内容: {content}")
            if len(content) > 1000:
                print(f"   [内容较长，已完整显示 {len(content)} 字符]")
    
    elif args.query:
        results = rag.search(args.query, args.top_k)
        print(f"\n=== 搜索: {args.query} ===")
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            content = result['content']
            
            print(f"\n{i}. 来源: {metadata['file_path']}")
            print(f"   类型: {metadata.get('file_type', 'N/A')}")
            print(f"   章节: {metadata.get('section_title', 'N/A')}")
            
            # 显示行号信息（如果有）
            if 'start_line' in metadata and 'end_line' in metadata:
                print(f"   位置: 第{metadata['start_line']}-{metadata['end_line']}行")
            
            # 显示相似度分数（如果有）
            if result.get('distance') is not None:
                similarity = 1 - result['distance']  # 转换为相似度分数
                print(f"   相关度: {similarity:.3f}")
            
            print(f"   内容: {content}")
            if len(content) > 1000:
                print(f"   [内容较长，已完整显示 {len(content)} 字符]")
    
    else:
        print("请指定操作: --index, --query 或 --character")
        print("示例:")
        print("  python story_rag_system.py --index")
        print("  python story_rag_system.py --query '小一的病娇特征'")
        print("  python story_rag_system.py --character '林晚晚-1'")


if __name__ == "__main__":
    main()