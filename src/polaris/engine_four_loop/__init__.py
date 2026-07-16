"""引擎四 — 自主科学发现循环

Polaris 的"大脑"——五引擎全串联，半自主运行。
"""

from .loop import (
    DiscoveryLoop, DiscoveryResult, CRTNode,
    LoopStatus, NodeType, InterventionType,
)

__all__ = [
    "DiscoveryLoop",
    "DiscoveryResult",
    "CRTNode",
    "LoopStatus",
    "NodeType",
    "InterventionType",
]
