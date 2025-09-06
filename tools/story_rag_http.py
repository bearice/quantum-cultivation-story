#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Story RAG HTTP Server - 用于调试MCP问题
"""

import sys
import os
import json
import traceback
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

# 设置编码
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('story_rag_debug.log', encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

try:
    from flask import Flask, request, jsonify
except ImportError:
    logger.error("Flask not installed. Installing...")
    os.system("uv add flask")
    from flask import Flask, request, jsonify

try:
    from story_rag_system import StoryRAGSystem
    logger.info("Successfully imported StoryRAGSystem")
except ImportError as e:
    logger.error(f"Failed to import StoryRAGSystem: {e}")
    # 创建dummy实现
    class StoryRAGSystem:
        def __init__(self, project_root="."):
            logger.warning("Using dummy StoryRAGSystem")
            self.project_root = project_root
            
        def search(self, query, top_k=5, filter_type=None):
            logger.info(f"Dummy search: query={query}, top_k={top_k}, filter_type={filter_type}")
            return [{"content": "Dummy result", "metadata": {"file_path": "dummy"}}]
        
        def search_character(self, character_name, top_k=3):
            logger.info(f"Dummy character search: {character_name}")
            return [{"content": f"Dummy character info for {character_name}", "metadata": {"file_path": "dummy"}}]
        
        def search_plot_thread(self, thread_keyword, top_k=5):
            logger.info(f"Dummy plot search: {thread_keyword}")
            return [{"content": f"Dummy plot info for {thread_keyword}", "metadata": {"file_path": "dummy"}}]

app = Flask(__name__)

class StoryRAGHTTP:
    def __init__(self):
        logger.info("Initializing StoryRAGHTTP...")
        self.rag = None
        self.project_root = self._get_project_root()
        logger.info(f"Project root: {self.project_root}")
    
    def _get_project_root(self):
        """获取项目根目录"""
        current = Path.cwd()
        logger.debug(f"Current working directory: {current}")
        
        if current.name == 'tools':
            root = current.parent
        else:
            root = current
            
        logger.info(f"Using project root: {root}")
        return str(root)
    
    def _get_rag(self):
        """延迟初始化RAG系统"""
        if self.rag is None:
            logger.info("Initializing RAG system...")
            try:
                start_time = datetime.now()
                self.rag = StoryRAGSystem(project_root=self.project_root)
                end_time = datetime.now()
                logger.info(f"RAG system initialized successfully in {end_time - start_time}")
            except Exception as e:
                logger.error(f"Failed to initialize RAG system: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        return self.rag
    
    def search_story_knowledge(self, query: str, top_k: int = 5, filter_type: Optional[str] = None):
        """搜索故事知识库"""
        logger.info(f"Searching story knowledge: query='{query}', top_k={top_k}, filter_type={filter_type}")
        
        try:
            start_time = datetime.now()
            rag = self._get_rag()
            init_time = datetime.now()
            logger.debug(f"RAG initialization took: {init_time - start_time}")
            
            results = rag.search(query, top_k=top_k, filter_type=filter_type)
            search_time = datetime.now()
            logger.debug(f"Search took: {search_time - init_time}")
            
            logger.info(f"Found {len(results)} results")
            for i, result in enumerate(results[:2]):  # 只记录前2个结果避免日志过长
                logger.debug(f"Result {i}: {result['metadata'].get('file_path', 'unknown')} - {len(result['content'])} chars")
            
            formatted = self._format_results(results)
            format_time = datetime.now()
            logger.debug(f"Formatting took: {format_time - search_time}")
            
            return {
                "success": True,
                "query": query,
                "results": formatted,
                "total_found": len(results),
                "timing": {
                    "init_ms": (init_time - start_time).total_seconds() * 1000,
                    "search_ms": (search_time - init_time).total_seconds() * 1000,
                    "format_ms": (format_time - search_time).total_seconds() * 1000
                }
            }
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "query": query,
                "results": []
            }
    
    def _format_results(self, results):
        """格式化搜索结果"""
        logger.debug(f"Formatting {len(results)} results...")
        formatted = []
        for result in results:
            try:
                formatted_result = {
                    "file_path": result["metadata"]["file_path"],
                    "section_title": result["metadata"].get("section_title", ""),
                    "file_type": result["metadata"].get("file_type", ""),
                    "content": result["content"][:500] + "..." if len(result["content"]) > 500 else result["content"],  # 截断长内容
                    "content_length": len(result["content"]),
                    "relevance_score": 1.0 - result.get("distance", 0.0) if "distance" in result else 1.0
                }
                formatted.append(formatted_result)
            except Exception as e:
                logger.error(f"Error formatting result: {e}")
                formatted.append({"error": str(e), "raw_result": str(result)})
        
        return formatted

def format_search_results_text(result, tool_name, arguments):
    """格式化搜索结果为文本"""
    if not result.get("success"):
        return f"搜索失败: {result.get('error', '未知错误')}"
    
    results = result.get("results", [])
    if not results:
        query = arguments.get("query") or arguments.get("character_name") or arguments.get("thread_keyword")
        return f"未找到关于 '{query}' 的相关信息"
    
    # 构建格式化输出
    lines = []
    query = arguments.get("query") or arguments.get("character_name") or arguments.get("thread_keyword")
    lines.append(f"=== 搜索结果: {query} ===\n")
    
    for i, item in enumerate(results, 1):
        lines.append(f"{i}. 来源: {item['file_path']}")
        if item.get('section_title'):
            lines.append(f"   标题: {item['section_title']}")
        if item.get('file_type'):
            lines.append(f"   类型: {item['file_type']}")
        if item.get('relevance_score') is not None:
            lines.append(f"   相关度: {item['relevance_score']:.3f}")
        
        # 显示内容
        content = item['content']
        lines.append(f"   内容: {content}")
        if item.get('content_length', len(content)) > len(content):
            lines.append(f"   [完整内容长度: {item['content_length']} 字符]")
        lines.append("")
    
    # 添加时间统计（如果有）
    timing = result.get("timing")
    if timing:
        lines.append(f"搜索耗时: 初始化 {timing.get('init_ms', 0):.1f}ms, "
                    f"搜索 {timing.get('search_ms', 0):.1f}ms, "
                    f"格式化 {timing.get('format_ms', 0):.1f}ms")
    
    return "\n".join(lines)

# 全局实例
rag_server = StoryRAGHTTP()

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    logger.info("Health check requested")
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "project_root": rag_server.project_root
    })

@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    """MCP over HTTP接口"""
    data = request.json
    logger.info(f"MCP request: {data}")
    
    method = data.get("method")
    params = data.get("params", {})
    request_id = data.get("id")
    
    try:
        if method == "initialize":
            return jsonify({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "story-rag-http",
                        "version": "1.0.0"
                    }
                }
            })
        
        elif method == "tools/list":
            return jsonify({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "search_story_knowledge",
                            "description": "🔍 搜索GPT Story Maker完整故事知识库。用于查找：世界观设定、角色资料、剧情大纲、章节内容、人物关系、修炼体系、哲学主题等。支持中文关键词搜索，返回完整且准确的原文内容。适合回答关于故事背景、角色性格、剧情发展、设定细节的问题。",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "搜索查询内容。例子：'林晚晚的人格机制'、'修炼等级体系'、'第二十一章剧情'、'量子叠加原理'、'系统009的对话格式'、'人格融合规则'、'核心冲突与主题'等"
                                    },
                                    "top_k": {
                                        "type": "integer",
                                        "description": "返回结果数量，默认5。建议：详细查询用1-2，概览用3-5",
                                        "default": 5
                                    },
                                    "filter_type": {
                                        "type": "string",
                                        "description": "文档类型过滤：'设定'(大纲、人物、世界观)、'章节'(具体剧情内容)、'支线'(跨卷剧情规划)",
                                        "enum": ["设定", "章节", "支线"]
                                    }
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "search_character_info",
                            "description": "👤 专门搜索角色详细信息。优化用于查找特定角色的人格设定、性格特点、能力描述、对话风格、出场情节等。比通用搜索更精准地定位到人物相关内容，包括人格图鉴、角色档案、对话规范等。",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "character_name": {
                                        "type": "string",
                                        "description": "角色名称。支持多种形式：'小一'、'林晚晚-1'、'病娇'、'小七'、'小二十一'、'二十一号'、'系统009'、'009'、'林月华'、'顾云霄'等"
                                    },
                                    "top_k": {
                                        "type": "integer",
                                        "description": "返回结果数量，默认3。通常1-2个结果就足够获得角色的核心信息",
                                        "default": 3
                                    }
                                },
                                "required": ["character_name"]
                            }
                        },
                        {
                            "name": "search_plot_threads",
                            "description": "🧵 搜索剧情线索、伏笔设计和支线规划。专门用于查找跨章节的剧情发展、伏笔追踪、支线剧情安排、角色成长轨迹等。重点搜索伏笔追踪表、支线设计文档、长期规划等内容。",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "thread_keyword": {
                                        "type": "string",
                                        "description": "剧情线索关键词。例如：'多元宇宙'、'观测者实验'、'量子叠加'、'归一者'、'人格融合'、'修炼突破'、'感情线发展'、'世界观揭示'等"
                                    },
                                    "top_k": {
                                        "type": "integer",
                                        "description": "返回结果数量，默认5。剧情线索通常需要更多上下文，建议3-5个结果",
                                        "default": 5
                                    }
                                },
                                "required": ["thread_keyword"]
                            }
                        }
                    ]
                }
            })
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "search_story_knowledge":
                result = rag_server.search_story_knowledge(
                    arguments.get("query", ""),
                    arguments.get("top_k", 5),
                    arguments.get("filter_type")
                )
            elif tool_name == "search_character_info":
                result = rag_server.search_story_knowledge(
                    arguments.get("character_name", ""),
                    arguments.get("top_k", 3),
                    "设定"
                )
            elif tool_name == "search_plot_threads":
                result = rag_server.search_story_knowledge(
                    arguments.get("thread_keyword", ""),
                    arguments.get("top_k", 5),
                    "设定"
                )
            else:
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                })
            
            # 格式化结果
            if result.get("success"):
                content_text = format_search_results_text(result, tool_name, arguments)
            else:
                content_text = f"搜索失败: {result.get('error', 'Unknown error')}"
            
            return jsonify({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": content_text
                        }
                    ]
                }
            })
        
        else:
            return jsonify({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            })
    
    except Exception as e:
        logger.error(f"MCP request failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        })

@app.route('/search', methods=['POST'])
def search():
    """直接搜索接口（非MCP）"""
    data = request.json
    logger.info(f"Search request: {data}")
    
    query = data.get('query', '')
    top_k = data.get('top_k', 5)
    filter_type = data.get('filter_type')
    
    if not query:
        return jsonify({"success": False, "error": "Missing query parameter"}), 400
    
    result = rag_server.search_story_knowledge(query, top_k, filter_type)
    
    logger.info(f"Returning result: success={result['success']}, results_count={len(result.get('results', []))}")
    return jsonify(result)

@app.route('/debug', methods=['GET'])
def debug():
    """调试信息"""
    logger.info("Debug info requested")
    
    debug_info = {
        "project_root": rag_server.project_root,
        "rag_initialized": rag_server.rag is not None,
        "working_directory": os.getcwd(),
        "python_path": sys.path[:3],  # 只显示前3个路径
        "environment": {
            "PYTHONIOENCODING": os.environ.get('PYTHONIOENCODING'),
            "platform": sys.platform
        }
    }
    
    # 尝试初始化RAG并获取更多信息
    try:
        rag = rag_server._get_rag()
        debug_info["rag_status"] = "initialized"
        
        # 检查是否能访问数据库
        if hasattr(rag, 'collection'):
            try:
                count = rag.collection.count()
                debug_info["database_count"] = count
            except Exception as e:
                debug_info["database_error"] = str(e)
    except Exception as e:
        debug_info["rag_error"] = str(e)
        debug_info["rag_traceback"] = traceback.format_exc()
    
    return jsonify(debug_info)

if __name__ == "__main__":
    logger.info("Starting Story RAG HTTP Server...")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python path: {sys.path[:5]}")
    
    # 启动服务器
    app.run(host='127.0.0.1', port=5555, debug=True)