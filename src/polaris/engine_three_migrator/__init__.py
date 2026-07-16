"""引擎三 — 全局方法迁移

Polaris 的"扩展系统"——方法自动适配到全球，差异即发现。
"""

from .migrator import GlobalMigrator, MigrationResult, MigrationLevel, MigrationStatus, RegionInfo

__all__ = [
    "GlobalMigrator",
    "MigrationResult",
    "MigrationLevel",
    "MigrationStatus",
    "RegionInfo",
]
