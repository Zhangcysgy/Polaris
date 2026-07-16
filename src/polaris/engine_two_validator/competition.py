"""引擎二 — 竞争假设生成

不只验证你的模型——主动找"能产生相同结果的其他模型"。

PRD §2-3: 竞争假设生成
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..engine_one_tracker.cleanroom import CleanRoomRequest


@dataclass
class CompetitionModel:
    """一个竞争模型。"""
    name: str
    mechanism: str         # 物理机制简述
    equation: str = ""     # 核心方程（如有）
    domain: str = ""       # 来源领域
    reference: str = ""    # 参考文献


@dataclass
class CompetitionReport:
    """竞争假设审查报告。"""
    report_id: str
    original_model: str = ""           # 原始模型描述
    competition_models: list[CompetitionModel] = field(default_factory=list)
    comparison_table: str = ""         # 模型对比表（Markdown）
    distinguishing_test: str = ""      # 区分性检验设计
    recommendation: str = ""           # 综合建议
    created_at: str = ""

    def __post_init__(self):
        if not self.report_id:
            self.report_id = f"compete_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_markdown(self) -> str:
        lines = [
            f"# 竞争假设审查报告",
            f"**报告ID**: {self.report_id}",
            f"**时间**: {self.created_at}",
            f"",
            f"## 原始模型",
            f"{self.original_model}",
            f"",
            f"## 竞争模型 ({len(self.competition_models)} 个)",
        ]
        for cm in self.competition_models:
            lines.append(f"\n### {cm.name}")
            lines.append(f"- **机制**: {cm.mechanism}")
            if cm.equation:
                lines.append(f"- **方程**: {cm.equation}")
            if cm.domain:
                lines.append(f"- **来源领域**: {cm.domain}")
            if cm.reference:
                lines.append(f"- **参考文献**: {cm.reference}")

        if self.comparison_table:
            lines.append(f"\n## 模型对比")
            lines.append(self.comparison_table)

        if self.distinguishing_test:
            lines.append(f"\n## 区分性检验")
            lines.append(self.distinguishing_test)

        if self.recommendation:
            lines.append(f"\n## 综合建议")
            lines.append(self.recommendation)

        return "\n".join(lines)


class CompetitionHypothesis:
    """竞争假设生成器。

    流程：
    1. 问题重述——将模型要解释的现象用数学语言重述
    2. 文献搜索——检索"解释类似现象的其他机制"
    3. 模型对比——在同一数据集上比较拟合优度
    4. 区分性检验——设计能区分不同模型的实验

    用法:
        comp = CompetitionHypothesis()
        request = comp.build_request(paper_content, model_description)
    """

    SYSTEM_PROMPT = """你是一位跨领域科学方法审查专家。你的任务是：
1. 理解论文中提出的模型/机制
2. 搜索物理学、化学、材料科学等相邻领域中能产生相同现象的其他机制
3. 设计能区分这些竞争模型的实验

流程：

## Step 1: 问题重述
用数学语言重述模型要解释的核心现象，去除领域特化术语。
例如："湿度在 X% 附近显著抑制颗粒摩擦起电" → "存在一个临界表面水覆盖度，在此之上表面电导率发生逾渗转变"

## Step 2: 竞争模型搜索
从以下领域搜索可能的替代机制：
- 统计物理（相变、逾渗、标度律）
- 表面科学（毛细凝聚、双层电化学）
- 材料科学（接触起电、功函数理论）
- 胶体科学（DLVO理论、离子迁移）

对每个竞争模型，给出：
- 机制名称和简述
- 核心方程（如果适用）
- 与原始模型的关键区别
- 在什么条件下竞争模型会比原始模型更好

## Step 3: 模型对比
生成一个对比表：
| 维度 | 原始模型 | 竞争模型A | 竞争模型B |
|:---|:---|:---|:---|
| 核心假设 | ... | ... | ... |
| 自由参数数量 | ... | ... | ... |
| 可解释性 | ... | ... | ... |
| 已知失效条件 | ... | ... | ... |

## Step 4: 区分性检验
设计一个实验/分析，能区分原始模型和最主要的竞争模型。
例如："如果原始模型正确，在条件X下应观测到现象Y；如果竞争模型正确，应观测到现象Z"

---
⚡ 本次审查在独立上下文中运行。请仅基于论文内容和你的知识进行审查。"""

    def build_request(
        self,
        paper_content: str,
        model_description: str = "",
        paper_path: str = "",
    ) -> CleanRoomRequest:
        """构建竞争假设审稿请求。"""
        full_content = paper_content
        if model_description:
            full_content = f"## 模型描述\n{model_description}\n\n## 论文正文\n{paper_content}"

        return CleanRoomRequest(
            paper_content=full_content,
            paper_path=paper_path,
            review_standard=self.SYSTEM_PROMPT,
            review_mode="competition",
            focus_dimensions=["竞争模型", "区分性检验"],
        )

    def parse_response(self, raw_response: str, original_model: str = "") -> CompetitionReport:
        """解析 LLM 回复为结构化报告。"""
        report = CompetitionReport(
            report_id=f"compete_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            original_model=original_model or "见论文",
            recommendation=raw_response[:500],
        )

        # 提取竞争模型（简化版——搜索 ### 标记）
        import re
        sections = re.split(r"###\s+", raw_response)
        for section in sections[1:]:
            lines = section.strip().split("\n")
            if not lines:
                continue
            name = lines[0].strip()
            mechanism = ""
            equation = ""
            domain = ""
            reference = ""

            for line in lines[1:]:
                line = line.strip()
                if "机制" in line or "mechanism" in line.lower():
                    mechanism = re.sub(r"^[-*]\s*(\*\*)?机制(\*\*)?\s*[:：]\s*", "", line)
                elif "方程" in line or "equation" in line.lower():
                    equation = re.sub(r"^[-*]\s*(\*\*)?方程(\*\*)?\s*[:：]\s*", "", line)
                elif "领域" in line or "domain" in line.lower():
                    domain = re.sub(r"^[-*]\s*(\*\*)?(来源)?领域(\*\*)?\s*[:：]\s*", "", line)
                elif "参考" in line or "reference" in line.lower():
                    reference = re.sub(r"^[-*]\s*(\*\*)?参考文献(\*\*)?\s*[:：]\s*", "", line)

            if name and mechanism:
                report.competition_models.append(CompetitionModel(
                    name=name,
                    mechanism=mechanism,
                    equation=equation,
                    domain=domain,
                    reference=reference,
                ))

        return report
