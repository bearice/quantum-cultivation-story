#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT Story Maker RAG MCP Server
为 Claude Code 提供故事知识库查询功能
"""

import json
import sys
import asyncio
from typing import Any, Dict, List, Optional
import os
import traceback

# 设置编码环境变量 - 简单方式
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'

try:
    from story_rag_system import StoryRAGSystem
except ImportError:
    # 如果无法导入，创建一个dummy实现
    class StoryRAGSystem:
        def __init__(self):
            pass
        def search(self, query, top_k=5, filter_type=None):
            return [{"content": "RAG系统未正确安装", "metadata": {"file_path": "error"}}]
        def search_character(self, character_name, top_k=3):
            return [{"content": "RAG系统未正确安装", "metadata": {"file_path": "error"}}]
        def search_plot_thread(self, thread_keyword, top_k=5):
            return [{"content": "RAG系统未正确安装", "metadata": {"file_path": "error"}}]


class StoryRAGMCP:
    """Story RAG MCP Server"""
    
    def __init__(self):
        self.rag = None
        self._initialize_rag()
    
    def _initialize_rag(self):
        """延迟初始化RAG系统"""
        # 延迟初始化，只在第一次使用时创建
        self.rag = None
        self.project_root = os.getcwd()
        if self.project_root.endswith('tools'):
            self.project_root = os.path.dirname(self.project_root)
    
    def _get_rag(self):
        """获取RAG实例，延迟初始化"""
        if self.rag is None:
            try:
                self.rag = StoryRAGSystem(project_root=self.project_root)
                print("RAG system initialized", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Failed to initialize RAG system: {e}", file=sys.stderr)
                # 创建dummy实现
                class DummyRAG:
                    def search(self, *args, **kwargs):
                        return [{"content": f"RAG系统未正确初始化: {e}", "metadata": {"file_path": "error"}}]
                    def search_character(self, *args, **kwargs):
                        return [{"content": f"RAG系统未正确初始化: {e}", "metadata": {"file_path": "error"}}]
                    def search_plot_thread(self, *args, **kwargs):
                        return [{"content": f"RAG系统未正确初始化: {e}", "metadata": {"file_path": "error"}}]
                self.rag = DummyRAG()
        return self.rag
    
    def _format_results(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """格式化搜索结果"""
        formatted = []
        for result in results:
            formatted.append({
                "file_path": result["metadata"]["file_path"],
                "section_title": result["metadata"].get("section_title", ""),
                "file_type": result["metadata"].get("file_type", ""),
                "content": result["content"],
                "relevance_score": 1.0 - result.get("distance", 0.0) if "distance" in result else 1.0
            })
        return formatted
    
    async def search_story_knowledge(self, query: str, top_k: int = 5, filter_type: Optional[str] = None) -> Dict[str, Any]:
        """搜索故事知识库"""
        try:
            rag = self._get_rag()
            results = rag.search(query, top_k=top_k, filter_type=filter_type)
            return {
                "success": True,
                "query": query,
                "results": self._format_results(results),
                "total_found": len(results)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": []
            }
    
    async def search_character_info(self, character_name: str, top_k: int = 3) -> Dict[str, Any]:
        """搜索角色信息"""
        try:
            rag = self._get_rag()
            results = rag.search_character(character_name, top_k=top_k)
            return {
                "success": True,
                "character": character_name,
                "results": self._format_results(results),
                "total_found": len(results)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "character": character_name,
                "results": []
            }
    
    async def search_plot_threads(self, thread_keyword: str, top_k: int = 5) -> Dict[str, Any]:
        """搜索剧情线索"""
        try:
            rag = self._get_rag()
            results = rag.search_plot_thread(thread_keyword, top_k=top_k)
            return {
                "success": True,
                "thread_keyword": thread_keyword,
                "results": self._format_results(results),
                "total_found": len(results)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "thread_keyword": thread_keyword,
                "results": []
            }


# MCP Protocol Implementation
class MCPServer:
    def __init__(self):
        self.story_rag = StoryRAGMCP()
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理MCP请求"""
        try:
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": "search_story_knowledge",
                                "description": "搜索GPT Story Maker故事知识库，包括设定、章节内容、人物信息等",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "搜索查询，可以是角色名、剧情关键词、设定概念等"
                                        },
                                        "top_k": {
                                            "type": "integer",
                                            "description": "返回结果数量，默认5",
                                            "default": 5
                                        },
                                        "filter_type": {
                                            "type": "string",
                                            "description": "过滤文档类型：设定、章节、支线",
                                            "enum": ["设定", "章节", "支线"]
                                        }
                                    },
                                    "required": ["query"]
                                }
                            },
                            {
                                "name": "search_character_info",
                                "description": "专门搜索角色信息，包括人格设定、对话风格、能力特点等",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "character_name": {
                                            "type": "string",
                                            "description": "角色名称，如：小一、林晚晚-1、病娇、小七、系统009等"
                                        },
                                        "top_k": {
                                            "type": "integer",
                                            "description": "返回结果数量，默认3",
                                            "default": 3
                                        }
                                    },
                                    "required": ["character_name"]
                                }
                            },
                            {
                                "name": "search_plot_threads",
                                "description": "搜索剧情线索和伏笔信息",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "thread_keyword": {
                                            "type": "string",
                                            "description": "剧情线索关键词，如：多元宇宙、观测者实验、量子叠加等"
                                        },
                                        "top_k": {
                                            "type": "integer",
                                            "description": "返回结果数量，默认5",
                                            "default": 5
                                        }
                                    },
                                    "required": ["thread_keyword"]
                                }
                            }
                        ]
                    }
                }
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "search_story_knowledge":
                    result = await self.story_rag.search_story_knowledge(**arguments)
                elif tool_name == "search_character_info":
                    result = await self.story_rag.search_character_info(**arguments)
                elif tool_name == "search_plot_threads":
                    result = await self.story_rag.search_plot_threads(**arguments)
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
                
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, ensure_ascii=False, indent=2)
                            }
                        ]
                    }
                }
            
            elif method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "story-rag-mcp",
                            "version": "1.0.0"
                        }
                    }
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
        
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }


async def main():
    """MCP服务器主函数"""
    import logging
    
    # 设置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - MCP - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('story_rag_mcp.log', encoding='utf-8'),
            logging.StreamHandler(sys.stderr)
        ]
    )
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting MCP server initialization...")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Platform: {sys.platform}")
        
        server = MCPServer()
        logger.info("MCP Server initialized successfully")
        print("MCP Server ready", file=sys.stderr, flush=True)
        
        # 读取stdin输入
        logger.info("Starting main loop, waiting for stdin input...")
        while True:
            try:
                logger.debug("Waiting for input...")
                line = input()
                logger.debug(f"Received input: {line[:100]}...")
                
                if not line or line.strip() == "":
                    logger.debug("Empty line, continuing...")
                    continue
                
                request = json.loads(line)
                logger.info(f"Processing request: {request.get('method', 'unknown')}")
                
                response = await server.handle_request(request)
                logger.debug(f"Response generated: {str(response)[:200]}...")
                
                # 输出响应 - 尝试UTF-8编码输出
                response_json = json.dumps(response, ensure_ascii=False, separators=(',', ':'))
                # 直接写入到stdout.buffer以确保UTF-8编码
                if hasattr(sys.stdout, 'buffer'):
                    sys.stdout.buffer.write(response_json.encode('utf-8'))
                    sys.stdout.buffer.write(b'\n')
                    sys.stdout.buffer.flush()
                else:
                    print(response_json, flush=True)
                logger.debug("Response sent")
            
            except EOFError:
                logger.info("EOF received, shutting down normally")
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}, input: {line}")
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                error_json = json.dumps(error_response, ensure_ascii=False, separators=(',', ':'))
                if hasattr(sys.stdout, 'buffer'):
                    sys.stdout.buffer.write(error_json.encode('utf-8'))
                    sys.stdout.buffer.write(b'\n')
                    sys.stdout.buffer.flush()
                else:
                    print(error_json, flush=True)
            
            except Exception as e:
                logger.error(f"Error processing request: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}\nTraceback: {traceback.format_exc()}"
                    }
                }
                error_json = json.dumps(error_response, ensure_ascii=False, separators=(',', ':'))
                if hasattr(sys.stdout, 'buffer'):
                    sys.stdout.buffer.write(error_json.encode('utf-8'))
                    sys.stdout.buffer.write(b'\n')
                    sys.stdout.buffer.flush()
                else:
                    print(error_json, flush=True)
                
    except Exception as e:
        logger.error(f"Fatal error in MCP server: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"FATAL: {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    asyncio.run(main())