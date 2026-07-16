"""引擎四 — 自主科学发现循环

DiscoveryLoop 是 Polaris 的"大脑"——五引擎全串联的终极形态。
半自主运行，关键节点汇报人类。

8步循环（PRD §4-1）:
    1.下载数据 → 2.匹配方法 → 3.执行分析 → 4.结果验证
    → 5.文献检索 → 6.判断补数据 → 7.区域扩展 → 8.循环判断

6个人类介入节点（PRD §4-2）:
    需新方法 | 异常信号 | 需新数据 | 幽灵信号 | 方向漂移 | 每周审批

4种退出条件（PRD §4-3）:
    软退出 | 硬退出 | 人类退出 | 资源退出
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from ..core.database import Database
from ..core.context_packet import ContextPacket


class LoopStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"        # 等待人类裁定
    SOFT_EXIT = "soft_exit"  # 收敛退出
    HARD_EXIT = "hard_exit"  # 超过重试限制
    HUMAN_EXIT = "human_exit"
    RESOURCE_EXIT = "resource_exit"


class NodeType(str, Enum):
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    MIGRATION = "migration"
    DISCOVERY = "discovery"
    DEAD = "dead"
    MILESTONE = "milestone"


class InterventionType(str, Enum):
    NEED_NEW_METHOD = "need_new_method"       # 方法库无匹配
    ANOMALY_SIGNAL = "anomaly_signal"         # 偏差 >3σ
    NEED_NEW_DATA = "need_new_data"           # 数据不足
    GHOST_SIGNAL = "ghost_signal"             # 幽灵信号（高原/极地）
    DIRECTION_DRIFT = "direction_drift"       # 偏离大方向
    WEEKLY_REVIEW = "weekly_review"           # 每周例行审批


@dataclass
class CRTNode:
    """CRT 拓扑中的一个节点。"""
    id: str = ""
    parent_id: str = ""
    project_id: str = ""
    node_type: NodeType = NodeType.ANALYSIS
    status: str = "active"
    summary: str = ""
    surprise_score: float = 0.0
    physics_fence_result: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"node_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class DiscoveryResult:
    """引擎四一次循环或里程碑的输出。"""
    loop_id: str
    direction: str              # 人类设定的大方向
    status: LoopStatus
    total_steps: int = 0
    nodes: list[CRTNode] = field(default_factory=list)
    discoveries: list[str] = field(default_factory=list)   # 发现标题列表
    anomalies: list[str] = field(default_factory=list)     # 异常区域列表
    ghost_signals: list[str] = field(default_factory=list) # 幽灵信号列表
    summary: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.loop_id:
            self.loop_id = f"loop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DiscoveryLoop:
    """自主科学发现循环。

    用法:
        db = Database(...)
        loop = DiscoveryLoop(db, max_steps=50)

        # 启动循环
        result = loop.start("全球沙尘起电的湿度调控机制")

        # 查询CRT拓扑
        nodes = loop.get_crt_chain()
    """

    # 配置
    DEFAULT_MAX_STEPS = 50
    SOFT_EXIT_NO_IMPROVEMENT = 3      # 连续N次无改进→软退出
    HARD_EXIT_MAX_RETRIES = 5         # 同一节点打回上限→硬退出
    DIRECTION_DRIFT_CHECK_INTERVAL = 10
    HUMAN_REPORT_INTERVAL = 20

    def __init__(self, db: Database, max_steps: int | None = None):
        self.db = db
        self.db.initialize()
        self.max_steps = max_steps or self.DEFAULT_MAX_STEPS
        self._current_step = 0
        self._current_loop_id: str = ""
        self._status: LoopStatus = LoopStatus.IDLE

    @property
    def status(self) -> LoopStatus:
        return self._status

    @property
    def current_step(self) -> int:
        return self._current_step

    # ---- 循环控制 ----

    def start(self, direction: str, project_id: str = "default") -> DiscoveryResult:
        """启动一个新的发现循环。

        M5框架版本：返回循环计划。
        M5+将执行完整的8步循环。
        """
        self._current_loop_id = f"loop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._current_step = 0
        self._status = LoopStatus.RUNNING

        # 创建根节点
        root_node = self._create_node(
            parent_id="",
            node_type=NodeType.MILESTONE,
            summary=f"循环启动: {direction}",
        )

        # 生成循环计划
        plan = self._generate_plan(direction)

        return DiscoveryResult(
            loop_id=self._current_loop_id,
            direction=direction,
            status=LoopStatus.RUNNING,
            total_steps=0,
            nodes=[root_node],
            summary=plan,
        )

    def step(self) -> CRTNode | None:
        """执行一步循环。

        M5框架版本：返回当前步骤的计划描述。
        M5+将执行完整的分析→验证→文献→判断流程。
        """
        if self._status != LoopStatus.RUNNING:
            return None

        self._current_step += 1

        if self._current_step > self.max_steps:
            self._status = LoopStatus.RESOURCE_EXIT
            return self._create_node(
                parent_id=f"node_step_{self._current_step - 1}",
                node_type=NodeType.MILESTONE,
                summary=f"达到最大步数 {self.max_steps}，自动退出。",
            )

        # 确定当前步骤类型
        step_type = self._determine_step_type(self._current_step)

        return self._create_node(
            parent_id=f"node_step_{self._current_step - 1}" if self._current_step > 1 else "",
            node_type=step_type,
            summary=self._step_description(self._current_step),
        )

    def pause(self, reason: InterventionType, detail: str = "") -> DiscoveryResult:
        """暂停循环——等待人类裁定。"""
        self._status = LoopStatus.PAUSED
        return DiscoveryResult(
            loop_id=self._current_loop_id,
            direction="",
            status=LoopStatus.PAUSED,
            total_steps=self._current_step,
            summary=f"暂停: {reason.value} — {detail}",
        )

    def resume(self) -> DiscoveryResult:
        """人类裁定后恢复循环。"""
        self._status = LoopStatus.RUNNING
        return DiscoveryResult(
            loop_id=self._current_loop_id,
            direction="",
            status=LoopStatus.RUNNING,
            total_steps=self._current_step,
            summary="循环已恢复。",
        )

    def stop(self, exit_type: LoopStatus = LoopStatus.HUMAN_EXIT) -> DiscoveryResult:
        """停止循环。"""
        self._status = exit_type

        # 汇总CRT节点
        nodes = self.get_crt_chain()

        return DiscoveryResult(
            loop_id=self._current_loop_id,
            direction="",
            status=exit_type,
            total_steps=self._current_step,
            nodes=nodes,
            summary=f"循环结束: {exit_type.value}。共 {self._current_step} 步。",
        )

    # ---- CRT 管理 ----

    def _create_node(
        self,
        parent_id: str,
        node_type: NodeType,
        summary: str,
        surprise_score: float = 0.0,
    ) -> CRTNode:
        """创建一个CRT节点并存入数据库。"""
        node = CRTNode(
            parent_id=parent_id,
            project_id=self._current_loop_id,
            node_type=node_type,
            status="active",
            summary=summary,
            surprise_score=surprise_score,
        )

        self.db.execute(
            """INSERT INTO crt_nodes
               (id, parent_id, project_id, node_type, status, summary, surprise_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (node.id, node.parent_id, node.project_id,
             node.node_type.value, node.status, node.summary,
             node.surprise_score, node.created_at),
        )

        # 创建边（连接到父节点）
        if parent_id:
            self.db.execute(
                """INSERT INTO crt_edges (source_node, target_node, edge_type)
                   VALUES (?, ?, 'parent')""",
                (parent_id, node.id),
            )

        self.db.commit()
        return node

    def get_crt_chain(self, limit: int = 50) -> list[CRTNode]:
        """获取当前循环的CRT节点链。"""
        rows = self.db.fetch_all(
            """SELECT * FROM crt_nodes
               WHERE project_id = ?
               ORDER BY created_at ASC LIMIT ?""",
            (self._current_loop_id, limit),
        )
        return [self._row_to_node(r) for r in rows]

    def get_node(self, node_id: str) -> Optional[CRTNode]:
        """查询单个CRT节点。"""
        row = self.db.fetch_one(
            "SELECT * FROM crt_nodes WHERE id = ?", (node_id,)
        )
        return self._row_to_node(row) if row else None

    # ---- 内部 ----

    def _generate_plan(self, direction: str) -> str:
        """生成循环执行计划。"""
        steps = [
            "Step 1: 下载初始数据（ERA5 全球相关变量）",
            "Step 2: 查询方法库 → 匹配分析方法",
            "Step 3: 执行分析 → 引擎一自动追踪版本",
            "Step 4: 引擎二深度验证（方法论溯源+红队+多角色辩论）",
            "Step 5: 检索相关文献 → 比对现有知识",
            "Step 6: 判断是否需要补充数据 → 是则回到Step 1",
            "Step 7: 引擎三全球方法迁移 → 发现跨区域差异",
            "Step 8: 循环判断 → 收敛? 退出? 继续?",
        ]
        return (
            f"# 发现循环计划\n"
            f"**方向**: {direction}\n"
            f"**最大步数**: {self.max_steps}\n"
            f"**计划步骤**:\n" +
            "\n".join(f"- {s}" for s in steps)
        )

    def _determine_step_type(self, step_num: int) -> NodeType:
        """根据步数确定节点类型。"""
        cycle = step_num % 8
        if cycle in (1, 2):
            return NodeType.ANALYSIS
        elif cycle in (3, 4):
            return NodeType.VALIDATION
        elif cycle in (5, 6):
            return NodeType.MIGRATION
        elif cycle == 7:
            return NodeType.DISCOVERY
        else:
            return NodeType.MILESTONE

    def _step_description(self, step_num: int) -> str:
        """生成步骤描述。"""
        descriptions = {
            1: "数据下载与预处理",
            2: "方法库匹配与分析执行",
            3: "引擎二深度验证启动",
            4: "验证结果汇总与反馈生成",
            5: "文献检索与知识比对",
            6: "引擎三区域迁移与差异发现",
            7: "发现评估与惊喜度计算",
            0: "循环状态检查与方向调整",
        }
        cycle = step_num % 8
        return f"Step {step_num}: {descriptions.get(cycle, '未知步骤')}"

    def _row_to_node(self, row) -> CRTNode:
        return CRTNode(
            id=row["id"],
            parent_id=row["parent_id"] or "",
            project_id=row["project_id"],
            node_type=NodeType(row["node_type"]),
            status=row["status"],
            summary=row["summary"],
            surprise_score=row["surprise_score"] or 0.0,
            physics_fence_result=row["physics_fence_result"] or "",
            created_at=row["created_at"],
        )
