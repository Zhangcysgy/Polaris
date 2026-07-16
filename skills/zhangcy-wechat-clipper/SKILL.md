---
name: zhangcy-wechat-clipper
description: "Save WeChat public account articles to Obsidian. Given an mp.weixin.qq.com URL, auto-fetch content, download images locally, generate YAML frontmatter, and save to Obsidian directory. Supports single and batch processing. Triggers on: 微信/公众号/wechat article/剪藏/保存文章/obsidian/微信公众号/保存到Obsidian/mp.weixin.qq.com."
---

# WeChat 公众号文章 → Obsidian 保存工具

将微信公众号文章从链接抓取、转换 Markdown、下载图片，并保存到 Obsidian vault 的指定目录。

## 工作目录

```
D:\500_Obsidian\Archive\000_INBOX\010_Web_Clipper\011_微信公众号
```

## 🔴 检查点

| # | 位置 | 动作 |
|:--:|------|------|
| 🔴 1 | 批量处理前（>3 篇） | 显示文章数量和总图片数，询问用户确认 |
| 🔴 2 | 图片下载前 | 告知用户预计下载图片数，确认是否继续 |
| 🔴 3 | 保存完成后 | 显示保存路径和图片数，确认是否打开 Obsidian 验证 |

## ⚠️ 失败模式

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|---------|------------|
| 链接非 mp.weixin.qq.com | 拒绝执行，告知仅支持公众号链接 | 建议用户手动复制内容 |
| 微信链接跳转到验证码 | 确认 `allow_redirects=False` | 建议用户浏览器打开后手动复制 |
| 图片 403（防盗链） | 确认 `Referer: mp.weixin.qq.com` | 跳过该图片，记录 URL |
| 目标目录不存在 | 自动创建 | 询问用户指定其他目录 |
| 批量处理中单篇失败 | 记录日志，继续下一篇 | 汇总失败列表告知用户 |
| 已存在同名文章 | 询问「覆盖/跳过/重命名」 | 默认跳过 |

## 执行方式

### 单篇保存

```bash
python <skill-dir>\scripts\clipper.py <URL>
```

### 批量保存

```bash
python <skill-dir>\scripts\clipper.py <URL1> <URL2> ...
```

skill-dir 为: `C:\Users\12426\.claude\skills\zhangcy-wechat-clipper`

### 自动调用（由 agent 执行）

当用户提供 `mp.weixin.qq.com` 链接并要求保存到 Obsidian 时，按以下步骤执行：

**🔴 CHECKPOINT：提取 URL 后，向用户展示识别到的链接数量和文章标题（如能提取到），询问"确认保存这 N 篇文章？"**

1. 提取 URL（支持多个链接批量处理）— 从用户消息中提取所有 `mp.weixin.qq.com` 链接
2. 对每个 URL，按顺序执行：
   - 运行 `clipper.py` 脚本完成抓取、转换、下载、保存
   - 如某篇文章失败，记录错误但**不中断**后续文章的处理
3. 汇总报告：成功/失败数量、各文章保存路径、图片总数

## 输出结构

每篇文章创建独立文件夹：

```
011_微信公众号/
└── {净化标题}/
    ├── {净化标题}.md    ← YAML frontmatter + Markdown 正文
    └── attachments/      ← 所有本地化图片
        ├── cover.webp    ← 封面图
        ├── image-0001.png
        ├── image-0002.jpg
        └── ...
```

### Frontmatter 格式

```yaml
---
title: "文章标题"
source: "https://mp.weixin.qq.com/s/..."
author:
  - "[[公众号名称]]"
wechat_account: "公众号名称"
published: "2026-05-20"
date: "2026-06-01"
cover: "attachments/cover.webp"
description: "文章摘要"
tags:
  - "微信公众号"
  - "clipper"
  - "待整理"
status: inbox
---
```

## 提取策略

脚本使用分层策略，从简到繁自动回退：

| 层级 | 方法 | 适用场景 |
|------|------|----------|
| Tier 1 | `allow_redirects=False` + 正则提取 JS 变量 + BeautifulSoup 提取正文 | **绝大多数文章**，绕过微信验证码 |
| Tier 2 | Playwright 渲染后提取 | 正文被 JS 动态加载的极少数情况 |

**关键**：使用 `allow_redirects=False` 避免微信服务器将请求重定向到验证码页面。首次响应（status 200）已包含完整的文章 HTML 和元数据。

## 图片处理

- **防盗链**：微信图片托管在 `mmbiz.qpic.cn`，必须设置 `Referer: https://mp.weixin.qq.com`
- **扩展名**：优先从 URL 的 `wx_fmt` 参数提取（`wx_fmt=png` → `.png`）
- **重试机制**：每张图片重试 3 次，最终失败保留原始 URL
- **单张失败不中断**整体流程

## 依赖检查

```bash
python -c "import requests, bs4, lxml, html2text; print('OK')"
```

Playwright 回退需要额外安装：
```bash
pip install playwright
python -m playwright install chromium
```

## 错误处理（三段式故障修复）

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|----------|------------|
| 网络错误（ConnectionError/Timeout） | 检查网络连接，等待 5 秒重试 | 记录错误日志，报告用户检查链接有效性 |
| 被重定向到验证码页面 | 提示用户先在浏览器打开该微信文章建立会话 | 等用户确认后在 clipper.py 中设置 Cookie 重试 |
| 正文为空或解析结果为 0 字符 | 尝试 Tier 2 Playwright 渲染 | 提示用户文章已删除/需登录，保留空 frontmatter 占位 |
| 图片下载部分失败 | 每张重试 3 次，失败记录 URL | 在 Markdown 中保留原始 URL 作为备选链接 |
| 同级目录名冲突 | 自动追加副本编号（标题-2、标题-3...） | 询问用户手动指定目录名 |

---

## 🚫 反例与黑名单

以下操作会导致剪藏失败或格式异常，**应避免**：

| # | 不要做 | 为什么 | 正确做法 |
|---|--------|--------|----------|
| 1 | 修改 frontmatter 字段（title/date/source/tags） | 这些字段是 Obsidian 知识库统一格式，变动后搜索/索引断裂 | 保持 `clipper.py` 生成的 frontmatter 不动 |
| 2 | 处理非 `mp.weixin.qq.com` 链接 | 本 skill 只针对微信公众号文章，其他来源（知乎/CSDN/网页）没有对应的提取逻辑 | 拒绝执行，告知用户仅支持公众号链接 |
| 3 | 直接访问微信链接（不带 `allow_redirects=False`） | 微信会重定向到验证码页面，无法获取内容 | 脚本已内置 Tier 1 策略，确保 `allow_redirects=False` |
| 4 | 下载图片时不设 `Referer: https://mp.weixin.qq.com` | 微信 CDN 防盗链，无 Referer 返回 403 | 脚本已内置 Referer，保持不动 |
| 5 | 单篇文章失败时中断批量处理 | 批量保存中一篇失败不等于全部失败 | 记录错误日志，继续处理剩余文章 |
| 6 | 手动重命名 attachments/ 目录中的图片文件 | 文件名与 Markdown 正文中的引用路径绑定，改名后图片断裂 | 保持脚本生成的原始文件名 |

---

## 旧脚本说明

`scripts/save_article.py` 基于 `defuddle` CLI，已被 `clipper.py` 取代。新文章统一使用 `clipper.py`。

## 示例

```
用户: 帮我把这些文章保存到 Obsidian
      https://mp.weixin.qq.com/s/xxx
      https://mp.weixin.qq.com/s/yyy

你: ✅ 2 篇文章已保存到 Obsidian
    📁 011_微信公众号/文章标题一/
    📁 011_微信公众号/文章标题二/
    🖼️ 共下载 15 张图片
```
