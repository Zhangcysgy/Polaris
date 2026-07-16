"""引擎一 — 反馈主线追踪

FeedbackTracker 是 Polaris 版本管理的核心——不追踪"版本"，追踪"意见"。
每条审稿意见是一个独立的追踪单元，从出生到解决有完整轨迹。

PRD §1-1: 反馈主线追踪
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..core.database import Database


# ============================================================
# 数据模型
# ============================================================

FeedbackStatus = str  # "open" | "in_progress" | "resolved" | "wontfix" | "duplicate"
FeedbackPriority = str  # "low" | "medium" | "high" | "critical"


@dataclass
class FeedbackItem:
    """一条审稿意见。"""
    id: str
    project_id: str
    source: str           # "引擎二·方法论溯源" | "红队" | "人类"
    content: str          # 审稿意见原文
    status: FeedbackStatus = "open"
    priority: FeedbackPriority = "medium"
    created_at: str = ""
    resolved_at: str = ""
    resolution_note: str = ""


@dataclass
class ResolutionStep:
    """一次修改尝试。"""
    id: int
    feedback_id: str
    step_order: int
    action_taken: str     # 做了什么修改
    version_ref: str = "" # 关联版本号
    file_paths: list[str] = field(default_factory=list)
    reviewer_result: str = ""  # Reviewer 复查结果


# ============================================================
# FeedbackTracker
# ============================================================

class FeedbackTracker:
    """审稿意见的全生命周期管理。

    用法:
        db = Database(...)
        tracker = FeedbackTracker(db)

        # 创建意见
        fid = tracker.create(
            project_id="sahara-dust",
            source="引擎二·方法论溯源",
            content="补充X敏感性实验",
            priority="high",
        )

        # 记录修改
        tracker.add_resolution_step(fid, step_order=1,
            action_taken="新增 scripts/sensitivity_x.py",
            version_ref="v5")

        # 解决
        tracker.resolve(fid, note="X在[0.1,0.5]范围内对η影响<3%")

        # 查询
        pending = tracker.get_open_items("sahara-dust")
    """

    def __init__(self, db: Database):
        self.db = db
        self.db.initialize()

    # ---- CRUD ----

    def create(
        self,
        project_id: str,
        source: str,
        content: str,
        priority: FeedbackPriority = "medium",
    ) -> str:
        """创建一条审稿意见。返回意见 ID。"""
        fid = f"fb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.db.execute(
            """INSERT INTO feedback_items
               (id, project_id, source, content, status, priority, created_at)
               VALUES (?, ?, ?, ?, 'open', ?, ?)""",
            (fid, project_id, source, content, priority, now),
        )
        self.db.commit()
        return fid

    def get(self, feedback_id: str) -> Optional[FeedbackItem]:
        """查询一条意见。"""
        row = self.db.fetch_one(
            "SELECT * FROM feedback_items WHERE id = ?", (feedback_id,)
        )
        if row is None:
            return None
        return FeedbackItem(
            id=row["id"],
            project_id=row["project_id"],
            source=row["source"],
            content=row["content"],
            status=row["status"],
            priority=row["priority"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"] or "",
            resolution_note=row["resolution_note"] or "",
        )

    def update_status(
        self, feedback_id: str, status: FeedbackStatus, note: str = ""
    ) -> bool:
        """更新意见状态。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if status == "resolved":
            self.db.execute(
                "UPDATE feedback_items SET status = ?, resolved_at = ?, resolution_note = ? WHERE id = ?",
                (status, now, note, feedback_id),
            )
        else:
            self.db.execute(
                "UPDATE feedback_items SET status = ?, resolution_note = ? WHERE id = ?",
                (status, note, feedback_id),
            )
        self.db.commit()
        return self.db.conn.total_changes > 0

    def resolve(self, feedback_id: str, note: str = "") -> bool:
        """标记为已解决。"""
        return self.update_status(feedback_id, "resolved", note)

    def mark_wontfix(self, feedback_id: str, reason: str = "") -> bool:
        """标记为不修复。"""
        return self.update_status(feedback_id, "wontfix", reason)

    def mark_duplicate(self, feedback_id: str, duplicate_of: str = "") -> bool:
        """标记为重复意见。"""
        note = f"重复于 {duplicate_of}" if duplicate_of else "重复意见"
        return self.update_status(feedback_id, "duplicate", note)

    # ---- 解决步骤 ----

    def add_resolution_step(
        self,
        feedback_id: str,
        step_order: int,
        action_taken: str,
        version_ref: str = "",
        file_paths: list[str] | None = None,
        reviewer_result: str = "",
    ) -> int:
        """记录一次修改尝试。返回步骤 ID。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        import json
        fps = json.dumps(file_paths or [], ensure_ascii=False)

        cursor = self.db.execute(
            """INSERT INTO feedback_resolution_steps
               (feedback_id, step_order, action_taken, version_ref, file_paths, reviewer_result, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (feedback_id, step_order, action_taken, version_ref, fps, reviewer_result, now),
        )

        # 自动将意见状态从 open 切换为 in_progress
        self.db.execute(
            "UPDATE feedback_items SET status = 'in_progress' WHERE id = ? AND status = 'open'",
            (feedback_id,),
        )
        self.db.commit()
        return cursor.lastrowid

    def get_resolution_steps(self, feedback_id: str) -> list[ResolutionStep]:
        """获取意见的所有修改记录。"""
        rows = self.db.fetch_all(
            "SELECT * FROM feedback_resolution_steps WHERE feedback_id = ? ORDER BY step_order",
            (feedback_id,),
        )
        import json
        steps = []
        for r in rows:
            try:
                fps = json.loads(r["file_paths"]) if r["file_paths"] else []
            except (json.JSONDecodeError, TypeError):
                fps = []
            steps.append(ResolutionStep(
                id=r["id"],
                feedback_id=r["feedback_id"],
                step_order=r["step_order"],
                action_taken=r["action_taken"],
                version_ref=r["version_ref"] or "",
                file_paths=fps,
                reviewer_result=r["reviewer_result"] or "",
            ))
        return steps

    # ---- 查询 ----

    def get_open_items(self, project_id: str) -> list[FeedbackItem]:
        """获取某项目的所有未解决意见。"""
        rows = self.db.fetch_all(
            """SELECT * FROM feedback_items
               WHERE project_id = ? AND status IN ('open', 'in_progress')
               ORDER BY
                 CASE priority
                   WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                   WHEN 'medium' THEN 3 WHEN 'low' THEN 4
                 END, created_at""",
            (project_id,),
        )
        return [self._row_to_item(r) for r in rows]

    def get_all_items(
        self, project_id: str, status: FeedbackStatus | None = None
    ) -> list[FeedbackItem]:
        """获取某项目的所有意见（可按状态筛选）。"""
        if status:
            rows = self.db.fetch_all(
                "SELECT * FROM feedback_items WHERE project_id = ? AND status = ? ORDER BY created_at DESC",
                (project_id, status),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM feedback_items WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            )
        return [self._row_to_item(r) for r in rows]

    def get_full_trail(self, feedback_id: str) -> dict:
        """获取一条意见的完整轨迹（意见+所有修改记录）。"""
        item = self.get(feedback_id)
        if item is None:
            return {}
        steps = self.get_resolution_steps(feedback_id)
        return {
            "item": item,
            "resolution_steps": steps,
            "total_attempts": len(steps),
            "is_resolved": item.status == "resolved",
        }

    def get_summary(self, project_id: str) -> dict:
        """获取项目的审稿意见摘要。"""
        rows = self.db.fetch_all(
            """SELECT status, COUNT(*) as c
               FROM feedback_items
               WHERE project_id = ?
               GROUP BY status""",
            (project_id,),
        )
        status_counts = {r["status"]: r["c"] for r in rows}
        total = sum(status_counts.values())
        resolved = status_counts.get("resolved", 0)

        return {
            "project_id": project_id,
            "total": total,
            "resolved": resolved,
            "open": status_counts.get("open", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "wontfix": status_counts.get("wontfix", 0),
            "completion_pct": resolved / total * 100 if total > 0 else 100.0,
        }

    def _row_to_item(self, row) -> FeedbackItem:
        return FeedbackItem(
            id=row["id"],
            project_id=row["project_id"],
            source=row["source"],
            content=row["content"],
            status=row["status"],
            priority=row["priority"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"] or "",
            resolution_note=row["resolution_note"] or "",
        )
