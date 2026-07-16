"""引擎二 — 方法论溯源审稿

追溯论文中每个关键公式/假设的原始成立条件，
逐一核查系统是否满足这些条件，输出对照表。

PRD §2-1: 方法论溯源
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..engine_one_tracker.cleanroom import CleanRoomRequest, CleanRoomScheduler


@dataclass
class AssumptionCheck:
    """一个假设的溯源检查结果。"""
    assumption: str
    """假设内容（如 "BET方程适用于多层吸附区 RH > 0.3"）。"""

    original_condition: str
    """原始文献中的成立条件。"""

    actual_condition: str
    """本系统的实际条件。"""

    deviation: str = ""
    """偏离程度（如 '无偏离' | '+15%' | '条件不成立'）。"""

    severity: str = "medium"
    """严重程度: low | medium | high | critical。"""

    reference: str = ""
    """原始文献引用。"""

    recommendation: str = ""
    """建议（如 '标注为局限' | '补充验证' | '条件不成立→修正方法'）。"""


@dataclass
class TraceReport:
    """方法论溯源审稿报告。"""
    report_id: str
    paper_title: str = ""
    checks: list[AssumptionCheck] = field(default_factory=list)
    summary: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.report_id:
            self.report_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_markdown(self) -> str:
        """生成 Markdown 格式的审查报告。"""
        lines = [
            f"# 方法论溯源审稿报告",
            f"**报告ID**: {self.report_id}",
            f"**时间**: {self.created_at}",
            f"**论文**: {self.paper_title or '未指定'}",
            f"",
            f"## 摘要",
            f"{self.summary or '无'}",
            f"",
            f"## 逐项溯源 ({len(self.checks)} 项)",
        ]

        for i, c in enumerate(self.checks, 1):
            sev_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(c.severity, "⚪")
            lines.append(f"\n### {i}. {sev_icon} {c.assumption}")
            lines.append(f"\n| 维度 | 内容 |")
            lines.append(f"|:---|:---|")
            lines.append(f"| **原始成立条件** | {c.original_condition} |")
            lines.append(f"| **本系统条件** | {c.actual_condition} |")
            lines.append(f"| **偏离程度** | {c.deviation} |")
            if c.reference:
                lines.append(f"| **参考文献** | {c.reference} |")
            if c.recommendation:
                lines.append(f"| **建议** | {c.recommendation} |")

        return "\n".join(lines)


class MethodologyTracer:
    """方法论溯源——审稿模式一。

    提取论文中的关键假设，追溯每个假设的原始文献成立条件，
    生成"成立条件 vs 实际条件"对照表。

    用法:
        tracer = MethodologyTracer()
        request = tracer.build_request(paper_content, paper_path)
        # 发送 request.to_llm_messages() 到 LLM
        # 解析 LLM 回复 → trace.parse_response(llm_response)
    """

    SYSTEM_PROMPT = """你是一位科学方法论审查专家。你的任务是追溯论文中每个关键公式和理论假设的原始文献来源，并逐一核查本系统是否满足原始成立条件。

审查流程：
1. 识别论文中使用的所有关键公式、模型和理论假设
2. 对每个假设，追溯其原始文献中的成立条件
3. 对比"原始条件"和"本系统实际条件"
4. 评估偏离程度及其对结论的影响
5. 给出具体的修正建议

输出格式（每个假设一个表格）：

## 假设 N: [假设名称]
| 维度 | 内容 |
|:---|:---|
| 原始成立条件 | [从原始文献中提取的精确条件] |
| 本系统实际条件 | [论文中描述或隐含的条件] |
| 偏离程度 | [无偏离 / 轻微 / 中等 / 严重] |
| 参考文献 | [原始文献的完整引用] |
| 建议 | [如何修正或标注局限]

请特别注意：
- 数值假设（参数值、阈值）：是否有文献支持？替代值会如何影响结论？
- 理论假设（线性、稳态、均匀等）：在本系统中是否被违反？
- 经验关系（参数化方案）：适用范围是否被超出？
- 跨领域引用：方法从其他领域引入时，核心假设是否仍成立？

--- 
⚡ 本次审稿在独立上下文中运行。请仅基于论文内容和你自身的知识进行审查。"""

    def build_request(
        self,
        paper_content: str,
        paper_path: str = "",
        title: str = "",
    ) -> CleanRoomRequest:
        """构建方法论溯源审稿请求。"""
        return CleanRoomRequest(
            paper_content=paper_content,
            paper_path=paper_path,
            review_standard=self.SYSTEM_PROMPT,
            review_mode="methodology_trace",
            focus_dimensions=["科学正确性", "方法论自洽性"],
        )

    def parse_response(self, raw_response: str, title: str = "") -> TraceReport:
        """解析 LLM 回复为结构化报告（简化版——提取关键信息）。"""
        report = TraceReport(
            report_id=f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            paper_title=title,
            summary="方法论溯源审稿完成（详见原始回复）",
        )

        # 简化解析：寻找 "## 假设" 标记
        import re
        sections = re.split(r"## 假设 \d+:", raw_response)
        if len(sections) > 1:
            for section in sections[1:]:
                check = self._parse_assumption_section(section.strip())
                if check:
                    report.checks.append(check)

        return report

    def _parse_assumption_section(self, text: str) -> AssumptionCheck | None:
        """从 Markdown 表格中提取假设信息。"""
        import re

        # 提取第一行作为假设名称
        first_line = text.split("\n")[0].strip() if text else ""
        if not first_line:
            return None

        # 提取表格行
        fields = {}
        for line in text.split("\n"):
            match = re.match(r"\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|", line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                field_map = {
                    "原始成立条件": "original_condition",
                    "本系统实际条件": "actual_condition",
                    "本系统条件": "actual_condition",
                    "偏离程度": "deviation",
                    "参考文献": "reference",
                    "建议": "recommendation",
                }
                if key in field_map:
                    fields[field_map[key]] = value

        severity = "medium"
        dev = fields.get("deviation", "")
        if "严重" in dev or "不成立" in dev:
            severity = "critical"
        elif "中等" in dev:
            severity = "high"
        elif "轻微" in dev:
            severity = "low"

        return AssumptionCheck(
            assumption=first_line,
            original_condition=fields.get("original_condition", "未识别"),
            actual_condition=fields.get("actual_condition", "未识别"),
            deviation=fields.get("deviation", ""),
            severity=severity,
            reference=fields.get("reference", ""),
            recommendation=fields.get("recommendation", ""),
        )
