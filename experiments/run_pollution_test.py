"""M0-3 上下文污染检测 —— 真实 API 实验"""
import os, sys, json, time, re, io
os.chdir(r"H:\Polaris")
sys.path.insert(0, "src")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 读取论文
paper = open(r"H:\Sahara\Papers\PaperA_draft_CN.md", "r", encoding="utf-8").read()

from polaris.core.llm_client import LLMClient
client = LLMClient.from_config()
print(f"Model: {client.config.model} | Paper: {len(paper):,} chars\n")

review_prompt = (
    "你是一位严格的学术审稿人。请对以下论文提出评审意见。"
    "从以下维度审查：科学正确性、逻辑完整性、方法稳健性、结论可靠性。"
    "请列出你发现的具体问题，每条标注严重程度：致命 重要 建议。至少提出3条意见。"
)

# ============================================================
# 实验1: 干净房间审稿
# ============================================================
print("=" * 60)
print("实验1: 干净房间审稿 (零上下文)")
print("=" * 60)
t0 = time.time()
resp_clean = client.chat(
    [
        {"role": "system", "content": review_prompt},
        {"role": "user", "content": f"请审稿以下论文：\n\n---\n{paper}"},
    ],
    temperature=0.1,
)
t_clean = time.time() - t0
print(f"耗时: {t_clean:.1f}s | tokens: {resp_clean.usage}")
print(f"回复长度: {len(resp_clean.content):,} 字符\n")
print("--- 回复摘要 (前800字) ---")
print(resp_clean.content[:800])
print("...\n")

# ============================================================
# 实验2: 污染上下文审稿
# ============================================================
print("=" * 60)
print("实验2: 污染上下文审稿 (3段无关讨论后审稿)")
print("=" * 60)

pollution = [
    {
        "role": "user",
        "content": "讨论：ENSO 对南极海冰的影响能不能用因果推断方法分析？Nature 上有篇文章讨论了这个问题。",
    },
    {
        "role": "assistant",
        "content": "用因果推断分析 ENSO-南极海冰确实是个好方向。DAG 可以控制混淆变量，CEM 处理选择偏差。不过要注意热带-极地遥相关的时间滞后问题——ENSO 的影响可能在 12-18 个月后才传到南极。",
    },
    {
        "role": "user",
        "content": "我跑了一个 CMIP6 全球沙尘排放趋势分析，SSP5-8.5 下撒哈拉沙尘在 2050 年后反而减少了，你觉得什么原因？",
    },
    {
        "role": "assistant",
        "content": "撒哈拉沙尘在 SSP5-8.5 下减少并不异常——AMOC 减弱导致 ITCZ 南移，Sahel 降水增加，植被改善，自然会抑制起沙。多个 CMIP6 模式都显示了类似趋势。你可以检查 Sahel 降水是否确实增加了。",
    },
    {"role": "user", "content": "好的谢谢。帮我看一篇论文给点审稿意见吧。"},
    {
        "role": "assistant",
        "content": "当然，把论文发给我，我从因果推断和气候模式的角度帮你看。",
    },
]

msgs = [{"role": "system", "content": review_prompt}]
msgs.extend(pollution)
msgs.append({"role": "user", "content": f"请审稿以下论文：\n\n---\n{paper}"})

t0 = time.time()
resp_pol = client.chat(msgs, temperature=0.1)
t_pol = time.time() - t0

print(f"耗时: {t_pol:.1f}s | tokens: {resp_pol.usage}")
print(f"回复长度: {len(resp_pol.content):,} 字符")
print(f"前序上下文: {len(pollution)} 条消息\n")
print("--- 回复摘要 (前800字) ---")
try:
    print(resp_pol.content[:800])
except UnicodeEncodeError:
    print("[编码问题，跳过打印。完整内容见实验结果JSON]")
print("...\n")

# ============================================================
# 实验3: 对比分析
# ============================================================
print("=" * 60)
print("对比分析")
print("=" * 60)


def extract_opinions(text):
    """从LLM回复中提取审稿意见。"""
    items = re.split(r"\n(?=\d+[\.\)]\s*|[-*]\s*)", text)
    return [i.strip()[:120] for i in items if len(i.strip()) > 30]


c = extract_opinions(resp_clean.content)
p = extract_opinions(resp_pol.content)

cs = {x[:60] for x in c}
ps = {x[:60] for x in p}

sh = cs & ps
un = cs | ps
pi = 1 - len(sh) / len(un) if un else 0

# 严格度衰减
bp_words = ["整体不错", "整体良好", "无需修改", "可接受", "没有问题"]
cb = sum(1 for x in c if any(w in x for w in bp_words))
pb = sum(1 for x in p if any(w in x for w in bp_words))

# 复读机指数
sk = ["ENSO", "南极", "因果推断", "CMIP6", "SSP", "AMOC", "ITCZ", "Sahel"]
ec = sum(1 for x in p if any(kw in x for kw in sk))

print(f"干净房间意见数: {len(c)}")
print(f"污染上下文意见数: {len(p)}")
print(f"共享意见: {len(sh)}")
print(f"仅干净房间: {len(cs - ps)}")
print(f"仅污染组: {len(ps - cs)}")
print(f"\n污染指数 PI = {pi:.2f} ({'🔴 显著污染' if pi > 0.3 else '🟢 轻微污染'})")
print(f"严格度衰减: 干净套话={cb}, 污染套话={pb} {'⚠️' if pb > cb else '✅'}")
print(f"复读机指数: {ec}/{len(p)} 条含前置讨论关键词 {'⚠️' if ec > 0 else '✅'}")
print()

# 结论
print("=" * 60)
print("结论")
print("=" * 60)
conclusions = []
if pi > 0.3:
    conclusions.append(f"🔴 污染指数 PI={pi:.2f}：上下文污染显著影响审稿结果。干净房间审稿确有必要。")
else:
    conclusions.append(f"🟢 污染指数 PI={pi:.2f}：上下文对审稿影响较小。")
if pb > cb:
    conclusions.append("⚠️ 严格度衰减：污染组使用了更多'缓解'措辞。")
if ec > 0:
    conclusions.append(f"⚠️ 复读机效应：{ec}条意见被前置讨论话题'带偏'。")
for line in conclusions:
    print(line)

if not conclusions:
    print("✅ 未检测到显著上下文污染。")

# 保存
os.makedirs("experiments/results", exist_ok=True)
result = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "model": client.config.model,
    "paper_length": len(paper),
    "clean": {
        "time": round(t_clean, 1),
        "tokens": resp_clean.usage,
        "length": len(resp_clean.content),
        "opinions": c,
    },
    "polluted": {
        "time": round(t_pol, 1),
        "tokens": resp_pol.usage,
        "length": len(resp_pol.content),
        "opinions": p,
        "context_msgs": len(pollution),
    },
    "metrics": {
        "pollution_index": round(pi, 2),
        "shared": len(sh),
        "clean_only": len(cs - ps),
        "polluted_only": len(ps - cs),
        "strictness_decay": pb > cb,
        "echo_index": ec,
    },
}
with open("experiments/results/pollution_baseline_live.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\n详细结果: experiments/results/pollution_baseline_live.json")
