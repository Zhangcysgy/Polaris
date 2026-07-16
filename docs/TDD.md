# Polaris — AI 科研自主发现系统 · 技术设计文档（TDD）

**版本**：v1.0
**作者**：张朝阳
**日期**：2026-07-16
**状态**：技术设计阶段
**前置文档**：[PRD v1.1](./PRD.md)

---

## 目录

1. [技术选型](#1-技术选型)
2. [系统架构](#2-系统架构)
3. [项目目录结构](#3-项目目录结构)
4. [数据模型](#4-数据模型)
5. [接口规范](#5-接口规范)
6. [核心模块设计](#6-核心模块设计)
7. [安全与约束](#7-安全与约束)
8. [里程碑排期](#8-里程碑排期)
9. [附录](#9-附录)

---

## 1. 技术选型

### 1.1 选型原则

- **本地优先**：分析数据和中间产物不离开用户工作站
- **CLI 原生**：用户明确在 CLI 环境工作，不引入 Web UI
- **Python 全栈**：科学计算 + LLM 编排统一语言，降低维护成本
- **SQLite 单文件**：零配置、零运维、备份即拷贝
- **约定优于配置**：目录结构即项目结构，减少显式配置文件

### 1.2 技术栈

| 层级 | 技术 | 选型理由 |
|:---|:---|:---|
| **语言** | Python 3.12+ | 科学计算生态 + LLM SDK + 用户熟悉 |
| **LLM 接入** | DeepSeek API（主力）/ 智谱 GLM API（备用） | 用户已订阅，成本可控 |
| **LLM SDK** | `openai` Python SDK（兼容 DeepSeek）+ 原生 HTTP | 统一接口，多模型可切换 |
| **数据存储** | SQLite（结构化）+ 文件系统（产物） | 零运维，备份即 cp |
| **配置格式** | YAML（`polaris.yaml`） | 人类可读写，Obsidian 友好 |
| **CLI 框架** | `click` 或 `typer` | 轻量、Python 原生 |
| **异步** | `asyncio` + `httpx` | 多 LLM 调用并行（引擎二多专家、引擎三多区域） |
| **科学计算** | `xarray` + `numpy` + `scipy` + `matplotlib` | 气象数据标准栈 |
| **日志** | `structlog` | 结构化日志，支持 JSON 输出到 CRT |
| **测试** | `pytest` + `pytest-asyncio` | 标准 Python 测试框架 |
| **代码质量** | `ruff`（lint + format） | 快、单一工具替代 flake8+black+isort |

### 1.3 不选的技术

| 技术 | 不选理由 |
|:---|:---|
| **LangChain / LlamaIndex** | 过度抽象，调试困难，用户偏好精准控制 Prompt |
| **Neo4j / 图数据库** | v1.0 CRT 节点量级在 SQLite 能处理范围（<10K 节点） |
| **Docker / K8s** | 单人单机，不需要容器编排 |
| **Web UI（React/Vue）** | 用户明确 CLI 环境 |
| **gRPC / REST API** | 单进程架构，模块间直接函数调用，不需要网络通信 |
| **微服务架构** | 过度工程，MVP 用单体架构 |

---

## 2. 系统架构

### 2.1 架构原则

```
┌──────────────────────────────────────────────────────────┐
│                    Polaris 单体进程                        │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  CLI 层      │  │  Scribe 层   │  │  LLM 网关    │       │
│  │ (click)     │  │ (structlog) │  │ (openai SDK)│       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │               │
│  ┌──────┴────────────────┴────────────────┴──────┐       │
│  │              引擎调度中心 (Engine Hub)          │       │
│  │   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐│       │
│  │   │引擎O │ │引擎一│ │引擎二│ │引擎三│ │引擎四││       │
│  │   │方法库│ │追踪 │ │验证 │ │迁移 │ │发现 ││       │
│  │   └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘│       │
│  └──────┼────────┼────────┼────────┼────────┼────┘       │
│         │        │        │        │        │             │
│  ┌──────┴────────┴────────┴────────┴────────┴────┐       │
│  │                 数据层 (SQLite)                 │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐   │       │
│  │  │ methods  │ │  crt_nodes│ │ feedback_items│   │       │
│  │  │ 方法库   │ │ CRT节点  │ │ 反馈追踪     │   │       │
│  │  └──────────┘ └──────────┘ └──────────────┘   │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐   │       │
│  │  │versions  │ │ reviews  │ │  ghost_signals│   │       │
│  │  │ 版本     │ │ 审稿记录 │ │  幽灵信号     │   │       │
│  │  └──────────┘ └──────────┘ └──────────────┘   │       │
│  └───────────────────────────────────────────────┘       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              文件系统 (workspace/)                 │   │
│  │  data/  │  scripts/  │  outputs/  │  papers/      │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 2.2 引擎调用流

```
用户指令 (CLI)
  │
  ▼
引擎四（自主发现循环）
  │
  ├─→ 引擎O（方法库）
  │     └─→ SQLite 查询 → 返回匹配方法
  │
  ├─→ 引擎一（产物追踪）
  │     ├─→ 自动捕获版本
  │     ├─→ 记录反馈状态
  │     └─→ 触发干净房间审稿
  │
  ├─→ 引擎二（深度验证）
  │     ├─→ 多 LLM 并行调用（独立会话）
  │     └─→ 汇总审查报告
  │
  ├─→ 引擎三（方法迁移）
  │     ├─→ 多区域并行执行
  │     └─→ 差异比对 → 异常路由到引擎二
  │
  └─→ 循环判断 → 继续 / 退出 / 汇报人类
```

### 2.3 引擎间依赖

```
引擎O（方法库）
  ↑ 被所有引擎调用
  │
引擎一（追踪）
  ↑ 被引擎二/三/四调用
  │
引擎二（验证）
  ↑ 被引擎一（收手判断）、引擎三（异常路由）、引擎四（循环内验证）调用
  ↑ 兼做引擎O的守门人
  │
引擎三（迁移）
  ↑ 被引擎四调用
  │
引擎四（循环）
  └─→ 编排以上所有引擎
```

---

## 3. 项目目录结构

```
Polaris/
├── polaris.yaml                 # 全局配置（LLM密钥、数据路径、默认参数）
├── README.md                    # 项目说明
├── docs/
│   ├── PRD.md                   # 产品需求文档
│   └── TDD.md                   # 本文档
│
├── src/
│   ├── __init__.py
│   ├── main.py                  # CLI 入口（click/typer）
│   ├── config.py                # 配置加载器（polaris.yaml → dataclass）
│   │
│   ├── engines/                 # 五引擎实现
│   │   ├── __init__.py
│   │   ├── engine_o_methods.py  # 引擎O：方法库
│   │   ├── engine_1_tracker.py   # 引擎一：产物追踪与收手
│   │   ├── engine_2_verify.py   # 引擎二：深度理论验证
│   │   ├── engine_3_migrate.py  # 引擎三：全局方法迁移
│   │   ├── engine_4_loop.py     # 引擎四：自主发现循环
│   │   └── hub.py               # 引擎调度中心
│   │
│   ├── db/                      # 数据层
│   │   ├── __init__.py
│   │   ├── schema.py            # SQLite 表定义（DDL）
│   │   ├── queries.py           # 常用查询封装
│   │   └── migrations/          # 数据库迁移（alembic 或手写 SQL）
│   │       └── 001_initial.sql
│   │
│   ├── llm/                     # LLM 网关
│   │   ├── __init__.py
│   │   ├── client.py            # 统一 LLM 调用接口（适配 DeepSeek/GLM）
│   │   ├── cleanroom.py         # 干净房间：隔离会话管理
│   │   └── prompts/             # System Prompt 模板
│   │       ├── coder.md
│   │       ├── reviewer.md
│   │       ├── red_team.md
│   │       └── cross_domain_expert.md
│   │
│   ├── crt/                     # CRT（认知推理拓扑）管理
│   │   ├── __init__.py
│   │   ├── node.py              # CRT 节点数据结构
│   │   ├── compressor.py        # L1/L2/L3 压缩器
│   │   └── context_packet.py    # 上下文数据包组装
│   │
│   ├── harness/                 # 制度约束（物理围栏 + 安全限制）
│   │   ├── __init__.py
│   │   ├── physics_fence.py     # 三级物理围栏（WARNING/REVIEW/REJECT）
│   │   ├── resource_limit.py    # API 调用/磁盘/时间上限
│   │   └── code_sandbox.py      # 代码执行沙箱（可选，v1.0 不强制）
│   │
│   └── utils/                   # 通用工具
│       ├── __init__.py
│       ├── file_watcher.py      # 文件变动监听（自动版本捕获）
│       ├── diff_engine.py       # 版本差异对比
│       └── data_downloader.py   # ERA5/卫星数据下载器
│
├── tests/                       # 测试
│   ├── __init__.py
│   ├── test_engine_o.py
│   ├── test_engine_1.py
│   ├── test_engine_2.py
│   ├── test_crt.py
│   └── benchmarks/              # 50题气象编码测试基准
│       ├── README.md
│       └── task_001_olr_trend.md
│
├── skills/                      # zhangcy 系列 skill（与现有体系兼容）
│   └── README.md                # skill 迁移映射表
│
├── workspace/                   # 用户工作区（每个研究项目一个子目录）
│   └── .gitkeep
│
└── polaris.db                   # SQLite 数据库文件（自动创建）
```

---

## 4. 数据模型

### 4.1 实体关系概览

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ Method   │     │  CRTNode     │     │ FeedbackItem │
│ 方法条目  │←───│  CRT节点      │────→│ 反馈意见      │
└──────────┘     └──────┬───────┘     └──────────────┘
                        │
                        │ parent_id
                        ▼
                 ┌──────────────┐
                 │  CRTNode     │（父子关系：DAG）
                 └──────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ Version  │  │ Review   │  │GhostSignal│
   │ 产物版本  │  │ 审稿记录  │  │ 幽灵信号  │
   └──────────┘  └──────────┘  └──────────┘
```

### 4.2 核心表结构

#### 4.2.1 方法库（engine_o）

```sql
-- 方法条目（原子方法 + 编排条目）
CREATE TABLE methods (
    id              TEXT PRIMARY KEY,          -- UUID
    name            TEXT NOT NULL,             -- 人类可读名称
    type            TEXT NOT NULL CHECK(type IN ('atomic', 'orchestration', 'param_instance')),
    parent_id       TEXT REFERENCES methods(id), -- 编排条目 → 原子方法（编排时非空）
    description     TEXT NOT NULL,             -- 一句话描述
    definition      TEXT,                      -- 方法定义（伪代码/自然语言/代码模板）
    parameters_json TEXT,                      -- 参数 schema（JSON）
    domain          TEXT,                      -- 领域标签（如 "atmospheric_electricity"）
    keywords        TEXT,                      -- 搜索关键词（逗号分隔）
    status          TEXT NOT NULL DEFAULT 'candidate'
                    CHECK(status IN ('candidate', 'pending_review', 'verified', 'rejected', 'deprecated')),
    quality_score   REAL DEFAULT 0.0,          -- 质量分数（0-1）
    use_count       INTEGER DEFAULT 0,         -- 被调用次数
    success_count   INTEGER DEFAULT 0,         -- 成功次数
    fail_count      INTEGER DEFAULT 0,         -- 失败次数
    fail_conditions TEXT,                      -- 已知失效条件
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at     TEXT,                      -- 人类审批时间
    reviewed_by     TEXT DEFAULT 'human'       -- 审批人
);

-- 方法引用关系（编排条目 ↔ 原子方法，多对多）
CREATE TABLE method_references (
    orchestration_id TEXT NOT NULL REFERENCES methods(id),
    atomic_id        TEXT NOT NULL REFERENCES methods(id),
    order_index      INTEGER NOT NULL,         -- 在编排中的顺序
    PRIMARY KEY (orchestration_id, atomic_id)
);

-- 方法调用历史
CREATE TABLE method_invocations (
    id          TEXT PRIMARY KEY,              -- UUID
    method_id   TEXT NOT NULL REFERENCES methods(id),
    crt_node_id TEXT REFERENCES crt_nodes(id), -- 关联的CRT节点
    params_json TEXT,                          -- 实际使用的参数
    status      TEXT CHECK(status IN ('success', 'failure', 'timeout')),
    error_msg   TEXT,
    started_at  TEXT NOT NULL,
    finished_at TEXT
);

CREATE INDEX idx_methods_status ON methods(status);
CREATE INDEX idx_methods_domain ON methods(domain);
CREATE INDEX idx_methods_type ON methods(type);
```

#### 4.2.2 CRT 节点（引擎一 + 引擎四）

```sql
CREATE TABLE crt_nodes (
    id              TEXT PRIMARY KEY,          -- UUID，格式：CRT_YYYYMMDD_HHMMSS_XXX
    parent_id       TEXT REFERENCES crt_nodes(id), -- 父节点
    title           TEXT NOT NULL,             -- 人类可读标题
    step_number     INTEGER NOT NULL,          -- 循环步数序号
    engine          TEXT NOT NULL CHECK(engine IN ('engine_o', 'engine_1', 'engine_2', 'engine_3', 'engine_4')),
    action          TEXT NOT NULL,             -- 执行的动作描述
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'running', 'completed', 'failed', 'rejected', 'frozen')),
    
    -- 上下文数据包（JSON）
    context_json    TEXT,                      -- 传入 LLM 的上下文数据包
    
    -- 物理校验结果
    physics_checks_total    INTEGER DEFAULT 0,
    physics_checks_passed   INTEGER DEFAULT 0,
    physics_checks_failed   INTEGER DEFAULT 0,
    physics_violations_json TEXT,              -- 详细违反记录
    
    -- 结果
    result_summary  TEXT,                      -- 结果摘要（≤500字）
    result_json     TEXT,                      -- 结构化结果
    artifact_paths  TEXT,                      -- 产物文件路径（逗号分隔）
    
    -- 置信度与质量
    confidence      REAL DEFAULT 0.0,          -- 置信度（0-1）
    surprise_score  REAL DEFAULT 0.0,          -- 惊喜度（0-1）
    black_box_index REAL DEFAULT 0.0,          -- 黑箱指数（0-1，越高越不可解释）
    
    -- 压缩元数据（L1/L2/L3）
    compression_level TEXT DEFAULT 'L1'
                      CHECK(compression_level IN ('L1', 'L2', 'L3')),
    compressed_at   TEXT,                      -- 压缩时间
    
    -- 时间戳
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    started_at      TEXT,
    finished_at     TEXT,
    
    -- 元数据
    session_id      TEXT NOT NULL,             -- 所属会话
    project         TEXT                       -- 所属研究项目
);

CREATE INDEX idx_crt_parent ON crt_nodes(parent_id);
CREATE INDEX idx_crt_status ON crt_nodes(status);
CREATE INDEX idx_crt_project ON crt_nodes(project);
CREATE INDEX idx_crt_compression ON crt_nodes(compression_level);
```

#### 4.2.3 反馈追踪（引擎一）

```sql
CREATE TABLE feedback_items (
    id              TEXT PRIMARY KEY,          -- UUID
    source          TEXT NOT NULL,             -- 来源：引擎二 / 人类 / zhangcy-nature-review
    source_detail   TEXT,                      -- 来源详情（如 "engine_2::red_team::round_2"）
    content         TEXT NOT NULL,             -- 审稿意见原文
    category        TEXT,                      -- 意见分类（方法/数据/逻辑/表述/其他）
    severity        TEXT DEFAULT 'medium'
                    CHECK(severity IN ('critical', 'high', 'medium', 'low', 'suggestion')),
    
    -- 状态追踪
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open', 'in_progress', 'resolved', 'wont_fix', 'duplicate')),
    resolved_in_version TEXT,                  -- 在哪个版本解决
    resolution_note TEXT,                      -- 解决说明
    
    -- 关联
    crt_node_id     TEXT REFERENCES crt_nodes(id), -- 产生此意见的审稿节点
    paper_version   TEXT,                      -- 审稿时论文版本
    
    -- 时间戳
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT,
    
    -- 修改溯源（子表，见下方）
    modification_count INTEGER DEFAULT 0
);

-- 反馈 → 修改记录（一次审稿意见可能对应多次修改）
CREATE TABLE modification_log (
    id              TEXT PRIMARY KEY,
    feedback_id     TEXT NOT NULL REFERENCES feedback_items(id),
    version_id      TEXT NOT NULL REFERENCES versions(id),
    action          TEXT NOT NULL,             -- 修改动作描述
    file_changes    TEXT,                      -- 文件变更摘要（哪些文件、哪些行）
    delta_size      INTEGER,                  -- 变更规模（新增/删除行数）
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_feedback_status ON feedback_items(status);
CREATE INDEX idx_feedback_source ON feedback_items(source);
```

#### 4.2.4 版本记录（引擎一）

```sql
CREATE TABLE versions (
    id              TEXT PRIMARY KEY,          -- UUID
    project         TEXT NOT NULL,             -- 所属项目
    version_type    TEXT NOT NULL
                    CHECK(version_type IN ('research', 'review_iteration', 'milestone', 'review_report')),
    label           TEXT NOT NULL,             -- 人类可读标签（如 "[审稿-v5] 处理意见#3"）
    parent_id       TEXT REFERENCES versions(id), -- 父版本
    
    -- 产物引用（不复制文件，只存路径+哈希）
    artifact_paths  TEXT,                      -- 文件路径（逗号分隔）
    artifact_hashes TEXT,                      -- SHA256 哈希（逗号分隔）
    
    -- 关联
    crt_node_id     TEXT REFERENCES crt_nodes(id),
    related_feedback_ids TEXT,                 -- 关联的反馈意见 ID
    
    -- 摘要
    change_summary  TEXT,                      -- 变更摘要（自动生成）
    total_lines     INTEGER,                   -- 总行数
    
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT DEFAULT 'auto'        -- auto | human
);

CREATE INDEX idx_versions_project ON versions(project);
CREATE INDEX idx_versions_type ON versions(version_type);
```

#### 4.2.5 审稿记录（引擎一干净房间）

```sql
CREATE TABLE review_sessions (
    id              TEXT PRIMARY KEY,
    session_type    TEXT NOT NULL,             -- 'cleanroom' | 'inline'
    paper_version   TEXT NOT NULL,             -- 审稿时的论文版本
    review_standard TEXT,                      -- 使用的审稿标准（nature-review / nature-review-strict / engine_2_red_team）
    isolation_confirmed INTEGER DEFAULT 0,     -- 0=未确认, 1=已确认隔离
    opinion_count   INTEGER DEFAULT 0,         -- 产生的审稿意见数
    opinion_ids     TEXT,                      -- 关联的 feedback_items ID
    duration_sec    REAL,                      -- 审稿耗时
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_review_type ON review_sessions(session_type);
```

#### 4.2.6 幽灵信号（引擎四）

```sql
CREATE TABLE ghost_signals (
    id              TEXT PRIMARY KEY,
    crt_node_id     TEXT REFERENCES crt_nodes(id),
    signal_type     TEXT NOT NULL,             -- 'systematic_bias' | 'anomaly_pattern' | 'unexplained_residual'
    region          TEXT,                      -- 区域（如 "Tibetan_Plateau"）
    description     TEXT NOT NULL,
    severity        TEXT DEFAULT 'yellow'
                    CHECK(severity IN ('yellow', 'orange', 'red')),
    multi_model_check TEXT,                    -- 多模式对比结果
    status          TEXT DEFAULT 'open'
                    CHECK(status IN ('open', 'investigating', 'resolved', 'dismissed', 'archived')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);
```

### 4.3 上下文数据包结构（JSON Schema）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CRT Context Packet",
  "type": "object",
  "required": ["packet_id", "current_task", "parent_summary", "global_state"],
  "properties": {
    "packet_id": {"type": "string"},
    "current_task": {
      "type": "object",
      "required": ["step_number", "action", "expected_output"],
      "properties": {
        "step_number": {"type": "integer"},
        "action": {"type": "string", "maxLength": 500},
        "expected_output": {"type": "string"},
        "deadline": {"type": "string", "format": "date-time"}
      }
    },
    "parent_summary": {
      "type": "object",
      "required": ["node_id", "what_was_done", "why_this_next"],
      "properties": {
        "node_id": {"type": "string"},
        "what_was_done": {"type": "string", "maxLength": 500},
        "why_this_next": {"type": "string", "maxLength": 500}
      }
    },
    "global_state": {
      "type": "object",
      "properties": {
        "confirmed_findings": {
          "type": "array",
          "items": {"type": "string", "maxLength": 200},
          "maxItems": 10
        },
        "active_hypotheses": {
          "type": "array",
          "items": {"type": "string", "maxLength": 200},
          "maxItems": 5
        },
        "physics_fence_status": {"type": "string", "enum": ["all_green", "warnings", "review_needed", "rejected"]},
        "unresolved_anomalies": {
          "type": "array",
          "items": {"type": "string", "maxLength": 200},
          "maxItems": 5
        },
        "direction_drift_flag": {"type": "boolean"}
      }
    },
    "on_demand": {
      "type": "object",
      "properties": {
        "methods": {
          "type": "array",
          "items": {"$ref": "#/$defs/method_ref"}
        },
        "literature": {
          "type": "array",
          "items": {"$ref": "#/$defs/literature_ref"}
        }
      }
    },
    "human_instruction": {"type": "string"}
  },
  "$defs": {
    "method_ref": {
      "type": "object",
      "properties": {
        "method_id": {"type": "string"},
        "name": {"type": "string"},
        "definition": {"type": "string"}
      }
    },
    "literature_ref": {
      "type": "object",
      "properties": {
        "title": {"type": "string"},
        "doi": {"type": "string"},
        "relevance_summary": {"type": "string", "maxLength": 200}
      }
    }
  }
}
```

---

## 5. 接口规范

### 5.1 CLI 命令

```
polaris
├── polaris init                  # 初始化项目：创建 polaris.yaml + 目录结构 + SQLite
│
├── polaris method                # 引擎O：方法库
│   ├── list [--domain] [--status] # 列出方法
│   ├── search <query>            # 自然语言搜索
│   ├── show <id>                 # 查看方法详情
│   ├── approve <id> [y/n]       # 审批待确认方法
│   └── stats                     # 方法库统计
│
├── polaris track                 # 引擎一：产物追踪
│   ├── status [project]          # 当前项目状态（哪些意见未解决）
│   ├── feedback <id>             # 查看某条意见的完整轨迹
│   ├── diff <v1> <v2>           # 版本差异
│   └── versions [project]        # 列出项目所有版本
│
├── polaris review                # 引擎一 + 引擎二
│   ├── cleanroom <paper.md>      # 干净房间审稿
│   ├── deep <paper.md>           # 引擎二深度验证
│   ├── redteam <paper.md>        # 红队模式
│   └── compare <v1> <v2>        # 对比两次审稿意见
│
├── polaris migrate               # 引擎三：方法迁移
│   ├── run <method_id> --regions # 迁移到指定区域
│   ├── status <job_id>           # 查看迁移进度
│   └── report <job_id>           # 生成迁移报告
│
├── polaris discover              # 引擎四：自主发现
│   ├── start "<研究方向>"        # 启动自主发现循环
│   ├── status                    # 查看循环状态
│   ├── pause / resume / stop     # 控制循环
│   └── brief [--weekly]          # 生成发现简报
│
└── polaris config                # 配置管理
    ├── show                      # 显示当前配置
    ├── set <key> <value>         # 设置配置项
    └── validate                  # 验证配置完整性
```

### 5.2 引擎间内部接口（Python API）

```python
# ——— 引擎O：方法库 ———
class MethodLibrary:
    def search(query: str, domain: str = None, method_type: str = None) -> list[Method]
    def get(method_id: str) -> Method
    def register(method: Method) -> str  # 返回 method_id
    def approve(method_id: str, approved: bool) -> None
    def record_invocation(method_id: str, crt_node_id: str, params: dict, status: str) -> str

# ——— 引擎一：产物追踪 ———
class Tracker:
    def capture_version(project: str, version_type: str, artifacts: list[str], 
                        crt_node_id: str = None) -> str  # 返回 version_id
    def create_feedback(content: str, source: str, crt_node_id: str) -> str  # 返回 feedback_id
    def resolve_feedback(feedback_id: str, version_id: str, note: str) -> None
    def get_open_feedback(project: str = None) -> list[FeedbackItem]
    def get_feedback_timeline(feedback_id: str) -> FeedbackTimeline
    def launch_cleanroom_review(paper_path: str, standard: str) -> ReviewSession
    def suggest_stop(project: str) -> StopSuggestion

# ——— 引擎二：深度验证 ———
class Verifier:
    def deep_verify(paper_path: str, modes: list[str] = None) -> VerificationReport
    def cross_domain_review(paper_path: str) -> CrossDomainReport
    def red_team_audit(paper_path: str) -> RedTeamReport
    def methodology_trace(paper_path: str) -> TraceReport
    def sensitivity_analysis(model_code: str, params: dict) -> SensitivityHeatmap
    def competing_hypotheses(paper_path: str) -> CompetingHypothesesReport

# ——— 引擎三：方法迁移 ———
class Migrator:
    def migrate(method_id: str, source_region: str, target_regions: list[str]) -> str  # 返回 job_id
    def compare(method_id: str, regions: list[str]) -> ComparisonReport
    def get_anomalies(job_id: str) -> list[Anomaly]

# ——— 引擎四：自主发现 ———
class DiscoveryLoop:
    def start(direction: str, config: LoopConfig = None) -> str  # 返回 session_id
    def pause(session_id: str) -> None
    def resume(session_id: str) -> None
    def stop(session_id: str) -> None
    def get_status(session_id: str) -> LoopStatus
    def generate_brief(session_id: str, period: str = 'weekly') -> DiscoveryBrief
    def request_human_decision(session_id: str, node_type: str, context: dict) -> HumanDecision
```

### 5.3 LLM 网关接口

```python
class LLMGateway:
    """统一 LLM 调用接口，适配 DeepSeek / 智谱 GLM"""
    
    def chat(
        messages: list[dict],           # OpenAI 格式消息列表
        model: str = "deepseek-chat",   # 模型名
        system_prompt: str = None,      # System Prompt（可选，覆盖 messages 中的 system）
        temperature: float = 0.3,       # 科研场景偏低温度
        max_tokens: int = 4096,
        cleanroom: bool = False,        # 是否使用干净房间（全新会话）
        timeout_sec: int = 120
    ) -> LLMResponse
    
    def parallel_chat(
        requests: list[ChatRequest],    # 多个并行请求
        max_concurrency: int = 5
    ) -> list[LLMResponse]              # 并行返回

class ChatRequest:
    messages: list[dict]
    model: str
    system_prompt: str
    temperature: float
    cleanroom: bool          # True = 独立会话，False = 继承当前会话
    metadata: dict           # 追踪元数据（crt_node_id, engine 等）
```

---

## 6. 核心模块设计

### 6.1 CRT 压缩器（`src/crt/compressor.py`）

```python
class CRTCompressor:
    """L1 → L2 → L3 自动压缩"""
    
    # 触发条件
    L1_TO_L2_THRESHOLD = 10    # 超过10个L1节点 → 最老的压缩到L2
    L2_TO_L3_THRESHOLD = 100   # 超过100个L2节点 → 同类合并到L3
    MERGE_SIMILARITY = 0.7     # 相似度阈值（基于嵌入/关键词Jaccard）
    
    def compress(self, session_id: str) -> CompressionReport:
        """
        1. 检查 L1 节点数 > THRESHOLD → 压缩最老的 N-10 个到 L2
        2. 检查 L2 节点数 > THRESHOLD → 合并同类 L2 → L3 元节点
        3. 连续3个同类 L1 节点 → 主动建议合并
        """
    
    def generate_summary(self, node: CRTNode) -> str:
        """从节点完整内容生成 ≤500 字结构化摘要"""
        # 模板：做了什么 → 用了什么方法 → 得到了什么 → 验证结果 → 下一步
    
    def merge_to_meta(self, nodes: list[CRTNode]) -> MetaNode:
        """合并同类节点为元节点"""
```

### 6.2 上下文数据包组装器（`src/crt/context_packet.py`）

```python
class ContextPacketBuilder:
    """为每一步组装上下文数据包"""
    
    def build(self, 
              current_node: CRTNode,
              parent_node: CRTNode,
              session_id: str) -> ContextPacket:
        """
        1. 当前任务：从 current_node.action 提取
        2. 父节点摘要：从 parent_node.result_summary 读取（若 L2 压缩过则直接用）
        3. 全局状态快照：
           - 查询该 session 下所有 confirmed_findings
           - 查询活跃 hypotheses
           - 查询 physics_fence 最新状态
           - 查询未解决异常
        4. 按需加载：根据 current_node 的 domain/keywords 检索引擎O方法
        5. 人类指令：从 latest human_intervention 读取
        """
    
    def estimate_tokens(self, packet: ContextPacket) -> int:
        """估算上下文数据包 token 数，确保不超过窗口"""
```

### 6.3 物理围栏（`src/harness/physics_fence.py`）

```python
class PhysicsFence:
    """三级物理约束检查"""
    
    RULES = {
        # 🟢 WARNING：不影响流程，仅记录
        "specific_humidity_nonnegative": {
            "check": "np.all(data.q >= -1e-12)",
            "severity": "WARNING",
            "on_fail": "clip to 0; if >1% negative, flag for source check"
        },
        # 🟡 REVIEW：暂停，人类可放行
        "mass_budget_closure": {
            "check": "abs(mass_residual) < 0.15",
            "severity": "REVIEW",
            "on_fail": "pause; human review required; multi-model comparison triggered"
        },
        # 🔴 REJECT：冻结，必须修改
        "olr_physical_range": {
            "check": "np.all((data.olr > 0) & (data.olr < 500))",
            "severity": "REJECT",
            "on_fail": "freeze node; check data source; possible unit error"
        }
    }
    
    def check(self, data: xr.Dataset, context: dict) -> FenceReport:
        """对所有已注册的规则逐一检查，返回分级报告"""
```

### 6.4 自动版本捕获（`src/utils/file_watcher.py`）

```python
class AutoVersionCapture:
    """从用户自然操作中自动捕获版本"""
    
    def on_cli_command(self, command: str, result: dict):
        """
        监听 CLI 操作，自动判定是否触发版本保存：
        - 代码运行结束且输出文件 → [研究] 版本
        - cleanroom review 完成 → [审稿] 记录
        - 人类执行修改指令 → [审稿迭代] 版本
        """
    
    def on_file_change(self, path: str, change_type: str):
        """
        监听 workspace 文件变动：
        - 论文 .md 被编辑（满足条件）→ 触发版本快照
        - 新图/数据文件出现 → 关联到当前活跃节点
        """
```

---

## 7. 安全与约束

### 7.1 LLM 调用安全

| 约束 | 实现 |
|:---|:---|
| **API Key 不外泄** | 从环境变量或 `polaris.yaml`（gitignore）读取，不硬编码 |
| **数据最小化** | 传给 LLM 的数据只包含分析所需切片，不传完整数据集 |
| **干净房间强制** | `cleanroom=True` 时禁止传入任何历史消息，SDK 层强制校验 |
| **速率限制** | 每引擎设置独立的 `max_tokens_per_minute`，防止账单爆炸 |

### 7.2 代码执行安全

| 约束 | 实现 |
|:---|:---|
| **禁止系统调用** | LLM 生成的代码在执行前过滤 `os.system` / `subprocess` 等 |
| **工作区限制** | 所有文件读写限制在 `workspace/` 和 `data/` 内 |
| **超时保护** | 每次代码执行设置 `timeout=600`（10分钟） |
| **资源上限** | 引擎四循环设置全局 `max_api_calls_per_session=10000` |

### 7.3 数据完整性

| 约束 | 实现 |
|:---|:---|
| **产物哈希** | 每次版本保存自动计算 SHA256，定期校验 |
| **CRT 不可变** | 节点一旦标记为 `completed`，内容不可修改（仅可追加 note） |
| **审计日志** | 所有人工审批操作记录到独立的 `audit_log` 表 |

---

## 8. 里程碑排期

### 8.1 五阶段路线图

```
阶段0：摸底（W1）
  └─→ 里程碑 M0：50 题气象编码测试基准 + 首次通过率基线

阶段1：夯实（W2-4）
  └─→ 里程碑 M1：引擎O方法库可运行（Manual CRUD + 种子方法入库）
                引擎一自动版本捕获可运行

阶段2：单步闭环（W5-8）
  └─→ 里程碑 M2：Coder + Reviewer 在一个任务内完成单次审稿闭环
                引擎二基础验证（红队模式 / 方法论溯源）可运行

阶段3：迭代闭环（W9-12）
  └─→ 里程碑 M3：打回-修改循环（上限3次）
                引擎四最小闭环（50步）可运行
                引擎三基础迁移可运行

阶段4：拓扑管理（M4+）
  └─→ 里程碑 M4：CRT 从线性日志升级为 DAG
                L3 压缩 + 负结果沉积层
                发现简报自动生成
```

### 8.2 每个阶段的交付物与验证标准

| 阶段 | 时间 | 核心交付物 | 验证标准 |
|:---|:---|:---|:---|
| **M0 摸底** | W1 | 50 题测试基准；LLM 气象编码能力基线报告 | 50 题全部有标准答案；首次通过率数据可追溯 |
| **M1 夯实** | W2-4 | 引擎O（SQLite + CRUD + 搜索）；引擎一（自动捕获 + 反馈追踪）；10 个种子方法入库 | 手动录入3个 Sahara 方法并成功检索调用；自动捕获到一次审稿-修改的完整轨迹 |
| **M2 单步闭环** | W5-8 | Coder→Reviewer 单次审查；引擎二红队/方法论溯源；干净房间审稿 | 对一个已知论文跑红队审查，产出 ≥3 个有效质疑；干净房间 vs 普通审稿意见差异度 ≥30% |
| **M3 迭代闭环** | W9-12 | 打回-修改循环；引擎四 50 步闭环；引擎三 3 区域迁移 | 引擎四在以 Sahara 为起点的任务中自主完成 50 步且方向不漂移；引擎三完成 Sahara→中亚→澳大利亚迁移 |
| **M4 拓扑管理** | M4+ | CRT DAG 可视化；L3 压缩；发现简报；收手标准学习 | 人工审批积压率 <20%；L3 自动合并准确率 >80%；发现简报人类满意度 >70% |

### 8.3 依赖关系

```
M0 ──→ M1 ──→ M2 ──→ M3 ──→ M4
              │               │
              └── 引擎三 ←────┘（M3 并行开发，M4 深度集成）
```

- M0 是全部后续阶段的前提——如果 LLM 首次通过率 <20%，M1 延长，先积累 Skill
- M1 是 M2-M4 的地基——方法库和追踪系统是所有上层引擎的依赖
- M2 和 M3 之间有一个**验证关口**：单次审稿闭环通过率 >60% 才能进入迭代闭环
- 引擎三可以在 M2 阶段启动并行开发，但深度集成在 M4

---

## 9. 附录

### 9.1 配置文件模板（`polaris.yaml`）

```yaml
# Polaris 全局配置
version: "1.0"

# LLM 配置
llm:
  primary:
    provider: deepseek
    api_key: ${DEEPSEEK_API_KEY}    # 从环境变量读取
    model: deepseek-chat
    base_url: https://api.deepseek.com/v1
    max_tokens: 4096
    temperature: 0.3
  fallback:
    provider: zhipu
    api_key: ${ZHIPU_API_KEY}
    model: glm-4-plus
    base_url: https://open.bigmodel.cn/api/paas/v4

# 路径配置
paths:
  workspace: ./workspace
  data: ./workspace/data
  scripts: ./workspace/scripts
  outputs: ./workspace/outputs
  papers: ./workspace/papers
  db: ./polaris.db

# 引擎配置
engines:
  engine_o:
    auto_register_on_success: true   # 成功分析自动创建方法条目
    approval_required: true          # 需要人类审批
    auto_deprecate_days: 90          # 超期未审批自动降级

  engine_1:
    auto_capture: true               # 自动版本捕获
    cleanroom_default: true          # 审稿默认干净房间
    max_iterations_per_node: 5       # 硬退出上限
    stop_rule:
      consecutive_zero_feedback: 2   # 连续 0 意见轮数 → 建议收手
      min_feedback_gap_days: 1       # 审稿最小间隔

  engine_2:
    parallel_experts: 3              # 多角色辩论的专家数
    red_team_min_issues: 3           # 红队最少质疑数
    sensitivity_default_range: 0.3   # 参数扫描默认 ±30%

  engine_3:
    default_regions:                 # 默认迁移区域
      - north_africa
      - central_asia
      - australia
      - north_america_southwest
    auto_escalate: true              # 异常自动路由到引擎二
    anomaly_threshold_sigma: 2.0     # 差异标记阈值

  engine_4:
    max_steps: 200                   # 单次循环最大步数
    max_api_calls: 10000             # 单次循环最大 API 调用
    max_runtime_hours: 48            # 单次循环最大运行时间
    report_interval_steps: 10        # 每 N 步生成阶段简报
    human_decision_timeout_hours: 72 # 人类决策超时 → 自动暂停

# 安全限制
security:
  sandbox:
    allowed_imports:                 # LLM 代码白名单导入
      - numpy
      - scipy
      - xarray
      - pandas
      - matplotlib
      - cartopy
      - netCDF4
      - cfgrib
    forbidden_calls:                 # 禁止的系统调用
      - os.system
      - subprocess
      - eval
      - exec
    execution_timeout_sec: 600

# 物理围栏
physics_fence:
  rules:
    - name: specific_humidity_nonnegative
      severity: WARNING
    - name: mass_budget_closure
      severity: REVIEW
    - name: olr_physical_range
      severity: REJECT
```

### 9.2 修订历史

| 版本 | 日期 | 变更 |
|:---|:---|:---|
| v1.0 | 2026-07-16 | 初始版本：技术选型、系统架构、数据模型、接口规范、里程碑排期 |

---

> **下一阶段**：M0 摸底——建立 50 题气象编码测试基准，测量 LLM 首次通过率基线。
