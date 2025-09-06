# GPT Story Maker RAG 系统

## 快速启动

### 1. 安装依赖
```bash
cd tools
uv sync
```

### 2. 启动 Ollama 并下载 embedding 模型
```bash
# 启动 ollama 服务
ollama serve

# 下载 embedding 模型（推荐）
ollama pull nomic-embed-text
```

### 3. 初始化向量数据库
```bash
cd ..  # 回到项目根目录
# 默认4线程并行处理
uv run --project tools story_rag_system.py --index

# 如果GPU性能强劲，可增加并行数
uv run --project tools story_rag_system.py --index --parallel-workers 8
```

## 使用示例

### 查找角色信息
```bash
# 搜索小一（病娇人格）的相关设定
uv run --project tools story_rag_system.py --character "小一"

# 搜索林晚晚-7（数学人格）的信息
uv run --project tools story_rag_system.py --character "小七"
```

### 通用搜索
```bash
# 搜索系统009的对话风格
uv run --project tools story_rag_system.py --query "系统009 对话格式"

# 搜索修炼体系相关内容
uv run --project tools story_rag_system.py --query "筑基境 金丹期"

# 搜索特定剧情线索
uv run --project tools story_rag_system.py --query "多元宇宙观测者实验"
```

## Python API 使用

```python
from tools.story_rag_system import StoryRAGSystem

# 初始化系统
rag = StoryRAGSystem()

# 搜索角色信息
char_info = rag.search_character("小一", top_k=3)
for info in char_info:
    print(f"来源: {info['metadata']['file_path']}")
    print(f"内容: {info['content'][:200]}...")

# 通用搜索
results = rag.search("病娇特征 占有欲", top_k=5)

# 获取章节上下文
context = rag.get_context_for_chapter(volume=1, chapter=5)
```

## 切片策略说明

系统针对不同类型文档采用不同的切片策略：

### 设定文档（按章节切片）
- `设定/*.md` - 按 # ## ### 标题分割
- 每个章节作为独立语义单元
- 适合精确查找特定设定项

### 章节文档（按段落切片） 
- `Vol*/*.md` - 按段落分割
- 保持对话和描述的完整性
- 适合查找具体情节和角色表现

### 支线设计（按章节切片）
- `设定/跨卷支线剧情设计/*.md`
- 按规划章节分割
- 适合查找长期剧情安排

## 数据库管理

```bash
# 强制重建索引（文档更新后）
uv run --project tools story_rag_system.py --index

# 清空数据库重新开始
rm -rf chroma_db/
uv run --project tools story_rag_system.py --index
```

## 常见查询模式

### 角色一致性检查
```python
# 检查小一在不同章节中的表现是否一致
results = rag.search("小一 病娇 占有欲 林晚晚")
```

### 伏笔追踪
```python
# 搜索特定伏笔线索的发展
results = rag.search_plot_thread("多元宇宙", top_k=10)
```

### 世界观查证
```python
# 查找修炼体系的详细设定
results = rag.search("筑基境界 金丹期 修炼体系", top_k=5, filter_type="设定")
```

## 优化建议

1. **模型选择**: `nomic-embed-text` 对中文支持较好，如果有更好的中文embedding模型可替换
2. **切片大小**: 当前按段落切片，可根据实际效果调整
3. **搜索精度**: 可以通过调整 `top_k` 和相似度阈值来优化结果
4. **增量更新**: 支持检测文件变化，只重新索引修改的文档