"""Polaris Skill 桥接层

将 zhangcy 系列 skill 的能力嵌入 Polaris 引擎。
"""

from .literature import LiteratureSearcher, Paper, SearchResult

__all__ = ["LiteratureSearcher", "Paper", "SearchResult"]
