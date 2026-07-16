"""引擎O — 双层质量门禁

Gate 类管理方法从"候选"到"已验证"的状态流转。

状态机:
    candidate ──[引擎二自动审查]──→ pending_confirm
    pending_confirm ──[人类批准]──→ verified
    pending_confirm ──[人类驳回]──→ rejected
    pending_confirm ──[超时2周]──→ candidate（降级）
    verified ──[连续失败>30%]──→ candidate（自动降级）

PRD §O-3: 双层门禁 = 引擎二自动审查 + 人类每周审批。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..core.database import Database


class Gate:
    """方法库质量门禁。

    用法:
        gate = Gate(db)
        gate.submit_for_review("atom_bet_isotherm", quality_score=0.85)
        gate.approve("atom_bet_isotherm", confirmed_by="张朝阳")
    """

    # 配置
    AUTO_DOWNGRADE_DAYS = 14      # 超时未审批自动降级天数
    FAILURE_RATE_THRESHOLD = 0.3  # 失败率超过此阈值自动降级

    def __init__(self, db: Database):
        self.db = db

    # ---- 状态流转 ----

    def submit_for_review(self, method_id: str, quality_score: float) -> bool:
        """第一层门禁：引擎二自动审查通过后，标为待人类确认。

        quality_score: 引擎二给出的质量分（0-1）。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.execute(
            """UPDATE methods
               SET status = 'pending_confirm',
                   quality_score = ?,
                   reviewed_at = ?,
                   updated_at = ?
               WHERE id = ? AND status IN ('candidate', 'deprecated')""",
            (quality_score, now, now, method_id),
        )
        self.db.commit()
        return self.db.conn.total_changes > 0

    def approve(self, method_id: str, confirmed_by: str = "human") -> bool:
        """第二层门禁：人类确认 → 已验证。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.execute(
            """UPDATE methods
               SET status = 'verified',
                   confirmed_at = ?,
                   confirmed_by = ?,
                   updated_at = ?
               WHERE id = ? AND status = 'pending_confirm'""",
            (now, confirmed_by, now, method_id),
        )
        self.db.commit()
        return self.db.conn.total_changes > 0

    def reject(self, method_id: str, reason: str = "") -> bool:
        """人类驳回 → rejected。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.execute(
            """UPDATE methods
               SET status = 'rejected',
                   updated_at = ?
               WHERE id = ? AND status = 'pending_confirm'""",
            (now, method_id),
        )
        self.db.commit()

        # 记录驳回原因到方法描述的末尾
        if reason:
            row = self.db.fetch_one("SELECT description FROM methods WHERE id = ?", (method_id,))
            if row:
                new_desc = row["description"] + f"\n\n[驳回原因 {now}] {reason}"
                self.db.execute("UPDATE methods SET description = ? WHERE id = ?",
                              (new_desc, method_id))
                self.db.commit()

        return self.db.conn.total_changes > 0

    def downgrade(self, method_id: str, reason: str = "auto") -> bool:
        """降级：verified → candidate 或 pending_confirm → candidate。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.execute(
            """UPDATE methods
               SET status = 'candidate',
                   updated_at = ?
               WHERE id = ? AND status IN ('verified', 'pending_confirm')""",
            (now, method_id),
        )
        self.db.commit()
        return self.db.conn.total_changes > 0

    def mark_deprecated(self, method_id: str) -> bool:
        """标记为已废弃。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.execute(
            "UPDATE methods SET status = 'deprecated', updated_at = ? WHERE id = ?",
            (now, method_id),
        )
        self.db.commit()
        return self.db.conn.total_changes > 0

    # ---- 自动维护 ----

    def auto_downgrade_stale(self) -> int:
        """自动降级超时未审批的待确认方法。

        返回降级的方法数量。
        """
        cutoff = (datetime.now() - timedelta(days=self.AUTO_DOWNGRADE_DAYS)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # 找到超过14天仍为 pending_confirm 的方法
        rows = self.db.fetch_all(
            """SELECT id FROM methods
               WHERE status = 'pending_confirm'
                 AND updated_at < ?""",
            (cutoff,),
        )

        count = 0
        for row in rows:
            self.downgrade(row["id"], "超时未审批")
            count += 1
        return count

    def auto_downgrade_by_failure_rate(self) -> int:
        """自动降级失败率过高的已验证方法。

        返回降级的方法数量。
        """
        rows = self.db.fetch_all(
            "SELECT id, success_count, failure_count FROM methods WHERE status = 'verified'"
        )

        count = 0
        for row in rows:
            total = row["success_count"] + row["failure_count"]
            if total > 5:  # 至少5次调用后才评估
                failure_rate = row["failure_count"] / total
                if failure_rate > self.FAILURE_RATE_THRESHOLD:
                    self.downgrade(row["id"], f"失败率过高: {failure_rate:.1%}")
                    count += 1
        return count

    def run_maintenance(self) -> dict:
        """运行一次自动维护。返回维护统计。"""
        stale = self.auto_downgrade_stale()
        failed = self.auto_downgrade_by_failure_rate()
        return {
            "stale_downgraded": stale,
            "failure_downgraded": failed,
            "timestamp": datetime.now().isoformat(),
        }

    # ---- 查询 ----

    def get_pending_count(self) -> int:
        """获取待审批方法数量。"""
        row = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM methods WHERE status = 'pending_confirm'"
        )
        return row["c"] if row else 0

    def get_pending_methods(self) -> list[dict]:
        """获取待审批方法列表（用于人类每周审批面板）。"""
        rows = self.db.fetch_all(
            """SELECT id, name, type, description, quality_score, reviewed_at
               FROM methods
               WHERE status = 'pending_confirm'
               ORDER BY reviewed_at DESC"""
        )
        return [dict(r) for r in rows]

    def get_review_stats(self) -> dict:
        """获取审查统计。"""
        rows = self.db.fetch_all(
            "SELECT status, COUNT(*) as c FROM methods GROUP BY status"
        )
        stats = {r["status"]: r["c"] for r in rows}
        return {
            "verified": stats.get("verified", 0),
            "pending_confirm": stats.get("pending_confirm", 0),
            "candidate": stats.get("candidate", 0),
            "rejected": stats.get("rejected", 0),
            "deprecated": stats.get("deprecated", 0),
        }
