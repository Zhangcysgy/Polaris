# Zotero 集成说明

## 概述

research-search 通过 Zotero MCP 服务器将搜索结果直接推送到 Zotero 库，无需手动操作。

## 前提条件

Zotero MCP 已在 Reasonix config 中配置：
```json
"mcp": [
  "zotero-mcp=streamable+http://127.0.0.1:23120/mcp"
]
```

本地需运行 Zotero + Zotero MCP 服务器。

## 可用 MCP 工具

| 工具名 | 说明 | 主要参数 |
|--------|------|----------|
| `search_items` | 搜索 Zotero 库中的条目 | `query: string` |
| `create_item` | 从元数据创建新条目 | `item: Item` |
| `list_collections` | 列出所有集合 | — |
| `create_collection` | 创建新集合 | `name: string`, `parent: string?` |
| `add_to_collection` | 将条目加入集合 | `itemKey: string`, `collectionKey: string` |

## 两种推送模式

### 模式 A：按需推送（默认）

```
用户搜索 → AI 返回结果 → 询问用户 → 用户确认 → AI 调 MCP 创建
```

工作流：
1. 搜索结果展示后，AI 询问"需要加入 Zotero 吗？"
2. 用户指定哪些篇： "第 1、3、5 篇" 或 "全部"
3. AI 调 `search_items` 检查是否已存在
4. AI 调 `create_item` 逐篇创建
5. AI 返回确认结果

### 模式 B：全自动推送

```
用户在 query 中包含 [auto-zotero] 标记
    或说"自动保存到 Zotero"
→ AI 搜索 + 自动推送 + 结果显示
```

工作流：
1. 检测到 `[auto-zotero]` 标记或"自动保存"意图
2. 搜索论文
3. 对每篇自动调 `create_item`（先检查重复）
4. 搜索结果中标注 ✅ 已入 Zotero

## 重复检查

推送前必须检查 Zotero 库中是否已存在该论文：

```
1. 用 DOI 搜索: zotero.search_items(query=doi)
2. 若无 DOI: 用标题搜索: zotero.search_items(query=title)
3. 已存在 → 跳过（返回 "⏭ 已存在"）
4. 不存在 → 创建
```

## 元数据字段映射

| 来源字段 | Zotero 字段 | 说明 |
|----------|-------------|------|
| DOI | `DOI` | 唯一标识 |
| title | `title` | 论文标题 |
| authors | `creators` | 数组，每个 `{creatorType:"author", firstName, lastName}` |
| journal | `publicationTitle` | 期刊名 |
| year | `date` | 出版年份 |
| volume | `volume` | 卷号 |
| issue | `issue` | 期号 |
| pages | `pages` | 页码 |
| abstract | `abstractNote` | 摘要 |
| url | `url` | URL |
| arXiv ID | `extra` | 额外标注 "arXiv:xxxx.xxxxx" |

## 条目类型选择

| 来源 | Zotero 条目类型 |
|------|----------------|
| 已发表期刊论文 | `journalArticle` |
| 预印本 (arXiv/bioRxiv) | `preprint` |
| 会议论文 | `conferencePaper` |
| 书籍章节 | `bookSection` |

## Fallback：pyzotero

当 Zotero MCP 不可用时（服务器未启动等），使用 Python pyzotero 脚本：

```bash
# 安装
uv pip install pyzotero

# 运行
uv run python scripts/save_to_zotero.py \
  --doi "10.1175/JCLI-D-23-0123.1" \
  --collection "precipitation-nowcasting"
```

需要设置环境变量：
```
ZOTERO_LIBRARY_ID=your_user_id
ZOTERO_API_KEY=your_api_key
ZOTERO_LIBRARY_TYPE=user
```
