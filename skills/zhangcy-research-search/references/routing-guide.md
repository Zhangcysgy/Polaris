# 路由指南

## 后端对比表

| 后端 | 数据源 | 查询方式 | 最佳场景 | 限流 | 认证 |
|------|--------|----------|----------|------|------|
| **OpenAlex** | 250M+ 论文 | REST API (keyword/title/author) | 跨学科宽搜索 | 10 req/s | 推荐 key |
| **Semantic Scholar** | 200M+ 论文 | REST API (keyword/DOI/author) | 引用图 + 推荐 | 100 req/s (有key) | 推荐 key |
| **CrossRef** | 150M+ DOI | REST API (DOI/keyword) | DOI 精确查找 | 50 req/s (polite) | email |
| **PubMed** | 37M+ 生物医学 | E-utilities API | 生物医学/临床 | 10 req/s (有key) | 推荐 key |
| **arXiv** | 2M+ 预印本 | API + Atom XML | 物理/CS/数学/大气 | 1 req/3s | 无 |
| **bioRxiv/medRxiv** | 生物/医学预印本 | API (日期/DOI) | 生物学/医学预印本 | 无明确限制 | 无 |
| **CORE** | 37M+ OA 全文 | REST API | 开放获取全文 | 有 key | 需要 key |
| **Unpaywall** | OA 状态 | REST API (DOI) | 查某篇论文是否 OA | 无明确限制 | email |
| **BGPT** | 结构化全文本 | MCP / REST API | 方法/样本量/质量评分 | 50次免费 | 可选 key |
| **Exa** | 语义索引 | Python SDK / API | 语义搜索/学术过滤 | 取决于套餐 | API key |
| **parallel-cli** | 通用 web | CLI | 兜底通用搜索 | 取决于后端 | API key |
| **Perplexity** | 学术 web | API (sonar-pro) | 学术深度搜索 | API key | API key |

## 数据源 → 路由映射

| 用户需求 | 主后端 | 备选 | 兜底 |
|----------|--------|------|------|
| 论文精确查找 (DOI) | Crossref | Semantic Scholar | OpenAlex |
| 主题宽搜 | OpenAlex | Semantic Scholar | parallel-cli |
| 大气科学 | OpenAlex + arXiv.ao-ph | Semantic Scholar | Perplexity |
| 生物医学 | PubMed | Semantic Scholar | OpenAlex |
| 预印本 (最新) | arXiv / bioRxiv / medRxiv | Semantic Scholar | — |
| 引用图/影响力 | Semantic Scholar | OpenAlex | — |
| 方法/样本量/质量 | BGPT | — | REST API |
| 语义/类似推荐 | Exa | Semantic Scholar | — |
| 中文文献 | CNKI/万方 (人工) | — | — |
| 开放获取全文 | Unpaywall | CORE | PMC |
| 全格式引用导出 | CrossRef → BibTeX | PubMed → RIS | 手动 |

## 并行查询策略

当需要全面搜索时，并行查询多个后端：

| 场景 | 并行组合 |
|------|----------|
| 大气科学综合搜索 | OpenAlex + arXiv.ao-ph + Semantic Scholar |
| 已发表+预印本 | OpenAlex + arXiv |
| 论文+引用+OA | Semantic Scholar + Unpaywall |
| 结构化数据+普通搜索 | BGPT + OpenAlex |
