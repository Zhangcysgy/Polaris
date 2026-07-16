#!/usr/bin/env python3
"""
fetch_paper.py — 从学术 API 获取论文元数据和摘要

Usage:
    python fetch_paper.py --doi 10.1016/j.atmosres.2021.105933
    python fetch_paper.py --arxiv 2006.01978
    python fetch_paper.py --title "Humidity-gated triboelectric charging"

依赖: requests (pip install requests)
"""

import argparse
import json
import sys
import urllib.parse
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


def fetch_by_doi(doi: str) -> dict:
    """从 OpenAlex 获取论文信息"""
    url = f"https://api.openalex.org/works/doi:{doi}"
    params = {
        "select": "id,doi,title,publication_year,authorships,primary_location,cited_by_count,abstract_inverted_index,keywords,concepts"
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_by_arxiv(arxiv_id: str) -> dict:
    """从 arXiv API 获取论文信息"""
    # 移除版本号（如 2006.01978v3 → 2006.01978）
    arxiv_id = arxiv_id.split("v")[0]
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    headers = {"Accept": "application/atom+xml"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return {"raw_xml": resp.text, "arxiv_id": arxiv_id}


def fetch_by_title(title: str) -> list:
    """在 OpenAlex 中按标题搜索论文"""
    url = "https://api.openalex.org/works"
    params = {
        "search": title,
        "per_page": 5,
        "sort": "relevance_score:desc",
        "select": "id,doi,title,publication_year,primary_location,cited_by_count"
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("results", [])


def decode_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    """将 OpenAlex 的倒排索引还原为可读文本"""
    if not inverted_index:
        return None
    try:
        # 计算总长度
        max_pos = max(pos for positions in inverted_index.values() for pos in positions)
        words = [""] * (max_pos + 1)
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word
        return " ".join(words)
    except (ValueError, TypeError, KeyError):
        return None


def format_authors(data: dict) -> str:
    """格式化作者列表"""
    authors = []
    for author in data.get("authorships", []):
        name = author.get("author", {}).get("display_name", "")
        if name:
            authors.append(name)
    return ", ".join(authors) if authors else "N/A"


def format_oa_status(data: dict) -> str:
    """获取 OA 状态"""
    loc = data.get("primary_location", {}) or {}
    is_oa = loc.get("is_oa", False)
    return "开放获取" if is_oa else "非开放获取"


def format_source(data: dict) -> str:
    """获取期刊名"""
    loc = data.get("primary_location", {}) or {}
    source = loc.get("source", {}) or {}
    return source.get("display_name", "N/A")


def fetch_and_report(doi: Optional[str] = None, arxiv: Optional[str] = None, title: Optional[str] = None):
    """主流程：获取论文并输出结构化报告"""
    result = {}

    if arxiv:
        print(f"📡 从 arXiv 获取: {arxiv}")
        data = fetch_by_arxiv(arxiv)
        result["source"] = "arXiv"
        result["arxiv_id"] = arxiv
        # 简单解析 arXiv XML（完整解析需要 xml.etree）
        result["raw_data"] = data["raw_xml"][:500]  # 截断显示
        print(f"✅ arXiv 数据已获取（{len(data['raw_xml'])} 字符）")

    elif doi:
        print(f"📡 从 OpenAlex 获取: {doi}")
        data = fetch_by_doi(doi)
        result["source"] = "OpenAlex"
        result["title"] = data.get("title", "N/A")
        result["authors"] = format_authors(data)
        result["journal"] = format_source(data)
        result["year"] = data.get("publication_year")
        result["cited_by_count"] = data.get("cited_by_count", 0)
        result["oa_status"] = format_oa_status(data)
        result["doi"] = data.get("doi", "").replace("https://doi.org/", "")

        # 解码摘要
        abstract = decode_abstract(data.get("abstract_inverted_index"))
        result["abstract"] = abstract[:2000] if abstract else "摘要不可用"

        # 关键词
        keywords = [k.get("display_name", "") for k in data.get("keywords", [])]
        result["keywords"] = keywords

        # 概念
        concepts = [(c.get("display_name", ""), c.get("score", 0))
                    for c in data.get("concepts", []) if c.get("score", 0) > 0.5]
        result["concepts"] = concepts

        # 输出
        print(f"\n{'='*60}")
        print(f"  {result['title']}")
        print(f"{'='*60}")
        print(f"  作者: {result['authors']}")
        print(f"  期刊: {result['journal']} ({result['year']})")
        print(f"  DOI: {result['doi']}")
        print(f"  引用: {result['cited_by_count']} 次")
        print(f"  OA: {result['oa_status']}")
        print(f"\n  📝 摘要 ({len(abstract)} 字符):")
        print(f"  {abstract[:500]}...")
        if abstract and len(abstract) > 500:
            print(f"  ...（共 {len(abstract)} 字符，已截断）")
        print(f"\n  关键词: {', '.join(keywords[:5])}")
        print(f"  相关主题:")
        for name, score in concepts[:3]:
            print(f"    - {name} (confidence: {score:.2f})")
        print(f"{'='*60}")

    elif title:
        print(f"📡 按标题搜索: {title}")
        results = fetch_by_title(title)
        print(f"\n找到 {len(results)} 篇匹配论文:\n")
        for i, paper in enumerate(results[:5], 1):
            loc = paper.get("primary_location", {}) or {}
            source = loc.get("source", {}) or {}
            doi = paper.get("doi", "").replace("https://doi.org/", "")
            print(f"  [{i}] {paper.get('title', 'N/A')}")
            print(f"      ({source.get('display_name', 'N/A')}, {paper.get('publication_year', 'N/A')})")
            print(f"      DOI: {doi}")
            print()

    return result


def main():
    parser = argparse.ArgumentParser(description="从学术 API 获取论文信息")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doi", help="论文 DOI")
    group.add_argument("--arxiv", help="arXiv ID (如 2006.01978)")
    group.add_argument("--title", help="论文标题（搜索模式）")
    args = parser.parse_args()

    fetch_and_report(doi=args.doi, arxiv=args.arxiv, title=args.title)


if __name__ == "__main__":
    main()
