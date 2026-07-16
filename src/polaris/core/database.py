"""SQLite 数据库 —— 建表与连接管理

TDD §4 定义的 13 张表。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


SCHEMA = """
-- ============================================================
-- 方法库（引擎O）
-- ============================================================
CREATE TABLE IF NOT EXISTS methods (
    id              TEXT PRIMARY KEY,          -- 如 "atom_bet_isotherm"
    name            TEXT NOT NULL,             -- 方法名称
    type            TEXT NOT NULL CHECK(type IN ('atom','orchestration','parameter_instance')),
    parent_id       TEXT,                      -- 编排条目→原子方法的引用
    description     TEXT NOT NULL,             -- 自然语言描述
    domain          TEXT,                      -- 学科领域
    variables       TEXT,                      -- 涉及变量（JSON 数组）
    status          TEXT NOT NULL DEFAULT 'candidate'
                        CHECK(status IN ('candidate','pending_confirm','verified','rejected','deprecated')),
    quality_score   REAL DEFAULT 0.0,          -- 引擎二审查质量分
    failure_count   INTEGER DEFAULT 0,         -- 累计失败次数
    success_count   INTEGER DEFAULT 0,         -- 累计成功次数
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    reviewed_at     TEXT,                      -- 最近一次引擎二审查时间
    confirmed_at    TEXT,                      -- 人类确认时间
    confirmed_by    TEXT DEFAULT 'human'       -- 确认者
);

CREATE TABLE IF NOT EXISTS method_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    method_id       TEXT NOT NULL REFERENCES methods(id),
    version         INTEGER NOT NULL,
    code_path       TEXT,                      -- 方法代码文件路径
    params_json     TEXT,                      -- 参数（JSON）
    change_summary  TEXT,                      -- 变更摘要
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS method_failure_conditions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    method_id       TEXT NOT NULL REFERENCES methods(id),
    condition_desc  TEXT NOT NULL,             -- 失效条件描述
    detected_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    context_json    TEXT                       -- 失效上下文（JSON）
);

-- ============================================================
-- 反馈主线 & 版本追踪（引擎一）
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback_items (
    id              TEXT PRIMARY KEY,          -- 如 "feedback_20260701_001"
    project_id      TEXT NOT NULL,             -- 所属项目
    source          TEXT NOT NULL,             -- 来源（引擎二·方法论溯源 / 红队 / 人类）
    content         TEXT NOT NULL,             -- 审稿意见原文
    status          TEXT NOT NULL DEFAULT 'open'
                        CHECK(status IN ('open','in_progress','resolved','wontfix','duplicate')),
    priority        TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    resolved_at     TEXT,
    resolution_note TEXT                       -- 解决方案说明
);

CREATE TABLE IF NOT EXISTS feedback_resolution_steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id     TEXT NOT NULL REFERENCES feedback_items(id),
    step_order      INTEGER NOT NULL,          -- 第几次修改
    version_ref     TEXT,                      -- 关联版本号
    action_taken    TEXT NOT NULL,             -- 做了什么修改
    file_paths      TEXT,                      -- 修改的文件（JSON 数组）
    reviewer_result TEXT,                      -- Reviewer 复查结果
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS versions (
    id              TEXT PRIMARY KEY,          -- 如 "v5_20260701_1432"
    project_id      TEXT NOT NULL,
    version_type    TEXT NOT NULL CHECK(version_type IN ('research','review_iteration','milestone','review_record')),
    parent_version  TEXT,                      -- 上一版本
    label           TEXT,                      -- 自动命名标签
    artifact_paths  TEXT,                      -- 产物路径（JSON 数组）
    summary         TEXT,                      -- 自动生成摘要
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- CRT 拓扑（引擎一 & 引擎四共用）
-- ============================================================
CREATE TABLE IF NOT EXISTS crt_nodes (
    id              TEXT PRIMARY KEY,          -- 如 "node_042"
    parent_id       TEXT,                      -- 父节点
    project_id      TEXT NOT NULL,
    node_type       TEXT NOT NULL CHECK(node_type IN ('analysis','validation','migration','discovery','dead','milestone','literature')),
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active','completed','frozen','merged')),
    summary         TEXT NOT NULL,             -- ≤500字摘要
    context_packet_json TEXT,                  -- 上下文数据包（JSON）
    surprise_score  REAL DEFAULT 0.0,
    physics_fence_result TEXT,                 -- 物理围栏结果
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS crt_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_node     TEXT NOT NULL REFERENCES crt_nodes(id),
    target_node     TEXT NOT NULL REFERENCES crt_nodes(id),
    edge_type       TEXT NOT NULL CHECK(edge_type IN ('parent','merge','contradict','reference')),
    label           TEXT
);

-- ============================================================
-- 深度验证（引擎二）
-- ============================================================
CREATE TABLE IF NOT EXISTS review_reports (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    target_node     TEXT,                      -- 被审查的 CRT 节点
    review_mode     TEXT NOT NULL CHECK(review_mode IN ('clean_room','methodology_trace','red_team','multi_expert','counterfactual','competition')),
    summary         TEXT NOT NULL,
    quality_score   REAL,                      -- 综合质量分
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS expert_opinions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id       TEXT NOT NULL REFERENCES review_reports(id),
    expert_role     TEXT NOT NULL,             -- 如 "表面科学专家"
    opinion_text    TEXT NOT NULL,
    severity        TEXT DEFAULT 'medium' CHECK(severity IN ('low','medium','high','critical')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS sensitivity_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id       TEXT NOT NULL REFERENCES review_reports(id),
    parameter_name  TEXT NOT NULL,
    base_value      REAL,
    range_low       REAL,
    range_high      REAL,
    impact_score    REAL,                      -- 对输出的影响程度
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- 全局方法迁移（引擎三）
-- ============================================================
CREATE TABLE IF NOT EXISTS migration_runs (
    id              TEXT PRIMARY KEY,
    method_id       TEXT NOT NULL REFERENCES methods(id),
    source_region   TEXT NOT NULL,             -- 源区域
    target_region   TEXT NOT NULL,             -- 目标区域
    migration_level INTEGER NOT NULL DEFAULT 0,-- 0/1/2
    status          TEXT NOT NULL DEFAULT 'running'
                        CHECK(status IN ('running','success','anomaly','blocked')),
    anomaly_detail  TEXT,                      -- 异常描述
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    completed_at    TEXT
);

-- ============================================================
-- 发现日志（引擎四）
-- ============================================================
CREATE TABLE IF NOT EXISTS discoveries (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    confidence      REAL,                      -- 0-1 置信度
    source_node     TEXT REFERENCES crt_nodes(id), -- 发现来源节点
    status          TEXT NOT NULL DEFAULT 'candidate'
                        CHECK(status IN ('candidate','confirmed','refuted','published')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- 索引
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_methods_status ON methods(status);
CREATE INDEX IF NOT EXISTS idx_methods_type ON methods(type);
CREATE INDEX IF NOT EXISTS idx_feedback_project ON feedback_items(project_id, status);
CREATE INDEX IF NOT EXISTS idx_crt_project ON crt_nodes(project_id, status);
CREATE INDEX IF NOT EXISTS idx_crt_parent ON crt_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_versions_project ON versions(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_review_project ON review_reports(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_migration_method ON migration_runs(method_id, status);
CREATE INDEX IF NOT EXISTS idx_discoveries_project ON discoveries(project_id, status);
"""


class Database:
    """SQLite 数据库连接管理器。

    用法:
        db = Database("H:\\Polaris\\data\\polaris.db")
        db.initialize()          # 建表（幂等）
        rows = db.fetch_all("SELECT * FROM methods WHERE status = ?", ("verified",))
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        """建表（幂等——所有 CREATE 语句均使用 IF NOT EXISTS）。"""
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def fetch_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchone()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
