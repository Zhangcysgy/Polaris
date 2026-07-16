# Polaris GitHub 协作规范

> 核心原则：**代码和框架公开，数据和结果留在本地。**

---

## 一、上传/不上传对照表

| 类型 | 上传到 GitHub？ | 原因 |
|:---|:---:|:---|
| 代码（`src/polaris/`） | ✅ 是 | 框架本身 |
| 配置模板（`polaris.yaml`） | ✅ 是 | 不含真实 API Key |
| 文档（`docs/`） | ✅ 是 | PRD、TDD、协作规范 |
| 种子方法（`seed.py`） | ✅ 是 | 通用示例数据 |
| 测试基准（`benchmarks/`） | ✅ 是 | 50题+评分脚本 |
| 实验脚本（`experiments/`） | ✅ 是 | 不含个人数据 |
| 精选展示（`showcases/`） | ✅ 手动 | 代表性的产出截图/简报 |
| 真实 API Key | ❌ 否 | 安全——仅存环境变量 |
| 下载的原始数据（NetCDF/GRIB 等） | ❌ 否 | 文件太大（GB级），`.gitignore` 已排除 |
| 分析产出（图、表、中间结果） | ❌ 否 | `projects/`和`reports/`已在`.gitignore` |
| SQLite 数据库（`polaris.db`） | ❌ 否 | 含个人研究轨迹 |
| 个人研究项目（`projects/*`） | ❌ 否 | 仅保留`_template/`模板 |
| IDE 配置（`.vscode/`等） | ❌ 否 | `.gitignore`已排除 |

---

## 二、日常操作

### 场景 1：改进代码 / 新增功能

```bash
# 日常开发循环
git add src/polaris/               # 只加代码
git commit -m "feat: 新增XXX功能"
git push
```

### 场景 2：跑完真实实验后同步代码变更

```bash
# 1. 检查哪些文件有变更
git status

# 2. 确保敏感文件不会误提交（.gitignore 已保护以下目录）
#    polaris.db
#    projects/*
#    reports/*
#    data/crt/nodes/*
#    experiments/results/
#    benchmarks/results/

# 3. 只提交代码层面改动
git add src/
git add docs/             # 如果更新了文档
git add polaris.yaml      # 如果改了默认配置（⚠️先确认无API Key）
git commit -m "feat: 引擎四接入真实数据下载，M5完成"
git push
```

### 场景 3：展示实验产出

```bash
# 在仓库里建展示目录
mkdir -p showcases/<项目名>

# 手动复制精选产出（不在 .gitignore 中，会被追踪）
cp <报告路径> showcases/<项目名>/
cp <图片路径> showcases/<项目名>/

# 提交
git add showcases/
git commit -m "showcase: <项目名> 的审稿报告+发现简报"
git push
```

### 场景 4：方法库积累大量经验后同步种子数据

```bash
# 1. 导出方法库摘要（可选）
polaris method list --status verified > showcases/method_library.md

# 2. 将代表性方法提炼到 seed.py 的社区方法函数
#    编辑 src/polaris/engine_o_methods/seed.py

# 3. 提交
git add src/polaris/engine_o_methods/seed.py
git commit -m "feat: 社区种子方法更新（新增N个验证模板）"
git push
```

---

## 三、推荐 Git 分支策略

```
main          ← 稳定版本，供外部 clone 使用
  │
  ├─ dev      ← 日常开发分支
  │
  ├─ m5-loop  ← 大型功能分支（完成后合并到 dev→main）
  │
  └─ experiment/xxx ← 探索性实验分支
```

```bash
# 初始设置
git checkout -b dev
git push -u origin dev

# 日常在 dev 上开发
git checkout dev
# ... 写代码 ...
git add src/
git commit -m "..."
git push

# 功能完成后合并到 main
git checkout main
git merge dev
git push
```

---

## 四、首次推送到 GitHub

```bash
cd H:\Polaris
git init
git add .
git commit -m "Polaris v0.1.0: 五引擎 AI 科研自主发现系统框架"
git remote add origin <your-repo-url>
git push -u origin main
```

**推送前确认：**
- [ ] `polaris.yaml` 中没有真实的 API Key（当前仅引用环境变量 ✅）
- [ ] `data/polaris.db` 已被 `.gitignore` 排除（✅）
- [ ] `projects/` 下的个人研究不在仓库中（仅保留 `_template/` ✅）
- [ ] 种子数据中无个人身份信息（✅）

---

## 五、版本号规范

```
v0.1.0  — 五引擎框架完整（当前版本）
v0.2.0  — M4: 引擎三接入真实数据
v0.3.0  — M5: 引擎四 50步闭环
v0.4.0  — 首个个案完整运行
v0.5.0  — 社区可用的第一个正式版
v1.0.0  — Polaris 自主发现首个经人类确认的科学成果
```
