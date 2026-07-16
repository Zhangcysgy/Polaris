"""Polaris Skill 桥接层 — 文献检索

LiteratureSearcher 封装 OpenAlex + arXiv API，实现文献检索能力。
支持深度/广度两种搜索模式。

此模块将 zhangcy-literature-review skill 的核心逻辑嵌入 Polaris，
使其可被引擎四的自主发现循环直接调用。
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ============================================================
# 数据模型
# ============================================================

@dataclass
class Paper:
    """一篇论文的结构化信息。"""
    title: str
    authors: list[str] = field(default_factory=list)
    year: int = 0
    doi: str = ""
    journal: str = ""
    abstract: str = ""
    citations: int = 0
    url: str = ""
    source: str = ""         # "openalex" | "arxiv" | "semantic_scholar"

    def to_summary(self) -> str:
        """生成人类可读的摘要。"""
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += f" et al."
        return (
            f"{authors_str} ({self.year}). {self.title}. "
            f"{self.journal}. DOI: {self.doi}"
        )


@dataclass
class SearchResult:
    """一次文献搜索的结果。"""
    query: str
    papers: list[Paper] = field(default_factory=list)
    total_found: int = 0
    source: str = ""
    elapsed_seconds: float = 0.0

    def to_markdown(self, max_papers: int = 10) -> str:
        """生成 Markdown 格式的结果。"""
        lines = [
            f"## 文献搜索: {self.query}",
            f"来源: {self.source} | 找到: {self.total_found} 篇 | 返回: {len(self.papers)} 篇",
            "",
        ]
        for i, p in enumerate(self.papers[:max_papers], 1):
            lines.append(f"{i}. **{p.title}**")
            lines.append(f"   {', '.join(p.authors[:3])}{' et al.' if len(p.authors) > 3 else ''} ({p.year}) — {p.journal}")
            if p.abstract:
                lines.append(f"   > {p.abstract[:200]}...")
            if p.doi:
                lines.append(f"   DOI: [{p.doi}](https://doi.org/{p.doi})")
            lines.append("")
        if len(self.papers) > max_papers:
            lines.append(f"... 还有 {len(self.papers) - max_papers} 篇")
        return "\n".join(lines)


# ============================================================
# LiteratureSearcher
# ============================================================

class LiteratureSearcher:
    """文献搜索引擎。

    封装 OpenAlex + arXiv API，支持:
    - 关键词搜索（深度模式）
    - 跨学科搜索（广度模式）
    - 引用回溯（snowballing）
    - 作者追踪

    用法:
        searcher = LiteratureSearcher()
        result = searcher.search("dust storm electrification", max_papers=20)
        for p in result.papers:
            print(p.to_summary())
    """

    # 气象核心期刊白名单
    CORE_JOURNALS = [
        "Journal of Climate", "Journal of the Atmospheric Sciences",
        "Geophysical Research Letters", "Atmospheric Chemistry and Physics",
        "Journal of Geophysical Research: Atmospheres", "Atmospheric Research",
        "Monthly Weather Review", "Bulletin of the American Meteorological Society",
        "Nature Geoscience", "Science Advances", "Nature", "Science",
        "Physical Review Letters", "Journal of Fluid Mechanics",
    ]

    def __init__(self, email: str = "polaris@research.org"):
        self.email = email
        self._cache: dict[str, SearchResult] = {}

    # ================================================================
    # 主搜索接口
    # ================================================================

    def search(
        self,
        query: str,
        max_papers: int = 20,
        mode: str = "depth",  # "depth" | "breadth"
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> SearchResult:
        """执行文献搜索。

        Args:
            query: 搜索关键词
            max_papers: 最大返回论文数
            mode: "depth"(精确) | "breadth"(广泛)
            year_from: 起始年份（None=不限）
            year_to: 截止年份（None=不限）
        """
        cache_key = f"{query}|{mode}|{year_from}|{year_to}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        papers = []
        t0 = time.time()

        # OpenAlex 搜索
        oa_result = self._search_openalex(query, max_papers, year_from, year_to)
        papers.extend(oa_result.papers)

        # arXiv 搜索（物理/大气科学相关）
        if mode == "breadth" or len(papers) < 10:
            ax_result = self._search_arxiv(query, max_papers=max(5, max_papers // 2))
            # 去重
            existing_titles = {p.title.lower() for p in papers}
            for p in ax_result.papers:
                if p.title.lower() not in existing_titles:
                    papers.append(p)

        elapsed = time.time() - t0

        result = SearchResult(
            query=query,
            papers=papers[:max_papers],
            total_found=len(papers),
            source=f"OpenAlex + arXiv ({mode})",
            elapsed_seconds=round(elapsed, 2),
        )
        self._cache[cache_key] = result
        return result

    def search_breadth(self, topic: str, num_routes: int = 3) -> list[SearchResult]:
        """广度搜索——多角度并行搜索。

        模仿 zhangcy-literature-review 的广度模式 5 路并行。
        """
        routes = [
            (f"{topic}", "核心领域"),
            (f"{topic} observation measurement", "观测与实验"),
            (f"{topic} model simulation theory", "理论与模拟"),
            (f"{topic} Mars planetary analogue", "行星类比"),
            (f"{topic} aerosol particle charge", "跨学科"),
        ]

        results = []
        for query, label in routes[:num_routes]:
            r = self.search(query, max_papers=10, mode="breadth")
            r.query = f"{label}: {query}"
            results.append(r)

        return results

    def search_author(self, author_name: str, max_papers: int = 20) -> SearchResult:
        """作者追踪——搜索特定作者的全部论文。"""
        return self.search(author_name, max_papers=max_papers, mode="depth")

    # ================================================================
    # API 实现
    # ================================================================

    def _search_openalex(
        self,
        query: str,
        max_papers: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> SearchResult:
        """通过 OpenAlex API 搜索论文。"""
        papers = []
        base_url = "https://api.openalex.org/works"

        params = {
            "search": query,
            "per_page": min(max_papers, 50),
            "sort": "cited_by_count:desc",
            "filter": "type:article",
        }
        if year_from:
            params["filter"] += f",publication_year:>{year_from - 1}"
        if year_to:
            params["filter"] += f",publication_year:<{year_to + 1}"

        url = f"{base_url}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", f"mailto:{self.email}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            return SearchResult(query=query, papers=[], total_found=0, source=f"OpenAlex (error: {e})")

        for work in data.get("results", []):
            try:
                p = self._parse_openalex_work(work)
                if p:
                    papers.append(p)
            except Exception:
                continue

        total = data.get("meta", {}).get("count", len(papers))
        return SearchResult(
            query=query, papers=papers, total_found=total,
            source="OpenAlex"
        )

    def _search_arxiv(self, query: str, max_papers: int = 10) -> SearchResult:
        """通过 arXiv API 搜索论文。"""
        papers = []
        base_url = "http://export.arxiv.org/api/query"

        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(max_papers, 30),
            "sortBy": "relevance",
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode()
        except (urllib.error.URLError, OSError):
            return SearchResult(query=query, papers=[], total_found=0, source="arXiv (error)")

        # 简易 XML 解析（避免引入额外依赖）
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(raw)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                title = title_el.text.strip() if title_el is not None and title_el.text else ""

                authors = []
                for author in entry.findall("atom:author", ns):
                    name_el = author.find("atom:name", ns)
                    if name_el is not None and name_el.text:
                        authors.append(name_el.text)

                summary_el = entry.find("atom:summary", ns)
                abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""

                # 从 id 提取 arXiv ID
                id_el = entry.find("atom:id", ns)
                arxiv_id = ""
                if id_el is not None and id_el.text:
                    arxiv_id = id_el.text.split("/abs/")[-1]

                papers.append(Paper(
                    title=title,
                    authors=authors,
                    year=2024,  # arXiv 不直接给年份，默认最近
                    doi="",
                    journal="arXiv",
                    abstract=abstract[:500] if abstract else "",
                    url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                    source="arxiv",
                ))
        except ET.ParseError:
            pass

        return SearchResult(
            query=query, papers=papers, total_found=len(papers),
            source="arXiv"
        )

    def _parse_openalex_work(self, work: dict) -> Optional[Paper]:
        """解析 OpenAlex 的 work 对象。"""
        title = work.get("title", "")
        if not title:
            return None

        # 作者
        authors = []
        for a in work.get("authorships", [])[:5]:
            name = a.get("author", {}).get("display_name", "")
            if name:
                authors.append(name)

        # 年份
        year = work.get("publication_year", 0)

        # DOI
        doi = work.get("doi", "").replace("https://doi.org/", "") if work.get("doi") else ""

        # 期刊
        journal = ""
        if work.get("primary_location") and work["primary_location"].get("source"):
            journal = work["primary_location"]["source"].get("display_name", "")

        # 摘要
        abstract = ""
        abstract_inv = work.get("abstract_inverted_index")
        if abstract_inv:
            abstract = self._decode_inverted_index(abstract_inv)

        # 引用数
        citations = work.get("cited_by_count", 0)

        return Paper(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            journal=journal or "Unknown",
            abstract=abstract[:500] if abstract else "",
            citations=citations,
            url=f"https://doi.org/{doi}" if doi else "",
            source="openalex",
        )

    @staticmethod
    def _decode_inverted_index(inverted_index: dict) -> str:
        """解码 OpenAlex 的 inverted abstract index。"""
        if not inverted_index:
            return ""
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return " ".join(w for _, w in word_positions)
