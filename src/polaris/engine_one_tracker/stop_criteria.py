"""引擎一 — 收手标准引擎

基于审稿历史和用户行为，自动判断"已经够好了"。

PRD §1-4: 收手标准自动化

三个阶段：
    - 冷启动（规则）: 连续2轮审稿零意见 + 物理校验全通过 + 无未解决意见
    - 学习期（统计）: 分析用户历史"确认收手"案例，提取特征
    - 自主期（预测）: 自动判断并提示——"建议收手 [Y/N]"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..core.database import Database
from .feedback import FeedbackTracker


@dataclass
class StopRecommendation:
    """一次收手建议。"""
    should_stop: bool
    confidence: float            # 0-1，建议的可信度
    reason: str
    evidence: list[str] = field(default_factory=list)
    """支持建议的证据列表。"""


class StopCriteria:
    """收手标准引擎。

    用法:
        db = Database(...)
        sc = StopCriteria(db)

        # 获取收手建议
        rec = sc.evaluate("sahara-dust")
        if rec.should_stop:
            print(f"建议收手: {rec.reason}（置信度: {rec.confidence:.0%}）")
    """

    def __init__(self, db: Database):
        self.db = db
        self.feedback = FeedbackTracker(db)

        # 冷启动规则
        self.RULE_CONSECUTIVE_ZERO_OPINIONS = 2  # 连续N轮审稿零意见
        self.RULE_MAX_ITERATIONS = 10             # 绝对上限

    def evaluate(self, project_id: str) -> StopRecommendation:
        """评估是否应该收手。

        优先使用规则（冷启动），积累足够数据后切换学习模式。
        """
        # 获取审稿历史
        feedback_summary = self.feedback.get_summary(project_id)

        # 1. 规则检查
        rule_result = self._rule_based_check(project_id, feedback_summary)
        if rule_result is not None:
            return rule_result

        # 2. 学习模式（数据不足时回退到规则）
        # M3 阶段：学习模式为框架，M4+ 完善
        return self._fallback_check(feedback_summary)

    def _rule_based_check(
        self, project_id: str, summary: dict
    ) -> Optional[StopRecommendation]:
        """冷启动规则检查。"""

        # 规则1: 无任何审稿意见 → 不能收手（还没开始审）
        if summary["total"] == 0:
            return StopRecommendation(
                should_stop=False,
                confidence=0.9,
                reason="尚未进行任何审稿。请至少运行一次审稿后再评估。",
            )

        # 规则2: 所有意见已解决 + 无新意见
        if summary["completion_pct"] >= 100.0:
            # 检查最近的审稿是否产生了新意见
            recent_zero_rounds = self._count_consecutive_zero_rounds(project_id)
            if recent_zero_rounds >= self.RULE_CONSECUTIVE_ZERO_OPINIONS:
                return StopRecommendation(
                    should_stop=True,
                    confidence=0.7,
                    reason=(
                        f"所有审稿意见已解决（{summary['total']}条），"
                        f"且连续 {recent_zero_rounds} 轮审稿未产生新意见。"
                    ),
                    evidence=[
                        f"总意见数: {summary['total']}",
                        f"已解决: {summary['resolved']}",
                        f"连续零意见轮次: {recent_zero_rounds}",
                    ],
                )

        # 规则3: 仍有无视的 critical 意见
        open_items = self.feedback.get_open_items(project_id)
        critical_open = [i for i in open_items if i.priority == "critical"]
        if critical_open:
            return StopRecommendation(
                should_stop=False,
                confidence=0.95,
                reason=(
                    f"仍有 {len(critical_open)} 条 🔴致命 意见未解决。"
                    f"请先处理这些关键问题。"
                ),
                evidence=[f"未解决致命意见: {i.content[:80]}..." for i in critical_open[:3]],
            )

        # 规则4: 迭代次数超过绝对上限
        total_versions = self._count_versions(project_id)
        if total_versions >= self.RULE_MAX_ITERATIONS:
            return StopRecommendation(
                should_stop=True,
                confidence=0.5,
                reason=(
                    f"已迭代 {total_versions} 次，达到预设上限。"
                    f"建议人工判断是否需要继续。"
                ),
                evidence=[f"总迭代次数: {total_versions}"],
            )

        return None  # 规则无法判断，交给下一层

    def _fallback_check(self, summary: dict) -> StopRecommendation:
        """回退检查——当规则无法判断时。"""
        open_count = summary["open"] + summary["in_progress"]

        if open_count == 0:
            return StopRecommendation(
                should_stop=True,
                confidence=0.5,
                reason="所有审稿意见已处理，但不确定是否已达到最优。建议人工确认。",
            )
        else:
            return StopRecommendation(
                should_stop=False,
                confidence=0.6,
                reason=f"仍有 {open_count} 条意见待处理。",
                evidence=[f"待处理: {open_count} 条"],
            )

    def _count_consecutive_zero_rounds(self, project_id: str) -> int:
        """计算连续几轮审稿未产生新意见。

        简化版：查询最近 N 次审稿记录中 opinion 数量为 0 的连续次数。
        """
        # 从 review_reports 表查询最近的审稿记录
        rows = self.db.fetch_all(
            """SELECT id, created_at FROM review_reports
               WHERE project_id = ?
               ORDER BY created_at DESC LIMIT 5""",
            (project_id,),
        )

        consecutive = 0
        for row in rows:
            # 检查此次审稿是否产生了 feedback_items
            fb_count = self.db.fetch_one(
                "SELECT COUNT(*) as c FROM feedback_items WHERE source LIKE ?",
                (f"%{row['id']}%",),
            )
            if fb_count and fb_count["c"] == 0:
                consecutive += 1
            else:
                break

        return consecutive

    def _count_versions(self, project_id: str) -> int:
        """计算项目总迭代版本数。"""
        row = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM versions WHERE project_id = ?",
            (project_id,),
        )
        return row["c"] if row else 0

    def record_stop_decision(
        self, project_id: str, decision: str, reason: str = ""
    ) -> None:
        """记录一次人类的收手决策（供学习模式使用）。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 存储到 versions 表作为里程碑
        self.db.execute(
            """INSERT INTO versions
               (id, project_id, version_type, label, summary, created_at)
               VALUES (?, ?, 'milestone', ?, ?, ?)""",
            (f"stop_{now[:10]}", project_id,
             f"人类裁定: {decision}",
             reason or f"收手决策: {decision}",
             now),
        )
        self.db.commit()
