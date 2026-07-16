"""引擎一 — 干净房间审稿调度器

CleanRoomScheduler 管理完全隔离的 LLM 审稿会话。
核心保证：审稿 LLM 不接收任何前序对话上下文。

PRD §1-3: 干净房间审稿
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..core.context_packet import ContextPacket


@dataclass
class CleanRoomRequest:
    """一次干净房间审稿的请求包。

    仅包含审稿必需的内容——不含任何对话历史。
    """

    # 审稿目标
    paper_content: str
    """论文全文。"""

    paper_path: str = ""
    """论文文件路径（用于元数据记录）。"""

    # 审稿标准
    review_standard: str = ""
    """审稿 System Prompt（审稿人角色定义 + 审查维度）。"""

    review_mode: str = "clean_room"
    """审稿模式: clean_room | methodology_trace | red_team | multi_expert | counterfactual | competition"""

    # 可选限定
    focus_dimensions: list[str] = field(default_factory=list)
    """指定审查维度（如仅审查'科学正确性'和'逻辑完整性'）。为空则全部维度。"""

    expert_roles: list[str] = field(default_factory=list)
    """多角色辩论时的专家角色列表。"""

    # 元数据
    request_id: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"cr_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_llm_messages(self) -> list[dict]:
        """生成发给 LLM 的消息列表（不含任何历史上下文）。"""
        messages = []

        # System Prompt
        system = self._build_system_prompt()
        messages.append({"role": "system", "content": system})

        # User Message: 论文内容
        user_msg = self._build_user_message()
        messages.append({"role": "user", "content": user_msg})

        return messages

    def _build_system_prompt(self) -> str:
        """构建审稿 System Prompt。"""
        parts = []

        # 审稿人角色
        parts.append(self.review_standard or self._default_standard())

        # 审稿模式特定指令
        if self.review_mode == "red_team":
            parts.append(
                "\n\n⚠️ 红队模式：你是一个持怀疑态度的审稿人。"
                "你的唯一任务是找到这篇论文的致命缺陷。"
                "不要给建设性意见，不要表扬，只找弱点。"
                f"请提出至少 3 个最尖锐的质疑。"
            )
        elif self.review_mode == "methodology_trace":
            parts.append(
                "\n\n🔍 方法论溯源模式：请追溯论文中每个关键公式和假设的原始文献来源。"
                "对于每个假设，检查：\n"
                "1. 原始成立条件是什么？\n"
                "2. 本文的系统是否满足这些条件？\n"
                "3. 如果不满足，偏离有多大？\n"
                "输出格式：每个假设一个'成立条件 vs 实际条件'对照表。"
            )
        elif self.review_mode == "multi_expert":
            roles = self.expert_roles or ["方法学专家", "领域专家", "统计专家"]
            parts.append(
                f"\n\n👥 多角色辩论模式：请同时从以下 {len(roles)} 个专家视角审查本文：\n"
                + "\n".join(f"- {r}" for r in roles)
                + "\n\n每个专家给出独立意见后，进行交叉辩论。"
                "输出格式：每个专家的独立意见 + 辩论记录（一致点 + 分歧点）。"
            )

        # 隔离声明
        parts.append(
            "\n\n---\n"
            "⚡ 本次审稿在独立上下文中运行。你不持有任何前序对话的记忆。"
            "请仅基于本文内容和你自身的知识进行审查。"
        )

        return "\n".join(parts)

    def _build_user_message(self) -> str:
        """构建包含论文内容的 User Message。"""
        msg = "请审稿以下论文：\n\n"
        if self.focus_dimensions:
            msg += f"重点关注维度：{', '.join(self.focus_dimensions)}\n\n"
        msg += f"---\n\n{self.paper_content}"
        return msg

    def _default_standard(self) -> str:
        """默认审稿标准。"""
        return (
            "你是一位严格的学术审稿人。请对以下论文进行全面审查，"
            "从以下维度提出具体意见：\n"
            "1. 科学正确性（方法是否有误、假设是否成立）\n"
            "2. 逻辑完整性（论证链条是否完整、是否有未证实的跳跃）\n"
            "3. 文献覆盖度（是否遗漏关键引用）\n"
            "4. 表述清晰度（是否有歧义或模糊的措辞）\n"
            "5. 结论稳健性（结论是否被数据充分支持）\n\n"
            "请给出具体、可操作的修改建议。每条意见标注严重程度："
            "🔴致命 / 🟡重要 / 🟢建议。"
        )

    def to_context_packet(self, task: str) -> ContextPacket:
        """转换为 ContextPacket 格式（用于引擎四长程推理）。"""
        return ContextPacket(
            task=task,
            parent_summary=f"干净房间审稿: {self.review_mode}",
            global_state={
                "review_mode": self.review_mode,
                "focus_dimensions": self.focus_dimensions,
            },
            human_instruction=f"对 {self.paper_path} 进行 {self.review_mode} 审稿",
        )


class CleanRoomScheduler:
    """干净房间审稿的总调度器。

    管理审稿请求的生命周期：
    - 创建请求
    - 发送到 LLM（M2+ 接入真实 API）
    - 解析审稿意见
    - 记录到 feedback_items
    """

    def __init__(self):
        self.requests: list[CleanRoomRequest] = []

    def create_request(
        self,
        paper_content: str,
        paper_path: str = "",
        review_mode: str = "clean_room",
        review_standard: str = "",
        focus_dimensions: list[str] | None = None,
        expert_roles: list[str] | None = None,
    ) -> CleanRoomRequest:
        """创建一个干净房间审稿请求。"""
        req = CleanRoomRequest(
            paper_content=paper_content,
            paper_path=paper_path,
            review_standard=review_standard,
            review_mode=review_mode,
            focus_dimensions=focus_dimensions or [],
            expert_roles=expert_roles or [],
        )
        self.requests.append(req)
        return req

    def get_llm_messages(self, request_id: str) -> list[dict] | None:
        """获取某次请求的 LLM 消息（用于发送到 API）。"""
        for req in self.requests:
            if req.request_id == request_id:
                return req.to_llm_messages()
        return None

    def estimate_isolation_quality(self) -> dict:
        """估算隔离质量（M2 阶段为基础版本）。

        检查：
        - 请求包是否仅包含 System + 1 User 消息（无历史）
        - paper_content 长度是否合理
        - 是否有隔离声明
        """
        checks = []
        for req in self.requests[-5:]:  # 检查最近5次请求
            msgs = req.to_llm_messages()
            checks.append({
                "request_id": req.request_id,
                "message_count": len(msgs),
                "has_system_prompt": any(m["role"] == "system" for m in msgs),
                "has_isolation_note": "独立上下文中运行" in msgs[0]["content"] if msgs else False,
                "paper_length_chars": len(req.paper_content),
                "is_clean": len(msgs) <= 2,  # 干净房间应该只有 2 条消息
            })

        clean_count = sum(1 for c in checks if c["is_clean"])
        return {
            "total_checked": len(checks),
            "clean_count": clean_count,
            "isolation_score": clean_count / len(checks) if checks else 1.0,
            "details": checks,
        }
