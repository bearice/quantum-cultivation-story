# Story RAG MCP Server 配置指南

## 概述

Story RAG MCP 为 Claude Code 提供故事知识库搜索功能，可以直接在 Claude Code 中查询：
- 角色人格设定
- 剧情线索和伏笔
- 世界观和背景信息
- 章节内容片段

## 安装步骤

### 1. 确保 RAG 系统正常工作

```bash
# 检查依赖
cd tools
uv sync

# 确保向量数据库已建立索引
cd ..
uv run --project tools story_rag_system.py --index

# 测试搜索功能
uv run --project tools story_rag_system.py --character "小一"
```

### 2. 安装 MCP 服务器

在 Claude Code 中运行：

```bash
claude mcp add story-rag file://$(pwd)/tools/story_rag_mcp.py --config $(pwd)/tools/mcp_config.json
```

或者手动配置：

```bash
# 方法1：本地项目安装（推荐）
claude mcp add story-rag -s local -- uv run --project tools tools/story_rag_mcp.py

# 方法2：用户全局安装  
claude mcp add story-rag -s user -- python tools/story_rag_mcp.py

# 方法3：使用绝对路径（Windows）
claude mcp add story-rag -s user -- python "C:\Users\bearice\Workspace\gpt-story-maker\tools\story_rag_mcp.py"
```

### 3. 验证安装

在 Claude Code 中应该能看到三个新工具：
- `search_story_knowledge` - 通用知识库搜索
- `search_character_info` - 角色信息专门搜索  
- `search_plot_threads` - 剧情线索搜索

## 使用示例

### 在 Claude Code 中的对话示例

```
用户: 小一的病娇特征有哪些？

Claude 会自动调用: search_character_info(character_name="小一")

返回结果包含:
- 来自世界: 恋爱游戏世界
- 能力: 所有人好感度MAX，魅惑术  
- 性格特点: 想把所有人关进小黑屋收藏
- 经典台词: "云霄哥哥，你受伤了呢...让我来治疗你吧，永远...永远地治疗..."
```

```
用户: 多元宇宙观测者实验的设定是什么？

Claude 会自动调用: search_plot_threads(thread_keyword="多元宇宙观测者实验")

返回相关伏笔和设定信息
```

```
用户: 查找第25章的剧情要点

Claude 会自动调用: search_story_knowledge(query="第25章", filter_type="章节")

返回第25章的详细剧情信息
```

## 工具详细说明

### search_story_knowledge
**功能**: 通用知识库搜索
**参数**:
- `query` (必填): 搜索关键词
- `top_k` (可选): 返回结果数量，默认5
- `filter_type` (可选): 过滤类型，可选"设定"、"章节"、"支线"

**使用场景**: 
- 查找特定概念或设定
- 搜索章节内容
- 寻找世界观信息

### search_character_info  
**功能**: 专门搜索角色信息，包含智能别名识别
**参数**:
- `character_name` (必填): 角色名称
- `top_k` (可选): 返回结果数量，默认3

**支持的角色名**:
- `小一`、`林晚晚-1`、`病娇` → 病娇人格
- `小二`、`林晚晚-2`、`吃货` → 吃货人格  
- `小七`、`林晚晚-7`、`数学家`、`计算姬` → 数学家人格
- `系统009`、`009` → 系统角色
- 其他人格和角色...

### search_plot_threads
**功能**: 搜索剧情线索和伏笔
**参数**:
- `thread_keyword` (必填): 剧情关键词
- `top_k` (可选): 返回结果数量，默认5

**典型关键词**:
- "多元宇宙观测者实验"
- "量子叠加态"  
- "42个房间的秘密"
- "归一者"
- "青云宗"

## 故障排除

### 常见问题

**1. MCP 服务器无法启动**
```bash
# 检查Python路径
which python
python --version

# 检查依赖安装
cd tools && uv sync
```

**2. 搜索结果为空**
```bash
# 重建索引
uv run --project tools story_rag_system.py --index --parallel-workers 4
```

**3. 编码错误**
确保在项目根目录运行，不要在 `tools` 目录内运行MCP服务器

**4. 权限问题（Windows）**
可能需要使用完整的绝对路径：
```bash
claude mcp add story-rag -s user -- python "C:\Users\bearice\Workspace\gpt-story-maker\tools\story_rag_mcp.py"
```

### 调试模式

测试 MCP 服务器是否正常工作：
```bash
cd tools
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | python story_rag_mcp.py
```

应该返回可用工具列表。

## 预期效果

安装成功后，在 Claude Code 中：

1. **智能角色查询** - 询问任何角色信息，自动匹配最相关的设定
2. **剧情一致性检查** - 快速查找相关伏笔和设定，确保写作一致性  
3. **设定快速查证** - 不需要手动翻找文档，直接询问即可获得准确信息
4. **创作辅助** - 写作时可随时查询角色台词风格、能力设定等

这将大幅提升你的创作效率和故事一致性！