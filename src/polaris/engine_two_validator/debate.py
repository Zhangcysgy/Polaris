"""引擎二 — 多角色辩论审稿

同时模拟 3 个不同领域专家，各自独立审查后互相辩论。

PRD §2-1: 多角色辩论
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..engine_one_tracker.cleanroom import CleanRoomRequest


@dataclass
class ExpertOpinion:
    """单个专家的独立审查意见。"""
    expert_role: str        # 如 "表面科学专家"
    opinions: list[str]     # 审查意见列表
    severity_counts: dict = field(default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0})


@dataclass
class DebatePoint:
    """辩论中的一个分歧/共识点。"""
    topic: str
    consensus: str = ""     # "agreed" | "disagreed" | "partial"
    position_a: str = ""    # 专家A的立场
    position_b: str = ""    # 专家B的立场
    resolution: str = ""    # 辩论后的结论


@dataclass
class DebateReport:
    """多角色辩论审稿报告。"""
    report_id: str
    paper_title: str = ""
    expert_opinions: list[ExpertOpinion] = field(default_factory=list)
    debate_points: list[DebatePoint] = field(default_factory=list)
    summary: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.report_id:
            self.report_id = f"debate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_markdown(self) -> str:
        lines = [
            f"# 👥 多角色辩论审稿报告",
            f"**报告ID**: {self.report_id}",
            f"**时间**: {self.created_at}",
            f"**论文**: {self.paper_title or '未指定'}",
            f"",
            f"## 参与专家",
        ]
        for e in self.expert_opinions:
            lines.append(f"- **{e.expert_role}**: {sum(e.severity_counts.values())} 条意见 "
                        f"(🔴{e.severity_counts['critical']} 🟠{e.severity_counts['high']} "
                        f"🟡{e.severity_counts['medium']} 🟢{e.severity_counts['low']})")

        lines.append(f"\n## 各专家独立意见")
        for e in self.expert_opinions:
            lines.append(f"\n### {e.expert_role}")
            for i, op in enumerate(e.opinions, 1):
                lines.append(f"{i}. {op}")

        lines.append(f"\n## 辩论记录 ({len(self.debate_points)} 个议题)")
        for i, d in enumerate(self.debate_points, 1):
            consensus_icon = {"agreed": "✅", "disagreed": "❌", "partial": "🟡"}.get(d.consensus, "⚪")
            lines.append(f"\n### {i}. {consensus_icon} {d.topic}")
            lines.append(f"- **状态**: {d.consensus}")
            if d.position_a:
                lines.append(f"- **立场A**: {d.position_a}")
            if d.position_b:
                lines.append(f"- **立场B**: {d.position_b}")
            if d.resolution:
                lines.append(f"- **结论**: {d.resolution}")

        lines.append(f"\n## 摘要")
        lines.append(f"{self.summary or '无'}")

        return "\n".join(lines)


class MultiExpertDebate:
    """多角色辩论——审稿模式三。

    同时启动 N 个专家视角的审查，然后发起交叉辩论。
    当前 M2 阶段：在单个 LLM 调用中模拟多角色（M3+ 可升级为并行调用）。

    用法:
        debate = MultiExpertDebate()
        request = debate.build_request(paper_content, paper_path,
            expert_roles=["表面科学专家", "大气物理专家", "统计物理专家"])
        # 发送 request.to_llm_messages() 到 LLM
    """

    # 预设专家角色库
    EXPERT_PRESETS = {
        "surface_science": "表面科学/胶体化学专家",
        "atmospheric_physics": "大气边界层物理专家",
        "statistical_physics": "统计物理/非线性动力学专家",
        "atmospheric_electricity": "大气电学专家",
        "aerosol_science": "气溶胶科学专家",
        "climate_dynamics": "气候动力学专家",
        "instrumentation": "仪器/实验方法专家",
        "data_science": "数据科学/统计方法专家",
    }

    SYSTEM_PROMPT_TEMPLATE = """你是一个多角色科学辩论的主持人和参与者。请同时从以下专家视角审查本文：

{expert_list}

审查流程：
1. **独立审查阶段**：每个专家独立阅读论文，给出各自视角的审查意见
2. **交叉辩论阶段**：专家之间就分歧点进行辩论
3. **综合结论阶段**：汇总一致意见和遗留分歧

输出格式：

## 参与专家
- 专家A: {role_a}
- 专家B: {role_b}
- 专家C: {role_c}

## 独立审查意见

### 专家A: {role_a}
1. [意见1]
2. [意见2]
...

### 专家B: {role_b}
...

### 专家C: {role_c}
...

## 交叉辩论

### 辩论议题 1: [争议点]
- **专家A立场**: ...
- **专家B立场**: ...
- **结论**: [一致 / 分歧 / A更合理 / B更合理 / 需补充数据]

### 辩论议题 2: ...
...

## 综合评估

- **一致认可的问题**: [所有专家同意的缺陷]
- **遗留分歧**: [专家之间无法达成一致的争议]
- **最关键的待解决问题**: [按优先级排序]

---
⚡ 本次审稿在独立上下文中运行。每位专家的审查应仅基于论文内容及其专业领域的知识。"""

    def build_request(
        self,
        paper_content: str,
        paper_path: str = "",
        expert_roles: list[str] | None = None,
    ) -> CleanRoomRequest:
        """构建多角色辩论审稿请求。"""
        if expert_roles is None:
            expert_roles = [
                self.EXPERT_PRESETS["surface_science"],
                self.EXPERT_PRESETS["atmospheric_physics"],
                self.EXPERT_PRESETS["statistical_physics"],
            ]

        role_a, role_b, role_c = (expert_roles + ["通用科学审查专家"] * 3)[:3]

        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
            expert_list="\n".join(f"- {r}" for r in expert_roles),
            role_a=role_a,
            role_b=role_b,
            role_c=role_c,
        )

        return CleanRoomRequest(
            paper_content=paper_content,
            paper_path=paper_path,
            review_standard=system_prompt,
            review_mode="multi_expert",
            expert_roles=expert_roles,
        )

    def auto_detect_experts(self, paper_content: str) -> list[str]:
        """从论文内容自动推断需要的专家角色。

        简易关键词匹配——M3+ 可升级为 LLM 自动识别。
        """
        experts = set()

        keyword_map = {
            "surface_science": ["BET", "吸附", "表面", "膜厚", "水膜", "adsorption", "surface"],
            "atmospheric_physics": ["边界层", "沙尘", "风", "湍流", "boundary layer", "dust", "wind", "turbulence"],
            "statistical_physics": ["逾渗", "percolation", "相变", "临界", "phase transition", "critical", "标度"],
            "atmospheric_electricity": ["起电", "放电", "闪电", "lightning", "电场", "electric", "triboelectric"],
            "aerosol_science": ["气溶胶", "颗粒", "aerosol", "particle", "PM"],
            "climate_dynamics": ["气候", "遥相关", "ENSO", "climate", "teleconnection"],
            "instrumentation": ["测量", "风洞", "实验室", "measurement", "experiment", "laboratory"],
            "data_science": ["机器学习", "回归", "因果推断", "DAG", "machine learning", "regression", "causal"],
        }

        paper_lower = paper_content.lower()
        for key, keywords in keyword_map.items():
            if any(kw.lower() in paper_lower for kw in keywords):
                experts.add(self.EXPERT_PRESETS[key])

        # 确保至少有3个专家
        result = list(experts)
        defaults = [
            self.EXPERT_PRESETS["atmospheric_physics"],
            self.EXPERT_PRESETS["data_science"],
            self.EXPERT_PRESETS["surface_science"],
        ]
        while len(result) < 3:
            for d in defaults:
                if d not in result:
                    result.append(d)
                    break
                if len(result) >= 3:
                    break

        return result[:5]  # 最多5个专家

    def parse_response(self, raw_response: str, title: str = "") -> DebateReport:
        """解析 LLM 回复为结构化辩论报告。"""
        report = DebateReport(
            report_id=f"debate_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            paper_title=title,
            summary="多角色辩论审稿完成",
        )

        import re

        # 提取专家角色
        expert_section = re.search(r"## 参与专家\n(.*?)(?=\n## |\Z)", raw_response, re.DOTALL)
        if expert_section:
            roles = re.findall(r"[-*]\s*专家\w:\s*(.+)", expert_section.group(1))
            for role in roles:
                report.expert_opinions.append(ExpertOpinion(expert_role=role.strip(), opinions=[]))

        # 提取辩论议题
        debate_sections = re.findall(
            r"### 辩论议题 \d+:\s*(.+?)\n(.*?)(?=\n### 辩论议题|\n## |\Z)",
            raw_response, re.DOTALL
        )
        for topic, content in debate_sections:
            consensus = "agreed"
            if "分歧" in content or "disagree" in content.lower():
                consensus = "disagreed"
            elif "部分" in content or "partial" in content.lower():
                consensus = "partial"

            pos_a_match = re.search(r"专家A[立场]*\s*[:：]\s*(.+)", content)
            pos_b_match = re.search(r"专家B[立场]*\s*[:：]\s*(.+)", content)

            report.debate_points.append(DebatePoint(
                topic=topic.strip(),
                consensus=consensus,
                position_a=pos_a_match.group(1).strip() if pos_a_match else "",
                position_b=pos_b_match.group(1).strip() if pos_b_match else "",
                resolution="",
            ))

        return report
