"""引擎四 — 分析能力层

解决 LLM 决策与系统执行能力之间的鸿沟。

LLM 说"计算 SPI 干旱指数" → 系统查能力库 → 无匹配 → 降级/生成代码/如实反馈
"""

from __future__ import annotations

import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AnalysisCapability:
    """一个可执行的分析能力。"""
    name: str               # 如 "时间平均"
    description: str        # 人类可读描述
    keywords: list[str]     # 触发关键词 ["mean", "average", "均值", "平均"]
    required_vars: list[str]  # 需要的变量 ["t2m"]
    output_type: str = "numeric"  # "numeric" | "array" | "figure" | "report"
    function_name: str = ""  # 对应的执行函数名


# ============================================================
# 能力注册表
# ============================================================

BUILTIN_CAPABILITIES: list[AnalysisCapability] = [
    AnalysisCapability(
        name="变量均值",
        description="计算指定变量的时间-空间平均值",
        keywords=["mean", "average", "均值", "平均", "气候态", "climatology"],
        required_vars=[],  # 任意变量
        output_type="numeric",
        function_name="compute_mean",
    ),
    AnalysisCapability(
        name="露点亏缺",
        description="计算温度-露点差 (T-Td)，作为大气干旱程度的代理指标",
        keywords=["drought", "干旱", "干燥", "露点亏缺", "T-Td", "aridity", "dew point depression", "湿度亏缺"],
        required_vars=["t2m", "d2m"],
        output_type="array",
        function_name="compute_dewpoint_depression",
    ),
    AnalysisCapability(
        name="强风频率",
        description="统计风速超过阈值的频率。默认阈值 6 m/s（起沙风经验阈值）",
        keywords=["强风", "大风", "风速阈值", "起沙风", "wind threshold", "extreme wind", "high wind frequency"],
        required_vars=["u10", "v10"],
        output_type="numeric",
        function_name="compute_wind_threshold_frequency",
    ),
    AnalysisCapability(
        name="变量标准差",
        description="计算变量的标准差（变率）",
        keywords=["std", "standard deviation", "标准差", "变率", "variability"],
        required_vars=[],
        output_type="numeric",
        function_name="compute_std",
    ),
    AnalysisCapability(
        name="变量极值",
        description="计算变量的最大值和最小值",
        keywords=["max", "min", "最大", "最小", "极值", "extreme", "maximum", "minimum"],
        required_vars=[],
        output_type="numeric",
        function_name="compute_extremes",
    ),
    AnalysisCapability(
        name="变量百分位",
        description="计算变量的指定百分位数（默认 5th, 25th, 50th, 75th, 95th）",
        keywords=["percentile", "百分位", "分位数", "quantile"],
        required_vars=[],
        output_type="numeric",
        function_name="compute_percentiles",
    ),
    AnalysisCapability(
        name="干旱+强风复合条件",
        description="识别同时满足 T-Td > 阈值 且 风速 > 阈值的时段",
        keywords=["复合", "compound", "co-occurrence", "同时", "干旱且大风", "起沙条件",
                   "dust emission condition", "干旱+强风", "干旱+大风", "复合事件",
                   "compound event", "joint occurrence", "combined", "concurrent",
                   "干燥大风", "干热风", "干旱风"],
        required_vars=["t2m", "d2m", "u10", "v10"],
        output_type="numeric",
        function_name="compute_compound_drought_wind",
    ),
    AnalysisCapability(
        name="时间序列趋势",
        description="用线性回归拟合变量的时间趋势",
        keywords=["trend", "趋势", "倾向", "变化率", "长期变化"],
        required_vars=[],
        output_type="numeric",
        function_name="compute_trend",
    ),
    AnalysisCapability(
        name="多年气候态",
        description="计算多年平均（气候态）和标准差。需要多个年份的数据文件",
        keywords=["多年", "multi-year", "climatology", "气候态", "多年平均", "年际", "长期", "44年", "1979", "历年", "逐年"],
        required_vars=[],
        output_type="numeric",
        function_name="compute_climatology",
    ),
    AnalysisCapability(
        name="年际趋势",
        description="逐年计算均值，拟合线性趋势，评估变化速率",
        keywords=["年际趋势", "interannual trend", "逐年趋势", "年代际", "decadal", "长期变化趋势", "时间序列趋势分析"],
        required_vars=[],
        output_type="numeric",
        function_name="compute_interannual_trend",
    ),
    AnalysisCapability(
        name="季节循环",
        description="按月份分组计算多年平均季节循环",
        keywords=["季节", "seasonal", "annual cycle", "季节变化", "季节循环", "逐月气候态", "年循环"],
        required_vars=[],
        output_type="numeric",
        function_name="compute_seasonal_cycle",
    ),
    AnalysisCapability(
        name="异常检测",
        description="将单个月份与多年气候态对比，计算异常值（距平/标准化距平）",
        keywords=["异常", "anomaly", "距平", "极端", "异常值", "偏离", "outlier", "异常年份", "extreme year"],
        required_vars=[],
        output_type="numeric",
        function_name="compute_anomaly",
    ),
]


@dataclass
class CapabilityMatch:
    """LLM 意图与系统能力的匹配结果。"""
    intent: str                # LLM 想要的
    matched: bool
    capability: AnalysisCapability | None = None
    fallback: AnalysisCapability | None = None  # 降级方案
    reason: str = ""
    variables_available: list[str] = field(default_factory=list)
    variables_missing: list[str] = field(default_factory=list)


class CapabilityResolver:
    """将 LLM 意图解析为可执行的能力。

    三层匹配:
    1. 精确匹配 — 能力库直接支持
    2. 降级匹配 — 变量不足时，自动推荐替代方案
    3. 代码生成 — 能力库无匹配时，用 LLM 生成 Python 代码
    """

    def __init__(self, capabilities: list[AnalysisCapability] | None = None):
        self.capabilities = capabilities or BUILTIN_CAPABILITIES

    def match(self, intent: str, available_vars: list[str]) -> CapabilityMatch:
        """将 LLM 的意图匹配到具体能力。"""
        intent_lower = intent.lower()

        # 第一层：精确匹配（关键词命中数 + 命中率双重打分）
        best_match = None
        best_score = 0

        for cap in self.capabilities:
            hits = [kw for kw in cap.keywords if kw.lower() in intent_lower]
            raw_score = len(hits)
            # 命中率加分：cap有5个关键词，命中4个 → 80%命中率
            hit_rate = raw_score / len(cap.keywords) if cap.keywords else 0
            score = raw_score + hit_rate * 2  # 命中率权重×2

            var_ok = all(v in available_vars for v in cap.required_vars)
            if var_ok and score > best_score:
                best_match = cap
                best_score = score

        if best_match and best_score > 0:
            return CapabilityMatch(
                intent=intent,
                matched=True,
                capability=best_match,
                reason=f"匹配到 {best_match.name} (得分:{best_score:.1f})",
                variables_available=available_vars,
            )

        # 第二层：降级匹配（放宽变量要求）
        for cap in self.capabilities:
            score = sum(1 for kw in cap.keywords if kw.lower() in intent_lower)
            if score > 0 and cap.required_vars:
                missing = [v for v in cap.required_vars if v not in available_vars]
                if missing:
                    # 尝试找替代
                    fallback = self._find_fallback(cap, available_vars)
                    if fallback:
                        return CapabilityMatch(
                            intent=intent,
                            matched=False,
                            capability=cap,
                            fallback=fallback,
                            reason=f"变量不足: 缺{missing}，降级为{fallback.name}",
                            variables_available=available_vars,
                            variables_missing=missing,
                        )

        # 第三层：无法匹配 → 自动智能降级
        # "基础统计分析"/"深入分析" 等通用词 → 降级到变量均值
        generic_terms = ["基础统计", "基本统计", "统计分析", "深入分析", "初步分析", "探索分析", "描述统计"]
        if any(t in intent_lower for t in generic_terms):
            mean_cap = next((c for c in self.capabilities if c.function_name == "compute_mean"), None)
            if mean_cap and all(v in available_vars for v in mean_cap.required_vars):
                return CapabilityMatch(
                    intent=intent, matched=True, capability=mean_cap,
                    reason=f"智能降级: '{intent}' → '{mean_cap.name}'（通用分析请求自动路由到基础统计）",
                    variables_available=available_vars,
                )

        # 彻底无法匹配
        return CapabilityMatch(
            intent=intent,
            matched=False,
            reason=f"能力库无匹配: '{intent}'. 可用能力: {[c.name for c in self.capabilities[:5]]}...",
            variables_available=available_vars,
        )

    def _find_fallback(
        self, target: AnalysisCapability, available_vars: list[str]
    ) -> Optional[AnalysisCapability]:
        """找到最接近的替代能力。"""
        # 简化：找关键词重叠最多的可用能力
        best = None
        best_score = 0
        target_kw = set(target.keywords)
        for cap in self.capabilities:
            if cap.name == target.name:
                continue
            if all(v in available_vars for v in cap.required_vars):
                score = len(target_kw & set(cap.keywords))
                if score > best_score:
                    best = cap
                    best_score = score
        return best

    def list_available(self, available_vars: list[str]) -> list[AnalysisCapability]:
        """列出当前数据可执行的全部能力。"""
        return [
            c for c in self.capabilities
            if all(v in available_vars for v in c.required_vars)
        ]

    def execute(self, capability: AnalysisCapability, data_file: str, all_files: list[str] | None = None) -> dict:
        """执行一个分析能力，返回结果。

        Args:
            capability: 要执行的能力
            data_file: 单文件路径（单月分析用）
            all_files: 多文件路径列表（多年分析用）
        """
        func_name = capability.function_name

        # 函数名 → 方法名映射
        method_map = {
            "compute_mean": "_exec_compute_mean",
            "compute_dewpoint_depression": "_exec_dewpoint_depression",
            "compute_wind_threshold_frequency": "_exec_wind_threshold",
            "compute_std": "_exec_compute_std",
            "compute_extremes": "_exec_extremes",
            "compute_percentiles": "_exec_percentiles",
            "compute_compound_drought_wind": "_exec_compound",
            "compute_trend": "_exec_trend",
            "compute_climatology": "_exec_compute_climatology",
            "compute_interannual_trend": "_exec_compute_interannual_trend",
            "compute_seasonal_cycle": "_exec_compute_seasonal_cycle",
            "compute_anomaly": "_exec_compute_anomaly",
        }

        method_name = method_map.get(func_name)
        if method_name is None:
            return {"error": f"未知能力: {func_name}", "capability": capability.name}

        if func_name in ["compute_climatology", "compute_interannual_trend",
                          "compute_seasonal_cycle", "compute_anomaly"]:
            return getattr(self, method_name)(all_files or [data_file], capability)
        else:
            return getattr(self, method_name)(data_file, capability)

    # ---- 具体执行函数 ----

    def _exec_compute_mean(self, data_file: str, cap: AnalysisCapability) -> dict:
        import xarray as xr
        ds = xr.open_dataset(data_file)
        results = {}
        for var in list(ds.data_vars)[:6]:
            results[f"{var}_mean"] = float(ds[var].mean())
        ds.close()
        return {"method": cap.name, "results": results}

    def _exec_dewpoint_depression(self, data_file: str, cap: AnalysisCapability) -> dict:
        import xarray as xr
        import numpy as np
        ds = xr.open_dataset(data_file)
        dd = ds.t2m - ds.d2m  # 露点亏缺 (K)
        results = {
            "dd_mean_K": float(dd.mean()),
            "dd_max_K": float(dd.max()),
            "dd_min_K": float(dd.min()),
            "dry_pct": float((dd > 10).mean() * 100),  # T-Td > 10K → 干燥
            "very_dry_pct": float((dd > 20).mean() * 100),  # T-Td > 20K → 非常干燥
        }
        ds.close()
        return {"method": cap.name, "results": results, "note": "露点亏缺 T-Td: 越大越干燥. >10K=干燥, >20K=非常干燥"}

    def _exec_wind_threshold(self, data_file: str, cap: AnalysisCapability) -> dict:
        import xarray as xr
        import numpy as np
        ds = xr.open_dataset(data_file)
        ws = np.sqrt(ds.u10**2 + ds.v10**2)
        results = {
            "ws_mean": float(ws.mean()),
            "ws_max": float(ws.max()),
            "over_6ms_pct": float((ws > 6).mean() * 100),
            "over_10ms_pct": float((ws > 10).mean() * 100),
        }
        ds.close()
        return {"method": cap.name, "results": results, "note": "起沙风经验阈值: 6 m/s"}

    def _exec_compute_std(self, data_file: str, cap: AnalysisCapability) -> dict:
        import xarray as xr
        ds = xr.open_dataset(data_file)
        results = {}
        for var in list(ds.data_vars)[:4]:
            results[f"{var}_std"] = float(ds[var].std())
        ds.close()
        return {"method": cap.name, "results": results}

    def _exec_extremes(self, data_file: str, cap: AnalysisCapability) -> dict:
        import xarray as xr
        ds = xr.open_dataset(data_file)
        results = {}
        for var in list(ds.data_vars)[:4]:
            results[f"{var}_max"] = float(ds[var].max())
            results[f"{var}_min"] = float(ds[var].min())
        ds.close()
        return {"method": cap.name, "results": results}

    def _exec_percentiles(self, data_file: str, cap: AnalysisCapability) -> dict:
        import xarray as xr
        import numpy as np
        ds = xr.open_dataset(data_file)
        results = {}
        for var in list(ds.data_vars)[:4]:
            vals = ds[var].values.flatten()
            for p in [5, 25, 50, 75, 95]:
                results[f"{var}_p{p}"] = float(np.percentile(vals, p))
        ds.close()
        return {"method": cap.name, "results": results}

    def _exec_compound(self, data_file: str, cap: AnalysisCapability) -> dict:
        import xarray as xr
        import numpy as np
        ds = xr.open_dataset(data_file)
        dd = ds.t2m - ds.d2m
        ws = np.sqrt(ds.u10**2 + ds.v10**2)
        compound = (dd > 10) & (ws > 6)
        results = {
            "compound_pct": float(compound.mean() * 100),
            "dd_gt_10_pct": float((dd > 10).mean() * 100),
            "ws_gt_6_pct": float((ws > 6).mean() * 100),
        }
        ds.close()
        return {"method": cap.name, "results": results, "note": "同时满足 T-Td>10K 且 风速>6m/s 的时次占比"}

    def _exec_trend(self, data_file: str, cap: AnalysisCapability) -> dict:
        import xarray as xr
        import numpy as np
        ds = xr.open_dataset(data_file)
        results = {}
        for var in list(ds.data_vars)[:3]:
            vals = ds[var].values
            if vals.ndim >= 1:
                x = np.arange(len(vals.flatten()[:1000]))
                y = vals.flatten()[:1000]
                if len(y) > 1:
                    slope, intercept = np.polyfit(x, y, 1)
                    results[f"{var}_trend_slope"] = float(slope)
        ds.close()
        return {"method": cap.name, "results": results, "note": "简化趋势（仅前1000点），精确趋势需逐月数据"}

    # ---- 多年分析执行函数 ----

    def _exec_compute_climatology(self, files: list[str], cap: AnalysisCapability) -> dict:
        """多年气候态：计算多年平均和标准差。"""
        import xarray as xr
        import numpy as np

        if len(files) < 2:
            return {"method": cap.name, "results": {}, "error": f"多年分析需要至少2个文件，当前{len(files)}个"}

        results = {}
        try:
            ds = xr.open_mfdataset(files[:min(len(files), 100)], combine='nested', concat_dim='valid_time')
            for var in ["t2m", "d2m", "u10", "v10"]:
                if var in ds.data_vars:
                    results[f"{var}_clim_mean"] = float(ds[var].mean())
                    results[f"{var}_clim_std"] = float(ds[var].std())
                    results[f"{var}_clim_years"] = len(files)
            # 露点亏缺
            if "t2m" in ds.data_vars and "d2m" in ds.data_vars:
                dd = ds.t2m - ds.d2m
                results["dd_clim_mean"] = float(dd.mean())
                results["dd_clim_std"] = float(dd.std())
            ds.close()
        except Exception as e:
            # 回退：逐文件读取
            return self._exec_climatology_fallback(files, cap)

        return {"method": cap.name, "results": results, "note": f"基于{len(files)}个文件的多年气候态"}

    def _exec_climatology_fallback(self, files: list[str], cap: AnalysisCapability) -> dict:
        """逐文件读取计算气候态（回退方案）。"""
        import xarray as xr
        import numpy as np

        accum = {"t2m": [], "d2m": [], "dd": [], "ws": []}
        for f in files[:min(len(files), 60)]:  # 最多60个文件
            try:
                ds = xr.open_dataset(f)
                if "t2m" in ds.data_vars:
                    accum["t2m"].append(float(ds.t2m.mean()))
                if "d2m" in ds.data_vars:
                    accum["d2m"].append(float(ds.d2m.mean()))
                if "t2m" in ds.data_vars and "d2m" in ds.data_vars:
                    accum["dd"].append(float((ds.t2m - ds.d2m).mean()))
                if "u10" in ds.data_vars and "v10" in ds.data_vars:
                    accum["ws"].append(float(np.sqrt(ds.u10**2 + ds.v10**2).mean()))
                ds.close()
            except Exception:
                continue

        results = {}
        for k, vals in accum.items():
            if vals:
                arr = np.array(vals)
                results[f"{k}_clim_mean"] = float(arr.mean())
                results[f"{k}_clim_std"] = float(arr.std())
                results[f"{k}_clim_min"] = float(arr.min())
                results[f"{k}_clim_max"] = float(arr.max())

        return {"method": cap.name, "results": results, "note": f"基于{len(accum.get('t2m',[]))}个文件（逐文件聚合）"}

    def _exec_compute_interannual_trend(self, files: list[str], cap: AnalysisCapability) -> dict:
        """年际趋势：逐年计算均值并拟合趋势。"""
        import xarray as xr
        import numpy as np
        import re

        # 按年份分组
        yearly = {}
        for f in files[:200]:
            match = re.search(r'(\d{4})', os.path.basename(f) if hasattr(os, 'path') else f.split('\\')[-1])
            if match:
                yr = int(match.group(1))
                if yr not in yearly:
                    yearly[yr] = []
                yearly[yr].append(f)

        results = {}
        for var_name in ["t2m", "d2m", "dd"]:
            annual_means = []
            years_list = []
            for yr in sorted(yearly.keys()):
                try:
                    ds = xr.open_mfdataset(yearly[yr][:12], combine='nested', concat_dim='valid_time')
                    if var_name == "dd":
                        if "t2m" in ds.data_vars and "d2m" in ds.data_vars:
                            val = float((ds.t2m - ds.d2m).mean())
                        else:
                            continue
                    elif var_name in ds.data_vars:
                        val = float(ds[var_name].mean())
                    else:
                        continue
                    ds.close()
                    annual_means.append(val)
                    years_list.append(yr)
                except Exception:
                    continue

            if len(annual_means) > 3:
                x = np.array(years_list)
                y = np.array(annual_means)
                slope, intercept = np.polyfit(x, y, 1)
                trend_per_decade = slope * 10
                results[f"{var_name}_trend_per_decade"] = float(trend_per_decade)
                results[f"{var_name}_trend_years"] = f"{min(years_list)}-{max(years_list)}"
                results[f"{var_name}_trend_n"] = len(years_list)
                # 趋势显著性（简化：R²）
                y_pred = slope * x + intercept
                ss_res = np.sum((y - y_pred) ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                results[f"{var_name}_trend_r2"] = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0

        return {"method": cap.name, "results": results, "note": f"基于{len(yearly)}年的年际趋势分析"}

    def _exec_compute_seasonal_cycle(self, files: list[str], cap: AnalysisCapability) -> dict:
        """季节循环：按月份分组计算多年平均。"""
        import xarray as xr
        import numpy as np
        import re

        monthly = {m: {"t2m": [], "dd": [], "ws": []} for m in range(1, 13)}
        for f in files[:200]:
            match = re.search(r'(\d{4})(\d{2})', os.path.basename(f) if hasattr(os, 'path') else f.split('\\')[-1])
            if not match:
                match = re.search(r'_(\d{4})(\d{2})', f)
            if match:
                month = int(match.group(2))
                if 1 <= month <= 12:
                    try:
                        ds = xr.open_dataset(f)
                        monthly[month]["t2m"].append(float(ds.t2m.mean()) if "t2m" in ds.data_vars else None)
                        if "t2m" in ds.data_vars and "d2m" in ds.data_vars:
                            monthly[month]["dd"].append(float((ds.t2m - ds.d2m).mean()))
                        if "u10" in ds.data_vars and "v10" in ds.data_vars:
                            monthly[month]["ws"].append(float(np.sqrt(ds.u10**2 + ds.v10**2).mean()))
                        ds.close()
                    except Exception:
                        continue

        results = {}
        for var in ["t2m", "dd", "ws"]:
            arr = np.array([np.nanmean(monthly[m][var]) for m in range(1, 13) if monthly[m][var]])
            if len(arr) == 12:
                results[f"{var}_jan"] = float(arr[0]) if not np.isnan(arr[0]) else 0
                results[f"{var}_jul"] = float(arr[6]) if not np.isnan(arr[6]) else 0
                results[f"{var}_annual_range"] = float(np.nanmax(arr) - np.nanmin(arr))

        return {"method": cap.name, "results": results, "note": "12个月季节循环（多年平均）"}

    def _exec_compute_anomaly(self, files: list[str], cap: AnalysisCapability) -> dict:
        """异常检测：将第一个文件与其余文件的气候态对比。"""
        import xarray as xr
        import numpy as np

        if len(files) < 3:
            return {"method": cap.name, "results": {}, "error": "需要至少3个文件（1个目标 + ≥2个气候态）"}

        target_file = files[0]
        climate_files = files[1:min(len(files), 100)]

        try:
            ds_target = xr.open_dataset(target_file)
            ds_clim = xr.open_mfdataset(climate_files, combine='nested', concat_dim='valid_time')

            results = {}
            for var in ["t2m", "d2m"]:
                if var in ds_target.data_vars and var in ds_clim.data_vars:
                    target_mean = float(ds_target[var].mean())
                    clim_mean = float(ds_clim[var].mean())
                    clim_std = float(ds_clim[var].std())
                    anomaly = target_mean - clim_mean
                    z_score = anomaly / clim_std if clim_std > 0 else 0
                    results[f"{var}_anomaly"] = round(anomaly, 2)
                    results[f"{var}_zscore"] = round(z_score, 2)
                    results[f"{var}_clim_mean"] = round(clim_mean, 2)

            ds_target.close()
            ds_clim.close()
        except Exception as e:
            return {"method": cap.name, "results": {}, "error": str(e)}

        interpretation = ""
        if abs(results.get("t2m_zscore", 0)) > 2:
            interpretation += f"温度异常显著 (z={results['t2m_zscore']:.1f}σ). "
        else:
            interpretation += f"温度在正常范围 (z={results.get('t2m_zscore',0):.1f}σ). "

        return {"method": cap.name, "results": results, "note": interpretation}
