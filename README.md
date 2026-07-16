# Polaris — AI 科研自主发现系统

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> 现有的气象数据太多，但利用率太低。有了 AI 的辅助，我们可以更加高效地利用现有数据，充分挖掘其中的价值，推动大气科学的发展。

**Polaris** 是一个 LLM 驱动的 AI 科研自主发现系统。以大气科学为首发领域，AI 扮演"科研工程师"，人类扮演"所长/守门人"。

Polaris 的目的**不是**训练更好的天气预报 AI 模型，而是构建一个 **"AI 科研操作体"**——用 LLM 驱动代码编写、数据分析、结果解读、文献检索、理论验证、方法迁移、迭代修正的全自动闭环。

---

## 架构：五引擎拓扑管控

```
┌──────────────────────────────────────────────────────┐
│                    引擎四：自主发现循环                  │
│              (DiscoveryLoop — 半自主 50 步闭环)         │
│  下载数据 → 分析方法 → 执行 → 验证 → 文献 → 补数据 → 循环  │
├──────────────────────────────────────────────────────┤
│  引擎三：全局迁移         │  引擎二：深度验证             │
│  (GlobalMigrator)        │  (DeepValidator)           │
│  三级适配策略             │  方法论溯源+红队+多角色辩论    │
│  全球比对 → 差异即发现    │  竞争假设+敏感性热图          │
├──────────────────────────┼────────────────────────────┤
│  引擎一：产物追踪         │  引擎O：方法库                │
│  (Tracker)               │  (MethodLibrary)            │
│  反馈主线+自动版本捕获    │  三层结构+自生长+双层门禁     │
│  干净房间审稿+收手标准    │  自然语言检索+同义词扩展      │
└──────────────────────────┴────────────────────────────┘
```

### 三大底层逻辑

| 逻辑维度 | 核心痛点 | Polaris 解法 |
|:---|:---|:---|
| **认知层** | LLM 擅长拟合已知，易陷入"数据内卷" | **第一性原理锚点**：所有结论必须接受物理守恒/量纲检验 |
| **操作层** | AI 快速产出海量"正确但无用"的中间结果 | **惊喜度导航**：优先探索预测残差最大或物理直觉最反常的边缘节点 |
| **组织层** | 单 Agent 易跑偏，多 Agent 易失序 | **五引擎拓扑管控**：方法库→追踪→验证→迁移→发现，线性推进 + 持续迭代 |

---

## 快速开始

### 环境要求

- Python 3.12+
- DeepSeek API Key（或智谱 GLM API Key）
- Windows / Linux / macOS

### 安装

```bash
git clone https://github.com/your-username/polaris.git
cd polaris
pip install -e .
```

### 配置

1. 设置 API Key 环境变量：
```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-your-key-here"

# Linux / macOS
export DEEPSEEK_API_KEY="sk-your-key-here"
```

2. （可选）编辑 `polaris.yaml` 调整模型参数、路径、物理围栏规则。

### 运行

```bash
# 查看帮助
polaris --help

# 录入示例种子数据
polaris method seed

# 搜索方法库
polaris method search "BET 吸附 湿度"

# 审稿论文（dry-run 预览 System Prompt）
polaris review paper paper.md --mode red-team --dry-run

# 审稿论文（真实 LLM 调用）
polaris review paper paper.md --mode multi-expert

# 查看项目状态
polaris status

# 生成发现简报
polaris report

# 方法迁移（dry-run）
polaris migrate run orch_bet -s sahara -t central_asia,australia --dry-run

# 启动自主发现循环（dry-run）
polaris discover start "全球沙尘起电的湿度调控机制" --dry-run
```

### 命令全览

```
polaris method search|list|show|seed|approve|reject|pending|stats
polaris status
polaris review paper|feedback
polaris migrate run|regions|anomalies
polaris discover start|status|nodes
polaris report
```

---

## 项目结构

```
polaris/
├── docs/
│   ├── PRD.md              ← 产品需求文档
│   └── TDD.md              ← 技术设计文档
├── src/polaris/
│   ├── core/               ← 基础设施（Config/DB/LLM/ContextPacket）
│   ├── engine_o_methods/   ← 引擎O：方法库
│   ├── engine_one_tracker/ ← 引擎一：产物追踪+收手
│   ├── engine_two_validator/← 引擎二：深度验证
│   ├── engine_three_migrator/← 引擎三：全局方法迁移
│   ├── engine_four_loop/   ← 引擎四：自主发现循环
│   └── cli/                ← CLI 入口
├── benchmarks/             ← 50题气象编码测试基准
├── experiments/            ← 上下文污染检测实验
├── data/                   ← SQLite 数据库
├── polaris.yaml            ← 全局配置
└── pyproject.toml
```

---

## 文档

- **[PRD.md](docs/PRD.md)** — 产品需求文档：五引擎功能定义、用户场景、成功指标、竞品分析
- **[TDD.md](docs/TDD.md)** — 技术设计文档：数据模型（13张表）、接口规范、技术选型、里程碑排期

---

## 核心理念

### 物理锚定 · 人机共驾 · 自研进化

1. **物理围栏**：三级分级响应（WARNING/REVIEW/REJECT），所有结论必须接受物理守恒/量纲检验
2. **干净房间审稿**：每次审稿在完全隔离的 LLM 上下文中运行，杜绝前序对话污染
3. **反馈主线追踪**：以审稿意见为追踪单元（非文件版本），每条意见从出生到解决有完整轨迹
4. **自生长方法库**：方法从每次成功分析中自动提取、沉淀、进化
5. **差异即发现**：方法在全球不同区域的适配差异，本身就是科学发现的燃料

---

## 当前状态

| 引擎 | 状态 | 说明 |
|:---|:---:|:---|
| 引擎O 方法库 | ✅ | CRUD + 三层结构 + 检索 + 双层门禁 |
| 引擎一 追踪 | ✅ | 反馈主线 + 自动版本 + 干净房间 + 收手标准 |
| 引擎二 验证 | ✅ | 方法论溯源 + 红队 + 多角色辩论 + 竞争假设 + 敏感性热图 |
| 引擎三 迁移 | ✅ | 三级迁移策略 + 6 个预设区域 + 异常发现 |
| 引擎四 循环 | ✅ | 8 步循环框架 + CRT 节点管理 + 4 种退出条件 |
| LLM API | ✅ | DeepSeek + 智谱双后端，已集成到审稿闭环 |

**全部五引擎框架完整。M5+ 阶段将接入真实数据下载、代码执行和全自动循环。**

---

## 竞品对比

| | AutoGPT | 求是引擎（浙大） | Polaris |
|:---|:---:|:---:|:---:|
| 自主循环 | ✅ | ✅ 千步级 | ✅ 50步MVP |
| 领域方法库 | ❌ | 未提及 | ✅ 自生长三层结构 |
| 反馈追踪 | ❌ | 未提及 | ✅ 意见→解决完整轨迹 |
| 干净房间审稿 | ❌ | 未提及 | ✅ 上下文隔离+污染检测 |
| 物理围栏 | ❌ | ❌ | ✅ 三级分级响应 |
| 全球方法迁移 | ❌ | ❌ | ✅ 大气科学专属 |
| 跨领域审查 | ❌ | 未公开 | ✅ 4 种审稿模式 |

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

## 作者

Polaris 由大气科学研究者开发，旨在为 AI 辅助科研提供一套可复制的方法论和工具系统。

*"不只是在工具层面加速科研，而是重新定义人与 AI 在科学发现中的关系。"*

---

# Polaris — AI-Powered Autonomous Scientific Discovery System

**Polaris** is an LLM-driven autonomous scientific discovery system, initially targeting atmospheric science. AI serves as the "research engineer," while humans serve as the "director/gatekeeper."

### Five-Engine Architecture

| Engine | Role | Description |
|:---|:---|:---|
| Engine O | Method Library | Self-growing three-layer knowledge base with dual quality gates |
| Engine I | Tracking | Feedback-based versioning, clean-room review, stop criteria |
| Engine II | Validation | Methodology tracing, red-team, multi-expert debate, sensitivity heatmaps |
| Engine III | Migration | Three-level cross-region method adaptation — differences are discoveries |
| Engine IV | Discovery Loop | Semi-autonomous 8-step scientific discovery cycle (50-step MVP) |

### Quick Start

```bash
pip install -e .
polaris method seed
polaris method search "BET adsorption humidity"
polaris review paper paper.md --mode red-team --dry-run
polaris discover start "Global dust electrification mechanisms" --dry-run
```

### License

MIT
