"""引擎O — 方法库核心引擎

MethodLibrary 类提供方法的完整生命周期管理：
- CRUD 操作
- 三层结构（原子方法 / 编排条目 / 参数实例）
- 自然语言 + 结构化检索
- 版本链管理
- 失败条件记录
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.database import Database


# ============================================================
# 数据模型
# ============================================================

MethodType = str  # "atom" | "orchestration" | "parameter_instance"
MethodStatus = str  # "candidate" | "pending_confirm" | "verified" | "rejected" | "deprecated"


@dataclass
class MethodEntry:
    """方法库条目的内存表示。"""

    id: str
    name: str
    type: MethodType
    description: str
    domain: str = ""
    variables: list[str] = field(default_factory=list)
    status: MethodStatus = "candidate"
    parent_id: str = ""
    quality_score: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "domain": self.domain,
            "variables": self.variables,
            "status": self.status,
            "parent_id": self.parent_id,
            "quality_score": self.quality_score,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
        }


# ============================================================
# MethodLibrary
# ============================================================

class MethodLibrary:
    """方法库核心引擎。

    用法:
        db = Database("H:\\Polaris\\data\\polaris.db")
        lib = MethodLibrary(db)

        # 录入
        lib.add_method(
            name="BET吸附等温线计算",
            type="atom",
            description="使用 BET 方程从 RH 计算水膜厚度",
            domain="表面科学",
            variables=["相对湿度", "BET常数c", "单层厚度"],
        )

        # 检索
        results = lib.search("BET 吸附")
        results = lib.search_by_filter(domain="大气科学", type="atom")

        # 版本
        lib.add_version("atom_bet_isotherm", 2, "/path/to/v2.py",
                        "修正了温度依赖项")
    """

    def __init__(self, db: Database):
        self.db = db
        self.db.initialize()

    # ---- CRUD ----

    def add_method(
        self,
        name: str,
        type: MethodType,
        description: str,
        domain: str = "",
        variables: list[str] | None = None,
        parent_id: str = "",
        status: MethodStatus = "candidate",
    ) -> str:
        """录入新方法。返回方法 ID。"""
        method_id = self._generate_id(name, type)

        # 检查重复
        existing = self.db.fetch_one(
            "SELECT id FROM methods WHERE id = ?", (method_id,)
        )
        if existing:
            method_id = f"{method_id}_{uuid.uuid4().hex[:6]}"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        vars_json = json.dumps(variables or [], ensure_ascii=False)

        self.db.execute(
            """INSERT INTO methods
               (id, name, type, description, domain, variables,
                parent_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (method_id, name, type, description, domain, vars_json,
             parent_id, status, now, now),
        )
        self.db.commit()

        # 初始版本
        self.add_version(method_id, 1, "", "初始录入")
        return method_id

    def get_method(self, method_id: str) -> Optional[MethodEntry]:
        """按 ID 查询方法。"""
        row = self.db.fetch_one(
            "SELECT * FROM methods WHERE id = ?", (method_id,)
        )
        if row is None:
            return None
        return self._row_to_entry(row)

    def update_method(
        self,
        method_id: str,
        name: str | None = None,
        description: str | None = None,
        domain: str | None = None,
        variables: list[str] | None = None,
        status: MethodStatus | None = None,
        quality_score: float | None = None,
    ) -> bool:
        """更新方法元数据。"""
        entry = self.get_method(method_id)
        if entry is None:
            return False

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if domain is not None:
            updates.append("domain = ?")
            params.append(domain)
        if variables is not None:
            updates.append("variables = ?")
            params.append(json.dumps(variables, ensure_ascii=False))
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if quality_score is not None:
            updates.append("quality_score = ?")
            params.append(quality_score)

        if not updates:
            return True

        updates.append("updated_at = ?")
        params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        params.append(method_id)

        self.db.execute(
            f"UPDATE methods SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        self.db.commit()
        return True

    def list_methods(
        self,
        type: MethodType | None = None,
        status: MethodStatus | None = None,
        domain: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MethodEntry]:
        """列出方法条目。"""
        clauses = ["1=1"]
        params: list = []

        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)

        rows = self.db.fetch_all(
            f"SELECT * FROM methods WHERE {' AND '.join(clauses)} "
            f"ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        )
        return [self._row_to_entry(r) for r in rows]

    # ---- 检索 ----

    def search(self, query: str, limit: int = 20) -> list[MethodEntry]:
        """自然语言检索。

        对 name + description 做关键词匹配。
        支持中文分词简化版（按字符 n-gram）。
        """
        keywords = self._tokenize(query)
        if not keywords:
            return []

        # 构建 LIKE 条件
        like_clauses = []
        params: list = []
        for kw in keywords:
            like_clauses.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{kw}%", f"%{kw}%"])

        rows = self.db.fetch_all(
            f"SELECT * FROM methods WHERE {' OR '.join(like_clauses)} "
            f"ORDER BY quality_score DESC, success_count DESC LIMIT ?",
            tuple(params + [limit]),
        )
        return [self._row_to_entry(r) for r in rows]

    def search_by_filter(
        self,
        domain: str | None = None,
        type: MethodType | None = None,
        status: MethodStatus | None = None,
        variable: str | None = None,
        min_quality: float | None = None,
        limit: int = 50,
    ) -> list[MethodEntry]:
        """结构化检索。"""
        clauses = ["1=1"]
        params: list = []

        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if variable is not None:
            clauses.append("variables LIKE ?")
            params.append(f"%{variable}%")
        if min_quality is not None:
            clauses.append("quality_score >= ?")
            params.append(min_quality)

        rows = self.db.fetch_all(
            f"SELECT * FROM methods WHERE {' AND '.join(clauses)} "
            f"ORDER BY quality_score DESC LIMIT ?",
            tuple(params + [limit]),
        )
        return [self._row_to_entry(r) for r in rows]

    def _tokenize(self, query: str) -> list[str]:
        """简易中文+英文分词。"""
        import re
        # 提取中文字符 + 英文单词
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", query)
        english = re.findall(r"[a-zA-Z]{2,}", query)
        # 对中文做 2-gram
        tokens = list(chinese)
        for cw in chinese:
            tokens.extend([cw[i:i+2] for i in range(len(cw)-1)])
        tokens.extend(english)
        # 去重 + 过滤太短的
        return list(set(t for t in tokens if len(t) >= 2))

    # ---- 版本管理 ----

    def add_version(
        self,
        method_id: str,
        version: int,
        code_path: str = "",
        change_summary: str = "",
        params: dict | None = None,
    ) -> int:
        """为方法添加一个版本记录。返回版本记录 ID。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params_json = json.dumps(params or {}, ensure_ascii=False)

        cursor = self.db.execute(
            """INSERT INTO method_versions
               (method_id, version, code_path, params_json, change_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (method_id, version, code_path, params_json, change_summary, now),
        )
        self.db.commit()
        return cursor.lastrowid

    def get_versions(self, method_id: str) -> list[dict]:
        """获取方法的所有版本。"""
        rows = self.db.fetch_all(
            "SELECT * FROM method_versions WHERE method_id = ? ORDER BY version DESC",
            (method_id,),
        )
        return [dict(r) for r in rows]

    def get_latest_version(self, method_id: str) -> int:
        """获取方法的最新版本号。"""
        row = self.db.fetch_one(
            "SELECT MAX(version) as max_v FROM method_versions WHERE method_id = ?",
            (method_id,),
        )
        return row["max_v"] if row and row["max_v"] else 0

    # ---- 失败条件 ----

    def add_failure_condition(
        self, method_id: str, condition_desc: str, context: dict | None = None
    ) -> int:
        """记录方法的失效条件。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ctx_json = json.dumps(context or {}, ensure_ascii=False)

        cursor = self.db.execute(
            """INSERT INTO method_failure_conditions
               (method_id, condition_desc, context_json, detected_at)
               VALUES (?, ?, ?, ?)""",
            (method_id, condition_desc, ctx_json, now),
        )

        # 递增 failure_count
        self.db.execute(
            "UPDATE methods SET failure_count = failure_count + 1, updated_at = ? WHERE id = ?",
            (now, method_id),
        )
        self.db.commit()
        return cursor.lastrowid

    def get_failure_conditions(self, method_id: str) -> list[dict]:
        """获取方法的失效条件列表。"""
        rows = self.db.fetch_all(
            "SELECT * FROM method_failure_conditions WHERE method_id = ? ORDER BY detected_at DESC",
            (method_id,),
        )
        return [dict(r) for r in rows]

    # ---- 统计 ----

    def get_stats(self) -> dict:
        """获取方法库统计。"""
        total = self.db.fetch_one("SELECT COUNT(*) as c FROM methods")
        by_type = self.db.fetch_all(
            "SELECT type, COUNT(*) as c FROM methods GROUP BY type"
        )
        by_status = self.db.fetch_all(
            "SELECT status, COUNT(*) as c FROM methods GROUP BY status"
        )
        by_domain = self.db.fetch_all(
            "SELECT domain, COUNT(*) as c FROM methods WHERE domain != '' GROUP BY domain"
        )

        return {
            "total": total["c"] if total else 0,
            "by_type": {r["type"]: r["c"] for r in by_type},
            "by_status": {r["status"]: r["c"] for r in by_status},
            "by_domain": {r["domain"]: r["c"] for r in by_domain},
        }

    # ---- 内部 ----

    def _generate_id(self, name: str, type: MethodType) -> str:
        """从名称生成方法 ID。"""
        type_prefix = {"atom": "atom", "orchestration": "orch", "parameter_instance": "param"}
        prefix = type_prefix.get(type, "meth")

        # 提取英文关键词或使用拼音简化
        import re
        english = re.findall(r"[a-zA-Z]+", name)
        if english:
            slug = "_".join(e.lower() for e in english[:3])
        else:
            slug = name[:8].replace(" ", "_")

        return f"{prefix}_{slug}"

    def _row_to_entry(self, row) -> MethodEntry:
        """将数据库行转换为 MethodEntry。"""
        variables = []
        if row["variables"]:
            try:
                variables = json.loads(row["variables"])
            except (json.JSONDecodeError, TypeError):
                variables = []

        return MethodEntry(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            description=row["description"],
            domain=row["domain"] or "",
            variables=variables,
            status=row["status"],
            parent_id=row["parent_id"] or "",
            quality_score=row["quality_score"] or 0.0,
            failure_count=row["failure_count"] or 0,
            success_count=row["success_count"] or 0,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
