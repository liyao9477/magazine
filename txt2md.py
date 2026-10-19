#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_outline.py —— 从自然语言段落中自动识别层级并编号
用法: python auto_outline.py
     遍历本脚本所在目录下所有 .txt 文件，转换结果保存到 md 文件夹
"""

import re
from pathlib import Path
from typing import List, Tuple

# ==================== 配置区（按需调整）====================

MAX_HEADING_LEN = 40          # 超过此长度不视为标题
MAX_COMMAS = 2                # 标题里最多允许多少个逗号

# 不以这些标点结尾 → 才可能是标题（问号除外，问句可以是标题）
NOT_HEADING_END = '。；;：:'

# 列表项前缀
LIST_PREFIX = re.compile(
    r'^\s*(?:\d+[、.．)]|[•·▪◦※]|[（(]\d+[)）]|[一二三四五六七八九十]+[、.．)])'
)

# 一级标题：主问题 / 全文总纲
LV1_PATTERNS = [
    re.compile(r'[?？]\s*$'),
    re.compile(r'^(为什么|如何|什么是|是什么|如何理解|论|浅谈)'),
]

# 二级标题：宏观议题
LV2_RE = re.compile(
    r'(总论|概述|综述|背景|原因|缘起|由来|意义|影响|结论|'
    r'总结|总纲|导论|问题|特征|特点|脉络|本质|核心背景|关键原因)'
)


# ==================== 标题判定 ====================

def is_heading(s: str) -> bool:
    s = s.strip()
    if not s or len(s) > MAX_HEADING_LEN:
        return False
    if s[-1] in NOT_HEADING_END:
        return False
    if LIST_PREFIX.match(s):
        return False
    if s.count('，') + s.count('、') + s.count(',') > MAX_COMMAS:
        return False
    return True


def guess_level(s: str) -> int:
    for pat in LV1_PATTERNS:
        if pat.search(s):
            return 1
    if LV2_RE.search(s):
        return 2
    return 3


# ==================== 文本切块 ====================

Block = Tuple[str, str]  # ('heading' | 'text' | 'list', 内容)


def split_blocks(text: str) -> List[Block]:
    text = text.replace('\u200b', '')  # 去掉零宽空格
    blocks: List[Block] = []

    for chunk in re.split(r'\n\s*\n', text):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = [l.strip() for l in chunk.splitlines() if l.strip()]
        if not lines:
            continue

        # 单行块
        if len(lines) == 1:
            line = lines[0]
            if is_heading(line):
                blocks.append(('heading', line))
            elif LIST_PREFIX.match(line):
                blocks.append(('list', line))
            else:
                blocks.append(('text', line))
            continue

        # 多行块：每行都以句末标点结尾 → 视为列表
        if all(l[-1] in '。！？' for l in lines):
            for l in lines:
                blocks.append(('list', l))
            continue

        # 否则：首行可能是标题，其余按内容归类
        first = lines[0]
        if is_heading(first) and len(first) < 25:
            blocks.append(('heading', first))
            rest = lines[1:]
        else:
            rest = lines
        for l in rest:
            kind = 'list' if LIST_PREFIX.match(l) else 'text'
            blocks.append((kind, l))

    return blocks


# ==================== 层级重映射 ====================

def assign_levels(blocks: List[Block]) -> List[int]:
    """给每个 heading 块分配最终层级（1-based，连续不跳级）"""
    raw = [guess_level(c) for k, c in blocks if k == 'heading']
    if not raw:
        return []
    present = sorted(set(raw))
    remap = {old: new for new, old in enumerate(present, start=1)}
    return [remap[r] for r in raw]


# ==================== 主转换 ====================

def convert(text: str) -> str:
    blocks = split_blocks(text)
    levels = assign_levels(blocks)

    if not levels:
        # 没有识别到标题，只整理段落
        return '\n\n'.join(c for k, c in blocks if k == 'text') + '\n'

    max_depth = max(levels)
    counters = [0] * max_depth
    h_idx = 0

    out: List[str] = []
    para_buf: List[str] = []
    list_buf: List[str] = []

    def flush_para():
        if para_buf:
            out.append(' '.join(para_buf))
            out.append('')
            para_buf.clear()

    def flush_list():
        if list_buf:
            for i, item in enumerate(list_buf, start=1):
                out.append(f'{i}. {LIST_PREFIX.sub("", item)}')
            out.append('')
            list_buf.clear()

    def flush_all():
        flush_para()
        flush_list()

    for kind, content in blocks:
        if kind == 'heading':
            flush_all()
            lv = levels[h_idx]
            h_idx += 1
            counters[lv - 1] += 1
            for i in range(lv, max_depth):
                counters[i] = 0
            num = '.'.join(str(c) for c in counters[:lv])
            out.append('#' * lv + f' {num} {content}')
            out.append('')
        elif kind == 'list':
            flush_para()
            list_buf.append(content)
        else:
            flush_list()
            para_buf.append(content)

    flush_all()
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(out))
    return result.strip() + '\n'


def main():
    # 遍历本脚本所在目录下的所有 .txt 文件（不含子目录），
    # 依次转换为 .md 文件，保存到所在目录下的 md 文件夹中
    base_dir = Path(__file__).resolve().parent
    out_dir = base_dir / 'md'
    out_dir.mkdir(exist_ok=True)

    txt_files = sorted(base_dir.glob('*.txt'))
    if not txt_files:
        print('未找到 .txt 文件')
        return

    done = 0
    skipped = 0
    for src in txt_files:
        if src.name.startswith('~$'):  # 跳过临时文件
            continue
        dst = out_dir / (src.stem + '.md')
        if dst.exists():  # 已转换过，跳过
            skipped += 1
            continue
        dst.write_text(convert(src.read_text(encoding='utf-8')), encoding='utf-8')
        print(f'已生成: {dst}')
        done += 1

    print(f'共 {len(txt_files)} 个文件，转换 {done} 个，跳过 {skipped} 个')


if __name__ == '__main__':
    main()