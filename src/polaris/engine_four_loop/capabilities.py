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

    def execute(self, capability: AnalysisCapability, data_file: str) -> dict:
        """执行一个分析能力，返回结果。"""
        func_name = capability.function_name

        if func_name == "compute_mean":
            return self._exec_compute_mean(data_file, capability)
        elif func_name == "compute_dewpoint_depression":
            return self._exec_dewpoint_depression(data_file, capability)
        elif func_name == "compute_wind_threshold_frequency":
            return self._exec_wind_threshold(data_file, capability)
        elif func_name == "compute_std":
            return self._exec_compute_std(data_file, capability)
        elif func_name == "compute_extremes":
            return self._exec_extremes(data_file, capability)
        elif func_name == "compute_percentiles":
            return self._exec_percentiles(data_file, capability)
        elif func_name == "compute_compound_drought_wind":
            return self._exec_compound(data_file, capability)
        elif func_name == "compute_trend":
            return self._exec_trend(data_file, capability)
        else:
            return {"error": f"未知能力: {func_name}", "capability": capability.name}

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
