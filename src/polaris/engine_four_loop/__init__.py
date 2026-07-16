"""引擎四 — 自主科学发现循环

Polaris 的"大脑"——LLM驱动决策 + 五引擎全串联。
"""

from .loop import DiscoveryLoop, CRTNode, LoopStatus, NodeType

__all__ = ["DiscoveryLoop", "CRTNode", "LoopStatus", "NodeType"]
