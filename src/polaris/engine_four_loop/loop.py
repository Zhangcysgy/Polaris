"""引擎四 — LLM 驱动的自主科学发现循环 (v2)

每一步由 LLM 动态决策，而非固定脚本。

循环逻辑:
    1. 构建当前状态上下文
    2. LLM 决策下一步行动
    3. 执行行动（数据分析/文献检索/迁移）
    4. 记录 CRT 节点
    5. 检查退出条件
    6. 生成发现简报
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from ..core.database import Database
from ..core.context_packet import ContextPacket


class LoopStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    SOFT_EXIT = "soft_exit"
    HARD_EXIT = "hard_exit"
    HUMAN_EXIT = "human_exit"


class NodeType(str, Enum):
    ANALYSIS = "analysis"
    LITERATURE = "literature"
    VALIDATION = "validation"
    MIGRATION = "migration"
    DISCOVERY = "discovery"
    DEAD = "dead"
    MILESTONE = "milestone"


@dataclass
class CRTNode:
    """CRT 拓扑节点。"""
    id: str = ""
    parent_id: str = ""
    project_id: str = ""
    node_type: NodeType = NodeType.ANALYSIS
    status: str = "active"
    summary: str = ""
    detail: str = ""         # 详细内容（分析结果/文献摘要）
    surprise_score: float = 0.0
    created_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"node_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# LLM 决策 Prompt
DISCOVERY_DECISION_PROMPT = """你是 Polaris 自主科学发现系统的决策引擎。分析当前状态，决定下一步行动。

## 当前状态
- 方向: {direction} | 步数: {step}/{max_steps}
- 已完成: {completed_nodes}
- 已执行的分析: {executed_capabilities}
- 最新发现: {latest_findings}
- 数据: {available_data}
- 可用分析能力（必须从以下列表中精确选一个）:
{capabilities_list}

## 规则
- 用自然语言描述你想做的分析，系统会自动匹配最接近的能力
- 每次选一个不同角度：温度、湿度、风、干旱程度、极端事件、复合条件、时间变化...
- 已执行: {executed_capabilities}

## 可选行动
1. **analyze** — 选一个新角度做分析
2. **literature** — 搜索文献（英文关键词）
3. **conclude** — 分析充分后生成结论

## 输出（仅一行JSON）:
{{"action":"analyze","target":"简短描述","intent":"自由描述想做的分析","reason":"为什么选这个角度"}}
{{"action":"literature","keywords":"英文搜索词","reason":"为什么"}}
{{"action":"conclude","target":"总结","reason":"探索充分"}}
"""

DISCOVERY_REPORT_PROMPT = """你是 Polaris 的科学发现报告生成器。请基于以下探索轨迹生成一份发现简报。

研究方向: {direction}
探索步数: {total_steps}
节点摘要:
{node_summaries}

请生成一份结构化的发现简报，包含:
1. 核心发现（1-2 句）
2. 关键数值结果
3. 与已有文献的关系
4. 值得进一步探索的方向
5. 方法学局限

输出 Markdown 格式。
"""


class DiscoveryLoop:
    """LLM 驱动的自主科学发现循环。

    用法:
        db = Database(...)
        loop = DiscoveryLoop(db, max_steps=10)
        loop.start("中亚沙尘源区湿度与风场特征分析")

        for _ in range(max_steps):
            node = loop.step()
            if node is None:
                break
            print(f"[{node.node_type}] {node.summary}")

        report = loop.generate_report()
        print(report)
    """

    DEFAULT_MAX_STEPS = 10
    SOFT_EXIT_NO_IMPROVEMENT = 3

    def __init__(self, db: Database, max_steps: int | None = None, data_dir: str = ""):
        self.db = db
        self.db.initialize()
        self.max_steps = max_steps or self.DEFAULT_MAX_STEPS
        self.data_dir = data_dir or os.environ.get("POLARIS_DATA_DIR", "")

        self._step = 0
        self._loop_id = ""
        self._status = LoopStatus.IDLE
        self._direction = ""
        self._nodes: list[CRTNode] = []
        self._no_improvement_count = 0
        self._llm_client = None  # 延迟初始化

    @property
    def status(self) -> LoopStatus:
        return self._status

    @property
    def current_step(self) -> int:
        return self._step

    # ---- 循环控制 ----

    def start(self, direction: str) -> CRTNode:
        """启动循环。"""
        self._loop_id = f"loop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._step = 0
        self._status = LoopStatus.RUNNING
        self._direction = direction
        self._nodes = []
        self._no_improvement_count = 0
        self._plan: list[dict] = []   # LLM 预生成的探索计划
        self._plan_index = 0

        root = self._add_node(
            NodeType.MILESTONE,
            f"循环启动: {direction}",
            f"最大步数: {self.max_steps}",
        )
        return root

    def scan_data_inventory(self) -> dict:
        """扫描数据目录，返回数据清单（变量、时空范围、文件数）。

        这是任何分析的前提——先知道有什么，再决定做什么。
        """
        inventory = {
            "data_dir": self.data_dir,
            "total_files": 0,
            "sample_file": "",
            "variables": [],
            "dims": {},
            "time_range": "",
            "spatial_range": "",
            "resolution": "",
        }

        files = self._find_data_files()
        if not files:
            inventory["error"] = "未找到 NetCDF 文件"
            return inventory

        inventory["total_files"] = len(files) if hasattr(self, '_all_file_count') else "多"
        inventory["sample_file"] = os.path.basename(files[0])

        try:
            import xarray as xr
            import numpy as np
            ds = xr.open_dataset(files[0])
            inventory["variables"] = list(ds.data_vars)
            inventory["dims"] = dict(ds.sizes)

            # 时间范围
            time_var = "valid_time" if "valid_time" in ds else "time"
            if time_var in ds:
                t0 = ds[time_var].values[0]
                t1 = ds[time_var].values[-1]
                inventory["time_range"] = f"{str(t0)[:19]} ~ {str(t1)[:19]} ({ds.sizes.get(time_var, '?')}步)"

            # 空间范围
            for coord in ["longitude", "latitude", "lon", "lat"]:
                if coord in ds:
                    vals = ds[coord].values
                    inventory["spatial_range"] += f"{coord}: {float(vals.min()):.1f}~{float(vals.max()):.1f} ({len(vals)}点) "
                    if len(vals) > 1:
                        inventory["resolution"] += f"Δ{coord}={abs(float(vals[1]-vals[0])):.2f}° "
            ds.close()
        except Exception as e:
            inventory["error"] = str(e)

        return inventory

    def suggest_directions(self, inventory: dict, llm_client=None) -> list[str]:
        """基于实际数据变量，建议可行的分析方向。

        无 LLM 时使用领域规则映射。
        """
        variables = inventory.get("variables", [])

        suggestions = []
        var_set = set(variables)

        # 规则映射：变量组合 → 分析方向
        if {"t2m", "d2m"}.issubset(var_set):
            suggestions.append("地表温度与露点温度的时空分布特征")
            suggestions.append("基于露点亏缺的干旱指数分析（T - Td）")
        if {"u10", "v10"}.issubset(var_set):
            suggestions.append("10m风速风向的气候态特征")
            suggestions.append("强风事件频率分析（起沙风的必要条件）")
        if {"blh"}.issubset(var_set):
            suggestions.append("边界层高度的季节变化——影响沙尘垂直扩散")
        if {"t2m", "d2m", "u10", "v10"}.issubset(var_set):
            suggestions.append("干旱+强风复合条件分析：识别潜在起沙时段")
        if {"sp"}.issubset(var_set):
            suggestions.append("地表气压系统与风场的关系")
        if {"tcwv"}.issubset(var_set):
            suggestions.append("大气水汽总量的时空变化")

        if not suggestions:
            suggestions.append(f"基础统计：{', '.join(variables[:5])}的均值与变率")

        # LLM 补充建议
        if llm_client and len(variables) > 3:
            try:
                prompt = (
                    f"你是一位大气科学专家。目前可用的数据变量为：{', '.join(variables)}。"
                    f"数据覆盖区域为东亚(70-140E, 15-55N)，时间范围为1979年起逐小时。"
                    f"请基于这些变量，建议3-5个最有科学价值的分析方向。"
                    f"每个方向一句话，不要编号。"
                )
                resp = llm_client.chat([
                    {"role": "user", "content": prompt}
                ], temperature=0.3, max_tokens=500)
                llm_suggestions = [s.strip("- ").strip() for s in resp.content.split("\n") if len(s.strip()) > 10]
                suggestions.extend(llm_suggestions[:5])
            except Exception:
                pass

        return suggestions[:8]

    def step(self, llm_client=None) -> Optional[CRTNode]:
        """执行一步——计划驱动或 LLM 决策 + 行动执行。"""
        if self._status != LoopStatus.RUNNING:
            return None

        self._step += 1
        if self._step > self.max_steps:
            self._status = LoopStatus.HARD_EXIT
            return self._add_node(NodeType.MILESTONE, f"达到最大步数 {self.max_steps}")

        # 第一步时用 LLM 生成完整计划
        if llm_client and self._step == 1 and not self._plan:
            self._plan = self._llm_plan(llm_client, min(self.max_steps, 8))
            if self._plan:
                # 第一个节点显示计划概况
                plan_summary = " → ".join(
                    f"{p.get('action','?')}:{p.get('intent',p.get('target','?'))[:20]}"
                    for p in self._plan[:6]
                )
                self._add_node(NodeType.MILESTONE, f"探索计划: {plan_summary}", "")

        # 决策来源：计划 > LLM 单步 > 规则
        if self._plan and self._plan_index < len(self._plan):
            decision = self._plan[self._plan_index]
            self._plan_index += 1
        elif llm_client:
            decision = self._llm_decide(llm_client)
        else:
            decision = self._rule_based_decide()

        # 执行
        node = self._execute_decision(decision)
        self._nodes.append(node)

        # 退出检查
        if decision.get("action") == "conclude":
            self._status = LoopStatus.SOFT_EXIT

        return node

    def _llm_plan(self, llm_client, total_steps: int) -> list[dict]:
        """让 LLM 一次性规划全部探索步骤，而非逐步决策。"""
        try:
            from .capabilities import CapabilityResolver
            resolver = CapabilityResolver()
            caps = resolver.list_available(self._available_vars_cache) if hasattr(self, '_available_vars_cache') else []

            cap_descriptions = "\n".join(f"- {c.name}: {c.description}" for c in caps)

            prompt = f"""你是大气科学数据分析专家。请为一组 ERA5 数据规划一个完整的探索计划。

## 数据
变量: {self._available_vars_cache if hasattr(self, '_available_vars_cache') else '未知'}
区域: 东亚 (70-140E, 15-55N)
研究方向: {self._direction}

## 可用的分析能力
{cap_descriptions}

## 要求
- 规划 {total_steps} 步探索
- 每步使用不同的分析能力
- 从基础统计开始，逐步深入
- 中间穿插 1-2 次文献搜索
- 最后一步是 conclude

## 输出（JSON数组，每元素一个步骤）:
[{{"action":"analyze","intent":"变量均值","reason":"先了解基本分布"}},
 {{"action":"analyze","intent":"露点亏缺","reason":"计算干旱程度"}},
 {{"action":"literature","keywords":"East Asia drought aridity","reason":"查文献"}},
 ...,
 {{"action":"conclude","target":"总结","reason":"探索完成"}}]"""

            resp = llm_client.chat([
                {"role": "system", "content": "你是科学数据分析规划器。仅输出 JSON 数组，不要其他内容。"},
                {"role": "user", "content": prompt},
            ], temperature=0.1, max_tokens=1500, no_thinking=True)

            content = resp.content.strip()
            if "[" in content and "]" in content:
                start = content.index("[")
                end = content.rindex("]") + 1
                plan = json.loads(content[start:end])
                if isinstance(plan, list) and len(plan) > 0:
                    return plan
        except Exception:
            pass
        return []  # 回退到规则决策

    def _llm_decide(self, llm_client) -> dict:
        """让 LLM 决策下一步。"""
        try:
            # 收集状态
            completed = [f"{n.node_type.value}: {n.summary[:80]}" for n in self._nodes[-5:]]
            latest = self._nodes[-1].detail[:300] if self._nodes else "无"

            # 收集已执行的能力名称
            executed = set()
            for n in self._nodes:
                if n.node_type == NodeType.ANALYSIS and "执行:" in n.detail:
                    # 从 detail 中提取 "执行: XXX"
                    for line in n.detail.split("\n"):
                        if line.startswith("执行:") or line.startswith("降级:"):
                            executed.add(line.split(":")[0] + ":" + line.split(":",1)[1][:40])

            prompt = DISCOVERY_DECISION_PROMPT.format(
                direction=self._direction,
                step=self._step,
                max_steps=self.max_steps,
                completed_nodes="\n".join(completed) if completed else "无",
                executed_capabilities=", ".join(executed)[:200] if executed else "无",
                latest_findings=latest,
                available_data=self._scan_data(),
                capabilities_list=self._list_capabilities(),
            )

            resp = llm_client.chat([
                {"role": "system", "content": "你是一个科学决策引擎。仅输出一行 JSON，不要输出其他内容。"},
                {"role": "user", "content": prompt},
            ], temperature=0.3, max_tokens=500)

            # 解析 JSON
            content = resp.content.strip()
            if "{" in content and "}" in content:
                start = content.index("{")
                end = content.rindex("}") + 1
                return json.loads(content[start:end])
        except Exception:
            pass

        return self._rule_based_decide()

    def _rule_based_decide(self) -> dict:
        """无 LLM 时的基于规则决策（回退方案）。"""
        cycle = self._step % 4
        if cycle == 1:
            return {"action": "analyze", "target": "基础统计分析", "reason": "探索可用数据的基本特征", "variables": ["t2m", "d2m", "wind"]}
        elif cycle == 2:
            return {"action": "validate", "target": "物理校验", "reason": "验证分析结果的物理合理性"}
        elif cycle == 3:
            return {"action": "literature", "target": "相关文献检索", "reason": "为发现提供文献背景", "keywords": self._direction}
        else:
            if self._step >= self.max_steps - 2:
                return {"action": "conclude", "target": "生成结论", "reason": "已达到探索边界"}
            return {"action": "analyze", "target": "深入分析", "reason": "继续探索", "variables": ["d2m", "wind", "t2m"]}

    def _execute_decision(self, decision: dict) -> CRTNode:
        """执行 LLM 的决策。"""
        action = decision.get("action", "analyze")
        target = decision.get("target", "")

        if action == "analyze":
            return self._do_analysis(decision)
        elif action == "validate":
            return self._do_validation(decision)
        elif action == "literature":
            return self._do_literature(decision)
        elif action == "migrate":
            return self._do_migration(decision)
        elif action == "conclude":
            return self._add_node(NodeType.MILESTONE, f"结论: {target}", decision.get("reason", ""))
        return self._add_node(NodeType.ANALYSIS, f"未知行动: {action}")

    # ---- 行动执行 ----

    def _do_analysis(self, decision: dict) -> CRTNode:
        """执行数据分析——使用能力层匹配 + 执行 + 自动去重。"""
        target = decision.get("target", "数据分析")
        intent = decision.get("intent", target)

        detail_lines = []
        surprise = 0.0

        try:
            import xarray as xr

            data_files = self._find_data_files()
            if not data_files:
                return self._add_node(NodeType.ANALYSIS, f"分析: {target}",
                                      "未找到数据文件", surprise_score=0)

            fname = data_files[0]
            ds = xr.open_dataset(fname)
            available_vars = list(ds.data_vars)
            ds.close()

            detail_lines.append(f"数据: {os.path.basename(fname)} ({len(available_vars)}变量)")
            detail_lines.append(f"LLM意图: {intent}")

            # 收集已执行的能力
            executed_names = set()
            for n in self._nodes:
                if n.node_type == NodeType.ANALYSIS:
                    for line in n.detail.split("\n"):
                        if "执行:" in line or "降级:" in line:
                            # 提取能力名称
                            name = line.split(":", 1)[1].strip().split("(")[0].strip().split(" ")[0]
                            if len(name) > 1:
                                executed_names.add(name)

            # 使用能力解析器
            from .capabilities import CapabilityResolver
            resolver = CapabilityResolver()
            match = resolver.match(intent, available_vars)

            # 如果匹配到的能力已执行过，尝试找下一个未使用的
            if match.matched and match.capability:
                if match.capability.name in executed_names:
                    # 找下一个未执行的能力
                    available = resolver.list_available(available_vars)
                    unused = [c for c in available if c.name not in executed_names]
                    if unused:
                        from .capabilities import CapabilityMatch as CM
                        old_name = match.capability.name
                        match = CM(
                            intent=intent, matched=True, capability=unused[0],
                            reason=f"自动切换: '{old_name}'已执行 → '{unused[0].name}'（{len(unused)}个未用能力剩余）",
                            variables_available=available_vars,
                        )
                        detail_lines.append(f"去重: {old_name}已执行，自动选{unused[0].name}")
                    else:
                        detail_lines.append(f"所有{len(available)}个能力已执行完毕")
                        # 提前退出：无可用的新分析
                        self._status = LoopStatus.SOFT_EXIT
                        return self._add_node(NodeType.MILESTONE,
                            f"分析完毕: {len(available)}个能力全部执行", "\n".join(detail_lines))

            if match.matched and match.capability:
                # 精确匹配 → 执行（多年能力传全部文件）
                cap = match.capability
                multi_year_funcs = ["compute_climatology", "compute_interannual_trend",
                                    "compute_seasonal_cycle", "compute_anomaly"]
                if cap.function_name in multi_year_funcs:
                    all_files = self._find_data_files(max_files=50)
                    result = resolver.execute(cap, fname, all_files=all_files)
                    detail_lines.append(f"多年分析: {len(all_files)}个文件")
                else:
                    result = resolver.execute(cap, fname)
                detail_lines.append(f"执行: {cap.name} ({match.reason})")
                detail_lines.append(self._format_results(result))
                surprise = self._calc_surprise_from_results(result)

            elif match.fallback:
                # 降级匹配 → 执行替代方案
                fb = match.fallback
                multi_year_funcs = ["compute_climatology", "compute_interannual_trend",
                                    "compute_seasonal_cycle", "compute_anomaly"]
                if fb.function_name in multi_year_funcs:
                    all_files = self._find_data_files(max_files=50)
                    result = resolver.execute(fb, fname, all_files=all_files)
                    detail_lines.append(f"多年分析: {len(all_files)}个文件")
                else:
                    result = resolver.execute(fb, fname)
                detail_lines.append(f"降级: {match.reason}")
                detail_lines.append(f"执行替代: {fb.name}")
                detail_lines.append(self._format_results(result))
                surprise = self._calc_surprise_from_results(result)

            else:
                # 无法匹配 → 列出可用能力，如实反馈
                available = resolver.list_available(available_vars)
                detail_lines.append(f"无法执行: {match.reason}")
                detail_lines.append(f"当前数据可用的分析 ({len(available)}项):")
                for c in available[:6]:
                    detail_lines.append(f"  - {c.name}: {c.description[:60]}")

        except ImportError as e:
            detail_lines.append(f"缺少依赖: {e}")
        except Exception as e:
            detail_lines.append(f"分析出错: {e}")

        detail = "\n".join(detail_lines)
        return self._add_node(NodeType.ANALYSIS, f"分析: {target}", detail, surprise_score=surprise)

    def _format_results(self, result: dict) -> str:
        """格式化分析结果。"""
        lines = []
        for k, v in result.get("results", {}).items():
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.3f}")
            else:
                lines.append(f"  {k}: {v}")
        if result.get("note"):
            lines.append(f"  [{result['note']}]")
        return "\n".join(lines) if lines else "无数值结果"

    def _calc_surprise_from_results(self, result: dict) -> float:
        """基于分析结果计算惊喜度。"""
        score = 0.0
        for k, v in result.get("results", {}).items():
            if isinstance(v, float):
                if "dry_pct" in k and v > 50:
                    score += 0.3  # 超过50%干燥 → 有意思
                if "compound_pct" in k and v > 10:
                    score += 0.2
                if "over_10ms" in k and v > 20:
                    score += 0.2
        return min(score, 1.0)

    def _do_validation(self, decision: dict) -> CRTNode:
        """执行物理校验。"""
        target = decision.get("target", "物理校验")
        last_node = self._nodes[-1] if self._nodes else None
        detail = last_node.detail if last_node else ""

        checks = []
        if "d2m" in detail.lower() and "t2m" in detail.lower():
            checks.append("✅ 露点 ≤ 温度 (物理约束)")

        if not checks:
            checks.append("⏳ 暂无可校验的数值结果")

        return self._add_node(NodeType.VALIDATION, f"校验: {target}", "\n".join(checks))

    def _do_literature(self, decision: dict) -> CRTNode:
        """执行文献检索。"""
        raw_keywords = decision.get("keywords", self._direction)
        # 自动翻译中文关键词 → 英文（气象领域常用映射）
        en_keywords = self._translate_keywords(raw_keywords)
        target = decision.get("target", f"搜索文献: {en_keywords}")

        detail_lines = [f"原始关键词: {raw_keywords}"]
        detail_lines.append(f"英文搜索: {en_keywords}")

        try:
            from ..skills.literature import LiteratureSearcher
            searcher = LiteratureSearcher()
            result = searcher.search(en_keywords, max_papers=5)

            detail_lines.append(f"找到 {result.total_found} 篇论文 (来源: {result.source})")
            for p in result.papers[:5]:
                detail_lines.append(f"  - {p.to_summary()[:120]}")
        except Exception as e:
            detail_lines.append(f"文献检索出错: {e}")

        return self._add_node(
            NodeType.LITERATURE,
            f"文献: {en_keywords[:60]}",
            "\n".join(detail_lines),
            surprise_score=0.2 if "未见报道" in "\n".join(detail_lines) else 0.0,
        )

    def _do_migration(self, decision: dict) -> CRTNode:
        """执行区域迁移。"""
        target = decision.get("target", "区域迁移")

        try:
            from ..engine_three_migrator import GlobalMigrator
            migrator = GlobalMigrator(self.db)
            targets = migrator.auto_select_targets("central_asia")

            detail_lines = [f"源区域: central_asia", f"目标: {', '.join(targets[:3])}"]
            for t in targets[:3]:
                info = GlobalMigrator.PRESET_REGIONS.get(t)
                if info:
                    detail_lines.append(f"  {t}: {info.data_availability} — {info.name}")
        except Exception as e:
            detail_lines = [f"迁移出错: {e}"]

        return self._add_node(NodeType.MIGRATION, f"迁移: {target}", "\n".join(detail_lines))

    # ---- 报告生成 ----

    def generate_report(self, llm_client=None) -> str:
        """生成发现简报。"""
        if not self._nodes:
            return "# 无探索节点"

        summaries = []
        for n in self._nodes:
            summaries.append(f"[{n.node_type.value}] {n.summary}")
            if n.detail:
                summaries.append(f"  {n.detail[:200]}")

        if llm_client:
            try:
                prompt = DISCOVERY_REPORT_PROMPT.format(
                    direction=self._direction,
                    total_steps=self._step,
                    node_summaries="\n".join(summaries),
                )
                resp = llm_client.chat([
                    {"role": "system", "content": "你是科学报告生成器。输出 Markdown。"},
                    {"role": "user", "content": prompt},
                ], temperature=0.3)
                return resp.content
            except Exception:
                pass

        # 回退：规则生成
        lines = [
            f"# Polaris 发现简报",
            f"**方向**: {self._direction}",
            f"**步数**: {self._step}/{self.max_steps}",
            f"**状态**: {self._status.value}",
            f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 探索轨迹",
        ]
        for n in self._nodes:
            icon = {"analysis": "🔬", "literature": "📚", "validation": "🔍",
                    "migration": "🌍", "discovery": "💡", "milestone": "🏁"}.get(n.node_type.value, "⚪")
            lines.append(f"- {icon} [{n.node_type.value}] {n.summary}")
            if n.detail:
                for dl in n.detail.split("\n")[:3]:
                    lines.append(f"    {dl}")

        return "\n".join(lines)

    # ---- 辅助方法 ----

    def _add_node(self, ntype: NodeType, summary: str, detail: str = "", surprise_score: float = 0.0) -> CRTNode:
        parent = self._nodes[-1].id if self._nodes else ""
        node = CRTNode(
            parent_id=parent,
            project_id=self._loop_id,
            node_type=ntype,
            summary=summary,
            detail=detail,
            surprise_score=surprise_score,
        )
        self.db.execute(
            "INSERT INTO crt_nodes (id, parent_id, project_id, node_type, status, summary, surprise_score, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (node.id, node.parent_id, node.project_id, node.node_type.value, "active", node.summary[:500], node.surprise_score, node.created_at),
        )
        self.db.commit()
        return node

    def _scan_data(self) -> str:
        """扫描可用数据。"""
        if not self.data_dir:
            return "未指定数据目录"
        import glob
        files = glob.glob(os.path.join(self.data_dir, "**", "*.nc"), recursive=True)[:20]
        if not files:
            return "无 NetCDF 文件"
        return f"{len(files)}+ NetCDF 文件 (如 {os.path.basename(files[0])})"

    def _list_capabilities(self) -> str:
        """列出当前数据可用的分析能力。"""
        try:
            from .capabilities import CapabilityResolver
            resolver = CapabilityResolver()
            files = self._find_data_files()
            if files:
                import xarray as xr
                ds = xr.open_dataset(files[0])
                vars_list = list(ds.data_vars)
                ds.close()
                caps = resolver.list_available(vars_list)
                return ", ".join(c.name for c in caps)
        except Exception:
            pass
        return "均值, 标准差, 极值, 百分位"

    def _list_methods(self) -> str:
        """列出方法库。"""
        rows = self.db.fetch_all("SELECT name FROM methods WHERE status='verified' LIMIT 10")
        if not rows:
            return "无已验证方法"
        return ", ".join(r["name"] for r in rows)

    def _find_data_files(self, pattern: str = "single", max_files: int = 200) -> list[str]:
        """查找数据文件——优先 single_levels instant 文件。

        Args:
            pattern: 文件名匹配模式 ("single" | "pressure" | "accum" | "all")
            max_files: 最大返回文件数
        """
        if not self.data_dir:
            return []
        import glob
        all_files = sorted(glob.glob(os.path.join(self.data_dir, "**", "*.nc"), recursive=True))

        if pattern == "single":
            files = [f for f in all_files if "single" in f and "instant" in f]
        elif pattern == "pressure":
            files = [f for f in all_files if "pressure" in f]
        elif pattern == "accum":
            files = [f for f in all_files if "accum" in f]
        else:
            files = all_files

        return files[:max_files]

    def _get_data_summary(self) -> dict:
        """获取数据概览：年份范围、总文件数、变量列表。"""
        files = self._find_data_files(max_files=5000)
        if not files:
            return {"error": "无数据"}

        import xarray as xr
        import re

        # 提取年份信息
        years = set()
        for f in files:
            match = re.search(r'(\d{4})', os.path.basename(f))
            if match:
                years.add(int(match.group(1)))

        ds = xr.open_dataset(files[0])
        vars_list = list(ds.data_vars)
        ds.close()

        return {
            "total_files": len(files),
            "year_range": f"{min(years)}-{max(years)}" if years else "未知",
            "num_years": len(years),
            "variables": vars_list,
            "sample_file": os.path.basename(files[0]),
        }

    def _translate_keywords(self, chinese: str) -> str:
        """将中文研究方向翻译为英文搜索关键词。"""
        mapping = [
            ("沙尘暴", "dust storm"), ("起沙", "dust emission"),
            ("沙尘", "dust"), ("干旱", "drought aridity"),
            ("边界层", "boundary layer"), ("风速", "wind speed"),
            ("风向", "wind direction"), ("湿度", "humidity"),
            ("温度", "temperature"), ("露点", "dew point"),
            ("降水", "precipitation"), ("闪电", "lightning"),
            ("东亚", "East Asia"), ("中亚", "Central Asia"),
            ("撒哈拉", "Sahara"), ("起电", "electrification"),
            ("摩擦", "triboelectric"), ("气候", "climate"),
            ("气象", "meteorology"), ("大气", "atmosphere"),
            ("地表", "surface"), ("区域", "region"),
            ("特征", "characteristics"), ("分析", ""),
        ]
        # 收集匹配到的英文词
        words = []
        remaining = chinese
        for cn, en in mapping:
            if cn in remaining:
                if en:  # 跳过空翻译（如"分析"→""）
                    words.append(en)
                remaining = remaining.replace(cn, " ", 1)

        if words:
            query = " ".join(words)
            # 如果是气象相关的，加 domain 限定
            if any(w in query for w in ["dust", "atmosphere", "meteorology", "climate", "wind", "temperature"]):
                query += " atmosphere reanalysis"
            return query[:150]

        # 全中文/无法翻译 → 用通用气象+区域关键词
        return "East Asia climatology reanalysis ERA5 meteorological"

    def _calc_surprise(self, detail_lines: list[str]) -> float:
        """简易惊喜度计算。"""
        score = 0.0
        for line in detail_lines:
            if "270" in line or "260" in line:
                score += 0.1  # 低温 → 可能干燥
            if "3." in line and "m/s" in line:
                score += 0.05
        return min(score, 1.0)
