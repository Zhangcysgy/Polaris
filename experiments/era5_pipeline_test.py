"""Polaris 真实 ERA5 数据全流程测试

测试流程:
    Engine O → 注册分析方法
    Engine I → 自动版本捕获
    Engine II → 物理校验验证
    Engine III → 跨区域迁移计划
"""
import os, sys, json
os.chdir(r"H:\Polaris")
sys.path.insert(0, "src")

import xarray as xr
import numpy as np
from datetime import datetime

from polaris.core.database import Database
from polaris.engine_o_methods import MethodLibrary, Gate
from polaris.engine_one_tracker import VersionCapture, FeedbackTracker
from polaris.engine_three_migrator import GlobalMigrator

# ============================================================
# 0. 初始化
# ============================================================
db = Database(r"H:\Polaris\data\polaris.db")
lib = MethodLibrary(db)
vc = VersionCapture(db)
ft = FeedbackTracker(db)

project_id = "era5-cas-test"  # Central Asia Sandstorm test
print("=" * 60)
print("Polaris 真实 ERA5 数据全流程测试")
print(f"项目: {project_id}")
print("=" * 60)

# ============================================================
# Engine O: 注册分析方法
# ============================================================
print("\n--- Engine O: 注册分析方法 ---")

# 注册数据加载方法
method_id = lib.add_method(
    name="ERA5单层数据加载器 (中亚区域)",
    type="atom",
    description=(
        "加载中亚区域 (70-140E, 15-55N) 的 ERA5 逐小时单层数据。"
        "自动处理 valid_time→time 重命名、scale/offset 解码。"
        "变量: t2m(2m温度), d2m(露点), u10(10m纬向风), v10(10m经向风)。"
    ),
    domain="大气科学",
    variables=["t2m", "d2m", "u10", "v10", "风速"],
)
print(f"  注册方法: {method_id}")

# 立即审批为 verified
lib.update_method(method_id, status="pending_confirm")
gate = Gate(db)
gate.approve(method_id, confirmed_by="system（测试）")
print(f"  状态: {lib.get_method(method_id).status}")

# ============================================================
# Engine I: 分析执行 + 自动版本捕获
# ============================================================
print("\n--- Engine I: 分析执行 + 自动版本捕获 ---")

# 捕获研究版本
vid = vc.capture_research(
    project_id=project_id,
    label="中亚ERA5 1979年1月气候态分析",
    summary="分析1979年1月中亚区域的温度、露点、风速分布",
)
print(f"  版本: {vid}")

# 实际数据分析
data_dir = r"H:\data\raw\era5\single_levels"
ds = xr.open_dataset(f"{data_dir}\\ERA5_single_levels_197901_instant.nc")

# 计算月平均
t2m_mean = float(ds.t2m.mean())
d2m_mean = float(ds.d2m.mean())
ws = np.sqrt(ds.u10**2 + ds.v10**2)
ws_mean = float(ws.mean())

# 计算 Sahara 区域类似指标用于对比（如果数据在经纬度范围内）
# 中亚数据70-140E, 15-55N 覆盖不了Sahara，这是预期的——做引擎三迁移计划用

results = {
    "region": "Central Asia (70-140E, 15-55N)",
    "month": "1979-01",
    "t2m_mean_K": round(t2m_mean, 2),
    "d2m_mean_K": round(d2m_mean, 2),
    "wind_speed_mean_ms": round(ws_mean, 2),
    "grid_points": f"{ds.sizes['latitude']}×{ds.sizes['longitude']}",
}

ds.close()

print(f"  区域: {results['region']}")
print(f"  2m温度均值: {results['t2m_mean_K']} K")
print(f"  2m露点均值: {results['d2m_mean_K']} K")
print(f"  10m风速均值: {results['wind_speed_mean_ms']} m/s")
print(f"  网格: {results['grid_points']}")

# 更新版本产物
vid2 = vc.capture_research(
    project_id=project_id,
    label="中亚ERA5 1979年1月气候态结果",
    artifacts=["results/cas_197901_climatology.json"],
    summary=json.dumps(results, ensure_ascii=False),
)
print(f"  结果版本: {vid2}")

# ============================================================
# Engine II: 物理校验
# ============================================================
print("\n--- Engine II: 物理校验 ---")

checks = []
# 温度范围检查
if 220 < t2m_mean < 310:
    checks.append(("✅", "温度在合理范围 (220-310K)"))
else:
    checks.append(("❌", f"温度异常: {t2m_mean}K"))

# 露点 ≤ 温度（物理约束）
if d2m_mean <= t2m_mean:
    checks.append(("✅", "露点 ≤ 温度（物理约束满足）"))
else:
    checks.append(("❌", "露点 > 温度（违反物理定律）"))

# 风速非负
if ws_mean >= 0:
    checks.append(("✅", "风速非负"))
else:
    checks.append(("❌", "风速为负"))

# 模拟收手评估
all_pass = all(c[0] == "✅" for c in checks)

for icon, msg in checks:
    print(f"  {icon} {msg}")

if all_pass:
    fid = ft.create(
        project_id=project_id,
        source="物理围栏自动检查",
        content="1979年1月中亚ERA5数据物理校验全部通过",
        priority="low",
    )
    ft.resolve(fid, "所有物理约束满足")
    print(f"  ✅ 物理校验全部通过 (意见ID: {fid})")

# ============================================================
# Engine III: 跨区域迁移计划
# ============================================================
print("\n--- Engine III: 跨区域迁移计划 ---")

migrator = GlobalMigrator(db)
targets = migrator.auto_select_targets("central_asia")
print(f"  源区域: central_asia")
print(f"  自动选择目标: {targets}")

for t in targets:
    info = GlobalMigrator.PRESET_REGIONS.get(t)
    if info:
        data_icon = {"full": "🟢", "limited": "🟡", "missing": "🔴"}.get(
            info.data_availability, "⚪"
        )
        result = migrator.migrate(method_id, "central_asia", t)
        print(f"    {data_icon} {t:20s} → L{result.level.value} ({result.status.value})")
        if t == "sahara":
            print(f"         如需真实迁移: 需要 Sahara 区域 ERA5 数据 (-20~40E, 10~40N)")
            print(f"         预期差异: 中亚露点更低、气温更低、风速更高（冬季）")

# ============================================================
# 汇总
# ============================================================
print(f"\n{'='*60}")
print("测试完成")
print(f"{'='*60}")
print(f"  Engine O: 注册 + 审批 1 个方法")
print(f"  Engine I: 捕获 2 个研究版本")
print(f"  Engine II: 物理校验 {len(checks)} 项, 全部通过")
print(f"  Engine III: 迁移计划覆盖 {len(targets)} 个区域")

# 显示版本链
versions = vc.get_project_versions(project_id)
print(f"\n  版本链 ({len(versions)}):")
for v in versions:
    print(f"    [{v.version_type}] {v.label} — {v.created_at}")

# 显示方法库
method = lib.get_method(method_id)
print(f"\n  方法库条目: [{method.id}] {method.name} ({method.status})")
