---
name: zhangcy-literature-review
description: "Multi-angle literature search, deep analysis, and review report generation. Two search modes: (1) DEPTH mode — exhaustive, no omissions, all years, snowball citation tracing, author tracking; (2) BREADTH mode — broad coverage, cross-disciplinary, semantic search, analogy fields. Calls zhangcy-research-search internally for paper retrieval, then organizes, analyzes, and generates structured literature review reports. Use when the user needs: 文献调研/文献综述/literature review/survey/systematic review/research synthesis/研究现状/综述报告/研究进展. Triggers on: 文献调研/写综述/文献综述/literature review/survey paper/研究现状/进展综述/系统综述/synthesize papers/深度搜索/广度搜索/不要遗漏/全面覆盖."
---

# zhangcy-literature-review — 文献调研与综述生成

## 概述

编排型 skill。不直接搜索论文，而是调用 `zhangcy-research-search` 从**多个角度**检索文献，再将结果整理、分析、生成结构化综述报告。

**依赖**：`zhangcy-research-search`（必须存在，负责实际论文搜索）

## 两种搜索模式

开始之前，先确定搜索模式——这决定了 Phase 1 的搜索策略：

### 🔽 模式 A：深度搜索（Depth Mode）

> **目标**：把一个点挖穿，不论年份、犄角旮旯的论文都要找出来，不能遗漏。

**适用场景**："帮我彻底搜一下 XXX 的所有文献"、"这个方向的所有论文都要找出来"

**策略特征**：
- 不限年份，最早的可追溯到 1950s
- 用多种同义词和关键词变体反复搜
- 回溯引用（snowballing）：已找到论文的参考文献→再搜
- 追踪关键作者：找到该领域核心作者→搜他们的全部论文
- 用 BGPT 后端爬结构化数据
- 搜到没有新论文出现为止（饱和原则）

**示例**：
```
深度搜索: "沙尘暴中雷电起电机制"
→ 搜 "dust storm electrification"（不限年份）
→ 搜 "triboelectric charging sand dust"（不限年份）
→ 搜 "dust devil charge electric field"（不限年份）
→ 回溯每篇论文的参考文献
→ 搜 Gangane, Pawar, Williams 等核心作者
→ 直到连续 2 轮无新论文出现 → 停止
```

### 🔀 模式 B：广度搜索（Breadth Mode）

> **目标**：把所有相关的、哪怕只能沾一点边的都要找出来，画一幅全景图。

**适用场景**："这个主题跨了哪些领域"、"探索一下相关方向"

**策略特征**：
- 使用宽泛关键词，而非精确术语
- 跨学科搜索：不只大气科学，还要搜物理/工程/行星科学等
- 用语义搜索（Exa 后端），找"概念相似"而非"关键词匹配"
- 搜"related topics"：OpenAlex 的关联主题推荐
- 粗筛：先看标题和摘要，宽进严出
- 大量结果（50-100+篇），后期再分类过滤

**示例**：
```
广度搜索: "沙尘暴中雷电现象"
→ 搜 "dust electrification"（宽泛关键词）
→ 搜 "particle charging atmosphere"（颗粒物起电）
→ 搜 "dust storm"（仅沙尘暴本身，看有什么子方向）
→ 搜 "triboelectric effect natural phenomena"（跨物理领域）
→ 搜 "Mars dust discharge"（跨行星科学）
→ 搜 "volcanic lightning"（类比：火山灰起电）
→ Exa 语义搜索 "sandstorm electrical effects"
→ OpenAlex 关联主题推荐
```

---

## 执行流程（4 阶段）

### Phase 1：搜索阶段（根据模式选择策略）

#### 深度模式（5 步搜索循环）

```
Step 1: 核心关键词精确搜
    → zhangcy-research-search "X"（title_and_abstract，不限年份）
    
Step 2: 同义词/变体搜
    → zhangcy-research-search "X synonym A", "X synonym B"
    
Step 3: 引用回溯
    → 对 Step 1-2 找到的关键论文，提取参考文献列表
    → 分别搜这些参考文献的 DOI/标题
    
Step 4: 作者追踪
    → 提取 Step 1-3 中出现频率最高的 5 位作者
    → zhangcy-research-search "author:Y"（按作者搜）
    
Step 5: 饱和检查
    → 如果 Step 4 没找到新论文 → 进入 Phase 2
    → 如果还有新论文 → 回到 Step 3（至多 2 轮循环）
```

#### 广度模式（5 路并行搜索）

```
Route 1: 核心领域
    → zhangcy-research-search "X"（宽泛关键词，大召回）
    
Route 2: 跨学科拓展
    → zhangcy-research-search "X in {other field}"
    → 如: "dust electrification in physics" "sand charging in engineering"
    
Route 3: 类比领域
    → zhangcy-research-search "analogous phenomena to X"
    → 如: "volcanic lightning" "Mars dust discharge" "wind-blown snow electrification"
    
Route 4: 语义搜索
    → zhangcy-research-search → 强制 Exa 后端
    → 语义相似度搜索，不依赖关键词精确匹配
    
Route 5: 关联主题
    → OpenAlex API 查询 X 的 primary_topic 和 related_topics
    → 对每个关联主题搜 Top 5 论文
```

#### 两种模式共用的基础搜索

无论哪种模式，**始终执行**以下 3 个基础搜索：

| # | 搜索 | 原因 |
|---|------|------|
| 1 | arXiv physics.ao-ph | 最新预印本，有时比期刊早 1-2 年 |
| 2 | 气象期刊白名单 | 确保核心期刊覆盖（JCLI/JAS/GRL/Atmospheric Research） |
| 3 | 高引论文（不限年份） | 确保不错过奠基性工作 |

**调用方式**：
```markdown
→ "帮我搜论文：{搜索词}"（触发 zhangcy-research-search）
→ 保存每次搜索结果
```

**搜索策略参考**：见 `references/search-strategies.md`
**API 调用示例**：见 `references/api-examples.md`（当 zhangcy-research-search 不可用时直接调 API）
**综述模板脚本**：`scripts/generate_review_template.py --topic "主题" --mode depth --papers 18`

### Phase 2：结果整理

1. **去重** — 合并多角度搜索的结果，按 DOI/标题去重
2. **分类** — 按主题/子方向归类（如"起电机制"、"观测证据"、"数值模拟"、"火星类比"）
3. **信息提取** — 每篇论文提取：

### 🔴 Phase 2.5：原文验证（Ground-truth Verification）← 新增

**核心原则**：AI 不得凭训练记忆解读论文内容。在对论文做任何分析之前，必须先获取原文或摘要。

**验证流程**：

```
对每篇论文：
    │
    ├── arXiv 论文？
    │   └── → 从 arXiv API 获取全文（summary 字段含完整摘要）
    │       https://export.arxiv.org/api/query?search_query=all:{arxiv_id}
    │
    ├── 有 DOI 且 OA 论文？
    │   └── → 用 Unpaywall API 获取 OA PDF 链接
    │       https://api.unpaywall.org/v2/{doi}?email=xxx
    │       → web_fetch PDF 链接提取文本
    │
    ├── 有 DOI 且非 OA？
    │   └── → 用 OpenAlex 获取摘要
    │       https://api.openalex.org/works/doi:{doi}?select=abstract_inverted_index
    │
    └── 以上都失败？
        └── → 标记为"未读取原文"，禁止在综述中引用具体结论
```

**验证记录表**——在 Phase 3 开始之前，必须生成以下记录：

```markdown
| 论文 | DOI | 验证方式 | 获取内容 | 可信度 |
|------|-----|---------|---------|:------:|
| Gangane 2022 | 10.1007/... | OpenAlex 摘要 | ✅ 摘要已获取 | ★★★ |
| Méndez Harper 2020 | 10.1016/... | arXiv 全文 | ✅ 全文已获取 | ★★★★★ |
| Melnik 1998 | 10.1029/... | 仅元数据 | ❌ 摘要不可用 | ★ (仅引用，不解读) |
```

**可信度规则**：

| 可信度 | 含义 | 在综述中的使用限制 |
|:------:|------|-----------------|
| ★★★★★ | 全文已读取 | 可引用具体方法、结果、结论 |
| ★★★ | 摘要已读取 | 仅可引用主要发现，不可引用具体数值 |
| ★ | 仅元数据 | **仅作为文献条目列出，不得对其内容做任何解读** |

**🔴 STOP**：如果某篇论文的可信度低于 ★★★，你不得在综述正文中对其方法、结果、结论做任何具体描述。你只能在参考文献列表中列出它。

**特别风险**：对于 DOI 格式为 `10.xxxx/xxxxxxxx` 的论文，如果 OpenAlex 和 Unpaywall 都返回空，**绝对不要** 根据你的训练数据脑补这篇论文的内容——标记为"无法验证"，在综述中仅列出标题和作者，不写任何结论。如果 OpenAlex 返回了 `abstract_inverted_index`，你可以解码后获得结构化的摘要文本，基于此写总结。

```markdown
| 论文 | 年份 | 期刊 | 方法 | 核心发现 | 创新点 | 局限 |
|------|------|------|------|----------|--------|------|
| Gangane 2022 | 2022 | Natural Hazards | 卫星闪电+气溶胶数据分析 | 沙尘粒子增加正地闪比例 | 首次定量沙尘对闪电极性影响 | 仅印度区域 |
```

### Phase 3：深度分析

基于整理后的文献矩阵，进行以下分析：

| 分析维度 | 产出 | 说明 |
|----------|------|------|
| **研究脉络** | 时间线图 | 该领域研究如何从早期观测发展到数值模拟 |
| **方法学对比** | 方法对比表 | 不同研究采用的方法（观测/实验/模拟/理论）及其优劣 |
| **争议焦点** | 争议列表 | 学界尚未达成一致的结论（如沙尘是否促进闪电） |
| **研究空白** | 空白清单 | 尚未被充分研究的方向（如中国沙尘暴的雷电特征） |
| **交叉启示** | 跨领域联系 | 源自其他领域的方法/发现对本文的启示（如火星尘埃放电） |

### Phase 4：综述生成

输出结构化综述报告：

```
# {主题} 文献综述

## 摘要
200-300 字概述

## 1. 引言
研究背景、意义、本综述的范围

## 2. 检索策略
搜索的关键词、数据库、时间范围、结果数量

## 3. 研究现状
### 3.1 {主题一：起电机制}
### 3.2 {主题二：观测证据}
### 3.3 {主题三：数值模拟}
...

## 4. 方法学对比
不同研究方法的优缺点对比表

## 5. 研究空白与未来方向

## 6. 结论

## 参考文献
（每篇含 DOI，可推送 Zotero）
```

## 与前端 skill 衔接

```
zhangcy-research-search ──→ zhangcy-literature-review ──→ 综述报告
                                  │
                                  ├──→ zhangcy-slide-content-builder（组会汇报PPT）
                                  ├──→ academic-paper（写成正式论文）
                                  └──→ zhangcy-nature-review（检查质量）
```

## 大气科学关键词库

| 中文主题 | 英文搜索词 | 建议后端 |
|----------|-----------|----------|
| 沙尘暴起电 | "dust storm electrification" "triboelectric charging sand" | OpenAlex + arXiv.ao-ph |
| 沙尘暴雷电观测 | "dust storm lightning observation" "dust lightning flash rate" | OpenAlex + Semantic Scholar |
| 沙尘暴数值模拟 | "dust storm WRF lightning" "dust model electrification" | OpenAlex |
| 沙尘暴气溶胶-云 | "dust aerosol cloud electrification" "Saharan dust lightning" | OpenAlex |
| 火星尘埃放电 | "Mars dust devil discharge" "triboelectric Mars" | arXiv.ao-ph + OpenAlex |
| 沙尘暴电荷结构 | "charge structure dust storm" "electric field dust" | OpenAlex + BGPT |

## 快速开始

```
用户: "深度搜索 沙尘暴中雷电起电机制"
→ 深度模式：snowballing 回溯 + 作者追踪，饱和为止
→ 整理分析 → 综述报告

用户: "广度搜索 沙尘暴与雷电"
→ 广度模式：5 路并行（核心+跨学科+类比+语义+关联主题）
→ 整理分析 → 综述报告
```

## 检查点

| # | 位置 | 类型 | 动作 |
|---|------|------|------|
| 🔴 1 | 搜索开始前 | STOP | "请选择模式：深度搜索（挖穿不漏） / 广度搜索（沾边都要）" |
| 🔴 2 | Phase 1 完成后（深度模式） | STOP | "已从 {N} 篇→回溯 {M} 篇→作者追踪 {K} 篇，去重后共 {T} 篇。确认进入整理？" |
| 🔴 3 | Phase 1 完成后（广度模式） | STOP | "已从 {5} 条路线搜到 {T} 篇，跨 {N} 个领域。确认进入整理？" |
| 🔴 4 | Phase 2.5 验证完成后 | STOP | "已从 {T} 篇论文中获取 {N} 篇原文/摘要，{M} 篇仅元数据（不可解读）。确认进入深度分析？" |
| 🔴 5 | Phase 3 完成后 | STOP | "分析完成，发现 {N} 个研究空白，确认生成综述报告？" |
| 🔴 6 | 生成报告后 | STOP | "是否将参考文献推送到 Zotero？" |

## 失败模式

| 症状 | 一线修复 | 仍失败 → 二线兜底 |
|------|---------|-----------------|
| 某方向搜索返回 0 篇 | 换同义词/中英文交替重搜 | 跳过该方向，记录"无文献"，在报告中说明搜索局限性 |
| 去重后论文 < 3 篇 | 扩大搜索范围至全字段(full-text search) | 提示用户主题可能过窄，建议放宽范围或用广度模式 |
| 去重后论文 > 200 篇 | 按被引量/年份/期刊筛选 Top 50 | 分主题子集处理，每个子集单独分析 |
| 引用回溯找不到全文 | 搜 DOI + 标题组合 | 跳过该引用，记录"无法获取" |
| 🔴 **原文验证失败（OA/arXiv/摘要都不可用）** | 用 web_search 搜索论文标题获取简介 | **标记为★，在综述中不引用其具体结论，仅列条目** |
| 作者追踪返回 0 篇 | 换作者姓名变体（全名/缩写/ORCID） | 跳过该作者追踪步骤 |
| 深度模式饱和检查循环 > 3 轮 | 强制进入 Phase 2 | 记录"仍有新论文但已达最大循环轮数" |
| 广度模式跨学科搜到无关论文 | 收紧关键词（加领域限定词） | 后期手动过滤，不影响 |
| Zotero 推送失败 | 重试 1 次 | 输出参考文献列表（含 DOI），用户手动导入 |
| zhangcy-research-search 不可用 | 直接用 REST API（OpenAlex/arXiv） | 使用 web_search 兜底 |
| 输出报告文件写入失败 | 重试 1 次 | 直接在对话中输出 Markdown |

## 反例

| # | 反模式 | 说明 |
|---|--------|------|
| 1 | ❌ 只搜一个角度 | 必须 ≥ 3 个搜索角度，否则综述偏颇 |
| 2 | ❌ 遗漏经典文献 | 必须专门搜一次高被引论文（不限年份） |
| 3 | ❌ 不标注研究空白 | 每篇综述必须有"研究空白与未来方向"章节 |
| 4 | ❌ 虚构引用 | 所有引用必须有真实 DOI |
| 5 | ❌ 忽略中国研究 | 大气科学领域中国研究很多，补充中文搜索 |
| 6 | ❌ 综述没有方法学对比 | 必须对比不同研究的方法差异 |
| 7 | ❌ **凭记忆编造论文内容** | 对任何论文的内容解读（方法/结果/结论）都必须基于 Phase 2.5 获取的原文或摘要。如果验证失败（★），**宁可不写**也不能编造 |
| 8 | ❌ **跳过原文验证直接分析** | 不得跳过 Phase 2.5。没有验证记录表，就不能进入 Phase 3 |
