#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Base Classes
提取公共代码，支持 Qwen3 模型和 rerank 功能
"""
import os
import re
import yaml
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
import concurrent.futures
import chromadb
from chromadb.config import Settings
import ollama


@dataclass
class DocumentChunk:
    """文档切片数据结构"""
    content: str
    metadata: Dict[str, Any]
    chunk_id: str


@dataclass
class RerankResult:
    """Rerank 结果数据结构"""
    content: str
    metadata: Dict[str, Any]
    original_score: float
    rerank_score: float
    chunk_id: str


class RAGConfig:
    """RAG 配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置
        
        Args:
            config_path: 配置文件路径，默认为当前目录下的 rag_config.yaml
        """
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "rag_config.yaml")
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            # 使用默认配置
            return self._get_default_config()
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "models": {
                "embedding": {
                    "model_name": "dengcao/Qwen3-Embedding-8B:Q5_K_M",
                    "embedding_dim": 768
                },
                "reranker": {
                    "enabled": True,
                    "model_name": "dengcao/Qwen3-Reranker-8B:Q5_K_M",
                    "max_results": 10,
                    "score_threshold": 0.5
                }
            },
            "vectordb": {
                "db_path": "./chroma_db",
                "collection_name": "story_knowledge",
                "persistent": True
            },
            "document_processing": {
                "parallel_workers": 8,
                "embedding_batch_size": 20,
                "storage_batch_size": 50,
                "doc_types": {
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
                },
                "chunking": {
                    "min_chunk_size": 50,
                    "max_chunk_size": 2000,
                    "context_chars": 200,
                    "add_context": True
                }
            },
            "search": {
                "default_top_k": 5,
                "max_top_k": 20,
                "enable_rerank": True,
                "character_search": {
                    "expand_variants": True,
                    "default_top_k": 3
                }
            },
            "system": {
                "log_level": "INFO",
                "debug": False,
                "ignore_patterns": [
                    ".venv", ".env", "venv", "env", "__pycache__",
                    ".git", "node_modules", "site-packages", "dist-info", ".uv"
                ]
            }
        }
    
    def get(self, key: str, default=None):
        """获取配置值，支持点分隔符"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value


class ModelInterface(ABC):
    """模型接口抽象基类"""
    
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """获取文本 embedding"""
        pass
    
    @abstractmethod
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """批量获取 embedding"""
        pass
    
    @abstractmethod
    def rerank(self, query: str, documents: List[str]) -> List[float]:
        """对文档重新排序"""
        pass


class OllamaModelInterface(ModelInterface):
    """Ollama 模型接口实现"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.embedding_model = config.get("models.embedding.model_name")
        self.reranker_model = config.get("models.reranker.model_name")
        self.reranker_enabled = config.get("models.reranker.enabled", True)
        
        # 检查并拉取模型
        self._ensure_models_available()
    
    def _ensure_models_available(self):
        """检查模型是否可用，如果不可用则拉取"""
        # 检查 embedding 模型
        try:
            ollama.show(self.embedding_model)
        except:
            print(f"Embedding model {self.embedding_model} not found, pulling...")
            ollama.pull(self.embedding_model)
            print(f"Successfully pulled {self.embedding_model}")
        
        # 检查 reranker 模型（如果启用）
        if self.reranker_enabled:
            try:
                ollama.show(self.reranker_model)
            except:
                print(f"Reranker model {self.reranker_model} not found, pulling...")
                ollama.pull(self.reranker_model)
                print(f"Successfully pulled {self.reranker_model}")
    
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
        all_embeddings = []
        parallel_workers = self.config.get("document_processing.parallel_workers", 8)
        
        # 分批处理，每批并行
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            print(f"正在处理批次 {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}，包含 {len(batch_texts)} 个文档...")
            
            # 并行处理当前批次
            max_workers = min(parallel_workers, len(batch_texts))
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
                    embedding = future.result()
                    batch_embeddings[idx] = embedding
                
                all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def rerank(self, query: str, documents: List[str]) -> List[float]:
        """使用 Qwen3-Reranker 模型对文档重新排序"""
        if not self.reranker_enabled:
            return [1.0] * len(documents)
        
        if not documents:
            return []
        
        print(f"Reranking {len(documents)} documents using Qwen3-Reranker model...")
        
        try:
            # 尝试使用专门的 rerank 接口
            if hasattr(ollama, 'rerank'):
                response = ollama.rerank(
                    model=self.reranker_model,
                    query=query,
                    documents=documents
                )
                if response and 'scores' in response:
                    return response['scores']
                elif response and 'results' in response:
                    # 处理不同的返回格式
                    return [item.get('relevance_score', 0.5) for item in response['results']]
            
            # 如果没有专门的 rerank 接口，抛出异常
            raise NotImplementedError(
                f"Ollama does not support rerank interface for model {self.reranker_model}. "
                f"Please use a proper rerank API or disable rerank feature."
            )
            
        except Exception as e:
            print(f"Reranker model failed: {e}")
            raise e
    
    


class BaseRAGSystem:
    """基础 RAG 系统类"""
    
    def __init__(self, 
                 project_root: Optional[str] = None,
                 config_path: Optional[str] = None):
        """
        初始化RAG系统
        
        Args:
            project_root: 项目根目录（可选，使用配置文件中的 docs_root）
            config_path: 配置文件路径
        """
        self.config = RAGConfig(config_path)
        
        # 解析项目根目录
        self.project_root = self._resolve_project_root(project_root)
        
        # 解析数据库路径
        self.db_path = self._resolve_db_path()
        
        # 初始化模型接口
        self.model_interface = OllamaModelInterface(self.config)
        
        # 初始化数据库
        self._init_database()
        
        # 设置日志
        self._setup_logging()
    
    def _resolve_project_root(self, project_root: Optional[str]) -> Path:
        """解析项目根目录路径"""
        if project_root is not None:
            return Path(project_root)
        
        # 使用配置文件中的 docs_root
        docs_root = self.config.get("paths.docs_root", "..")
        
        # 如果是相对路径，相对于配置文件所在目录
        if not os.path.isabs(docs_root):
            config_dir = Path(self.config.config_path).parent if self.config.config_path else Path.cwd()
            return (config_dir / docs_root).resolve()
        else:
            return Path(docs_root)
    
    def _resolve_db_path(self) -> str:
        """解析数据库路径"""
        db_path = self.config.get("paths.db_path", "./chroma_db")
        
        # 如果是相对路径，相对于配置文件所在目录
        if not os.path.isabs(db_path):
            config_dir = Path(self.config.config_path).parent if self.config.config_path else Path.cwd()
            return str((config_dir / db_path).resolve())
        else:
            return db_path
    
    def _init_database(self):
        """初始化向量数据库"""
        collection_name = self.config.get("vectordb.collection_name", "story_knowledge")
        
        # 初始化ChromaDB客户端
        self.chroma_client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 创建或获取collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "GPT Story Maker knowledge base"}
        )
    
    def _setup_logging(self):
        """设置日志"""
        log_level = self.config.get("system.log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def chunk_by_section(self, content: str, file_path: str) -> List[DocumentChunk]:
        """使用markdown解析器按章节切片 - 支持多级标题"""
        import re
        
        lines = content.split('\n')
        chunks = []
        
        # 找到所有标题行
        headers = []
        for i, line in enumerate(lines):
            # 匹配 markdown 标题 (## 到 ######)
            header_match = re.match(r'^(#{2,6})\s+(.+)$', line.strip())
            if header_match:
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                headers.append({
                    'line': i,
                    'level': level,
                    'title': title,
                    'full_line': line
                })
        
        if not headers:
            # 如果没有标题，作为整个文档处理
            return self._create_single_chunk(content, file_path, "document")
        
        # 为每个标题创建独立的chunk
        for idx, header in enumerate(headers):
            # 确定这个section的结束位置
            start_line = header['line']
            
            # 找到下一个同级或更高级的标题
            end_line = len(lines)
            for next_header in headers[idx + 1:]:
                if next_header['level'] <= header['level']:
                    end_line = next_header['line']
                    break
            
            # 提取section内容
            section_lines = lines[start_line:end_line]
            section_content = '\n'.join(section_lines).strip()
            
            if section_content and len(section_content) > 20:  # 过滤太短的section
                chunk_id = self._generate_chunk_id(file_path, len(chunks), header['title'])
                
                chunks.append(DocumentChunk(
                    content=section_content,
                    metadata={
                        "file_path": str(file_path),
                        "chunk_type": "section",
                        "section_title": header['title'],
                        "section_level": header['level'],
                        "chunk_index": len(chunks),
                        "start_line": start_line + 1,
                        "end_line": end_line,
                        "file_type": self._get_file_type(file_path)
                    },
                    chunk_id=chunk_id
                ))
        
        return chunks
    
    def _create_single_chunk(self, content: str, file_path: str, chunk_type: str) -> List[DocumentChunk]:
        """创建单个chunk"""
        if not content.strip():
            return []
        
        chunk_id = self._generate_chunk_id(file_path, 0, chunk_type)
        return [DocumentChunk(
            content=content.strip(),
            metadata={
                "file_path": str(file_path),
                "chunk_type": chunk_type,
                "section_title": chunk_type,
                "chunk_index": 0,
                "start_line": 1,
                "end_line": len(content.split('\n')),
                "file_type": self._get_file_type(file_path)
            },
            chunk_id=chunk_id
        )]
    
    def chunk_by_paragraph(self, content: str, file_path: str) -> List[DocumentChunk]:
        """按段落切片（适合章节内容）"""
        chunks = []
        lines = content.split('\n')
        min_chunk_size = self.config.get("document_processing.chunking.min_chunk_size", 50)
        
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
                if len(para.strip()) < min_chunk_size:
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
    
    def _add_context(self, main_para: str, all_paragraphs: list, para_idx: int) -> str:
        """为段落添加上下文信息"""
        if not self.config.get("document_processing.chunking.add_context", True):
            return main_para.strip()
        
        context_chars = self.config.get("document_processing.chunking.context_chars", 200)
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
        doc_types = self.config.get("document_processing.doc_types", {})
        
        for doc_type, config in doc_types.items():
            patterns = config.get("path_patterns", [])
            for pattern in patterns:
                if any(part in path_str for part in pattern.split('/')):
                    return doc_type
        
        return "其他"
    
    def search_with_rerank(self, query: str, top_k: int = 5, filter_type: Optional[str] = None) -> List[Dict]:
        """搜索并使用 rerank 重新排序"""
        enable_rerank = self.config.get("search.enable_rerank", True)
        max_results = self.config.get("models.reranker.max_results", 10)
        
        # 如果启用 rerank，先获取更多候选结果
        if enable_rerank:
            initial_top_k = min(max_results, max(top_k * 2, 10))
        else:
            initial_top_k = top_k
        
        # 获取初始搜索结果（包含embeddings）
        initial_results = self._search_vector(query, initial_top_k, filter_type)
        
        if not initial_results or not enable_rerank:
            return initial_results[:top_k]
        
        # 使用 Qwen3-Reranker 模型进行 rerank
        documents = [result['content'] for result in initial_results]
        rerank_scores = self.model_interface.rerank(query, documents)
        
        # 合并分数并重新排序
        reranked_results = []
        for i, (result, rerank_score) in enumerate(zip(initial_results, rerank_scores)):
            result_copy = result.copy()
            result_copy['original_distance'] = result.get('distance', 0.0)
            result_copy['rerank_score'] = rerank_score
            result_copy['final_score'] = rerank_score  # 使用 rerank 分数作为最终分数
            reranked_results.append(result_copy)
        
        # 按 rerank 分数排序
        reranked_results.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        # 过滤低分结果
        score_threshold = self.config.get("models.reranker.score_threshold", 0.0)
        filtered_results = [r for r in reranked_results if r['rerank_score'] >= score_threshold]
        
        return filtered_results[:top_k]
    
    def _search_vector(self, query: str, top_k: int = 5, filter_type: Optional[str] = None) -> List[Dict]:
        """基础向量搜索"""
        # 使用缓存避免重复获取同一查询的embedding
        query_key = f"query_embed_{hash(query)}"
        if hasattr(self, '_query_embed_cache') and query_key in self._query_embed_cache:
            query_embedding = self._query_embed_cache[query_key]
        else:
            query_embedding = self.model_interface.get_embedding(query)
            # 简单缓存
            if not hasattr(self, '_query_embed_cache'):
                self._query_embed_cache = {}
            self._query_embed_cache[query_key] = query_embedding
            if len(self._query_embed_cache) > 10:
                oldest_key = next(iter(self._query_embed_cache))
                del self._query_embed_cache[oldest_key]
        
        # 构建过滤条件
        where_clause = {}
        if filter_type:
            where_clause["file_type"] = filter_type
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause if where_clause else None,
            include=['documents', 'metadatas', 'distances', 'embeddings']  # 获取存储的embeddings
        )
        
        # 格式化结果
        formatted_results = []
        for i in range(len(results['documents'][0])):
            formatted_results.append({
                'content': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i] if 'distances' in results else None,
                'embedding': results['embeddings'][0][i] if 'embeddings' in results else None  # 添加embedding
            })
        
        return formatted_results
    
    def search(self, query: str, top_k: int = 5, filter_type: Optional[str] = None) -> List[Dict]:
        """统一搜索接口"""
        return self.search_with_rerank(query, top_k, filter_type)
    
    def search_character(self, character_name: str, top_k: Optional[int] = None) -> List[Dict]:
        """搜索特定角色相关信息 - 基础实现"""
        if top_k is None:
            top_k = self.config.get("search.character_search.default_top_k", 3)
        
        expand_variants = self.config.get("search.character_search.expand_variants", True)
        
        if not expand_variants:
            # 简单搜索，不扩展变体
            return self.search(f"{character_name} 人格设定", top_k=top_k, filter_type="设定")
        
        # 扩展搜索词汇，包含更多变体
        character_variants = self._get_character_variants(character_name)
        
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
        unique_results = self._deduplicate_results(all_results)
        
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
    
    def search_plot_thread(self, thread_keyword: str, top_k: Optional[int] = None) -> List[Dict]:
        """搜索剧情线索 - 基础实现"""
        if top_k is None:
            top_k = self.config.get("search.default_top_k", 5)
        
        return self.search(
            f"{thread_keyword} 伏笔 剧情",
            top_k=top_k,
            filter_type="设定"
        )
    
    def _get_character_variants(self, character_name: str) -> List[str]:
        """获取角色名称变体 - 可以被子类重写"""
        # 根据常见人格命名模式生成搜索变体
        if character_name in ["小一", "1号", "林晚晚-1"]:
            return ["小一", "林晚晚-1", "病娇", "收藏家", "恋爱游戏"]
        elif character_name in ["小二", "2号", "林晚晚-2"]:
            return ["小二", "林晚晚-2", "吃货", "美食家", "消化器"]
        elif character_name in ["小七", "7号", "林晚晚-7"]:
            return ["小七", "林晚晚-7", "数学家", "计算姬", "公式女王"]
        elif character_name in ["小二十一", "21号", "林晚晚-21"]:
            return ["小二十一", "林晚晚-21", "二十一号", "幼态"]
        elif character_name in ["小三十五", "35号", "林晚晚-35"]:
            return ["小三十五", "林晚晚-35", "三十五号", "律师"]
        elif character_name in ["小四十二", "42号", "林晚晚-42"]:
            return ["小四十二", "林晚晚-42", "四十二号", "答案守护者"]
        else:
            return [character_name]
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """去重搜索结果"""
        import hashlib
        seen_ids = set()
        unique_results = []
        
        for result in results:
            content_hash = hashlib.md5(result['content'].encode()).hexdigest()
            if content_hash not in seen_ids:
                seen_ids.add(content_hash)
                unique_results.append(result)
        
        return unique_results
    
    def format_search_results(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """格式化搜索结果 - 统一的结果格式化逻辑"""
        formatted = []
        for result in results:
            # 优先使用 rerank 后的分数
            if "rerank_score" in result:
                relevance_score = result["rerank_score"]
                score_type = "rerank"
            elif "final_score" in result:
                relevance_score = result["final_score"]
                score_type = "final"
            elif "distance" in result:
                # 回退到原始向量距离（转换为相似度）
                relevance_score = 1.0 - result["distance"]
                score_type = "vector_similarity"
            else:
                relevance_score = 1.0
                score_type = "default"
            
            formatted.append({
                "file_path": result["metadata"]["file_path"],
                "section_title": result["metadata"].get("section_title", ""),
                "file_type": result["metadata"].get("file_type", ""),
                "chunk_type": result["metadata"].get("chunk_type", ""),
                "content": result["content"],
                "relevance_score": relevance_score,
                "score_type": score_type,  # 调试信息：显示使用的分数类型
                # 可选的详细分数信息
                "original_distance": result.get("original_distance"),
                "rerank_score": result.get("rerank_score"),
                "final_score": result.get("final_score")
            })
        return formatted