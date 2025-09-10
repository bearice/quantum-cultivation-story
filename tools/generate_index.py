#!/usr/bin/env python3
"""
文档索引生成器
结构：# TOC + # 文件路径（每个文件都是一级标题）
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Dict

def extract_sections_with_lines(file_path: str) -> List[Tuple[str, int, int]]:
    """
    使用markdown解析器提取章节和行号范围
    返回: [(标题, 起始行号, 结束行号), ...]
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"读取文件 {file_path} 失败: {e}")
        return []

    lines = content.split('\n')
    sections = []

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
                'title': title
            })

    if not headers:
        # 如果没有标题，整个文档作为一个section
        if content.strip():
            sections.append(("整个文档", 1, len(lines)))
        return sections

    # 为每个标题创建section记录
    for idx, header in enumerate(headers):
        start_line = header['line'] + 1  # 转换为1基准行号

        # 找到下一个同级或更高级的标题作为结束位置
        end_line = len(lines)
        for next_header in headers[idx + 1:]:
            if next_header['level'] <= header['level']:
                end_line = next_header['line']
                break

        # 构建完整的层级路径
        title_path = []
        current_level = header['level']

        # 从当前位置往前找，收集所有直接父级
        for i in range(idx - 1, -1, -1):
            parent_header = headers[i]
            if parent_header['level'] < current_level:
                title_path.insert(0, parent_header['title'])
                current_level = parent_header['level']

        # 添加当前标题
        title_path.append(header['title'])

        # 生成层级标题
        if len(title_path) > 1:
            hierarchical_title = " > ".join(title_path)
        else:
            hierarchical_title = header['title']

        sections.append((hierarchical_title, start_line, end_line))

    return sections


def collect_setting_files() -> Dict[str, List[Tuple[str, int, int]]]:
    """
    收集设定文档及其章节信息
    返回: {文件相对路径: [(章节标题, 起始行, 结束行), ...]}
    """
    settings_data = {}

    # 只收集设定目录文件
    settings_dir = Path("设定")
    if settings_dir.exists():
        for md_file in sorted(settings_dir.glob("**/*.md")):
            if md_file.name in ["内容索引.md", "README.md"]:
                continue

            relative_path = str(md_file.relative_to("."))
            sections = extract_sections_with_lines(str(md_file))
            if sections:
                settings_data[relative_path] = sections

    return settings_data


def generate_index_content(settings_data: Dict[str, List[Tuple[str, int, int]]]) -> str:
    """
    生成索引内容：# TOC + 每个文件作为一级section
    """
    content_lines = []

    # 第一步：生成内容并记录文件section在索引中的位置
    file_positions = {}  # {文件路径: (起始行号, 结束行号)}

    # 0. 文件结构说明
    content_lines.append("#索引结构\nTOC节：文件名→本文件内行号范围\n各文件分节：分节名称→原文件内行号范围")
    content_lines.append("")

    # 1. TOC部分（一级标题）
    content_lines.append("# TOC")
    content_lines.append("")

    for file_path in sorted(settings_data.keys()):
        content_lines.append(f"- {file_path} → PLACEHOLDER:{file_path}")

    content_lines.append("")

    # 2. 每个文件的详细索引（每个文件都是一级标题）
    for file_path, sections in sorted(settings_data.items()):
        # 记录这个文件section在索引中的起始位置
        start_pos = len(content_lines) + 1  # +1 因为行号从1开始

        content_lines.append(f"# {file_path}")
        content_lines.append("")

        for section_title, start_line, end_line in sections:
            content_lines.append(f"- {section_title} (第{start_line}-{end_line}行)")

        content_lines.append("")

        # 记录结束位置
        end_pos = len(content_lines)
        file_positions[file_path] = (start_pos, end_pos)

    # 第二步：替换TOC中的占位符
    final_lines = []
    for line in content_lines:
        if "PLACEHOLDER:" in line:
            # 提取文件路径
            placeholder_part = line.split("PLACEHOLDER:")[1]
            file_path = placeholder_part.strip()

            if file_path in file_positions:
                start_line, end_line = file_positions[file_path]
                # 替换占位符为实际行号范围
                final_lines.append(line.replace(f"PLACEHOLDER:{file_path}", f"第{start_line}-{end_line}行"))
            else:
                # 如果找不到，移除占位符部分
                final_lines.append(line.replace(f" → PLACEHOLDER:{file_path}", ""))
        else:
            final_lines.append(line)

    # 移除末尾的空行
    while final_lines and final_lines[-1] == "":
        final_lines.pop()

    return "\n".join(final_lines)


def main():
    """主函数"""
    print("开始生成设定文档索引...")

    # 确保在项目根目录运行
    if not os.path.exists("设定"):
        print("错误：请在项目根目录运行此脚本")
        return

    # 收集设定文件数据
    settings_data = collect_setting_files()

    if not settings_data:
        print("未找到任何设定文档")
        return

    # 生成索引内容
    index_content = generate_index_content(settings_data)

    # 写入索引文件
    index_file = "设定/内容索引.md"
    try:
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(index_content)

        print(f"✅ 索引已生成: {index_file}")

        # 显示统计信息
        total_files = len(settings_data)
        total_sections = sum(len(sections) for sections in settings_data.values())
        print(f"📊 统计: {total_files} 个设定文档, {total_sections} 个章节")

    except Exception as e:
        print(f"❌ 写入索引文件失败: {e}")


if __name__ == "__main__":
    main()
