# BGPT 结构化论文搜索

## 概述

BGPT 是一个远程 MCP 服务器，从全文中提取结构化实验数据。

## 接入方式

```json
{
  "mcpServers": {
    "bgpt": {
      "url": "https://bgpt.pro/mcp/sse"
    }
  }
}
```

或通过 npx：
```json
{
  "mcpServers": {
    "bgpt": {
      "command": "npx",
      "args": ["-y", "bgpt-mcp"]
    }
  }
}
```

## 工具

### search_papers

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索词 |
| num_results | int | 否 | 1-100，默认 10 |
| days_back | int | 否 | 仅返回 N 天内论文 |
| api_key | string | 否 | 付费订阅 key |

## 返回数据结构

每篇论文返回 25+ 字段：
- **Title, DOI** — 标识
- **Methods** — 实验设计、技术
- **Results** — 原始数据、统计结果
- **Conclusions** — 作者结论
- **Quality scores** — 方法学质量评估
- **Sample sizes** — 样本量
- **Limitations** — 局限性

## 定价

| 层级 | 费用 | 说明 |
|------|------|------|
| Free | $0 | 50 次免费，无需 key |
| Pay-as-you-go | $0.02/条 | 在 bgpt.pro/mcp 获取 key |
