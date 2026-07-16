"""引擎二 — 红队审稿模式

只找致命缺陷——不给建设性意见，不表扬。
模仿安全领域的 red team 方法论应用于科学审查。

PRD §2-1: 红队模式
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..engine_one_tracker.cleanroom import CleanRoomRequest


@dataclass
class RedTeamFinding:
    """红队发现的一个潜在缺陷。"""
    title: str
    description: str
    severity: str = "high"       # high | critical
    category: str = ""           # 方法 / 数据 / 逻辑 / 假设 / 其他
    exploitability: str = ""     # 这个缺陷如何可能导致错误结论
    suggested_fix: str = ""      # 如何修补（红队模式仍给修补建议——但重点是发现）


@dataclass
class RedTeamReport:
    """红队审稿报告。"""
    report_id: str
    paper_title: str = ""
    findings: list[RedTeamFinding] = field(default_factory=list)
    overall_risk: str = "medium"  # low | medium | high | critical
    summary: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.report_id:
            self.report_id = f"redteam_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_markdown(self) -> str:
        lines = [
            f"# 🔴 红队审稿报告",
            f"**报告ID**: {self.report_id}",
            f"**时间**: {self.created_at}",
            f"**论文**: {self.paper_title or '未指定'}",
            f"**总体风险**: {self.overall_risk}",
            f"",
            f"## 摘要",
            f"{self.summary or '无'}",
            f"",
            f"## 发现 ({len(self.findings)} 个潜在缺陷)",
        ]
        for i, f in enumerate(self.findings, 1):
            sev = {"high": "🟠", "critical": "🔴"}.get(f.severity, "⚪")
            lines.append(f"\n### {i}. {sev} {f.title}")
            lines.append(f"- **类别**: {f.category}")
            lines.append(f"- **描述**: {f.description}")
            if f.exploitability:
                lines.append(f"- **潜在影响**: {f.exploitability}")
            if f.suggested_fix:
                lines.append(f"- **修补建议**: {f.suggested_fix}")
        return "\n".join(lines)


class RedTeamReviewer:
    """红队审稿——审稿模式二。

    给 LLM 明确的对抗角色指令，只找弱点。

    用法:
        rt = RedTeamReviewer()
        request = rt.build_request(paper_content, paper_path)
        # 发送 request.to_llm_messages() 到 LLM
    """

    SYSTEM_PROMPT = """你是一个"红队"科学审稿人。你的唯一任务是找到这篇论文的致命缺陷。

规则：
1. 不要表扬。不要给出"整体不错"的评价。
2. 不要给建设性修改建议（除非它直接揭示了一个隐藏缺陷）。
3. 只找弱点、漏洞、未证实的假设、方法论缺陷、数据问题、逻辑跳跃。
4. 对于你发现的每个问题，解释它如何可能被"利用"来推翻论文的核心结论。
5. 提出至少 3 个最尖锐的质疑。

审查维度（按优先级）：
- 核心假设：是否有未被充分证明的假设？如果这个假设错了会怎样？
- 方法论：方法的选择是否有更好的替代方案？当前方法是否可能产生系统性偏差？
- 数据：数据是否足以支撑结论？是否存在选择偏差或确认偏差？
- 逻辑：论证链中是否有跳跃？结论是否过度外推？
- 可复现性：是否提供了足够信息让其他研究者复现？
- 反例：是否存在该理论无法解释的已知观测？

输出格式：
## 发现 N: [缺陷标题]
- **严重程度**: 🔴致命 / 🟠重要
- **类别**: [方法/数据/逻辑/假设/其他]
- **描述**: [具体问题]
- **潜在影响**: [这个缺陷如何可能导致错误结论]
- **修补建议**: [可选]

---
⚡ 本次审稿在独立上下文中运行。你是一个独立的安全审查者——你没有任何关于这篇论文的前序知识。"""

    def build_request(
        self,
        paper_content: str,
        paper_path: str = "",
        title: str = "",
    ) -> CleanRoomRequest:
        """构建红队审稿请求。"""
        return CleanRoomRequest(
            paper_content=paper_content,
            paper_path=paper_path,
            review_standard=self.SYSTEM_PROMPT,
            review_mode="red_team",
            focus_dimensions=["致命缺陷"],
        )

    def parse_response(self, raw_response: str, title: str = "") -> RedTeamReport:
        """解析 LLM 回复为结构化报告。"""
        report = RedTeamReport(
            report_id=f"redteam_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            paper_title=title,
            summary="红队审稿完成",
        )

        import re
        sections = re.split(r"## 发现 \d+:", raw_response)
        if len(sections) > 1:
            for section in sections[1:]:
                finding = self._parse_finding(section.strip())
                if finding:
                    report.findings.append(finding)

        # 评估总体风险
        critical_count = sum(1 for f in report.findings if f.severity == "critical")
        if critical_count >= 2:
            report.overall_risk = "critical"
        elif critical_count >= 1 or len(report.findings) >= 4:
            report.overall_risk = "high"
        elif len(report.findings) >= 2:
            report.overall_risk = "medium"
        else:
            report.overall_risk = "low"

        return report

    def _parse_finding(self, text: str) -> RedTeamFinding | None:
        """从 Markdown 文本中提取红队发现。"""
        first_line = text.split("\n")[0].strip() if text else ""
        if not first_line:
            return None

        import re
        severity = "high"
        category = ""
        description = ""
        exploitability = ""
        suggested_fix = ""

        for line in text.split("\n"):
            line = line.strip()
            if "严重程度" in line or "severity" in line.lower():
                if "致命" in line or "critical" in line:
                    severity = "critical"
            elif "类别" in line or "category" in line:
                cat_match = re.search(r"[方法数据逻辑假设其他]+", line)
                if cat_match:
                    category = cat_match.group()
            elif "描述" in line or "description" in line:
                description = re.sub(r"^[-*]\s*(\*\*)?描述(\*\*)?\s*[:：]\s*", "", line)
            elif "潜在影响" in line or "exploit" in line.lower():
                exploitability = re.sub(r"^[-*]\s*(\*\*)?潜在影响(\*\*)?\s*[:：]\s*", "", line)
            elif "修补" in line or "fix" in line.lower():
                suggested_fix = re.sub(r"^[-*]\s*(\*\*)?修补建议(\*\*)?\s*[:：]\s*", "", line)

        return RedTeamFinding(
            title=first_line,
            description=description or first_line,
            severity=severity,
            category=category or "方法",
            exploitability=exploitability,
            suggested_fix=suggested_fix,
        )
