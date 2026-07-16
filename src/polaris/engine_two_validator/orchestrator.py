"""引擎二 — 审稿编排器

ReviewOrchestrator 是审稿闭环的核心：
1. 接收审稿请求（CleanRoomRequest）
2. 调用 LLMClient 发送到模型
3. 解析回复为结构化数据
4. 存入 review_reports + expert_opinions 表
5. 自动创建 feedback_items

M3 阶段重点：将四种审稿模式串联为完整管线。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..core.database import Database
from ..core.llm_client import LLMClient, LLMResponse
from ..engine_one_tracker.cleanroom import CleanRoomRequest
from ..engine_one_tracker.feedback import FeedbackTracker
from ..engine_one_tracker.versioning import VersionCapture
from .trace import MethodologyTracer, TraceReport
from .redteam import RedTeamReviewer, RedTeamReport
from .debate import MultiExpertDebate, DebateReport


@dataclass
class ReviewResult:
    """一次审稿的完整结果（所有模式通用）。"""
    report_id: str
    review_mode: str
    llm_response: LLMResponse | None = None
    trace_report: TraceReport | None = None
    redteam_report: RedTeamReport | None = None
    debate_report: DebateReport | None = None
    feedback_ids: list[str] = None
    elapsed_seconds: float = 0.0

    def __post_init__(self):
        if self.feedback_ids is None:
            self.feedback_ids = []


class ReviewOrchestrator:
    """审稿编排器——四种审稿模式的统一调度。

    用法:
        orch = ReviewOrchestrator(db, llm_client)

        # 红队审稿
        result = orch.run_red_team(paper_content, paper_path)

        # 多角色辩论
        result = orch.run_multi_expert(paper_content, paper_path)

        # 查询历史审稿
        reports = orch.get_review_history(project_id)
    """

    def __init__(self, db: Database, llm_client: LLMClient | None = None):
        self.db = db
        self.db.initialize()
        self.llm = llm_client
        self.feedback = FeedbackTracker(db)
        self.versions = VersionCapture(db)

    # ---- 四种审稿模式 ----

    def run_clean_room(
        self,
        paper_content: str,
        paper_path: str = "",
        project_id: str = "default",
        review_standard: str = "",
    ) -> ReviewResult:
        """运行标准干净房间审稿。"""
        from ..engine_one_tracker.cleanroom import CleanRoomScheduler

        scheduler = CleanRoomScheduler()
        req = scheduler.create_request(
            paper_content=paper_content,
            paper_path=paper_path,
            review_mode="clean_room",
            review_standard=review_standard,
        )

        return self._execute_and_store(req, project_id, "clean_room")

    def run_methodology_trace(
        self,
        paper_content: str,
        paper_path: str = "",
        project_id: str = "default",
    ) -> ReviewResult:
        """运行方法论溯源审稿。"""
        tracer = MethodologyTracer()
        paper_title = paper_path.rsplit("\\", 1)[-1].rsplit(".", 1)[0] if paper_path else ""
        req = tracer.build_request(paper_content, paper_path, title=paper_title)

        result = self._execute_and_store(req, project_id, "methodology_trace")

        # 解析为结构化报告
        if result.llm_response:
            try:
                result.trace_report = tracer.parse_response(
                    result.llm_response.content, title=paper_title
                )
            except Exception:
                pass

        return result

    def run_red_team(
        self,
        paper_content: str,
        paper_path: str = "",
        project_id: str = "default",
    ) -> ReviewResult:
        """运行红队审稿。"""
        rt = RedTeamReviewer()
        paper_title = paper_path.rsplit("\\", 1)[-1].rsplit(".", 1)[0] if paper_path else ""
        req = rt.build_request(paper_content, paper_path, title=paper_title)

        result = self._execute_and_store(req, project_id, "red_team")

        if result.llm_response:
            try:
                result.redteam_report = rt.parse_response(
                    result.llm_response.content, title=paper_title
                )
            except Exception:
                pass

        return result

    def run_multi_expert(
        self,
        paper_content: str,
        paper_path: str = "",
        project_id: str = "default",
        expert_roles: list[str] | None = None,
    ) -> ReviewResult:
        """运行多角色辩论审稿。"""
        debate = MultiExpertDebate()
        if expert_roles is None:
            expert_roles = debate.auto_detect_experts(paper_content)
        req = debate.build_request(paper_content, paper_path, expert_roles=expert_roles)

        result = self._execute_and_store(req, project_id, "multi_expert")

        paper_title = paper_path.rsplit("\\", 1)[-1].rsplit(".", 1)[0] if paper_path else ""
        if result.llm_response:
            try:
                result.debate_report = debate.parse_response(
                    result.llm_response.content, title=paper_title
                )
            except Exception:
                pass

        return result

    # ---- 内部执行 + 存储 ----

    def _execute_and_store(
        self,
        req: CleanRoomRequest,
        project_id: str,
        review_mode: str,
    ) -> ReviewResult:
        """执行审稿（发送 LLM 或 dry-run），将结果存入数据库。"""
        report_id = f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 调用 LLM
        llm_response = None
        if self.llm:
            try:
                llm_response = self.llm.chat(req.to_llm_messages())
            except Exception as e:
                llm_response = LLMResponse(
                    content=f"LLM 调用失败: {e}",
                    model=self.llm.config.model,
                    elapsed_seconds=0.0,
                )
        else:
            # Dry-run 模式
            llm_response = LLMResponse(
                content="[DRY-RUN] LLM 客户端未配置。审稿请求已生成，等待真实 API 调用。",
                model="dry-run",
                elapsed_seconds=0.0,
            )

        # 存入 review_reports 表
        self.db.execute(
            """INSERT INTO review_reports
               (id, project_id, target_node, review_mode, summary, quality_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (report_id, project_id, "", review_mode,
             f"{review_mode} 审稿完成 (模式: {req.review_mode})",
             0.0, now),
        )

        # 创建版本记录
        self.versions.capture_review_record(
            project_id=project_id,
            review_report_id=report_id,
            label=f"{review_mode}审稿_{now[:10]}",
        )

        # 从 LLM 回复中提取审稿意见 → 创建 feedback_items
        feedback_ids = self._extract_feedback_items(
            project_id=project_id,
            source=f"引擎二·{review_mode}",
            raw_response=llm_response.content,
        )

        self.db.commit()

        return ReviewResult(
            report_id=report_id,
            review_mode=review_mode,
            llm_response=llm_response,
            feedback_ids=feedback_ids,
            elapsed_seconds=llm_response.elapsed_seconds,
        )

    def _extract_feedback_items(
        self,
        project_id: str,
        source: str,
        raw_response: str,
    ) -> list[str]:
        """从 LLM 回复中提取审稿意见并创建 feedback_items。

        当前为简化版——将整个回复作为多段意见处理。
        M4+ 可升级为 LLM 结构化提取。
        """
        if not raw_response or raw_response.startswith("[DRY-RUN]"):
            return []

        # 按 ## 或 ### 分割为段落，每段作为一条意见
        import re
        sections = re.split(r"\n(?=##?\s)", raw_response)

        ids = []
        for i, section in enumerate(sections[:10]):  # 最多提取10条
            section = section.strip()
            if len(section) < 20:  # 太短的忽略
                continue

            # 检测严重程度
            priority = "medium"
            if "🔴" in section or "致命" in section or "critical" in section.lower():
                priority = "critical"
            elif "🟠" in section or "重要" in section or "high" in section.lower():
                priority = "high"
            elif "🟢" in section or "建议" in section:
                priority = "low"

            fid = self.feedback.create(
                project_id=project_id,
                source=source,
                content=section[:500],  # 截断长意见
                priority=priority,
            )
            ids.append(fid)

        return ids

    # ---- 查询 ----

    def get_review_history(
        self, project_id: str, limit: int = 20
    ) -> list[dict]:
        """获取项目的审稿历史。"""
        rows = self.db.fetch_all(
            """SELECT * FROM review_reports
               WHERE project_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (project_id, limit),
        )
        return [dict(r) for r in rows]

    def get_review_report(self, report_id: str) -> dict | None:
        """获取单次审稿的完整报告（含专家意见）。"""
        report = self.db.fetch_one(
            "SELECT * FROM review_reports WHERE id = ?", (report_id,)
        )
        if report is None:
            return None

        expert_rows = self.db.fetch_all(
            "SELECT * FROM expert_opinions WHERE report_id = ?", (report_id,)
        )
        sensitivity_rows = self.db.fetch_all(
            "SELECT * FROM sensitivity_results WHERE report_id = ?", (report_id,)
        )

        return {
            "report": dict(report),
            "expert_opinions": [dict(r) for r in expert_rows],
            "sensitivity": [dict(r) for r in sensitivity_rows],
        }
