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

# 编码修复
if sys.platform == "win32":
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

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
        """初始化RAG系统"""
        try:
            # 确保在正确的工作目录
            project_root = os.getcwd()
            if project_root.endswith('tools'):
                project_root = os.path.dirname(project_root)
                os.chdir(project_root)
            
            self.rag = StoryRAGSystem(project_root=project_root)
        except Exception as e:
            print(f"Warning: Failed to initialize RAG system: {e}", file=sys.stderr)
            self.rag = StoryRAGSystem()  # dummy implementation
    
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
            results = self.rag.search(query, top_k=top_k, filter_type=filter_type)
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
            results = self.rag.search_character(character_name, top_k=top_k)
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
            results = self.rag.search_plot_thread(thread_keyword, top_k=top_k)
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
    server = MCPServer()
    
    # 读取stdin输入
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            request = json.loads(line)
            response = await server.handle_request(request)
            
            # 输出响应
            print(json.dumps(response, ensure_ascii=False), flush=True)
        
        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(error_response, ensure_ascii=False), flush=True)
        
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())