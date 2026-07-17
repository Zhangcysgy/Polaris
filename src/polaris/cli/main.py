"""Polaris CLI —— 命令行入口

用法:
    polaris --help
    polaris status
    polaris method search "关键词"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="polaris")
def main():
    """Polaris — AI 科研自主发现系统（大气科学首发）

    五引擎架构：方法库 | 产物追踪 | 深度验证 | 全局迁移 | 自主发现
    """
    pass


# ---- 项目状态 ----

def _read_paper(paper_path: str) -> str:
    """读取论文文件内容。"""
    from pathlib import Path
    p = Path(paper_path)
    if not p.exists():
        raise click.FileError(str(p), "文件未找到")
    return p.read_text(encoding="utf-8")


@main.command()
@click.option("--project", "-p", default="default", help="项目名称")
def status(project: str):
    """查看当前项目状态（版本、审稿意见、方法库关联）"""
    from polaris.engine_one_tracker.feedback import FeedbackTracker
    from polaris.engine_one_tracker.versioning import VersionCapture
    from polaris.engine_o_methods import MethodLibrary

    with _get_db() as db:
        tracker = FeedbackTracker(db)
        vc = VersionCapture(db)
        lib = MethodLibrary(db)

        # 反馈统计
        fb_summary = tracker.get_summary(project)
        latest_v = vc.get_latest_version(project)
        method_stats = lib.get_stats()

        click.echo(f"\n{'='*50}")
        click.echo(f"  Polaris 项目状态: {project}")
        click.echo(f"{'='*50}")

        # 审稿意见
        click.echo(f"\n  [List] 审稿意见:")
        click.echo(f"     总计: {fb_summary['total']}  |  "
                   f"已解决: {fb_summary['resolved']}  |  "
                   f"处理中: {fb_summary['in_progress']}  |  "
                   f"待处理: {fb_summary['open']}")
        if fb_summary['total'] > 0:
            click.echo(f"     完成率: {fb_summary['completion_pct']:.0f}%")

        # 未解决的意见
        open_items = tracker.get_open_items(project)
        if open_items:
            click.echo(f"\n  [!]  未解决意见 ({len(open_items)} 条):")
            for item in open_items[:5]:
                prio_icon = {"critical": "[CRIT]", "high": "[HIGH]", "medium": "[WARN]", "low": "[OKAY]"}.get(item.priority, "⚪")
                click.echo(f"     {prio_icon} [{item.id[-8:]}] {item.content[:80]}...")

        # 版本
        if latest_v:
            click.echo(f"\n  [Data] 最新版本: {latest_v.label}")
            click.echo(f"     类型: {latest_v.version_type}  |  "
                       f"时间: {latest_v.created_at}")
            v_counts = vc.count_versions(project)
            click.echo(f"     版本统计: {v_counts}")

        # 方法库
        click.echo(f"\n  🔧 方法库: {method_stats['total']} 个方法")
        click.echo(f"     已验证: {method_stats['by_status'].get('verified', 0)}")

        click.echo()


# ---- 方法库（引擎O）----

def _get_db():
    """获取数据库连接（从配置文件读取路径）。"""
    from polaris.core.config import get_config
    from polaris.core.database import Database
    cfg = get_config()
    db_path = cfg.get("paths", "db_path", default="data/polaris.db")
    return Database(db_path)


@main.group()
def method():
    """方法库管理（引擎O）—— 检索、录入、审批"""
    pass


@method.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=10, help="返回条数上限")
def method_search(query: str, limit: int):
    """搜索方法库（自然语言）"""
    from polaris.engine_o_methods import MethodLibrary, expand_query

    with _get_db() as db:
        lib = MethodLibrary(db)
        # 扩展查询词
        expanded = expand_query(query)
        combined = f"{query} {' '.join(expanded)}"

        results = lib.search(combined, limit=limit)

        if not results:
            click.echo(f"未找到与 '{query}' 相关的方法。")
            click.echo(f"提示：尝试用英文关键词或领域术语。")
            return

        click.echo(f"\n搜索 '{query}' 找到 {len(results)} 个方法:\n")
        for r in results:
            status_icon = {
                "verified": "[OK]", "pending_confirm": "[...]",
                "candidate": "🔶", "rejected": "[X]", "deprecated": "⚫"
            }.get(r.status, "❓")
            type_label = {"atom": "原子", "orchestration": "编排", "parameter_instance": "参数"}
            click.echo(f"  {status_icon} [{r.id}] {type_label.get(r.type, r.type)} | {r.name}")
            click.echo(f"     {r.description[:120]}...")


@method.command("list")
@click.option("--status", "-s", default=None, help="筛选状态: candidate | pending_confirm | verified | rejected")
@click.option("--type", "-t", "mtype", default=None, help="筛选类型: atom | orchestration | parameter_instance")
@click.option("--domain", "-d", default=None, help="筛选领域")
def method_list(status: str | None, mtype: str | None, domain: str | None):
    """列出方法库条目"""
    from polaris.engine_o_methods import MethodLibrary

    with _get_db() as db:
        lib = MethodLibrary(db)
        results = lib.list_methods(type=mtype, status=status, domain=domain)

        if not results:
            click.echo("方法库为空。运行 polaris method seed 录入种子数据。")
            return

        type_label = {"atom": "原子", "orchestration": "编排", "parameter_instance": "参数"}
        click.echo(f"\n方法库（{len(results)} 条）:\n")
        for r in results:
            status_icon = {"verified": "[OK]", "pending_confirm": "[...]", "candidate": "🔶"}.get(r.status, "❓")
            click.echo(f"  {status_icon} [{r.id}] {type_label.get(r.type, r.type):4s} | {r.name}")
            if r.domain:
                click.echo(f"     领域: {r.domain}  |  调用: {r.success_count}成功/{r.failure_count}失败")


@method.command("show")
@click.argument("method_id")
def method_show(method_id: str):
    """查看方法详情"""
    from polaris.engine_o_methods import MethodLibrary

    with _get_db() as db:
        lib = MethodLibrary(db)
        entry = lib.get_method(method_id)

        if entry is None:
            click.echo(f"方法 '{method_id}' 未找到。")
            return

        click.echo(f"\n{'='*60}")
        click.echo(f"  {entry.name}")
        click.echo(f"  ID: {entry.id}  |  类型: {entry.type}  |  状态: {entry.status}")
        click.echo(f"{'='*60}")
        click.echo(f"\n{entry.description}")
        click.echo(f"\n领域: {entry.domain or '未指定'}")
        click.echo(f"变量: {', '.join(entry.variables) if entry.variables else '未指定'}")
        click.echo(f"质量分: {entry.quality_score:.2f}")
        click.echo(f"调用统计: {entry.success_count}成功 / {entry.failure_count}失败")
        click.echo(f"创建: {entry.created_at}  |  更新: {entry.updated_at}")

        # 版本
        versions = lib.get_versions(method_id)
        if versions:
            click.echo(f"\n版本历史 ({len(versions)}):")
            for v in versions:
                click.echo(f"  v{v['version']}: {v['change_summary'] or '无描述'}  ({v['created_at']})")


@method.command("seed")
def method_seed():
    """录入 Sahara 种子方法数据"""
    from polaris.engine_o_methods import MethodLibrary, seed_all

    with _get_db() as db:
        lib = MethodLibrary(db)
        result = seed_all(lib, approve=True)

        click.echo(f"\n[OK] 种子数据录入完成:")
        click.echo(f"  原子方法:   {len(result['atom'])} 条  {result['atom']}")
        click.echo(f"  编排条目:   {len(result['orch'])} 条  {result['orch']}")
        click.echo(f"  参数实例:   {len(result['param'])} 条  {result['param']}")


@method.command("approve")
@click.argument("method_id")
def method_approve(method_id: str):
    """审批方法（待确认 → 已验证）"""
    from polaris.engine_o_methods import Gate

    with _get_db() as db:
        gate = Gate(db)
        ok = gate.approve(method_id)
        if ok:
            click.echo(f"[OK] 方法 '{method_id}' 已审批通过。")
        else:
            click.echo(f"[X] 审批失败。请确认方法状态为 'pending_confirm'。")


@method.command("reject")
@click.argument("method_id")
@click.option("--reason", "-r", default="", help="驳回原因")
def method_reject(method_id: str, reason: str):
    """驳回方法（待确认 → 已驳回）"""
    from polaris.engine_o_methods import Gate

    with _get_db() as db:
        gate = Gate(db)
        ok = gate.reject(method_id, reason)
        if ok:
            click.echo(f"[X] 方法 '{method_id}' 已驳回。")
        else:
            click.echo(f"驳回失败。请确认方法状态为 'pending_confirm'。")


@method.command("pending")
def method_pending():
    """查看待审批方法列表"""
    from polaris.engine_o_methods import Gate

    with _get_db() as db:
        gate = Gate(db)
        methods = gate.get_pending_methods()

        if not methods:
            click.echo("[OK] 没有待审批的方法。")
            return

        click.echo(f"\n待审批方法 ({len(methods)} 条):\n")
        for m in methods:
            click.echo(f"  [...] [{m['id']}] {m['type']} | {m['name']}")
            click.echo(f"     质量分: {m['quality_score']:.2f}  |  审查时间: {m['reviewed_at']}")


@method.command("stats")
def method_stats():
    """方法库统计"""
    from polaris.engine_o_methods import MethodLibrary, Gate

    with _get_db() as db:
        lib = MethodLibrary(db)
        stats = lib.get_stats()

        gate = Gate(db)
        review = gate.get_review_stats()

        click.echo(f"\n{'='*40}")
        click.echo(f"  方法库统计")
        click.echo(f"{'='*40}")
        click.echo(f"  总方法数: {stats['total']}")
        click.echo(f"  按类型: {stats['by_type']}")
        click.echo(f"  按状态: {review}")
        click.echo(f"  按领域: {stats['by_domain']}")


# ---- 审稿（引擎一 & 二）----

@main.group()
def review():
    """深度审稿与验证（引擎一 + 引擎二）"""
    pass


@review.command("paper")
@click.argument("paper_path")
@click.option("--mode", "-m", default="clean-room",
              type=click.Choice(["clean-room", "red-team", "multi-expert", "methodology-trace"]),
              help="审稿模式: clean-room | red-team | multi-expert | methodology-trace")
@click.option("--project", "-p", default="default", help="关联项目")
@click.option("--dry-run", is_flag=True, help="仅生成审稿请求包（不调用LLM）")
def review_paper(paper_path: str, mode: str, project: str, dry_run: bool):
    """对论文运行深度审稿"""
    from polaris.engine_one_tracker.cleanroom import CleanRoomScheduler
    from polaris.engine_one_tracker.feedback import FeedbackTracker
    from polaris.engine_one_tracker.versioning import VersionCapture
    from polaris.engine_two_validator.trace import MethodologyTracer
    from polaris.engine_two_validator.redteam import RedTeamReviewer
    from polaris.engine_two_validator.debate import MultiExpertDebate
    from pathlib import Path

    try:
        content = _read_paper(paper_path)
    except click.FileError as e:
        click.echo(f"[X] {e}")
        return

    click.echo(f"\n[Report] 论文: {paper_path}  ({len(content):,} 字符)")
    click.echo(f"[Search] 审稿模式: {mode}")

    # 构建审稿请求
    paper_title = Path(paper_path).stem

    if mode == "clean-room":
        scheduler = CleanRoomScheduler()
        req = scheduler.create_request(
            paper_content=content,
            paper_path=paper_path,
            review_mode="clean_room",
            review_standard="",
        )
        click.echo(f"  请求ID: {req.request_id}")
        msgs = req.to_llm_messages()
        click.echo(f"  消息数: {len(msgs)}（仅 System + User，无历史上下文）")

    elif mode == "methodology-trace":
        tracer = MethodologyTracer()
        req = tracer.build_request(content, paper_path, title=paper_title)
        click.echo(f"  请求ID: {req.request_id}")
        click.echo(f"  审稿模式: 方法论溯源")

    elif mode == "red-team":
        rt = RedTeamReviewer()
        req = rt.build_request(content, paper_path, title=paper_title)
        click.echo(f"  请求ID: {req.request_id}")
        click.echo(f"  审稿模式: 红队模式（只找致命缺陷）")

    elif mode == "multi-expert":
        debate = MultiExpertDebate()
        experts = debate.auto_detect_experts(content)
        click.echo(f"  自动识别专家: {', '.join(experts)}")
        req = debate.build_request(content, paper_path, expert_roles=experts)
        click.echo(f"  请求ID: {req.request_id}")
        click.echo(f"  审稿模式: 多角色辩论（{len(experts)} 位专家）")

    if dry_run:
        click.echo(f"\n[List] System Prompt 预览（前500字符）:")
        click.echo(f"{'─'*50}")
        msgs = req.to_llm_messages()
        sys_msg = msgs[0]["content"][:500]
        click.echo(sys_msg)
        click.echo(f"...")
        click.echo(f"{'─'*50}")
        click.echo(f"\n[OK] 审稿请求已生成（dry-run，未调用 LLM）。")
        return

    # M3: 真实 LLM 调用
    from polaris.core.llm_client import LLMClient
    from polaris.engine_two_validator.orchestrator import ReviewOrchestrator

    try:
        llm = LLMClient.from_config()
        click.echo(f"\n[AI] 调用 LLM: {llm.config.model}...")
    except Exception as e:
        click.echo(f"\n[!] LLM 配置失败: {e}")
        click.echo(f"   请检查 polaris.yaml 中的 API Key 配置。")
        click.echo(f"   使用 --dry-run 可预览 System Prompt。")
        return

    orch = ReviewOrchestrator(_get_db(), llm)

    if mode == "clean-room":
        result = orch.run_clean_room(content, paper_path, project)
    elif mode == "methodology-trace":
        result = orch.run_methodology_trace(content, paper_path, project)
    elif mode == "red-team":
        result = orch.run_red_team(content, paper_path, project)
    elif mode == "multi-expert":
        experts = debate.auto_detect_experts(content)
        result = orch.run_multi_expert(content, paper_path, project, expert_roles=experts)

    # 输出结果
    click.echo(f"\n{'='*50}")
    click.echo(f"  审稿完成: {mode}")
    click.echo(f"  报告ID: {result.report_id}")
    click.echo(f"  耗时: {result.elapsed_seconds:.1f}s")
    click.echo(f"  提取意见: {len(result.feedback_ids)} 条")
    click.echo(f"{'='*50}")

    if result.llm_response:
        preview = result.llm_response.content[:800]
        click.echo(f"\n📝 LLM 回复摘要（前800字符）:\n")
        click.echo(preview)
        if len(result.llm_response.content) > 800:
            click.echo(f"\n...（共 {len(result.llm_response.content):,} 字符）")

    # 显示收手建议
    from polaris.engine_one_tracker.stop_criteria import StopCriteria
    sc = StopCriteria(_get_db())
    rec = sc.evaluate(project)
    icon = "[OK]" if rec.should_stop else "[!]"
    click.echo(f"\n{icon} 收手建议: {rec.reason}（置信度: {rec.confidence:.0%}）")


@review.command("feedback")
@click.argument("project", default="default")
def review_feedback(project: str):
    """查看项目的审稿意见状态"""
    from polaris.engine_one_tracker.feedback import FeedbackTracker

    with _get_db() as db:
        tracker = FeedbackTracker(db)
        items = tracker.get_all_items(project)

        if not items:
            click.echo(f"项目 '{project}' 暂无审稿意见。")
            return

        click.echo(f"\n项目 '{project}' 审稿意见 ({len(items)} 条):\n")
        for item in items:
            status_icon = {
                "open": "[CRIT]", "in_progress": "[WARN]",
                "resolved": "[OK]", "wontfix": "⚫", "duplicate": "🔄"
            }.get(item.status, "❓")
            click.echo(f"  {status_icon} [{item.id[-8:]}] {item.status:12s} | {item.priority:8s}")
            click.echo(f"     来源: {item.source}")
            click.echo(f"     内容: {item.content[:100]}...")
            if item.resolution_note:
                click.echo(f"     备注: {item.resolution_note}")


# ---- 方法迁移（引擎三）----

@main.group()
def migrate():
    """全局方法迁移（引擎三）—— 方法自动适配到全球区域"""
    pass


@migrate.command("run")
@click.argument("method_id")
@click.option("--source-region", "-s", required=True, help="源区域: sahara | central_asia | australia ...")
@click.option("--target-regions", "-t", required=True, help="目标区域列表（逗号分隔），或 'auto' 自动选择")
@click.option("--dry-run", is_flag=True, help="仅生成迁移计划（不执行）")
def migrate_run(method_id: str, source_region: str, target_regions: str, dry_run: bool):
    """将方法从源区域迁移到目标区域"""
    from polaris.engine_three_migrator import GlobalMigrator
    from polaris.engine_o_methods import MethodLibrary

    with _get_db() as db:
        migrator = GlobalMigrator(db)
        lib = MethodLibrary(db)

        # 确认方法存在
        method = lib.get_method(method_id)
        if method is None:
            click.echo(f"[X] 方法 '{method_id}' 未找到。")
            return

        # 确定目标区域
        if target_regions == "auto":
            targets = migrator.auto_select_targets(source_region)
            click.echo(f"自动选择目标区域: {', '.join(targets)}")
        else:
            targets = [t.strip() for t in target_regions.split(",")]

        if dry_run:
            click.echo(f"\n[List] 迁移计划: {method.name}")
            click.echo(f"   源区域: {source_region}")
            click.echo(f"   目标区域: {', '.join(targets)}")
            click.echo(f"\n   迁移策略（按区域）:")
            for t in targets:
                info = GlobalMigrator.PRESET_REGIONS.get(t)
                if info:
                    level_icon = {"full": "[OKAY]", "limited": "[WARN]", "missing": "[CRIT]"}
                    icon = level_icon.get(info.data_availability, "⚪")
                    click.echo(f"     {icon} {t}: {info.name}")
                    click.echo(f"        数据: {info.data_availability} | {info.notes[:80]}...")
            return

        # 执行迁移
        results = migrator.batch_migrate(method_id, source_region, targets)

        click.echo(f"\n{'='*50}")
        click.echo(f"  迁移完成: {method.name}")
        click.echo(f"{'='*50}")
        for r in results:
            status_icon = {
                "running": "🔄", "success": "[OK]", "anomaly": "[!]", "blocked": "[X]"
            }.get(r.status.value, "⚪")
            click.echo(f"  {status_icon} {r.target_region}: L{r.level.value} — {r.status.value}")
            if r.anomaly_detail:
                click.echo(f"     异常: {r.anomaly_detail[:100]}...")


@migrate.command("regions")
def migrate_regions():
    """列出预设区域库"""
    from polaris.engine_three_migrator import GlobalMigrator

    click.echo(f"\n预设区域库 ({len(GlobalMigrator.PRESET_REGIONS)} 个):\n")
    for rid, info in GlobalMigrator.PRESET_REGIONS.items():
        level_icon = {"full": "[OKAY]", "limited": "[WARN]", "missing": "[CRIT]"}
        icon = level_icon.get(info.data_availability, "⚪")
        click.echo(f"  {icon} {rid:20s} {info.name}")
        click.echo(f"     经纬度: lat {info.lat_range}, lon {info.lon_range}")
        click.echo(f"     数据: {info.data_availability:8s} | {info.notes}")


@migrate.command("anomalies")
@click.option("--method-id", "-m", default=None, help="筛选方法（默认全部）")
def migrate_anomalies(method_id: str | None):
    """查看迁移异常（潜在发现）"""
    from polaris.engine_three_migrator import GlobalMigrator

    with _get_db() as db:
        migrator = GlobalMigrator(db)
        anomalies = migrator.get_anomalies(method_id)

        if not anomalies:
            click.echo("暂无迁移异常。运行 polaris migrate run 后产生。")
            return

        click.echo(f"\n迁移异常 ({len(anomalies)} 个) — 差异即发现:\n")
        for a in anomalies:
            click.echo(f"  [!] {a.method_id}: {a.source_region} → {a.target_region}")
            click.echo(f"     {a.anomaly_detail[:120]}...")


# ---- 自主发现（引擎四）----

@main.group()
def discover():
    """自主科学发现循环（引擎四）—— 五引擎全串联"""
    pass


@discover.command("start")
@click.argument("direction")
@click.option("--max-steps", "-n", default=10, help="最大步数（默认10）")
@click.option("--dry-run", is_flag=True, help="仅生成循环计划（不执行）")
@click.option("--data-dir", "-d", default=None, help="数据目录路径（如 H:\\data\\raw\\era5）")
@click.option("--use-llm/--no-llm", default=True, help="是否使用LLM决策（默认开启）")
def discover_start(direction: str, max_steps: int, dry_run: bool, data_dir: str | None, use_llm: bool):
    """启动自主科学发现循环

    \b
    示例:
      polaris discover start "中亚沙尘源区湿度与风场特征"
      polaris discover start "分析撒哈拉沙尘起电机制" -d H:\\data\\raw\\era5 -n 15
    """
    from polaris.engine_four_loop import DiscoveryLoop
    from polaris.core.llm_client import LLMClient

    # 数据目录
    if data_dir is None:
        from polaris.core.config import get_config
        cfg = get_config()
        data_dir = cfg.get("paths", "data_dir", default="")
        if not data_dir:
            candidates = [r"H:\data\raw\era5", r"D:\data\era5", "./data"]
            for c in candidates:
                if os.path.exists(c):
                    data_dir = c
                    break

    with _get_db() as db:
        loop = DiscoveryLoop(db, max_steps=max_steps, data_dir=data_dir or "")

        click.echo(f"\n{'='*60}")
        click.echo(f"  Polaris 自主科学发现循环")
        click.echo(f"  方向: {direction}")
        click.echo(f"{'='*60}")

        # ──── 第一步：数据感知（必须先做）────
        click.echo(f"\n  [Data] 扫描数据目录: {data_dir or '未指定'}")
        inventory = loop.scan_data_inventory()

        if inventory.get("error"):
            click.echo(f"  [X] {inventory['error']}")
            return

        click.echo(f"  样本文件: {inventory['sample_file']}")
        click.echo(f"  变量 ({len(inventory['variables'])}): {', '.join(inventory['variables'])}")
        loop._available_vars_cache = inventory['variables']  # 缓存供 LLM 规划使用
        click.echo(f"  维度: {inventory['dims']}")
        click.echo(f"  时间: {inventory['time_range']}")
        click.echo(f"  空间: {inventory['spatial_range']}")
        click.echo(f"  分辨率: {inventory['resolution']}")

        # 多年数据范围
        summary = loop._get_data_summary()
        if summary.get("num_years", 0) > 1:
            click.echo(f"  数据跨度: {summary['year_range']} ({summary['num_years']}年, {summary['total_files']}文件)")
            click.echo(f"  [MultiYear] 多年分析能力已激活：气候态 | 年际趋势 | 季节循环 | 异常检测")

        # ──── 第二步：建议分析方向 ────
        llm = None
        if use_llm:
            try:
                llm = LLMClient.from_config()
            except Exception:
                pass

        suggestions = loop.suggest_directions(inventory, llm_client=llm)
        click.echo(f"\n  [Idea] 基于实际数据变量，可执行的分析方向:")
        for i, s in enumerate(suggestions, 1):
            click.echo(f"     {i}. {s}")
        click.echo(f"\n  [!]  以上建议仅基于数据中实际存在的变量。")
        click.echo(f"  没有沙尘浓度/AOD/沙尘排放等变量 → 无法直接分析沙尘。")
        click.echo(f"  可以分析的是起沙的气象条件（风、干旱度、边界层等）。")

        if dry_run:
            click.echo(f"\n[OK] 数据感知完成（dry-run）。使用 --no-dry-run 开始执行分析。")
            return

        # 启动循环
        loop.start(direction)

        # 初始化 LLM 客户端（如果可用）
        llm = None
        if use_llm:
            try:
                llm = LLMClient.from_config()
                click.echo(f"\n[AI] LLM 决策引擎: {llm.config.model}")
            except Exception as e:
                click.echo(f"\n[!] LLM 不可用 ({e})，使用规则决策模式。")

        # 执行循环
        click.echo(f"\n开始探索...\n")
        for i in range(max_steps):
            node = loop.step(llm_client=llm)
            if node is None:
                break

            icon = {"analysis": "[A]", "literature": "[L]", "validation": "[V]",
                    "migration": "[M]", "discovery": "[D]", "milestone": "[*]"}.get(node.node_type.value, "?")
            click.echo(f"  Step {i+1}: {icon} [{node.node_type.value}] {node.summary[:100]}")
            if node.detail:
                for line in node.detail.split("\n")[:6]:
                    click.echo(f"         {line[:120]}")

            if loop.status.value in ("soft_exit", "hard_exit", "human_exit"):
                break

        # 生成报告
        click.echo(f"\n{'='*60}")
        click.echo(f"  生成发现简报...")
        report = loop.generate_report(llm_client=llm)
        click.echo(f"{'='*60}\n")
        click.echo(report[:2000])

        # 保存报告
        report_path = f"H:\\Polaris\\reports\\discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        try:
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)
            click.echo(f"\n[Report] 简报已保存: {report_path}")
        except Exception:
            pass


@discover.command("status")
def discover_status():
    """查看当前循环状态"""
    from polaris.engine_four_loop import DiscoveryLoop

    with _get_db() as db:
        loop = DiscoveryLoop(db)
        click.echo(f"\n循环状态: {loop.status.value}")
        click.echo(f"当前步数: {loop.current_step}")


@discover.command("nodes")
@click.option("--limit", "-n", default=20, help="显示最近N个节点")
def discover_nodes(limit: int):
    """查看CRT拓扑节点"""
    from polaris.engine_four_loop import DiscoveryLoop
    from polaris.core.database import Database

    with _get_db() as db:
        rows = db.fetch_all(
            "SELECT * FROM crt_nodes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        if not rows:
            click.echo("暂无CRT节点。运行 polaris discover start 后产生。")
            return

        click.echo(f"\nCRT 拓扑节点（最近 {len(rows)} 个）:\n")
        for r in rows:
            type_icon = {
                "analysis": "[A]", "validation": "[Search]", "migration": "🌍",
                "discovery": "[Idea]", "dead": "💀", "milestone": "[Done]"
            }.get(r["node_type"], "⚪")
            click.echo(f"  {type_icon} [{r['id'][-12:]}] {r['node_type']:12s} | {r['summary'][:80]}")


# ---- 简报 ----

@main.command()
@click.option("--period", "-p", default="weekly",
              type=click.Choice(["weekly", "monthly", "latest"]),
              help="简报周期")
@click.option("--project", default="default", help="项目名称")
@click.option("--output", "-o", default=None, help="输出文件路径（默认打印到终端）")
def report(period: str, project: str, output: str | None):
    """查看发现简报（审稿历史+版本统计+收手建议）"""
    from polaris.engine_one_tracker.feedback import FeedbackTracker
    from polaris.engine_one_tracker.versioning import VersionCapture
    from polaris.engine_one_tracker.stop_criteria import StopCriteria
    from polaris.engine_o_methods import MethodLibrary
    from datetime import datetime

    with _get_db() as db:
        tracker = FeedbackTracker(db)
        vc = VersionCapture(db)
        sc = StopCriteria(db)
        lib = MethodLibrary(db)

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 收集数据
        fb_summary = tracker.get_summary(project)
        latest_v = vc.get_latest_version(project)
        v_counts = vc.count_versions(project)
        method_stats = lib.get_stats()
        rec = sc.evaluate(project)
        review_history = db.fetch_all(
            "SELECT * FROM review_reports WHERE project_id = ? ORDER BY created_at DESC LIMIT 5",
            (project,),
        )

        lines = [
            f"# Polaris 发现简报",
            f"**项目**: {project}  |  **周期**: {period}  |  **生成时间**: {now}",
            f"",
            f"## [List] 审稿状态",
            f"- 总意见: {fb_summary['total']}  |  已解决: {fb_summary['resolved']}  |  完成率: {fb_summary['completion_pct']:.0f}%",
            f"- 待处理: {fb_summary['open']}  |  处理中: {fb_summary['in_progress']}",
            f"",
            f"## [Data] 版本管理",
            f"- 最新版本: {latest_v.label if latest_v else '无'}",
            f"- 版本统计: {v_counts}",
            f"",
            f"## 🔧 方法库",
            f"- 总方法: {method_stats['total']}  |  已验证: {method_stats['by_status'].get('verified', 0)}",
            f"",
            f"## 🎯 收手建议",
            f"- {'[OK] 建议收手' if rec.should_stop else '[!] 继续迭代'}: {rec.reason}（置信度: {rec.confidence:.0%}）",
            f"",
            f"## 📝 最近审稿",
        ]

        for r in review_history:
            lines.append(f"- {r['created_at'][:16]} | {r['review_mode']} | 质量分: {r['quality_score']}")

        report_text = "\n".join(lines)

        if output:
            from pathlib import Path
            Path(output).write_text(report_text, encoding="utf-8")
            click.echo(f"[OK] 简报已保存到 {output}")
        else:
            click.echo(report_text)


if __name__ == "__main__":
    main()
