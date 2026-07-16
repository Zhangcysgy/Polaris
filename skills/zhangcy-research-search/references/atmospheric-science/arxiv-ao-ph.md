# arXiv physics.ao-ph — 大气与海洋物理预印本

## 分类代码

| 代码 | 全称 | 覆盖领域 |
|------|------|----------|
| **physics.ao-ph** | Atmospheric and Oceanic Physics | 大气物理、气象、气候、海洋物理 |

## API 信息

| 项目 | 内容 |
|------|------|
| 基础 URL | `https://export.arxiv.org/api/query` |
| 返回格式 | Atom XML |
| 限流 | 最多 1 请求 / 3 秒 |
| 最大返回 | 单次 2000 条 |

## 查询语法

### 分类限定查询
```
https://export.arxiv.org/api/query?search_query=all:{query}&cat=physics.ao-ph
```

### 时间范围限定
```
https://export.arxiv.org/api/query?search_query=all:{query}&cat=physics.ao-ph&start=0&max_results=50&sortBy=submittedDate&sortOrder=descending
```

### 最新论文（无关键词）
```
https://export.arxiv.org/api/query?search_query=cat:physics.ao-ph&sortBy=submittedDate&sortOrder=descending&max_results=50
```

## 主要子领域

- 大气动力学 — 环流、波动、涡旋
- 气候动力学 — ENSO、季风、PDO、遥相关
- 云物理与辐射 — 云微物理、辐射传输
- 大气边界层 — 湍流、通量
- 气溶胶与大气化学 — 气溶胶-云相互作用
- 降水物理 — 云降水、极端降水
- 数值天气预报 — 资料同化、模式
- 卫星气象 — 遥感反演
- 海洋物理 — 海气相互作用、海洋环流

## 与其他数据源交叉查询

```
# 已发表 + 预印本同时覆盖
OpenAlex: search "precipitation nowcasting machine learning"
arXiv:   search "precipitation nowcasting deep learning" cat:physics.ao-ph
```
