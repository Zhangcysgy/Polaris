"""
M0-3 上下文污染检测基线实验

实验设计：
    用 Sahara 论文作为测试样本，分别在"干净房间"和"污染上下文"中运行审稿，
    量化意见差异度，建立污染指数的基线数值。

实验流程:
    1. 准备测试样本（Sahara 论文草稿）
    2. 干净房间审稿：新 LLM 会话 + 仅传入论文 + 审稿标准
    3. 污染上下文审稿：同一会话中，先讨论 3 个不相关的分析任务，
       然后在累积的上下文中审稿
    4. 对比两组意见：重叠度、严格度变化、新问题发现率

污染指数定义:
    PI = 1 - |A_clean ∩ A_polluted| / |A_clean ∪ A_polluted|
    即：两组意见的 Jaccard 距离。
    PI = 0 → 完全重叠（无污染）
    PI = 1 → 完全不相交（严重污染）

    辅助指标：
    - 严格度衰减率：污染组中"整体不错/无需修改"类措辞的出现频率
    - 复读机指数：污染组中与前置讨论措辞相似的审稿意见比例
    - 盲区扩大率：干净房间发现但污染组遗漏的新问题数

用法:
    python experiments/pollution_baseline.py --dry-run      # 打印实验协议（不调用API）
    python experiments/pollution_baseline.py --run          # 执行实验（需API Key）
    python experiments/pollution_baseline.py --report       # 查看历史实验结果
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
# 实验配置
# ============================================================

@dataclass
class ExperimentConfig:
    """上下文污染实验配置。"""

    # 测试样本
    sample_paper_path: str = "H:\\Sahara\\Papers\\论文一_湿度门控BET逾渗模型_中文初稿.md"
    """被审稿的论文路径。"""

    # 审稿标准（与 zhangcy-nature-review-strict 一致）
    review_standard: str = (
        "你是一位严格的学术审稿人。请对以下论文进行全面审查，"
        "从以下维度提出具体意见：\n"
        "1. 科学正确性（方法是否有误、假设是否成立）\n"
        "2. 逻辑完整性（论证链条是否完整、是否有未证实的跳跃）\n"
        "3. 文献覆盖度（是否遗漏关键引用）\n"
        "4. 表述清晰度（是否有歧义或模糊的措辞）\n"
        "5. 结论稳健性（结论是否被数据充分支持）\n"
        "请给出具体、可操作的修改建议。每条意见标注严重程度："
        "🔴致命 / 🟡重要 / 🟢建议。"
    )

    # 污染上下文内容（模拟"前序对话讨论过的无关话题"）
    pollution_seed_topics: list[str] = field(default_factory=lambda: [
        "讨论：最近 Nature 上一篇关于 ENSO 对南极海冰影响的文章很有趣，"
        "他们用了因果推断方法。你觉得这个方法能否用于分析 Saharan 沙尘对 AMO 的影响？"
        "我觉得可以试试，但要注意热带和温带系统的耦合时间尺度差异...",

        "讨论：我前两天跑了一个 CMIP6 未来情景下的全球沙尘排放趋势分析，"
        "发现 SSP5-8.5 下撒哈拉沙尘在 2050 年后反而减少了，这和直觉不符。"
        "可能是因为 AMOC 减弱导致 ITCZ 南移，改变了 Sahel 降水。"
        "对了，BET 模型里有没有考虑未来气候变化对表面吸附的影响？",

        "讨论：审稿人让我补充一个敏感性实验——把 BET 常数 c 从 10 改到 5-50 的范围，"
        "看看 RH_c 偏移多少。我觉得这个建议很合理，毕竟矿物成分有不确定性。"
        "实际上我做过了，偏移不超过 5%，说明模型对 c 不敏感——这反而是个优势。"
        "但这个结果我放在补充材料里了，正文里只是一句话带过。",
    ])
    """在污染组审稿之前注入的对话内容（模拟上下文污染）。"""

    # LLM 配置
    model: str = "deepseek-chat"
    temperature_clean: float = 0.1
    temperature_polluted: float = 0.1

    # 实验元数据
    experiment_id: str = field(default_factory=lambda: f"pollution_exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")


# ============================================================
# 污染指数计算
# ============================================================

@dataclass
class ReviewOpinion:
    """一条审稿意见。"""
    id: str
    content: str
    severity: str          # 🔴 / 🟡 / 🟢
    dimension: str         # 科学正确性 / 逻辑完整性 / 文献 / 表述 / 结论
    is_boilerplate: bool = False  # 是否为套话/复读


@dataclass
class ReviewResult:
    """一次审稿的完整结果。"""
    source: str            # "clean_room" | "polluted"
    opinions: list[ReviewOpinion]
    raw_response: str
    elapsed_seconds: float


class PollutionAnalyzer:
    """分析两组审稿结果，计算污染指数。"""

    def __init__(self, clean: ReviewResult, polluted: ReviewResult):
        self.clean = clean
        self.polluted = polluted

    def compute_all(self) -> dict:
        """计算所有污染指标。"""
        pi = self._pollution_index()
        strictness = self._strictness_decay()
        echo = self._echo_index()
        blind_spot = self._blind_spot_expansion()

        return {
            "pollution_index": pi,
            "strictness_decay": strictness,
            "echo_index": echo,
            "blind_spot_expansion": blind_spot,
            "summary": self._summarize(pi, strictness, echo, blind_spot),
        }

    def _pollution_index(self) -> dict:
        """Jaccard 距离：PI = 1 - |A∩B| / |A∪B|。

        注意：这衡量的是意见集合的重叠度，而非措辞相似度。
        PI 高 → 两组意见差异大 → 上下文污染严重。
        """
        clean_texts = {o.content[:80] for o in self.clean.opinions}
        polluted_texts = {o.content[:80] for o in self.polluted.opinions}

        if not clean_texts and not polluted_texts:
            return {"value": 0.0, "note": "两组均无意见"}

        intersection = clean_texts & polluted_texts
        union = clean_texts | polluted_texts

        jaccard = len(intersection) / len(union) if union else 1.0
        pi = 1.0 - jaccard

        return {
            "value": round(pi, 4),
            "clean_count": len(self.clean.opinions),
            "polluted_count": len(self.polluted.opinions),
            "shared_count": len(intersection),
            "clean_only_count": len(clean_texts - polluted_texts),
            "polluted_only_count": len(polluted_texts - clean_texts),
            "interpretation": (
                "🟢 PI < 0.3: 上下文污染轻微"
                if pi < 0.3 else
                "🟡 PI 0.3-0.6: 上下文污染中等——建议使用干净房间"
                if pi < 0.6 else
                "🔴 PI > 0.6: 上下文污染严重——必须使用干净房间"
            ),
        }

    def _strictness_decay(self) -> dict:
        """检测严格度衰减：污染组中是否出现更多"整体不错"类措辞。"""
        boilerplate_patterns = [
            "整体不错", "整体良好", "总体合格", "基本满足",
            "无需修改", "可接受", "没有重大问题",
            "well-written", "well organized", "no major issues",
        ]

        def count_boilerplate(opinions: list[ReviewOpinion]) -> int:
            return sum(
                1 for o in opinions
                if any(p in o.content for p in boilerplate_patterns)
            )

        clean_bp = count_boilerplate(self.clean.opinions)
        polluted_bp = count_boilerplate(self.polluted.opinions)

        return {
            "clean_boilerplate_count": clean_bp,
            "polluted_boilerplate_count": polluted_bp,
            "decay_detected": polluted_bp > clean_bp,
            "note": (
                "⚠️ 污染组中套话比例更高——严格度衰减"
                if polluted_bp > clean_bp else
                "✅ 未检测到严格度衰减"
            ),
        }

    def _echo_index(self) -> dict:
        """检测复读机指数：污染组意见是否与前置讨论措辞高度相似。"""
        # 简易实现：检查污染组意见中是否包含种子话题的关键词
        seed_keywords = [
            "ENSO", "南极海冰", "因果推断", "AMO",
            "CMIP6", "SSP5-8.5", "AMOC", "ITCZ", "Sahel",
            "BET常数", "敏感性实验", "补充材料",
        ]

        echo_opinions = []
        for o in self.polluted.opinions:
            matched = [kw for kw in seed_keywords if kw in o.content]
            if matched:
                echo_opinions.append({"opinion_id": o.id, "matched_keywords": matched})

        return {
            "echo_count": len(echo_opinions),
            "total_opinions": len(self.polluted.opinions),
            "echo_ratio": len(echo_opinions) / len(self.polluted.opinions)
                          if self.polluted.opinions else 0.0,
            "echo_opinions": echo_opinions,
            "note": (
                "🔴 检测到复读——污染组意见与前置讨论高度相关"
                if len(echo_opinions) > 0 else
                "✅ 未检测到明显复读"
            ),
        }

    def _blind_spot_expansion(self) -> dict:
        """检测盲区扩大：干净房间发现但污染组遗漏的问题。"""
        # 基于意见内容的简易文本去重
        clean_only = []
        polluted_texts = {o.content[:80] for o in self.polluted.opinions}
        for o in self.clean.opinions:
            if o.content[:80] not in polluted_texts:
                clean_only.append(o.content[:120])

        return {
            "clean_only_count": len(clean_only),
            "note": (
                f"🔴 干净房间发现了 {len(clean_only)} 条污染组遗漏的独立意见——盲区扩大"
                if len(clean_only) > 0 else
                "✅ 两组覆盖了相同的问题域"
            ),
            "sample": clean_only[:3],
        }

    def _summarize(self, pi, strictness, echo, blind_spot) -> str:
        """生成人类可读的摘要。"""
        lines = [
            f"污染指数 PI = {pi['value']:.2f}  ({pi['interpretation']})",
            f"干净房间意见: {pi['clean_count']} 条  |  "
            f"污染组意见: {pi['polluted_count']} 条  |  "
            f"共享: {pi['shared_count']} 条",
            f"严格度衰减: {strictness['note']}",
            f"复读机指数: {echo['note']}",
            f"盲区扩大: {blind_spot['note']}",
        ]
        return "\n".join(lines)


# ============================================================
# 实验执行器
# ============================================================

class PollutionExperiment:
    """上下文污染基线实验。

    M0 阶段使用 dry-run 模式（打印协议）。
    M2+ 阶段接入真实 LLM API 执行。
    """

    def __init__(self, config: ExperimentConfig | None = None):
        self.config = config or ExperimentConfig()
        self.output_dir = Path(__file__).parent / "results"
        self.output_dir.mkdir(exist_ok=True)

    def dry_run(self) -> None:
        """打印实验协议（不调用 API）。"""
        cfg = self.config

        print(f"\n{'='*70}")
        print(f"  上下文污染检测基线实验 —— DRY RUN")
        print(f"  实验ID: {cfg.experiment_id}")
        print(f"  模型: {cfg.model}")
        print(f"{'='*70}")

        # 检查论文文件是否存在
        paper_path = Path(cfg.sample_paper_path)
        if paper_path.exists():
            print(f"\n  ✅ 测试样本: {paper_path}")
            print(f"     文件大小: {paper_path.stat().st_size:,} bytes")
        else:
            print(f"\n  ⚠️ 测试样本未找到: {paper_path}")
            print(f"     请将 Sahara 论文复制到指定路径，或修改 sample_paper_path")

        print(f"\n{'─'*70}")
        print(f"  实验流程")
        print(f"{'─'*70}")

        print(f"""
  Step 1: 准备测试样本
      论文: {cfg.sample_paper_path}
      审稿标准: {cfg.review_standard[:100]}...

  Step 2: 干净房间审稿（对照组）
      - 创建新的 LLM 会话（零上下文）
      - System Prompt: {cfg.review_standard[:80]}...
      - User Message: [论文全文]
      - Temperature: {cfg.temperature_clean}
      - 收集全部审稿意见

  Step 3: 污染上下文审稿（实验组）
      - 在同一 LLM 会话中，先注入 {len(cfg.pollution_seed_topics)} 段无关讨论
      - 模拟与用户的"前序对话"，内容涉及:
""")
        for i, topic in enumerate(cfg.pollution_seed_topics, 1):
            print(f"        {i}. {topic[:100]}...")

        print(f"""
      - 然后发送: "好的，现在请审稿以下论文"
      - User Message: [论文全文]
      - Temperature: {cfg.temperature_polluted}
      - ⚠️  此时 LLM 已有前序上下文（3段讨论）

  Step 4: 对比分析
      - 提取两组审稿意见的结构化表示
      - 计算:
        · 污染指数 PI = 1 - Jaccard(clean, polluted)
        · 严格度衰减率
        · 复读机指数
        · 盲区扩大率
      - 生成基线报告

  Step 5: 基线建立
      - 重复实验 ≥3 次（不同种子话题）以排除随机波动
      - 记录 PI 的均值 ± 标准差
      - 写入 M0 验收报告
""")

        print(f"{'─'*70}")
        print(f"  预期结果（假设）")
        print(f"{'─'*70}")
        print(f"""
  基于用户报告的"BD 现象"（严格度递减 + 意见摇摆），预期:
    - PI > 0.4（两组意见差异显著）
    - 严格度衰减率 > 0（污染组中"整体不错"类措辞更多）
    - 复读机指数 > 0（污染组意见与前置讨论内容有关联）
    - 盲区扩大 ≥ 1 条（干净房间发现但污染组遗漏的问题）

  如果以上假设成立 → Polaris 的"干净房间审稿"需求被定量验证。
""")

        print(f"{'─'*70}")
        print(f"  如何执行真实实验")
        print(f"{'─'*70}")
        print(f"""
  当前为 M0 摸底阶段。M2（引擎二 MVP）完成后，执行:
    python experiments/pollution_baseline.py --run

  需要:
    1. 有效的 LLM API Key（DeepSeek 或 智谱）
    2. Sahara 论文文件在指定路径
    3. 网络连接
""")

    def run(self) -> dict | None:
        """执行真实实验（需 API Key）。

        当前返回 None 并提示用户等待 M2。
        """
        print("\n⚠️ 真实实验需要 LLM API 接入和 M2 引擎二 MVP 完成。")
        print("当前实验仅支持 dry-run 模式。")
        print("M2 完成后，此方法将接入 engine_two_validator 的干净房间审稿功能。")
        return None

    def save_config(self) -> Path:
        """保存实验配置。"""
        import json as _json
        cfg_path = self.output_dir / f"{self.config.experiment_id}_config.json"
        cfg_dict = {
            "experiment_id": self.config.experiment_id,
            "sample_paper_path": self.config.sample_paper_path,
            "model": self.config.model,
            "num_seed_topics": len(self.config.pollution_seed_topics),
            "timestamp": datetime.now().isoformat(),
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            _json.dump(cfg_dict, f, ensure_ascii=False, indent=2)
        return cfg_path


# ============================================================
# 简化版手动实验（M0 阶段可用）
# ============================================================

def manual_experiment_guide() -> None:
    """打印手动实验指南——用户手动在两个会话中执行审稿。"""
    print(f"""
{'='*70}
  手动上下文污染实验指南（M0 阶段）
{'='*70}

不需要编写代码。你只需要在 LLM 工具中手动操作：

  Step 1: 干净房间审稿
      1. 打开一个新的 Claude Code / Reasonix 会话
      2. 输入:
         "/zhangcy-nature-review-strict H:\\Sahara\\Papers\\论文一_湿度门控BET逾渗模型_中文初稿.md"
      3. ⚠️ 在此之前确保会话中没有任何其他对话
      4. 将审稿意见保存为 clean_room_review.md

  Step 2: 污染上下文审稿
      1. 打开另一个新会话
      2. 先和 LLM 聊 3 个不相关的话题（3-5分钟），例如:
         a. "你觉得 ENSO 对南极海冰的影响能不能用因果推断方法分析？"
         b. "CMIP6 里 SSP5-8.5 下撒哈拉沙尘为什么反而减少了？"
         c. "审稿人让我补充敏感性实验，但我觉得结果影响不大..."
      3. 然后输入:
         "/zhangcy-nature-review-strict H:\\Sahara\\Papers\\论文一_湿度门控BET逾渗模型_中文初稿.md"
      4. 将审稿意见保存为 polluted_review.md

  Step 3: 对比
      逐条对比两份审稿意见:
      - 有多少条是两方都提到的？（共享意见）
      - 有多少条只有干净房间提到？（污染组漏掉的新问题）
      - 有多少条只有污染组提到？（被前序讨论"带偏"的关注点）
      - 污染组是否更倾向于说"整体不错"？
      - 污染组的措辞是否和前置讨论相似？

  Step 4: 计算
      PI = 1 - (共享意见数) / (两方意见总数 - 共享意见数)
      记录 PI 值作为基线。

  将对比结果保存为 pollution_baseline_YYYYMMDD.md，放入实验结果目录。
""")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Polaris M0-3 上下文污染检测基线实验")
    parser.add_argument("--dry-run", action="store_true", help="打印实验协议（不调用 API）")
    parser.add_argument("--run", action="store_true", help="执行真实实验（需 M2 完成）")
    parser.add_argument("--manual", action="store_true", help="打印手动实验指南")
    parser.add_argument("--report", action="store_true", help="查看历史实验结果")

    args = parser.parse_args()
    exp = PollutionExperiment()

    if args.dry_run:
        exp.dry_run()
        exp.save_config()
        print(f"\n  实验配置已保存。")

    elif args.manual:
        manual_experiment_guide()

    elif args.run:
        exp.run()

    elif args.report:
        rp = Path(__file__).parent / "results"
        reports = sorted(rp.glob("*.json"), reverse=True)
        if not reports:
            print("暂无实验结果。请先执行 --run。")
        else:
            for r in reports[:10]:
                print(f"  {r.name}")

    else:
        # 默认展示实验概述
        print(f"\n  Polaris M0-3 上下文污染检测基线实验")
        print(f"\n  实验目标: 量化干净房间 vs 污染上下文审稿的意见差异")
        print(f"  测试样本: Sahara BET-逾渗模型论文")
        print(f"  核心指标: 污染指数 PI (Jaccard 距离)")
        print(f"\n  用法:")
        print(f"    python experiments/pollution_baseline.py --dry-run  查看完整实验协议")
        print(f"    python experiments/pollution_baseline.py --manual   查看手动实验指南")
        print(f"    python experiments/pollution_baseline.py --run      执行真实实验（M2+）")
