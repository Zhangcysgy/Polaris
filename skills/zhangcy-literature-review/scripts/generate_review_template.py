#!/usr/bin/env python
"""
generate_review_template.py — 生成文献综述报告模板

Usage:
    python generate_review_template.py --topic "沙尘暴中雷电现象" --mode depth --papers 18
"""

import argparse
from datetime import datetime


def generate_template(topic, mode, paper_count, themes=None):
    mode_label = "深度搜索（挖穿不漏）" if mode == "depth" else "广度搜索（沾边都要）"
    themes = themes or ["主题一", "主题二", "主题三"]
    today = datetime.now().strftime("%Y-%m-%d")

    template = f"""# {topic} — 文献综述

> 生成日期：{today}
> 搜索模式：{mode_label}
> 文献数量：{paper_count} 篇

## 摘要

（200-300 字概述本综述的范围、主要发现和结论）

---

## 1. 引言

### 1.1 研究背景
{topic} 的科学意义、现实需求。

### 1.2 研究现状概述
已有研究的总体情况。

### 1.3 本综述的目的与范围
明确综述覆盖什么、不覆盖什么。

---

## 2. 检索策略

### 2.1 搜索关键词
| 角度 | 关键词 | 结果数 |
|------|--------|--------|
| 核心关键词 | ... | ... |
| ... | ... | ... |

### 2.2 数据来源
- OpenAlex、Semantic Scholar、arXiv physics.ao-ph

### 2.3 筛选标准
纳入/排除标准。

---

## 3. 研究现状

### 3.1 {themes[0]}
（逐篇介绍核心论文，比较方法、结果、结论）

### 3.2 {themes[1]}

### 3.3 {themes[2]}

---

## 4. 方法学对比

| 方法类型 | 代表研究 | 优势 | 局限 |
|----------|---------|------|------|
| 观测分析 | ... | ... | ... |
| 数值模拟 | ... | ... | ... |
| 实验研究 | ... | ... | ... |

---

## 5. 研究空白与未来方向

### 5.1 当前研究的不足
1. ...
2. ...

### 5.2 未来研究方向
1. ...
2. ...

---

## 6. 结论

（总结性陈述）

---

## 参考文献

| # | 作者 | 年份 | 标题 | 期刊 | DOI |
|---|------|------|------|------|-----|
| 1 | ... | ... | ... | ... | ... |
"""
    return template


def main():
    parser = argparse.ArgumentParser(description="生成文献综述模板")
    parser.add_argument("--topic", required=True, help="综述主题")
    parser.add_argument("--mode", choices=["depth", "breadth"], default="depth",
                        help="搜索模式")
    parser.add_argument("--papers", type=int, default=10, help="论文数量")
    parser.add_argument("--themes", nargs="+", help="主题分类")
    parser.add_argument("-o", "--output", default=None, help="输出文件")
    args = parser.parse_args()

    template = generate_template(args.topic, args.mode, args.papers, args.themes)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(template)
        print(f"✅ 模板已保存到 {args.output}")
    else:
        print(template)


if __name__ == "__main__":
    main()
