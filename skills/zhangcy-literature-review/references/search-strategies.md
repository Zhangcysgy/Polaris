# 文献搜索策略参考

## 通用 5 角度搜索模板

以主题 "X" 为例：

```markdown
角度 1 — 核心关键词：  "X" (最直接的关键词组合)
角度 2 — 细分方向：    "X sub-topic A", "X sub-topic B"
角度 3 — 经典文献：    "X" sort:cited_by_count:desc (不限年份)
角度 4 — 最新进展：    "X" filter:2023-2025 (近 2-3 年)
角度 5 — 领域专属：    arXiv.ao-ph + 气象期刊白名单
```

## 大气科学通用搜索策略

### 气候动力学

| 角度 | 搜索词 |
|------|--------|
| 核心 | "climate dynamics" "ENSO" "teleconnection" |
| 细分 | "Pacific decadal oscillation" "North Atlantic Oscillation" |
| 经典 | "ENSO mechanism" sort:cited_by_count:desc |
| 最新 | "climate change extreme events" filter:2023-2025 |
| 专属 | arXiv.ao-ph + journals.ametsoc.org |

### 极端天气

| 角度 | 搜索词 |
|------|--------|
| 核心 | "extreme precipitation" "heatwave" "tropical cyclone" |
| 细分 | "precipitation extremes Clausius-Clapeyron" "storm surge" |
| 经典 | "extreme weather climate change attribution" |
| 最新 | "compound extreme events" filter:2023-2025 |
| 专属 | arXiv.ao-ph |

### 气溶胶-云-降水

| 角度 | 搜索词 |
|------|--------|
| 核心 | "aerosol cloud interaction" "aerosol precipitation" |
| 细分 | "dust aerosol indirect effect" "black carbon cloud" |
| 经典 | "Twomey effect" "aerosol indirect effect" |
| 最新 | "aerosol convection precipitation" filter:2023-2025 |
| 专属 | journals.ametsoc.org + agupubs |

### 数值模式

| 角度 | 搜索词 |
|------|--------|
| 核心 | "WRF model" "CMIP6" "parameterization" |
| 细分 | "WRF microphysics scheme" "convection parameterization" |
| 经典 | "WRF development history" sort:cited_by_count:desc |
| 最新 | "machine learning parameterization" filter:2023-2025 |
| 专属 | GMD (Geoscientific Model Development) |

## 搜索参数优化

| 目标 | OpenAlex 参数 | 说明 |
|------|---------------|------|
| 查最新 | `sort=publication_date:desc` | 最新论文在前 |
| 查经典 | `sort=cited_by_count:desc` | 高引论文在前 |
| 时间限定 | `filter=publication_year:2023-2025` | 指定年份范围 |
| 标题精确 | `filter=title.search:X` | 只在标题搜（高精确度） |
| 标题摘要 | `filter=title_and_abstract.search:X` | 标题+摘要（平衡） |
| 全文搜索 | `search=X` | 全文包含（高召回，有噪声） |
| 领域限定 | `filter=primary_topic.field.id:XX` | OpenAlex 领域过滤 |

## 中文文献搜索

由于 CNKI/万方 无公开 API，推荐：

1. 先用英文关键词在 OpenAlex 搜，过滤 `language:zh`
2. 提示用户手动到 CNKI 搜索，提供推荐关键词
3. 中国气象相关期刊：大气科学、气象学报、应用气象学报、高原气象
