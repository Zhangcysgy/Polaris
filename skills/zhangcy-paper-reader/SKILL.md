---
name: zhangcy-paper-reader
description: "Read a paper by DOI/arXiv ID/PMID/title, fetch original text/abstract from 6 sources (OpenAlex + DOI publisher page + Semantic Scholar + OpenAIRE + Unpaywall + arXiv), return structured analysis with trust-level scoring (★~★★★★★). Multi-source cross-validation prevents hallucination. For use in literature review pipelines (Phase 2.5 paper verification) and peer review citation checking. Triggers on: read paper, analyze paper, paper content, DOI lookup, what does this paper say, extract paper info, summarize paper, paper summary, check reference, verify citation, 读论文/论文分析/查看文献/论文摘要/文献验证/检查参考文献."
run_as: subagent
---

# zhangcy-paper-reader — 论文阅读分析器

## 概述

给定一篇论文的标识符（DOI / arXiv ID / 标题），自动获取原文或摘要，提取结构化信息并返回分析报告。

**适用于**：
- 文献调研中验证论文内容（补充 zhangcy-literature-review 的 Phase 2.5）
- 审稿时检查被引文献是否支持 claim（辅助 zhangcy-nature-review-strict）
- 快速了解一篇论文的核心贡献

## 输入

接受以下任一格式：

```
DOI: 10.1175/JCLI-D-23-0123.1
arXiv: 2006.01978
标题: "Humidity-gated triboelectric charging in dust storms"
```

## 获取流程（4 步，严格顺序）

**Step 1**: 解析输入 —— 判断输入类型（DOI / arXiv ID / PMID / 标题）

**Step 2**: 按类型分支获取

```
输入解析完成
    │
    ├── 【分支 A】arXiv ID（优先级最高——可获取全文）
    │   └── → 调 arXiv API
    │       GET https://export.arxiv.org/api/query?id_list={id}
    │       → 返回 entry/title + entry/summary（完整摘要）+ entry/author + category
    │
    ├── 【分支 B】DOI（最常用——多源交叉验证）
    │   │
    │   ├── B1. OpenAlex（结构化元数据）
    │   │   GET https://api.openalex.org/works/doi:{doi}?select=abstract_inverted_index,...
    │   │   → title, authors, journal, year, cited_by_count, abstract, keywords, concepts
    │   │
    │   ├── B2. DOI 网页（出版商原始页面，可能比 API 更详细）
    │   │   web_fetch https://doi.org/{doi}
    │   │   → 页面自动跳转至 publisher (nature/Wiley/Elsevier/AMS...)
    │   │   → 提取 HTML 中的摘要、关键词、资助信息
    │   │   → 与 B1 的摘要对比验证，取更完整者
    │   │
    │   ├── B3. Semantic Scholar（引用图和 TLDR）
    │   │   GET https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,abstract,tldr,...
    │   │   → tldr（AI 一句话总结）+ citationCount
    │   │
    │   ├── B4. OpenAIRE（欧洲 OA 论文——可作为 Unpaywall 补充）
│   │   GET https://api.openaire.eu/search/publications?doi={doi}&format=json
│   │   → 获取欧洲研究委员会的 OA 状态、项目资助信息
│   │   → 当 Unpaywall 返回 closed 时，尝试此源
│   │
│   └── B5. Unpaywall（OA 状态检测）
    │       GET https://api.unpaywall.org/v2/{doi}?email=research@example.com
    │       → is_oa, oa_status, best_oa_location.url_for_pdf
    │       → 若 is_oa == true → web_fetch PDF 链接提取全文
    │
    ├── 【分支 C】PMID（PubMed 生物医学专用）
    │   └── → 调 PubMed E-utilities
    │       GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml
    │       → 结构化摘要、MeSH 词、作者、期刊
    │
    └── 【分支 D】仅标题（模糊匹配）
        └── → 调 OpenAlex 搜索
            GET https://api.openalex.org/works?search={title}&per_page=5&sort=relevance_score:desc
            → 取第一篇作为候选，标注"标题匹配（可能不精确）"
```

**Step 3**: 合并结果 —— 将所有来源的输出合并为统一结构：

```python
result = {
    "title": str,         # 标题（优先取 OpenAlex）
    "authors": list,      # 作者列表
    "journal": str,       # 期刊名
    "year": int,          # 出版年份
    "doi": str,           # DOI
    "cited_by": int,      # 被引数
    "oa_status": bool,    # 开放获取状态
    "abstract": str,      # 正文摘要（取多源中最完整者）
    "tldr": str,          # 一句话总结（Semantic Scholar）
    "keywords": list,     # 关键词
    "concepts": list,     # OpenAlex 概念
    "source_list": list,  # 实际获取到的来源列表
}
```

**Step 4**: 输出报告 —— 按输出格式模板渲染 Markdown 报告：
- 标注每篇论文的 **可信度**（根据实际获取到的来源计算）
- 如果所有来源均未返回摘要 → 返回"无法获取"并终止

## 输出格式

```markdown
## 论文分析报告

### 基本信息
- **标题**: 
- **作者**: 
- **期刊**: 
- **年份**: 
- **DOI**: 
- **引用数**: 
- **OA 状态**: 开放获取 / 付费

### 摘要（原文）
> （直接从 OpenAlex/arXiv 获取的原始摘要，逐字引用）

### 方法学
（从摘要/全文提取）

### 关键发现
（从摘要/全文提取）

### 局限性与未来工作
（从摘要/全文提取，如原文未提及则标注"原文未明确提及"）

### 可信度声明
- 信息来源: 列出获取到的所有来源（OpenAlex 摘要 / DOI 网页 / Semantic Scholar TLDR / arXiv 全文 / Unpaywall PDF / PubMed XML）
- 内容真实性: 以上所有信息均直接从学术数据库或出版商页面获取，未经过 AI 改写
- DOI 网页内容: 出版商页面（HTML）可能包含比 OpenAlex 摘要更详细的信息（方法描述、关键词、资助信息），但也可能因 paywall 限制仅显示摘要
- 局限性: 如果仅获取了摘要，部分细节（具体数值、统计方法）可能不完整

### 关键词
- ...

### 相关主题（OpenAlex Concepts）
- ...
```

## 可信度声明规则

| 信息来源 | 可信度 | 输出标注 |
|---------|:------:|---------|
| arXiv 全文 / Unpaywall OA PDF | ★★★★★ | "信息来源: arXiv 全文 / OA PDF" |
| DOI 网页（出版商 HTML）| ★★★★ | "信息来源: DOI 网页（含摘要+关键词+资助信息）" |
| OpenAlex 摘要 | ★★★ | "信息来源: OpenAlex 摘要" |
| Semantic Scholar TLDR | ★★ | "信息来源: Semantic Scholar TLDR（AI 生成摘要，仅供参考）" |
| PubMed XML | ★★★★ | "信息来源: PubMed（结构化摘要+MeSH词）" |
| 仅标题匹配（无摘要） | ★ | "信息来源: 仅元数据，未获取到内容" |

**可信度计算规则**：如果成功获取了多个来源，取最高可信度作为该论文的最终可信度。在报告中列出**所有实际获取到的来源**。

## 批处理模式（多篇论文批量分析）

当需要同时分析多篇论文时（如文献调研的 10+ 篇），使用以下方式：

```
输入: 多篇论文的 DOI/arXiv 列表（每行一个）
输出: 每篇论文的结构化报告（按顺序输出）
```

对每篇论文执行相同的获取→分析流程，结果依次输出。每篇之间用 `---` 分隔。

## 辅助脚本

`scripts/fetch_paper.py` 提供确定性的 API 调用：

```bash
# 安装依赖
pip install requests

# 按 DOI 获取
python scripts/fetch_paper.py --doi 10.1016/j.atmosres.2021.105933

# 按 arXiv ID 获取
python scripts/fetch_paper.py --arxiv 2006.01978

# 按标题搜索
python scripts/fetch_paper.py --title "Humidity-gated triboelectric charging"
```

**何时使用脚本**：
- 当 API 返回格式复杂（如 abstract_inverted_index 需要解码）时
- 当需要批量获取多篇论文时
- 当需要确保输出结果可重现时

## 失败模式

| 症状 | 一线修复 | 仍失败 → 二线兜底 |
|------|---------|-----------------|
| OpenAlex 返回 429 | 等待 3 秒重试 | 跳过 OpenAlex，直接尝试 Unpaywall |
| arXiv API 超时 | 重试 1 次（最多 1 次/3 秒） | 跳过 arXiv，标记"仅元数据" |
| Unpaywall 返回 `is_oa: false` | 切换 OpenAlex 获取摘要 | 标记为★（仅元数据） |
| DOI 不存在（404） | 用标题在 OpenAlex 搜索 | 返回"未找到该论文" |
| OpenAlex 搜索标题返回 0 篇 | 换同义词/缩写 | 返回"无法定位该论文" |
| 多个匹配（标题搜索返回 >1 篇） | 取 publication_year 最近的 | 在报告中列出所有候选 |
| PDF 链接可用但下载失败 | 尝试将 PDF 链接通过 web_fetch 提取文本 | 降级到 OpenAlex 摘要 |
| DOI 网页访问失败（404/timeout） | 跳过 DOI 网页，直接使用 OpenAlex 摘要 | OpenAlex 摘要作为兜底 |
| DOI 网页显示 paywall（需订阅） | 提取页面可见部分（通常含摘要+关键词） | 配合 OpenAlex 摘要补充 |
| Semantic Scholar 无此论文 | 跳过 Semantic Scholar | 不影响其他来源 |
| OpenAIRE 返回空结果 | 跳过 OpenAIRE（仅欧洲 OA 论文有收录） | 不影响其他来源 |
| abstract_inverted_index 解码失败 | 直接返回原始 JSON 中的 title 等非摘要字段，摘要标注"解码失败" | 降级到 DOI 网页或 Semantic Scholar 获取摘要 |
| DOI 网页跳转到登录页面（非 paywall 而是 SSO） | 识别页面是否为登录页（含"sign in"、"login"等关键词） | 跳过，使用 OpenAlex 摘要 |
| 论文为非英文（中文/日文等） | 标注原始语言，用 OpenAlex 的英文元数据替代 | 用机器翻译（如有可用工具） |
| Semantic Scholar 返回 outdated TLDR | 与 OpenAlex 摘要对比时间戳，取新者 | 以 OpenAlex 摘要为准 |

## 重要限制

1. 本 skill **不编造**论文内容。如果无法获取原文或摘要，返回"无法获取"并终止。
2. 对于获取到的摘要，**逐字引用**原始文本（不 paraphrasing）。
3. 对于无法获取全文的论文，不尝试根据训练数据补充细节。
4. 本 skill 是只读的——不修改任何文件，仅返回分析报告。

## 反例

| # | 反模式 | 说明 |
|---|--------|------|
| 1 | ❌ **编造摘要内容** | 如果 API 未返回摘要，不得用 LLM 训练数据"补充"。宁可不写，不可编造 |
| 2 | ❌ **混淆 arXiv 预印本和已发表版本** | arXiv 论文可能后续在期刊发表。在报告中标注"arXiv 预印本" |
| 3 | ❌ **过度解读摘要** | 摘要中的"may suggest"不能写成"proves"。保留原文的限定词 |
| 4 | ❌ **忽略多作者贡献** | 列出所有作者，不要省略为"et al."——用户需要知道具体作者 |
| 5 | ❌ **跨论文串联结论** | 不把这篇论文的结论和另一篇关联。每篇论文独立分析 |
| 6 | ❌ **忽略 OA 状态标注** | 必须标注论文是 OA 还是付费（决定用户能否自行获取全文） |
| 7 | ❌ **多源冲突时择一丢弃** | 当 OpenAlex 摘要和 DOI 网页摘要内容不一致时，保留两者并标注差异，而非择一丢弃 |

## 使用示例

### 作为 subagent 调用（推荐）

```
从 zhangcy-literature-review 或 zhangcy-nature-review-strict 中调用：
→ "分析论文 DOI: 10.1175/JCLI-D-23-0123.1"
→ 返回结构化报告 → 上游 skill 基于此报告做进一步分析
```

### 直接使用

```
读一下这篇论文: 10.1016/j.atmosres.2021.105933
→ 返回分析报告
```
