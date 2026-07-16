"""引擎二 — 假设敏感性热图

自动提取模型中的数值假设，逐一扫描 ±30%，找出"阿喀琉斯之踵"。

PRD §2-2: 假设敏感性热图
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SensitivityResult:
    """单个参数的敏感性分析结果。"""
    parameter_name: str
    base_value: float
    range_low: float
    range_high: float
    impact_score: float = 0.0    # 0-1，1=极度敏感
    impact_description: str = ""  # 人类可读的影响描述
    rank: int = 0                 # 敏感度排名


@dataclass
class SensitivityReport:
    """敏感性热图报告。"""
    report_id: str
    results: list[SensitivityResult] = field(default_factory=list)
    summary: str = ""
    achilles_heel: str = ""      # 最敏感的参数（命门）
    created_at: str = ""

    def __post_init__(self):
        if not self.report_id:
            self.report_id = f"sens_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 自动排序
        self.results.sort(key=lambda r: r.impact_score, reverse=True)
        for i, r in enumerate(self.results):
            r.rank = i + 1
        if self.results:
            self.achilles_heel = self.results[0].parameter_name

    def to_markdown(self) -> str:
        lines = [
            f"# 假设敏感性热图",
            f"**报告ID**: {self.report_id}",
            f"**时间**: {self.created_at}",
            f"",
            f"## 阿喀琉斯之踵",
            f"最敏感参数: **{self.achilles_heel}**",
            f"",
            f"## 敏感性排名",
            f"",
            f"| 排名 | 参数 | 基准值 | 范围 | 敏感度 |",
            f"|:---:|:---|:---:|:---|:---:|",
        ]
        for r in self.results:
            bar = "█" * int(r.impact_score * 10) + "░" * (10 - int(r.impact_score * 10))
            lines.append(
                f"| {r.rank} | {r.parameter_name} | {r.base_value:.3g} | "
                f"[{r.range_low:.3g}, {r.range_high:.3g}] | {bar} {r.impact_score:.2f} |"
            )

        lines.append(f"\n## 解读")
        lines.append(self.summary or "无")
        return "\n".join(lines)


class SensitivityHeatmap:
    """假设敏感性分析器。

    流程：
    1. 从模型/论文中自动提取所有数值假设和参数
    2. 基于文献设定每个参数的合理不确定性范围（默认 ±30%）
    3. 逐一扫描每个参数，计算对输出的影响
    4. 生成"阿喀琉斯之踵"热图排名

    当前 M3 版本：LLM 辅助提取假设 + 人工确认范围。
    M4+ 可升级为自动运行模型代码进行数值扫描。

    用法:
        sh = SensitivityHeatmap()
        report = sh.analyze_from_paper(paper_content)
    """

    EXTRACT_PROMPT = """从以下论文中提取所有**数值假设和自由参数**。

对于每个参数，给出：
1. 参数名称
2. 基准值（论文中使用的值）
3. 合理的不确定性范围（基于你的领域知识）
4. 这个参数影响哪个输出

输出格式（每行一个参数）：
参数名 | 基准值 | 下限 | 上限 | 影响的输出

示例：
BET常数c | 10 | 5 | 50 | 临界湿度RH_c
逾渗阈值h_c | 2.0 | 1.5 | 2.5 | 电荷保留效率η

仅提取**数值**参数，不提取方程形式或理论选择。"""

    def __init__(self, default_range_pct: float = 0.30):
        self.default_range_pct = default_range_pct

    def analyze_from_manual(
        self,
        parameters: list[dict],
        impact_scores: list[float],
    ) -> SensitivityReport:
        """从手动指定的参数和影响分数生成报告。

        Args:
            parameters: [{"name": str, "base": float, "low": float, "high": float}, ...]
            impact_scores: [float, ...] 每个参数的影响分数 0-1
        """
        results = []
        for param, score in zip(parameters, impact_scores):
            results.append(SensitivityResult(
                parameter_name=param["name"],
                base_value=param["base"],
                range_low=param.get("low", param["base"] * (1 - self.default_range_pct)),
                range_high=param.get("high", param["base"] * (1 + self.default_range_pct)),
                impact_score=score,
            ))

        # 生成解读
        high_impact = [r for r in results if r.impact_score > 0.5]
        summary = ""
        if high_impact:
            summary += f"⚠️ {len(high_impact)} 个参数对输出有显著影响（>0.5）：\n"
            for r in high_impact:
                summary += f"- {r.parameter_name}: 敏感度 {r.impact_score:.2f}，"
                summary += f"范围 [{r.range_low:.3g}, {r.range_high:.3g}]"
                if r.impact_score > 0.8:
                    summary += " 🔴 极端敏感——建议优先验证"
                summary += "\n"
        else:
            summary = "✅ 无参数对输出有显著影响——模型对参数不确定性稳健。"

        return SensitivityReport(
            report_id=f"sens_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            results=results,
            summary=summary,
        )

    def analyze_sahara_default(self) -> SensitivityReport:
        """Sahara BET-逾渗模型的预计算敏感性（基于论文已知结果）。

        这些结果来自 Sahara 论文 §3.3 敏感性分析：
        - RH_c 对 c 的敏感性在 h_c/h_m ∈ [1.5, 2.5] 下变化 ≤ ±5 个百分点
        - 最敏感参数是 h_c（逾渗阈值层数）
        """
        return self.analyze_from_manual(
            parameters=[
                {"name": "逾渗阈值 h_c (分子层数)", "base": 2.0, "low": 1.5, "high": 2.5},
                {"name": "BET常数 c", "base": 10.0, "low": 5.0, "high": 50.0},
                {"name": "单层厚度 h_m (nm)", "base": 0.28, "low": 0.25, "high": 0.31},
                {"name": "二维逾渗指数 t", "base": 1.3, "low": 1.1, "high": 1.5},
                {"name": "表面电导率 σ₀ (S/m)", "base": 1e-7, "low": 1e-8, "high": 1e-6},
                {"name": "碰撞时间 τ_coll (ms)", "base": 1.0, "low": 0.5, "high": 2.0},
                {"name": "相对介电常数 ε_r", "base": 4.5, "low": 3.5, "high": 5.5},
            ],
            impact_scores=[0.85, 0.45, 0.30, 0.25, 0.10, 0.15, 0.05],
        )
