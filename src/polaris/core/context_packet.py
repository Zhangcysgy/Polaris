"""核心数据模型 —— 上下文数据包（ContextPacket）"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContextPacket:
    """每次 LLM 调用时裁剪后的上下文（不包含完整历史）。

    对应 PRD §4.5：长程推理与上下文管理策略。
    """

    # 当前任务
    task: str
    """当前步骤需要完成的任务描述。"""

    # 父节点溯源
    parent_summary: Optional[str] = None
    """上一步的摘要（≤500字）：从哪来的、为什么。"""

    parent_node_id: Optional[str] = None
    """父节点在 CRT 中的标识。"""

    # 全局状态快照
    global_state: dict = field(default_factory=dict)
    """全局状态快照（≤1000字等价），包含：
    - confirmed_discoveries: list[str]  已确认的发现
    - active_hypotheses: list[str]      当前活跃的假设
    - physics_fence_status: dict        物理围栏状态
    - unresolved_anomalies: list[str]   未解决的异常
    """

    # 按需加载
    method_refs: list[str] = field(default_factory=list)
    """引用的方法库条目 ID 列表（从引擎O按需检索）。"""

    literature_refs: list[str] = field(default_factory=list)
    """引用的文献摘要（按需检索）。"""

    # 人类指令
    human_instruction: Optional[str] = None
    """人类最近一次下达的指令或裁定。"""

    # 排除标记
    exclude_history: bool = True
    """是否排除完整历史（始终为 True，这是核心设计）。"""
