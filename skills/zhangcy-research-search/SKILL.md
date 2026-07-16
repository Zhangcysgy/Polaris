---
name: zhangcy-research-search
description: "Unified scientific paper search engine with intelligent backend routing. Searches 10+ academic databases (PubMed, arXiv, OpenAlex, Crossref, Semantic Scholar, bioRxiv, medRxiv, CORE, Unpaywall, Exa), structured full-text evidence (BGPT), and web academic search (parallel-cli/Perplexity). Includes atmospheric science specialization: arXiv physics.ao-ph, AMS/AGU journal white-list. Supports one-click push to Zotero (on-demand or auto-push). Use when searching for papers, finding DOI/PMID, literature review, evidence synthesis, atmospheric science research, climate/meteorology literature, or adding papers to Zotero. Triggers on: 搜论文/找文献/search papers/find papers/literature search/论文搜索/文献搜索/帮我找/加入Zotero/推送Zotero/大气科学文献/气象文献/zhangcy-research-search."
---

# research-search — 统一学术论文搜索引擎

## 概述

整合 5 个论文搜索工具的统一入口。根据查询类型自动路由到最佳后端，支持大气科学专属源，搜索结果可一键推送至 Zotero。

**整合来源**：`paper-lookup` + `research-lookup` + `bgpt-paper-search` + `exa-search` + `nature-academic-search`

## 执行流程（5 步）

### Step 1：理解查询
解析用户意图，匹配路由条件。

### Step 2：路由选择
```
用户输入 query
    │
    ├── 需要结构化实验数据（方法/样本量/质量评分/临床试验）?
    │   └── → BGPT 后端（search_papers）
    │
    ├── 需要大气科学文献 / 气象/气候/台风/降水/沙尘暴/ENSO/CMIP6?
    │   └── → REST API 并行搜索 + 气象域白名单
    │       OpenAlex + arXiv physics.ao-ph + Semantic Scholar
    │       --include-domains: journals.ametsoc.org,
    │         agupubs.onlinelibrary.wiley.com, nature.com,
    │         link.springer.com, iop.org, sciencedirect.com
    │
    ├── 需要特定 DOI/PMID/arXiv ID 精确查询?
    │   └── → Crossref / OpenAlex / PubMed（精确查找）
    │
    ├── 需要语义搜索（"像这篇论文一样"、"推荐类似"）?
    │   └── → Exa 后端 + category="research paper"
    │
    ├── 需要中文文献（CNKI/万方）?
    │   └── → 提示人工搜索 + 提供中文数据库指南
    │
    ├── 需要引用格式转换 / MeSH 策略 / 引用管理?
    │   └── → 工作流模式（引用格式、MeSH 策略、文件管理）
    │
    └── 默认兜底（一般学术搜索）
        └── → parallel-cli / Perplexity 后端
```

### Step 3：执行搜索
调对应后端的 API/MCP 工具。如有必要并行查询多个后端。

### Step 4：展示结果
按统一的输出格式返回。询问用户是否需要加入 Zotero。

### Step 5：后续操作
- 用户说"加入 Zotero" → 按需推送
- 用户说"搜更多" → 换后端重搜
- 用户说"导出 BibTeX" → 引用格式转换

## 搜索模式

| 模式 | 触发 | 后端 | 速度 |
|------|------|------|------|
| 精确查找 | "查 DOI:10.xxx"、"找 PMID:xxx" | Crossref / PubMed | ⚡ 快 (1-3s) |
| 主题搜索 | "搜关于XX的论文" | OpenAlex + Semantic Scholar | ⚡ 快 (3-5s) |
| 大气科学 | "搜气象/气候/台风/降水" | OpenAlex + arXiv.ao-ph + 气象白名单 | ⚡ 快 (3-6s) |
| 结构化数据 | "找实验方法/样本量/质量评分" | BGPT | 🐢 中 (5-15s) |
| 语义搜索 | "类似这篇"、"推荐论文" | Exa | ⚡ 快 (2-5s) |
| 综合搜索 | "全方位搜索XX" | 多后端并行 | 🐢 慢 (10-30s) |
| 引用管理 | "导出BibTeX"、"生成RIS" | 工作流 | ⚡ 快 |

## Zotero 集成 — 两种推送模式

### 🔵 模式 A：按需推送（默认）

用户搜索后，AI 返回结果并询问是否需要保存到 Zotero。用户确认后执行。

```
用户: "搜一下 precipitation nowcasting 的论文"
AI  → 搜索 → 返回结果列表
    → "需要把这 3 篇加入 Zotero 吗？"

用户: "把第1和第3篇加进去"
AI  → Zotero MCP: add_items(metadata[0], metadata[2])
    → ✅ "已添加到 Zotero [My Library]"
```

### 🟢 模式 B：全自动推送

搜索时自动将每一篇推送到 Zotero 指定集合，无需用户额外指令。

**触发方式**：用户说 "自动保存到 Zotero" 或在查询中包含 `[auto-zotero]` 标记。

```
用户: "自动搜 precipitation nowcasting 的论文[auto-zotero]"
AI  → 搜索论文
    → 每篇自动调 Zotero MCP 创建条目
    → 返回结果 + "✅ 已自动推送到 Zotero [集合名]"
```

### Zotero 配置

```json
// Reasonix config.json 中已配置
"mcp": [
  "zotero-mcp=streamable+http://127.0.0.1:23120/mcp"
]
```

Zotero MCP 提供的工具：
- `search_items` — 搜索 Zotero 库（检查重复）
- `create_item` — 根据元数据创建条目
- `list_collections` — 列出所有集合
- `create_collection` — 创建新集合
- `add_to_collection` — 将条目添加到集合

**添加入库前的重复检查**：先用 DOI/标题搜索 Zotero，已存在则跳过。

### Fallback：pyzotero

当 Zotero MCP 不可用时，自动降级到 pyzotero：

```bash
uv run --with pyzotero python scripts/save_to_zotero.py \
  --doi "10.1175/JCLI-D-23-0123.1" \
  --collection "precipitation-nowcasting"
```

## 输出格式（示例）

以"沙尘暴中的雷电现象"为例：

```
## 搜索结果

路由后端：[OpenAlex + arXiv physics.ao-ph + Semantic Scholar]
查询时间：2026-06-11

### 论文列表
| # | 标题 | 作者 | 期刊 | 年份 | DOI | 来源 |
|---|------|------|------|------|-----|------|
| 1 | Electrical characteristics of dust devils and dust storms observed by field mills | Zhang Y, Li X, Wang T | JGR-Atmospheres | 2023 | 10.1029/2023JD038912 | OpenAlex |
| 2 | Observations of lightning initiation in dust storms over the Taklimakan Desert | Liu C, Chen Z, Ma Y | Atmospheric Research | 2024 | 10.1016/j.atmosres.2024.107342 | OpenAlex |
| 3 | A review of electrification and lightning in volcanic plumes and dust storms | Williams E, Nathou N, Hicks E | Bulletin of the American Meteorological Society | 2022 | 10.1175/BAMS-D-21-0152.1 | Semantic Scholar |
| 4 | Charge structure and lightning activity in dust storms: a numerical modeling study | Huang T, Sun L, Zhao P | Journal of Geophysical Research | 2024 | 10.1029/2024JD041234 | OpenAlex |
| 5 | Laboratory study of contact electrification in wind-blown sand and dust | Zheng X, Bo T, Zhu W | Physics of Fluids | 2023 | 10.1063/5.0145678 | Semantic Scholar |

### 大气科学匹配
| 期刊 | 论文数 | 源 |
|------|--------|-----|
| JGR-Atmospheres | 2 | AGU |
| Atmospheric Research | 1 | Elsevier |
| BAMS | 1 | AMS |
| Physics of Fluids | 1 | AIP |

### 可执行操作
- 💾 "把第 1、2、4 篇加入 Zotero" → 按需推送
- ⚡ "自动保存所有" → 切换全自动模式
- 📄 "导出第 1 篇的 BibTeX" → 引用格式转换
- 🔄 "搜更多" → 换 BGPT 后端搜结构化数据
```

## 引用管理

| 功能 | 说明 | 参考 |
|------|------|------|
| DOI→BibTeX | 从 Crossref 获取元数据 → BibTeX | `references/rest-apis/crossref.md` |
| PMID→RIS | PubMed → RIS/.nbib 导出 | `references/rest-apis/pubmed.md` |
| 格式转换 | .nbib/.ris/.bib 互转 | `scripts/format-converter.py` |
| MeSH 策略 | 构建 PubMed 检索式 | `references/workflows/mesh-strategy.md` |

## 可供参考的引用文件

| 模块 | 路径 | 何时读取 |
|------|------|----------|
| REST API 参考 | `references/rest-apis/` | 使用 REST 后端时 |
| Exa 语义搜索 | `references/semantic-search/` | 使用 Exa 后端时 |
| BGPT 结构化数据 | `references/structured-data/` | 使用 BGPT 后端时 |
| 气象源指南 | `references/atmospheric-science/` | 大气科学搜索时 |
| Zotero 集成 | `references/zotero/` | 推送至 Zotero 时 |

## 检查点

| # | 位置 | 类型 | 动作 |
|---|------|------|------|
| 🔴 1 | 搜索结果返回后 | STOP | 展示结果，问用户"要加入Zotero吗？"或"要换后端重新搜吗？" |
| 🔴 2 | 推送 Zotero 前（批量>5篇） | STOP | "即将推送 10 篇到 Zotero [集合]，确认？" |
| 🔴 3 | 换后端前 | STOP | "当前后端结果不够好，要换 XX 后端重新搜吗？" |

## 失败模式

| 症状 | 一线修复 | 仍失败 → 二线兜底 |
|------|---------|-----------------|
| REST API 返回 429 | 等待 3 秒重试 | 降级到 parallel-cli 后端 |
| REST API 返回空结果 | 换关键词/换数据库 | 降级到 Exa 语义搜索 |
| BGPT 无结果 | 换 REST API 后端 | 降级到 parallel-cli |
| Exa API Key 缺失 | 检查环境变量 | 降级到 REST API |
| Zotero MCP 不可用 | 重试 1 次 | 降级到 pyzotero 脚本 |
| 全文获取失败 | 尝试 Unpaywall | 尝试 CORE API |

## 反例 & 不要做的事

| # | 反模式 | 说明 |
|---|--------|------|
| 1 | ❌ 虚构引用 | 任何时候都不捏造 DOI/作者/期刊信息——查不到就说查不到 |
| 2 | ❌ 跳过源验证 | 即使是顶级期刊的论文也要验证 DOI 是否存在 |
| 3 | ❌ 不做重复检查就推 Zotero | 推送前必须检查 Zotero 库中是否已有 |
| 4 | ❌ 一次推超过 20 篇 | 批量操作需分页，每批最多 20 篇 |
| 5 | ❌ 忽略作者姓名 | 推送 Zotero 时必须包含作者字段 |
| 6 | ❌ 自动推送时不告知用户 | 自动推送完成后必须显示 ✅ 确认 |
| 7 | ❌ 将 arXiv 预印本标注为"已发表" | 预印本和已发表论文要分开标注 |

## 大气科学源速查

| 源 | 路由 | 说明 |
|----|------|------|
| arXiv physics.ao-ph | REST API | 大气海洋物理预印本，每日更新 |
| AMS 期刊 (JCLI/JAS/MWR/BAMS) | OpenAlex + 域白名单 | 美国气象学会旗舰期刊 |
| AGU 期刊 (GRL/JGRA) | OpenAlex + 域白名单 | 美国地球物理学会 |
| Springer (Climate Dynamics) | OpenAlex + 域白名单 | 气候动力学 |
| Elsevier (Atmospheric Research) | OpenAlex + 域白名单 | 大气研究 |
| 中文气象文献 | 人工搜索指南 | CNKI / 万方 (无公开 API) |

详情见 `references/atmospheric-science/` 下的参考文件。
