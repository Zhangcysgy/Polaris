# API 调用示例 — 文献调研中的实际搜索

当 `zhangcy-research-search` 不可用时，或需要手动精细控制搜索时，直接调用以下 API。

## OpenAlex

### 标题+摘要精确搜索
```
GET https://api.openalex.org/works?
  filter=title_and_abstract.search:dust+storm+lightning,
         publication_year:2018-2025&
  sort=cited_by_count:desc&
  per_page=25&
  select=id,doi,title,publication_year,primary_location,cited_by_count
```

### 高引经典论文（不限年份）
```
GET https://api.openalex.org/works?
  search=dust+storm+electrification&
  sort=cited_by_count:desc&
  per_page=25
```

### 按作者搜索
```
GET https://api.openalex.org/works?
  filter=authorships.author.display_name:Gangane,
         publication_year:2018-2025&
  per_page=25
```

### 关联主题推荐
```
GET https://api.openalex.org/works/W4306353777
→ 返回中的 primary_topic 和 related_topics 字段
```

## arXiv

### physics.ao-ph 最新论文
```
GET https://export.arxiv.org/api/query?
  search_query=cat:physics.ao-ph&
  sortBy=submittedDate&
  sortOrder=descending&
  max_results=25
```

### physics.ao-ph 关键词搜索
```
GET https://export.arxiv.org/api/query?
  search_query=all:%22dust+storm%22+AND+all:%22lightning%22&
  start=0&max_results=25
```

## 引用回溯流程

1. 找到一篇核心论文 → 取它的 `referenced_works` 列表
2. 批量查询这些 ID：
```
GET https://api.openalex.org/works?
  filter=ids.openalex:W4306353777|W3217030109|W4412556057&
  select=id,doi,title,publication_year,cited_by_count
```

## 被引追踪流程

1. 找到一篇核心论文的 OpenAlex ID
2. 查谁引用了它：
```
GET https://api.openalex.org/works/W4306353777/cited_by?
  per_page=25&
  select=id,doi,title,publication_year
```
