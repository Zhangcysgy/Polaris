# Polaris 内置 Skill 集

此目录包含 9 个 zhangcy 系列 Claude Code skill，覆盖大气科学研究的完整流程：

| Skill | 功能 | 触发词 |
|:---|:---|:---|
| `zhangcy-research-search` | 论文搜索（10+学术数据库） | 搜论文/查文献/search paper |
| `zhangcy-literature-review` | 文献综述生成（深度/广度模式） | 文献综述/literature review |
| `zhangcy-paper-reader` | 论文阅读（DOI/arXiv/PMID/标题） | 读论文/read paper |
| `zhangcy-nature-review-simple` | 轻量级投稿前自查 | 审稿/review/simple review |
| `zhangcy-nature-review-strict` | 严格多角色学术审稿 | 严格审稿/strict review |
| `zhangcy-python-coding` | Python科学计算与可视化 | 写代码/python/coding |
| `zhangcy-slide-content-builder` | PPT内容与演讲脚本生成 | 做PPT/slide/slides |
| `zhangcy-slide-designer` | LaTeX/Beamer PDF生成 | 设计PPT/beamer |
| `zhangcy-wechat-clipper` | 微信公众号文章保存到Obsidian | 剪藏/wechat/save article |

## 使用方式

在 Claude Code CLI 或 Reasonix CLI 中：

```
/zhangcy-literature-review 沙尘暴摩擦起电机制
/zhangcy-nature-review-strict paper.md
/zhangcy-research-search "dust storm electrification"
```

## 与 Polaris 引擎的关系

- **引擎四**（DiscoveryLoop）内置了 `LiteratureSearcher`，可直接调用 OpenAlex/arXiv API，不需要依赖这些 skill
- 这些 skill 通过 Claude Code CLI 的 `/skill` 机制运行，提供更丰富的交互式工作流
- Polaris CLI（`polaris review paper --mode red-team`）提供替代的审稿能力，适合自动化场景
