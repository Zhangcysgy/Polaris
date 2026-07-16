"""引擎三 — 全局方法迁移

GlobalMigrator 将一个区域验证的分析方法自动适配到全球其他区域。

三级迁移策略（PRD §3-1）:
    Level 0: 直接复用 — 只改数据源区域
    Level 1: 参数适配 — 自动查找本地参数替换
    Level 2: 方程适配 — 标记为不可迁移，生成诊断报告

核心理念（PRD §3-3）:
    价值不在"全球验证"，而在发现差异。
    模型在源区域吻合但在目标区域偏离 → 引擎二的燃料。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from ..core.database import Database


class MigrationLevel(int, Enum):
    DIRECT_REUSE = 0      # 只改数据区域
    PARAMETER_ADAPT = 1   # 替换本地参数
    EQUATION_ADAPT = 2    # 方程不适用——标记


class MigrationStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    ANOMALY = "anomaly"       # 迁移成功但结果异常（差异即发现）
    BLOCKED = "blocked"       # 方程不适用——不可迁移


@dataclass
class MigrationResult:
    """一次区域迁移的结果。"""
    run_id: str
    method_id: str
    source_region: str
    target_region: str
    level: MigrationLevel
    status: MigrationStatus
    anomaly_detail: str = ""
    """异常描述——为什么目标区域的结果与源区域不同。"""
    migration_note: str = ""
    """迁移说明——做了哪些适配。"""
    created_at: str = ""

    def __post_init__(self):
        if not self.run_id:
            self.run_id = f"mig_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class RegionInfo:
    """区域信息。"""
    region_id: str          # 如 "sahara" | "central_asia" | "australia"
    name: str               # 人类可读名称
    lat_range: tuple[float, float] = (-90, 90)
    lon_range: tuple[float, float] = (-180, 180)
    data_availability: str = "unknown"   # "full" | "limited" | "missing"
    notes: str = ""


class GlobalMigrator:
    """全局方法迁移引擎。

    用法:
        db = Database(...)
        migrator = GlobalMigrator(db)

        # 将方法从 Sahara 迁移到中亚
        result = migrator.migrate(
            method_id="orch_bet",
            source_region="sahara",
            target_region="central_asia",
        )
        print(f"状态: {result.status}, 级别: {result.level}")
    """

    # 预设区域库（大气科学常用沙尘源区）
    PRESET_REGIONS: dict[str, RegionInfo] = {
        "sahara": RegionInfo(
            "sahara", "撒哈拉沙漠",
            lat_range=(10, 40), lon_range=(-20, 40),
            data_availability="full",
            notes="北非沙尘主要源区。ERA5+卫星闪电数据充足。"
        ),
        "central_asia": RegionInfo(
            "central_asia", "中亚（塔克拉玛干/戈壁）",
            lat_range=(35, 50), lon_range=(70, 120),
            data_availability="limited",
            notes="矿物成分与Sahara不同（更多长石和黏土）。卫星闪电数据可用。"
        ),
        "australia": RegionInfo(
            "australia", "澳大利亚沙漠",
            lat_range=(-35, -20), lon_range=(120, 145),
            data_availability="limited",
            notes="南半球沙尘源区。矿物以石英为主。闪电数据有限。"
        ),
        "middle_east": RegionInfo(
            "middle_east", "中东（阿拉伯半岛）",
            lat_range=(15, 35), lon_range=(35, 60),
            data_availability="limited",
            notes="含高比例方解石沙尘。闪电数据可用。"
        ),
        "north_america": RegionInfo(
            "north_america", "北美西南部",
            lat_range=(25, 45), lon_range=(-125, -100),
            data_availability="limited",
            notes="美国西南部和墨西哥北部。沙尘排放量远小于Sahara。"
        ),
        "south_america": RegionInfo(
            "south_america", "南美（巴塔哥尼亚）",
            lat_range=(-55, -35), lon_range=(-75, -60),
            data_availability="missing",
            notes="数据覆盖差。暂不适合自动迁移。"
        ),
    }

    def __init__(self, db: Database):
        self.db = db
        self.db.initialize()

    def migrate(
        self,
        method_id: str,
        source_region: str,
        target_region: str,
    ) -> MigrationResult:
        """执行方法迁移。

        当前M4框架版本：返回迁移策略分析。
        M5+将接入真实数据下载和代码执行。
        """
        target_info = self.PRESET_REGIONS.get(target_region)
        if target_info is None:
            return MigrationResult(
                run_id="",
                method_id=method_id,
                source_region=source_region,
                target_region=target_region,
                level=MigrationLevel.EQUATION_ADAPT,
                status=MigrationStatus.BLOCKED,
                anomaly_detail=f"未知区域: {target_region}",
            )

        # 确定迁移级别
        if target_info.data_availability == "full":
            level = MigrationLevel.DIRECT_REUSE
        elif target_info.data_availability == "limited":
            level = MigrationLevel.PARAMETER_ADAPT
        else:
            level = MigrationLevel.EQUATION_ADAPT

        # 创建迁移运行记录
        result = MigrationResult(
            method_id=method_id,
            source_region=source_region,
            target_region=target_region,
            level=level,
            status=MigrationStatus.RUNNING if level != MigrationLevel.EQUATION_ADAPT
                   else MigrationStatus.BLOCKED,
            migration_note=self._generate_migration_note(source_region, target_region, level),
        )

        # 存入数据库
        self.db.execute(
            """INSERT INTO migration_runs
               (id, method_id, source_region, target_region, migration_level, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (result.run_id, method_id, source_region, target_region,
             level.value, result.status.value, result.created_at),
        )
        self.db.commit()

        return result

    def batch_migrate(
        self,
        method_id: str,
        source_region: str,
        target_regions: list[str],
    ) -> list[MigrationResult]:
        """批量迁移——将一个方法并行应用到多个区域。"""
        results = []
        for region in target_regions:
            result = self.migrate(method_id, source_region, region)
            results.append(result)
        return results

    def auto_select_targets(
        self, source_region: str, method_domain: str = "atmospheric_science"
    ) -> list[str]:
        """自动选择目标区域——排除源区域，按数据可用性排序。"""
        targets = []
        for rid, info in self.PRESET_REGIONS.items():
            if rid == source_region:
                continue
            if info.data_availability != "missing":
                targets.append(rid)

        # 按数据可用性排序: full > limited > missing
        order = {"full": 0, "limited": 1, "missing": 2}
        targets.sort(key=lambda r: order.get(
            self.PRESET_REGIONS[r].data_availability, 2
        ))
        return targets

    def get_migration_history(
        self, method_id: str, limit: int = 20
    ) -> list[MigrationResult]:
        """获取方法的迁移历史。"""
        rows = self.db.fetch_all(
            """SELECT * FROM migration_runs
               WHERE method_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (method_id, limit),
        )
        return [
            MigrationResult(
                run_id=r["id"],
                method_id=r["method_id"],
                source_region=r["source_region"],
                target_region=r["target_region"],
                level=MigrationLevel(r["migration_level"]),
                status=MigrationStatus(r["status"]),
                anomaly_detail=r["anomaly_detail"] or "",
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_anomalies(self, method_id: str | None = None) -> list[MigrationResult]:
        """获取所有标记为'异常'的迁移结果——这些是潜在的发现。"""
        if method_id:
            rows = self.db.fetch_all(
                "SELECT * FROM migration_runs WHERE method_id = ? AND status = 'anomaly'",
                (method_id,),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM migration_runs WHERE status = 'anomaly'"
            )
        return self._rows_to_results(rows)

    def _generate_migration_note(
        self, source: str, target: str, level: MigrationLevel
    ) -> str:
        """生成迁移说明。"""
        src_name = self.PRESET_REGIONS.get(source, RegionInfo(source, source)).name
        tgt_name = self.PRESET_REGIONS.get(target, RegionInfo(target, target)).name

        notes = {
            MigrationLevel.DIRECT_REUSE: (
                f"从 {src_name} 迁移到 {tgt_name}：数据充足，仅需调整区域参数。"
            ),
            MigrationLevel.PARAMETER_ADAPT: (
                f"从 {src_name} 迁移到 {tgt_name}：需要适配本地参数"
                f"（如矿物成分、粒径分布）。建议先运行参数敏感性分析。"
            ),
            MigrationLevel.EQUATION_ADAPT: (
                f"从 {src_name} 迁移到 {tgt_name}：❌ 目标区域数据不足或物理条件不满足模型假设。"
                f"标记为'不可迁移'，等待更多数据。"
            ),
        }
        return notes.get(level, f"迁移: {source} → {target}")

    def _rows_to_results(self, rows) -> list[MigrationResult]:
        return [
            MigrationResult(
                run_id=r["id"], method_id=r["method_id"],
                source_region=r["source_region"], target_region=r["target_region"],
                level=MigrationLevel(r["migration_level"]),
                status=MigrationStatus(r["status"]),
                anomaly_detail=r["anomaly_detail"] or "",
                created_at=r["created_at"],
            )
            for r in rows
        ]
