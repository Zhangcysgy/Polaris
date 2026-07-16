---
name: zhangcy-python-coding
description: >-
  Use this skill for writing, reviewing, or refactoring Python code in scientific computing and dust-lightning research. Covers: data processing with pandas/xarray/NumPy/NetCDF, publication-quality matplotlib figures, file naming (NN_english_description.py), ProjectConfig dataclass, and code quality improvements (type annotations, Chinese docstrings, logging over print, data assertions, vectorized operations, code review with subagent).
trigger: /python-coding
---

# zhangcy-python-coding Skill

You are a Python coding assistant that enforces project-specific standards for the atmospheric science / dust-lightning research project. Follow the rules below in all code you write, review, or refactor.

## 1. Python Code Rules (01-coding-rules)

### Section Separators
For files ≥20 lines or with multiple logical sections, use:
```python
# ==================== 1. Data Loading ====================

# -------------------- 1.1 Read Raw Data --------------------
```
- Level 1: `# ===` with exactly 20 `=`, 1 blank line before and after, Chinese title ≤10 chars
- Level 2: `# ---` with 20 `-`, sub-numbering `1.1`, `1.2`
- Standard block order: `1. 导入库与配置` → `2. 数据加载` → `3. 数据清洗` → `4. 特征工程` → `5. 统计分析` → `6. 可视化` → `7. 结果保存`

### Comments (Chinese, explain WHY not WHAT)
- Core algorithms, magic numbers, complex logic → must comment
- Obvious code (`import pandas`) → no comment
- Multi-line comments use `"""..."""`
- Good: `df['ratio'] = df['A'] / df['B']  # 归一化处理，消除量纲影响`
- Bad: `df['ratio'] = df['A'] / df['B']  # 计算 A 除以 B`

### Functions
- **Must have docstring** (Chinese): brief, params, returns, notes
- **Must have type annotations**: all params and return values
- **Naming**: lowercase_english_with_underscores, verb-first (`calculate_cape`, `load_era5`)
- **Length**: ≤50 lines, split if exceeded
- **Single responsibility**: one thing per function

```python
def calculate_cape(t2m: np.ndarray, td2m: np.ndarray, blh: np.ndarray) -> np.ndarray:
    """
    计算对流有效位能（CAPE）

    参数:
        t2m: 2米温度 (K)
        td2m: 2米露点温度 (K)
        blh: 边界层高度 (m)

    返回:
        CAPE 值 (J/kg)
    """
    ...
```

### Variable Naming
- English, meaningful, no pinyin, no single-letter (loop vars excepted)
- Booleans: `is_`, `has_`, `should_` prefix
- Constants: `UPPER_CASE` (`MAX_TEMPERATURE`)
- DataFrames: `df_raw`, `df_clean`, `df_merged`

### Data Processing
- **Vectorized first**: `df['new'] = df['A'] + df['B']`, no for loops
- **Chained operations**: one step per line, wrapped in parentheses
- **Use `.loc`**, never chained indexing

```python
df_clean = (
    df_raw
    .dropna(subset=['temperature'])
    .query('temperature > 0')
    .assign(wind_speed=lambda x: np.sqrt(x['u']**2 + x['v']**2))
)
```

### xarray / NetCDF Conventions
- All gridded data uses `(time, lat, lon)` dimension order
- Coordinate variables must have `units` and `long_name` attributes
- Global attributes: `source`, `history`, `time_window`
- Integer variables: use minimum sufficient dtype (`int8` for 0/1 flags, `int32` for plume_id)
- Batch load monthly files with `xr.open_mfdataset(..., combine='by_coords', chunks={'time': 24})`
- Select with `.sel()` using labels, not integer indices
- Save with encoding for compression: `{'dtype': 'int8', 'zlib': True, 'complevel': 4}`

**⚠️ 数据处理失败模式：**

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|----------|------------|
| 数据加载报 `FileNotFoundError` | 检查路径拼写，改用 `Path(__file__).parent` 相对路径 | 提示用户确认数据文件位置，全量搜索目录 |
| 大文件加载 OOM（内存溢出） | 添加 `chunksize` 参数或用 `dask` 分块加载 | 只加载前 N 行做代码验证，提示用户分批处理 |
| assert 检查失败（数据质量问题） | 检查输入数据是否有异常值/缺失/类型错误 | `logger.warning()` 记录后继续，标注自动跳过的异常行 |
| xarray 维度顺序不匹配 | 用 `.transpose('time', 'lat', 'lon')` 重排 | 自动检测维度名后重排：`ds.squeeze().expand_dims(...)` |

### Data Quality Checks
Assert at entry and exit of every processing step:
- Dimension checks: `assert ds.dims['lat'] == N`
- Value range checks: `assert var.min() >= 0 and var.max() <= 4`
- Missing data checks: `assert missing_ratio < 0.5`
- Time continuity: `assert ds.time.diff('time').min() == np.timedelta64(1, 'h')`
- Assert failure → stop and report. Recoverable issues → `logger.warning()`

### Logging
```python
import logging
logger = logging.getLogger(__name__)
logger.info(...)
logger.warning(...)
```
`print()` only for end-user-facing prompts.

### DRY
Same logic ≥3 occurrences → extract to function. Same literal ≥3 occurrences → define as constant.

## 2. Nature-Style Plots (02-nature-plots)

### Global Settings (run once at script start)
```python
plt.rcParams['font.family'] = 'Arial'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['lines.linewidth'] = 1.5
plt.rcParams['axes.linewidth'] = 0.8
sns.set_style('white')
sns.set_context('paper')
```

### Colorblind-Friendly Palette
```python
COLORS = {
    'blue':   '#0072B2',
    'orange': '#D55E00',
    'green':  '#009E73',
    'red':    '#CC79A7',
    'purple': '#9400D3',
    'gray':   '#999999',
}
```

### Figure Sizes (inches)
| Type | Width | Use |
|------|-------|-----|
| Single column | 3.5 | Single panel |
| Double column | 7.0 | Large figure or subplots |
| 2×2 subplots | 7.0 × 5.5 | Four-panel |

### Labels & Style
- All English (titles, axis labels, legends)
- Subplot labels: `(a)`, `(b)`, `(c)`, `(d)`
- Inward ticks: `ax.tick_params(axis='both', direction='in', length=3)`
- No grid (Nature style)

### Save (PDF + PNG)
```python
fig.savefig('fig1_result.pdf', dpi=300, bbox_inches='tight', pad_inches=0.05)
fig.savefig('fig1_result.png', dpi=300, bbox_inches='tight')
```

### Toolkit Functions (to avoid repetition)
```python
def create_figure(n_rows=1, n_cols=1, size='single'):
    """创建 Nature 风格画布。size: 'single'(3.5") 或 'double'(7.0")"""
    w = 3.5 if size == 'single' else 7.0
    h = w * 0.7 * n_rows / n_cols
    return plt.subplots(n_rows, n_cols, figsize=(w, h))

def save_figure(fig, filename, out_dir):
    """保存 PDF + PNG"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for fmt, ext in [('pdf', '.pdf'), ('png', '.png')]:
        fig.savefig(out_dir / f'{filename}{ext}', dpi=300, bbox_inches='tight')
    plt.close(fig)
```

## 3. File Organization (03-file-organization)

### Naming Convention
`NN_english_description.py` — two-digit sequence + underscore + lowercase english description
- Examples: `01_data_loading.py`, `02_wwlln_gridding.py`, `03_cem_matching.py`
- Utilities: `utils/01_visualization_tools.py`
- Main entry: `main.py` (no sequence number)

### Config File Pattern (`utils/01_config.py`)
Use a `ProjectConfig` dataclass with typed fields, auto-creating directories in `__post_init__`:
```python
@dataclass
class ProjectConfig:
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = project_root / 'Data'
    raw_dir: Path = data_dir / 'raw_data'
    processed_dir: Path = data_dir / 'processed_data'
    results_dir: Path = project_root / 'Results'
    lat_range: tuple = (5.75, 42.25)
    lon_range: tuple = (-11.5, 77.25)
    start_date: str = '2017-12-01'
    end_date: str = '2022-11-30'
    ring2_ratio: int = 10
    ring1_ratio: int = 50
    seed: int = 42

CONFIG = ProjectConfig()
```

## 4. 代码审查机制（Code Review）

每次生成或修改 Python 代码后，**必须执行代码审查**，不能跳过。

### 审查流程

**Step 1: 写出代码后，保存到文件**

先用 Write 工具将代码写入 `.py` 文件。

**Step 2: 启动 subagent 审查**

先读取 `references/code_review.md` 获取完整审查 prompt，然后使用 Agent 工具启动一个独立的审查 subagent，将 prompt 中的 `{文件路径}` 替换为实际文件路径。

**Step 3: 根据审查结果处理**

- 审查通过（无问题）→ 直接展示给用户
- 仅有 P1 建议 → 按建议修改后展示，告知用户做了优化
- 有 P0 问题 → **必须修复全部 P0 问题**，然后重新审查，直到通过为止

**Step 4: 向用户报告审查结果**

在最终回复中附上一行审查结论，如：
```
📋 代码审查: ✅ 通过 | 3 个 P1 建议已采纳
```
或
```
📋 代码审查: ❌ 发现 2 个 P0 问题 → 已修复 → ✅ 通过
```

### 关键原则

- 审查人必须是 **独立 subagent**，不能自己审自己写的代码
- 审查必须严格——宁可误报也不要漏报
- 修复 P0 问题是硬性要求，不可跳过
- 审查不通过时不要向用户展示未修复的代码

**⚠️ 代码审查失败模式：**

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|----------|------------|
| subagent 不可用（超时/资源限制） | 手动对照 code_review.md 清单逐项自检 | 在回复中声明"未启动独立审查"，附自检清单结果 |
| subagent 审查报 P0 问题但修改建议不可行 | 评估 P0 严重程度，尝试替代方案 | 保留 P0 注释，向用户解释并征求意见 |
| 用户代码文件路径不存在 | 提示用户检查路径，或粘贴代码文本 | 接受用户粘贴的代码片段审查 |
| 用户代码文件 > 500 行 | 按函数/模块分段审查 | 先审查核心函数，次要部分快速扫描 |

### Script Template
```python
"""
NN_script_name.py

功能：
    简短描述

输入：
    processed_data/xxx/

输出：
    processed_data/yyy/
"""

import logging
import numpy as np
import pandas as pd
from pathlib import Path
from utils.config import CONFIG

logger = logging.getLogger(__name__)


def main():
    """主流程"""
    logger.info("开始执行...")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    main()
```

---

## ⚠️ 失败模式

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|---------|------------|
| module 导入报错（ModuleNotFoundError） | `pip install <module>` | 检查 Python 环境是否激活（`.venv\Scripts\activate`） |
| 数据量过大导致 OOM | 用 `chunksize` / `dask` 分块加载 | 减少数据范围或增加内存 |
| NetCDF 文件路径不存在 | `dir Data\raw_data\` 检查文件是否已下载 | 运行下载脚本 `python Code/download_data/download_ERA5.py` |
| matplotlib 中文显示为方框 | 检查 `simhei.ttf` 是否存在 | `font_manager.fontManager.addfont('C:/Windows/Fonts/simhei.ttf')` |
| xarray 加载多文件时维度不匹配 | 检查所有文件的 time/lat/lon 维度是否一致 | 用 `xr.open_mfdataset(combine='by_coords')` |
| GitHub Copilot 建议的代码不符合规范 | 不接受建议，手动编写 | 用 `zhangcy-python-coding` 规范审查 |
| 代码审查 subagent 报错 | 手动审查关键模块（10-20 行核心逻辑） | 分段审查 |

---

## 🚫 反例与黑名单

| # | 不要做 | 为什么 | 正确做法 |
|---|--------|--------|----------|
| 1 | 用中文变量名或拼音（`wen_du`） | 与英文代码混合，可读性差，其他开发者看不懂 | 用英文命名：`temperature` |
| 2 | 用 for 循环遍历 DataFrame 行 | 比向量化慢 100-1000 倍，数据量大时卡死 | 用 `df['new'] = df['A'] + df['B']` |
| 3 | 不加类型注解的函数参数 | 静态检查失效，调用者不知道传什么类型 | `def func(x: np.ndarray) -> float:` |
| 4 | 用 `print()` 调试代替 logging | print 无法分级/归档，生产环境不可控 | `logger.info()` / `logger.warning()` |
| 5 | 跳过代码审查直接给用户 | 未审查的代码可能包含 P0 漏洞 | **必须**启动 subagent 审查通过后再展示 |
| 6 | 硬编码路径（如 `C:/Users/.../data.csv`） | 换机器/换目录后代码立刻断裂 | 用 `ProjectConfig` 或 `Path(__file__).parent` |
| 7 | 用 `pd.read_csv()` 读 10GB+ 文件 | 一次性读入耗尽内存 | 用 `pd.read_csv(chunksize=...)` 或 `dask` |
