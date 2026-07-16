"""引擎一 — 自动版本捕获

VersionCapture 从 Polaris 的自然操作中自动创建版本记录。
用户无需手动标记——系统从事件中自动触发。

触发事件:
    - 代码运行结束并输出结果 → 研究版本
    - 收到审稿意见并执行修改 → 审稿迭代版本
    - 人类确认"收手" → 里程碑版本
    - 干净房间审稿完成 → 审稿记录

PRD §1-2: 自动版本捕获
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..core.database import Database


VersionType = str  # "research" | "review_iteration" | "milestone" | "review_record"


@dataclass
class Version:
    """一个版本。"""
    id: str
    project_id: str
    version_type: VersionType
    parent_version: str = ""
    label: str = ""
    artifact_paths: list[str] = None
    summary: str = ""
    created_at: str = ""

    def __post_init__(self):
        if self.artifact_paths is None:
            self.artifact_paths = []


class VersionCapture:
    """自动版本管理。

    用法:
        db = Database(...)
        vc = VersionCapture(db)

        # 自动创建研究版本
        vid = vc.capture_research(
            project_id="sahara-dust",
            label="BET模型 RH_c 计算",
            artifacts=["figures/fig2.png", "outputs/results.json"],
            summary="成功运行 BET-逾渗模型，RH_c=54%"
        )

        # 查询版本链
        chain = vc.get_version_chain("v5_20260701_1432")
    """

    def __init__(self, db: Database):
        self.db = db
        self.db.initialize()

    # ---- 创建版本 ----

    def capture_research(
        self,
        project_id: str,
        label: str = "",
        artifacts: list[str] | None = None,
        summary: str = "",
        parent_version: str = "",
    ) -> str:
        """捕获一个研究版本。"""
        return self._create_version(
            project_id=project_id,
            version_type="research",
            label=label or f"研究_{datetime.now().strftime('%m%d_%H%M')}",
            artifacts=artifacts or [],
            summary=summary,
            parent_version=parent_version,
        )

    def capture_review_iteration(
        self,
        project_id: str,
        feedback_id: str,
        label: str = "",
        artifacts: list[str] | None = None,
        summary: str = "",
        parent_version: str = "",
    ) -> str:
        """捕获一个审稿迭代版本。"""
        fb_short = feedback_id[-8:] if len(feedback_id) > 8 else feedback_id
        return self._create_version(
            project_id=project_id,
            version_type="review_iteration",
            label=label or f"审稿_v{fb_short}",
            artifacts=artifacts or [],
            summary=summary,
            parent_version=parent_version,
        )

    def capture_milestone(
        self,
        project_id: str,
        name: str,
        artifacts: list[str] | None = None,
        summary: str = "",
        parent_version: str = "",
    ) -> str:
        """捕获一个里程碑版本。"""
        return self._create_version(
            project_id=project_id,
            version_type="milestone",
            label=f"里程碑_{datetime.now().strftime('%Y%m%d')}_{name}",
            artifacts=artifacts or [],
            summary=summary,
            parent_version=parent_version,
        )

    def capture_review_record(
        self,
        project_id: str,
        review_report_id: str,
        label: str = "",
        parent_version: str = "",
    ) -> str:
        """捕获一个审稿记录版本。"""
        return self._create_version(
            project_id=project_id,
            version_type="review_record",
            label=label or f"审稿_{datetime.now().strftime('%m%d_%H%M')}",
            artifacts=[f"reviews/{review_report_id}.md"],
            summary=f"审稿报告 {review_report_id}",
            parent_version=parent_version,
        )

    def _create_version(
        self,
        project_id: str,
        version_type: VersionType,
        label: str,
        artifacts: list[str],
        summary: str,
        parent_version: str = "",
    ) -> str:
        """内部：创建版本记录。"""
        import json

        vid = f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        artifacts_json = json.dumps(artifacts, ensure_ascii=False)

        self.db.execute(
            """INSERT INTO versions
               (id, project_id, version_type, parent_version, label, artifact_paths, summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (vid, project_id, version_type, parent_version, label, artifacts_json, summary, now),
        )
        self.db.commit()
        return vid

    # ---- 查询 ----

    def get_version(self, version_id: str) -> Optional[Version]:
        """查询单个版本。"""
        import json
        row = self.db.fetch_one("SELECT * FROM versions WHERE id = ?", (version_id,))
        if row is None:
            return None
        try:
            artifacts = json.loads(row["artifact_paths"]) if row["artifact_paths"] else []
        except (json.JSONDecodeError, TypeError):
            artifacts = []
        return Version(
            id=row["id"],
            project_id=row["project_id"],
            version_type=row["version_type"],
            parent_version=row["parent_version"] or "",
            label=row["label"] or "",
            artifact_paths=artifacts,
            summary=row["summary"] or "",
            created_at=row["created_at"],
        )

    def get_version_chain(self, version_id: str, max_depth: int = 20) -> list[Version]:
        """获取版本链（从指定版本追溯到根）。"""
        chain = []
        current = version_id
        for _ in range(max_depth):
            v = self.get_version(current)
            if v is None:
                break
            chain.append(v)
            if not v.parent_version:
                break
            current = v.parent_version
        return chain

    def get_latest_version(self, project_id: str) -> Optional[Version]:
        """获取项目最新版本。"""
        row = self.db.fetch_one(
            "SELECT * FROM versions WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        )
        if row is None:
            return None
        return self.get_version(row["id"])

    def get_project_versions(
        self, project_id: str, version_type: VersionType | None = None, limit: int = 20
    ) -> list[Version]:
        """列出项目的版本。"""
        import json
        if version_type:
            rows = self.db.fetch_all(
                "SELECT * FROM versions WHERE project_id = ? AND version_type = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, version_type, limit),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM versions WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            )
        return [self.get_version(r["id"]) for r in rows if self.get_version(r["id"])]

    def count_versions(self, project_id: str) -> dict:
        """统计项目版本数（按类型）。"""
        rows = self.db.fetch_all(
            "SELECT version_type, COUNT(*) as c FROM versions WHERE project_id = ? GROUP BY version_type",
            (project_id,),
        )
        return {r["version_type"]: r["c"] for r in rows}
