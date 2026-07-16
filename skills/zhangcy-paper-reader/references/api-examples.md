# API 调用示例与响应解析

## OpenAlex 获取摘要（最常用）

```
GET https://api.openalex.org/works/doi:10.1016/j.atmosres.2021.105933?select=id,doi,title,publication_year,authorships,primary_location,cited_by_count,abstract_inverted_index,keywords,concepts
```

### 解析 abstract_inverted_index

OpenAlex 的摘要是倒排索引格式，需要还原：

```python
# 还原示例
inverted = {"the": [0, 5], "quick": [1], "brown": [2], ...}
# 还原为: "the quick brown fox ..." 
words = [""] * (max(pos for positions in inverted.values() for pos in positions) + 1)
for word, positions in inverted.items():
    for pos in positions:
        words[pos] = word
abstract = " ".join(words)
```

### 完整响应示例

```json
{
  "title": "Did dust intrusion and lofting escalate the catastrophic widespread lightning on 16th April 2019, India?",
  "publication_year": 2021,
  "cited_by_count": 16,
  "primary_location": {
    "source": {"display_name": "Atmospheric Research"},
    "is_oa": false
  },
  "abstract_inverted_index": {
    "The": [0], "present": [1], "study": [2], ...
  }
}
```

## arXiv 获取全文

```
GET https://export.arxiv.org/api/query?id_list=2006.01978
```

### 解析

arXiv 返回 Atom XML。核心字段在 entry 中：
- `entry/title` — 标题
- `entry/summary` — 完整摘要
- `entry/author/name` — 作者
- `entry/arxiv:doi` — 关联 DOI
- `entry/category` — 分类（如 `physics.ao-ph`）

### 完整响应示例（关键字段）

```xml
<entry>
  <title>Detection of spark discharges in an agitated Mars dust simulant...</title>
  <summary>Numerous laboratory experiments... (完整摘要文本)</summary>
  <author><name>Joshua Méndez Harper</name></author>
  <arxiv:doi>10.1016/j.icarus.2020.114268</arxiv:doi>
  <category term="astro-ph.EP"/>
</entry>
```

## Unpaywall 获取 OA 链接

```
GET https://api.unpaywall.org/v2/10.1016/j.atmosres.2021.105933?email=research@example.com
```

### 解析

```json
{
  "is_oa": true,
  "oa_status": "green",
  "best_oa_location": {
    "url_for_pdf": "https://.../paper.pdf",
    "host_type": "repository"
  }
}
```

如果 `is_oa: false`，说明是付费论文，无法直接获取全文。

## 标题搜索（DOI 未知时）

```
GET https://api.openalex.org/works?search=Humidity-gated+triboelectric+charging+in+dust+storms&per_page=3&select=id,doi,title,publication_year
```

返回匹配度最高的前 3 篇论文，按相关性排序。
