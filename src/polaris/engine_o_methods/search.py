"""引擎O — 方法检索索引

在 MethodLibrary 的 SQL 检索基础上，提供：
- 领域词典（同义词映射）
- 热度排序（调用频率加权）
- 关联推荐（"使用此方法的人也使用了..."）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core.database import Database


# ============================================================
# 领域词典
# ============================================================

# 大气科学领域同义词映射
DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "湿度": ["比湿", "相对湿度", "RH", "specific humidity", "水汽", "q", "露点", "D2M"],
    "温度": ["气温", "t2m", "地表温度", "位温", "potential temperature", "SAT"],
    "风场": ["U", "V", "风速", "wind speed", "矢量风", "风应力", "850hPa风场"],
    "降水": ["precipitation", "tp", "降雨", "降雪", "总降水", "对流降水", "大尺度降水"],
    "沙尘": ["dust", "矿物沙尘", "气溶胶", "AOD", "沙尘暴", "粉尘", "PM10"],
    "起电": ["摩擦起电", "triboelectric", "电荷", "闪电", "lightning", "静电", "放电"],
    "BET": ["Brunauer-Emmett-Teller", "多层吸附", "吸附等温线", "表面吸附"],
    "逾渗": ["percolation", "渗流", "连通性", "逾渗阈值", "导电网络"],
    "EOF": ["经验正交函数", "主成分分析", "PCA", "模态", "时空分解"],
    "回归": ["线性回归", "多元回归", "logistic", "Firth", "惩罚回归", "GLM"],
    "因果": ["因果推断", "DAG", "有向无环图", "CEM", "匹配", "工具变量"],
    "BET吸附": ["BET", "Brunauer-Emmett-Teller", "吸附等温线", "多层吸附", "表面吸附"],
    "电荷": ["起电", "摩擦起电", "triboelectric", "静电", "放电", "闪电", "lightning"],
    "RC电路": ["电荷弛豫", "RC弛豫", "放电时间", "surface conductivity"],
    "湿度门控": ["湿度抑制", "humidity gating", "RH dependence", "湿度依赖"],
}


def expand_query(query: str) -> list[str]:
    """扩展查询词——加入同义词。"""
    tokens = [query]
    for canonical, synonyms in DOMAIN_SYNONYMS.items():
        if canonical in query:
            tokens.extend(synonyms)
        for syn in synonyms:
            if syn.lower() in query.lower():
                tokens.append(canonical)
                tokens.extend(synonyms)
                break
    return list(set(tokens))


# ============================================================
# 热度追踪
# ============================================================

class UsageTracker:
    """方法调用频率追踪。

    每次方法被调用（成功或失败）时记录，用于排序优化。
    热度 = α × 近期调用次数 + (1-α) × 历史调用次数（指数衰减）。
    """

    def __init__(self, db: Database):
        self.db = db
        self.alpha = 0.3  # 近期权重

    def record_usage(self, method_id: str, success: bool) -> None:
        """记录一次方法调用。"""
        if success:
            self.db.execute(
                "UPDATE methods SET success_count = success_count + 1, updated_at = datetime('now','localtime') WHERE id = ?",
                (method_id,),
            )
        else:
            self.db.execute(
                "UPDATE methods SET failure_count = failure_count + 1, updated_at = datetime('now','localtime') WHERE id = ?",
                (method_id,),
            )
        self.db.commit()

    def get_hot_methods(self, limit: int = 10) -> list[str]:
        """获取热门方法（按成功调用次数排序）。"""
        rows = self.db.fetch_all(
            "SELECT id FROM methods WHERE status = 'verified' ORDER BY success_count DESC LIMIT ?",
            (limit,),
        )
        return [r["id"] for r in rows]

    def get_success_rate(self, method_id: str) -> float:
        """获取方法的成功率。"""
        row = self.db.fetch_one(
            "SELECT success_count, failure_count FROM methods WHERE id = ?",
            (method_id,),
        )
        if row is None:
            return 0.0
        total = row["success_count"] + row["failure_count"]
        return row["success_count"] / total if total > 0 else 0.0


# ============================================================
# 关联推荐
# ============================================================

class RecommendationEngine:
    """基于编排条目的关联推荐。

    "使用此原子方法的人也使用了..."
    通过编排条目中共同出现的原子方法来推断关联。
    """

    def __init__(self, db: Database):
        self.db = db

    def get_related_methods(self, method_id: str, limit: int = 5) -> list[str]:
        """找到与本方法在相同编排条目中共现的其他原子方法。"""
        # 找到包含本方法的所有编排条目
        orch_rows = self.db.fetch_all(
            "SELECT id FROM methods WHERE type = 'orchestration' AND description LIKE ?",
            (f"%{method_id}%",),
        )

        related_ids: set[str] = set()
        for orch in orch_rows:
            # 找到同一编排条目下的其他原子方法
            child_rows = self.db.fetch_all(
                "SELECT id FROM methods WHERE parent_id = ? AND id != ?",
                (orch["id"], method_id),
            )
            related_ids.update(r["id"] for r in child_rows)

        return list(related_ids)[:limit]
