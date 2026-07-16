"""50题气象编码测试基准 —— 评分脚本

用法:
    python -m benchmarks.scorer --list          # 列出全部50题
    python -m benchmarks.scorer --category io   # 按分类列出
    python benchmarks/scorer.py --list          # 直接运行也行
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 处理两种运行方式
try:
    from .questions import QUESTIONS, Category, Difficulty
except ImportError:
    _here = Path(__file__).parent
    sys.path.insert(0, str(_here))
    from questions import QUESTIONS, Category, Difficulty  # type: ignore


# ============================================================
# 评分器
# ============================================================

class Scorer:
    """自动/人工评分器。

    每道题有 N 个验证维度：
    - assertions: 代码中应包含的 assert/check
    - forbidden: 代码中不应出现的错误模式
    - expected_keys: 输出中应包含的键/字段
    - expected_range: 输出数值的期望范围

    当前版本为"人工辅助评分"——打印验证标准，由用户手动确认。
    """

    def __init__(self, results_path: str | Path | None = None):
        if results_path is None:
            results_path = Path(__file__).parent / "results"
        self.results_path = Path(results_path)
        self.results_path.mkdir(exist_ok=True)

    def list_questions(self, category: Category | None = None) -> list:
        """列出题目。"""
        if category is None:
            return QUESTIONS
        return [q for q in QUESTIONS if q.category == category]

    def run_single(
        self,
        question,
        llm_code: str = "",
        llm_output: str = "",
        manual_scores: list[bool] | None = None,
    ) -> dict:
        """评分单题。"""
        verif = question.verification
        checklist = []

        # 构建验证清单
        for a in verif.assertions:
            checklist.append(("assert", a))
        for f in verif.forbidden:
            checklist.append(("forbidden", f))
        for k in verif.expected_keys:
            checklist.append(("expected_key", k))
        if verif.expected_range:
            checklist.append(("expected_range", verif.expected_range))

        total = len(checklist)
        if total == 0:
            return {"question_id": question.id, "score": 1.0, "details": [], "note": "无验证标准"}

        if manual_scores is not None:
            passed = sum(manual_scores)
            details = [
                {"type": t, "item": c, "passed": s}
                for (t, c), s in zip(checklist, manual_scores)
            ]
        else:
            details = []
            passed = 0
            for check_type, item in checklist:
                ok = self._auto_check(check_type, item, llm_code, llm_output)
                if ok:
                    passed += 1
                details.append({"type": check_type, "item": item, "passed": ok})

        score = passed / total

        return {
            "question_id": question.id,
            "category": question.category.value,
            "title": question.title,
            "total_checks": total,
            "passed_checks": passed,
            "score": score,
            "details": details,
        }

    def _auto_check(self, check_type: str, item: str, code: str, output: str) -> bool:
        """简易自动检查。保守策略：不确定的返回 False。"""
        code_l = code.lower()
        out_l = output.lower()
        item_l = item.lower()

        if check_type == "assert":
            keywords = ["assert", "try:", "except", "isnan", "isnull", "notnull",
                       "dropna", "fillna", "isfinite", "isinf"]
            return any(kw in code_l for kw in keywords)

        if check_type == "forbidden":
            # 检查是否真的避免了禁止模式
            return item_l not in code_l

        if check_type == "expected_key":
            return item_l in code_l or item_l in out_l

        if check_type == "expected_range":
            return True  # 数值范围检查需要运行代码，暂跳过

        return False

    def run_batch(self, model: str, llm_results: dict, manual_scores: dict | None = None) -> dict:
        """批量评分。"""
        results = []
        for q in QUESTIONS:
            llm = llm_results.get(q.id, {"code": "", "output": ""})
            ms = manual_scores.get(q.id) if manual_scores else None
            result = self.run_single(q, llm.get("code", ""), llm.get("output", ""), ms)
            results.append(result)

        scores = [r["score"] for r in results]
        by_category: dict[str, list[float]] = {}
        for r in results:
            by_category.setdefault(r["category"], []).append(r["score"])

        summary = {
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "total_questions": len(results),
            "overall_score": sum(scores) / len(scores) if scores else 0.0,
            "by_category": {c: sum(v) / len(v) for c, v in by_category.items()},
            "details": results,
        }

        safe_model = model.replace("/", "_").replace(":", "_")
        fname = f"benchmark_{safe_model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(self.results_path / fname, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return summary

    def print_summary(self, summary: dict) -> None:
        """打印评分摘要。"""
        print(f"\n{'='*60}")
        print(f"  模型: {summary['model']}")
        print(f"  题目总数: {summary['total_questions']}")
        print(f"  总得分: {summary['overall_score']:.1%}")
        print(f"  评测时间: {summary['timestamp']}")
        print(f"{'='*60}\n  按分类得分:")
        for cat, score in summary["by_category"].items():
            bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
            print(f"    {cat:10s}  {score:.1%}  {bar}")
        print()

        low = [d for d in summary["details"] if d["score"] < 0.5]
        if low:
            print(f"  ⚠️ 低分题目（<50%）: {len(low)} 题")
            for d in low:
                print(f"    {d['question_id']} {d['title']}: {d['score']:.0%} "
                      f"({d['passed_checks']}/{d['total_checks']})")

    def print_question_detail(self, question) -> None:
        """打印单题详情（用于人工评分）。"""
        verif = question.verification
        diff_icon = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(question.difficulty.value, "⚪")

        print(f"\n{'─'*60}")
        print(f"  {diff_icon} [{question.id}] {question.category.value} | {question.title}")
        print(f"  难度: {question.difficulty.value}")
        print(f"  描述: {question.description}")
        if question.context:
            print(f"  上下文: {question.context}")
        if question.known_llm_errors:
            print(f"  已知 LLM 错误: {', '.join(question.known_llm_errors)}")

        n = 1
        print(f"\n  验证标准:")
        for a in verif.assertions:
            print(f"    {n}. [assert] {a}")
            n += 1
        for f in verif.forbidden:
            print(f"    {n}. [禁止] {f}")
            n += 1
        for k in verif.expected_keys:
            print(f"    {n}. [期望输出] 包含 '{k}'")
            n += 1
        if verif.expected_range:
            print(f"    {n}. [数值范围] {verif.expected_range}")
            n += 1
        if verif.notes:
            print(f"\n  📝 {verif.notes}")


# ============================================================
# CLI
# ============================================================

def print_list(category: Category | None = None):
    """打印题目列表。"""
    scorer = Scorer()
    qs = scorer.list_questions(category)
    cat_name = category.value if category else "全部"

    # 统计
    cats: dict[str, int] = {}
    diffs: dict[str, int] = {}
    for q in qs:
        cats[q.category.value] = cats.get(q.category.value, 0) + 1
        diffs[q.difficulty.value] = diffs.get(q.difficulty.value, 0) + 1

    print(f"\n{'='*60}")
    print(f"  Polaris 50题气象编码测试基准")
    print(f"  筛选: {cat_name}  |  题目数: {len(qs)}")
    print(f"  难度分布: {diffs}")
    print(f"{'='*60}")

    for q in qs:
        scorer.print_question_detail(q)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Polaris 50题气象编码测试基准")
    parser.add_argument("--list", action="store_true", help="列出全部题目")
    parser.add_argument("--category", "-c", type=str, help="按分类筛选: io | coord | stat | physics | viz")
    parser.add_argument("--report", action="store_true", help="查看历史评分报告")

    args = parser.parse_args()

    if args.list or args.category:
        cat = Category(args.category) if args.category else None
        print_list(cat)

    elif args.report:
        rp = Path(__file__).parent / "results"
        reports = sorted(rp.glob("*.json"), reverse=True)
        if not reports:
            print("暂无评分报告。运行 --run-all 后生成。")
        else:
            print(f"\n  历史评分报告 ({len(reports)} 份):")
            for r in reports[:10]:
                print(f"    {r.name}")

    else:
        # 默认：打印摘要
        print(f"\n  Polaris 50题气象编码测试基准")
        print(f"  共 {len(QUESTIONS)} 题，覆盖 5 大类别\n")
        cats = {}
        for q in QUESTIONS:
            cats.setdefault(q.category.value, []).append(q)
        for cat_name, qs in cats.items():
            diffs = {}
            for q in qs:
                diffs[q.difficulty.value] = diffs.get(q.difficulty.value, 0) + 1
            print(f"  {cat_name:10s}  {len(qs):2d} 题  "
                  f"简单:{diffs.get('easy',0)}  中等:{diffs.get('medium',0)}  困难:{diffs.get('hard',0)}")
        print(f"\n  {'总计':10s}  {len(QUESTIONS):2d} 题")
        print(f"\n  用法: python benchmarks/scorer.py --list  查看全部题目")
