---
name: zhangcy-slide-designer
description: "Generate LaTeX/Beamer presentation PDF from slide_content.md (output of zhangcy-slide-content-builder). Supports multi-template switching (USTC beamer / generic / etc.). Compiles with xelatex — no longer generates PPTX. Use when the user needs to: generate slides, compile beamer, make PDF presentation, 生成PPT/编译幻灯片/制作PDF演示文稿/做Beamer. Triggers on: 做PPT/编译/生成 slides/compile beamer/make PDF/slide designer/PDF 演示."
---
# zhangcy-slide-designer

从 `slide_content.md`（由 `zhangcy-slide-content-builder` 产出）生成 **LaTeX Beamer 演示文稿 PDF**。只负责"长什么样"（排版、模板、配色），不修改内容本身。

---

## 快速开始

```
输入: slide_content.md（由 zhangcy-slide-content-builder 产出）
输出: main.pdf（LaTeX Beamer 演示文稿）

流程（6 步）:
  Step 1: 确认模板 → Step 2: 复制模板 → Step 3: 生成 main.tex
  → Step 4: 处理插图 → Step 5: xelatex 编译 → Step 6: 交付文件
```

## 重要原则

- **输出为 PDF（LaTeX Beamer 编译）**，不再生成 PPTX/PPT
- **支持多模板切换**，通过指定 `template` 参数选择不同大学的 Beamer 主题
- **模板文件已内置在 skill 目录中**，无需联网克隆
- 仅处理排版/模板/结构，不修改 `slide_content.md` 中的内容逻辑

---

## 模板系统

### 模板位置

所有模板文件存放在 skill 所在目录的 `templates/` 子目录下：

```
~/.reasonix/skills/zhangcy-slide-designer/
├── SKILL.md                     ← 本 skill 文件
└── templates/
    ├── ustc/                    ← 中科大 beamer 模板
    │   ├── ustcbeamer.sty       ← 主题宏包（颜色、页眉页脚）
    │   ├── ustctheme.tex        ← 封面/背景 TikZ 配置
    │   ├── Makefile             ← 一键编译（make / latexmk）
    │   ├── figures/
    │   │   └── ustc_logo.pdf    ← 中科大校徽
    │   └── theme/
    │       ├── ustc_background.tex  ← 正文页背景
    │       ├── ustc_cover.tex       ← 封面页背景
    │       └── ustc_logo_side.pdf   ← 侧边校徽
    ├── thu/                     ← (预留) 清华大学
    ├── pku/                     ← (预留) 北京大学
    └── generic/                 ← (预留) 通用模板
```

### 可用模板

| 模板名称 | 适用场景 | 状态 |
|----------|----------|------|
| `ustc` | 中科大汇报/答辩 | ✅ 已内置 |
| `thu` | 清华大学 | 📌 预留 |
| `pku` | 北京大学 | 📌 预留 |
| `generic` | 通用学术汇报（标准 Beamer） | 📌 预留 |

如未指定，默认使用 `ustc` 模板。

---

## 工作流程

### 第一步：确认模板

直接询问用户使用哪个模板，或根据上下文判断。默认 `ustc`。

**🔴 CHECKPOINT 1：向用户展示所选模板名称（如"当前选项：ustc — 中科大 Beamer 模板"），请用户确认后再继续。**

**⚠️ 失败模式：**

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|----------|------------|
| 用户指定模板不存在（如 thu 未就绪） | 说明该模板为预留状态 | 回退到 `ustc` 默认模板 |
| 用户未指定模板 | 默认使用 `ustc` | 询问用户是否需要其他模板 |

### 第二步：准备模板目录

将对应模板文件**复制**到输出目录，保持目录结构不变：

```bash
# 输出目录为 <output_dir>/template/
xcopy /E "C:\Users\12426\.claude\skills\zhangcy-slide-designer\templates\ustc" "<output_dir>\template\"
```

然后**在 `template/` 目录内工作**——所有后续文件（`main.tex`、`figures/` 等）都放在 `template/` 下。

**⚠️ 失败模式：**

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|----------|------------|
| 模板源目录路径错误 | 检查 skill 目录下 `templates\ustc\` 是否存在 | 询问用户手动输入模板路径 |
| 输出目录权限不足 | 换到 `%TEMP%` 或桌面输出 | 逐层创建目录后再复制 |

### 第三步：生成 LaTeX 源文件

根据 `slide_content.md` 生成 `main.tex`，放在模板目录中。

#### USTC 模板 LaTeX 头部

```latex
\documentclass[aspectratio=169]{ctexbeamer}
\usepackage[bluetheme]{ustcbeamer}   % 可选: bluetheme / redtheme / blacktheme
\usepackage{listings}
\lstset{basicstyle=\ttfamily\small, breaklines=true, columns=flexible}
\input{ustctheme.tex}

\title[短标题]{长标题}
\author[短作者]{作者姓名\\学号}
\institute[机构]{机构名称}
\date{YYYY年M月D日}
```

#### USTC 模板特有命令

| 命令 | 说明 |
|------|------|
| `\maketitleframe` | 生成封面页（含 USTC 背景 + 校徽） |
| `[bluetheme]` | 校徽蓝（默认） |
| `[redtheme]` | 红色 |
| `[blacktheme]` | 黑色 |

#### 内容页 LaTeX 结构

```latex
\begin{document}
\maketitleframe                                    % 封面

\begin{frame}
  \frametitle{汇报提纲}
  \tableofcontents[hideallsubsections]
\end{frame}

\AtBeginSection[]{                                % 节前目录
  \setbeamertemplate{footline}[footlineoff]
  \begin{frame}
    \frametitle{汇报提纲}
    \tableofcontents[currentsection,subsectionstyle=show/show/hide]
  \end{frame}
  \setbeamertemplate{footline}[footlineon]
}

\section{章节标题}
\begin{frame}
  \frametitle{页面标题}
  % 内容...
\end{frame}

% ...更多页面...

\begin{frame}
  \centerline{\Huge 谢谢！}
\end{frame}
\end{document}
```

**🔴 CHECKPOINT 2：向用户展示生成的 `main.tex` 核心结构（标题/章节/页数），询问用户是否审阅内容或直接进入插图阶段。**

### 第四步：处理插图

根据 `slide_content.md` 中的插图建议，用 Python + matplotlib 生成 PNG 示意图。

**图片生成规范：**
- 中文用 SimHei 字体：`FontProperties(fname='C:/Windows/Fonts/simhei.ttf')`
- 格式：PNG（xelatex 兼容性更好，避免 PDF 字体嵌入问题）
- DPI：≥ 200
- 配色与 USTC 校徽蓝协调（#003C98）
- **图例放在绘图区域内部**（如 `loc='lower right'`），不要放在图外
- **中文字体标签与图形主体间距 ≤ 0.1 坐标单位**
- 生成的 PNG 保存到 `template/figures/` 下

**⚠️ 插图失败模式：**

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|----------|------------|
| `SimHei.ttf` 字体路径不存在 | 搜索系统字体 `findstr /m "SimHei" C:\Windows\Fonts\*` | 回退到 `SimSun` 或用英文标签 |
| matplotlib 报 `No module named 'matplotlib'` | `pip install matplotlib` | 用 Python 内置的 `turtle` 或直接生成不带中文的简单 SVG |
| PNG 生成后 LaTeX 报 `cannot determine size` | PNG 损坏或格式不对，重新生成 | 转成 `PDF` 格式：`plt.savefig('fig.pdf')` |

**在 LaTeX 中引用图片：**
```latex
\centering
\includegraphics[width=0.6\textwidth]{figures/fig_xxx.png}
```

**插图布局建议：**
- 小图（宽度 0.5-0.65\textwidth）居中，上下用 `\vspace` 控制间距
- 大图可与文字左右分栏（`columns` 环境）
- 避免图片内图例与主体分离太远

**🔴 CHECKPOINT 3：向用户展示即将编译的文件列表（main.tex + figures/），询问"确认编译？"或让用户最后修改。**

### 第五步：编译

**必须在 `template/` 目录下编译**（cwd 正确才能找到所有文件）：

```bash
cd <output_dir>/template
"D:\400_Tools\030_Envs\texlive\2026\bin\windows\xelatex.exe" -synctex=1 -interaction=nonstopmode main.tex
# 编译两遍保证引用解析
```

**⚠️ 编译失败模式：**

| 触发条件 | 一线修复 | 仍失败兜底 |
|----------|----------|------------|
| `! LaTeX Error: File \`ustcbeamer.sty' not found` | 确认 cwd 是否在 `template/` 目录内 | 用绝对路径指定 `\usepackage{template/ustcbeamer}` 或重新复制模板 |
| `! Package ctex Error: CTeX font set \`windows' is unavailable` | 确认系统已安装中文字体（Windows 自带 SimSun/SimHei） | 在导言区加 `\setCJKmainfont{SimSun}` 指定字体 |
| 编译卡死/内存不足 | 减少图片 DPI 到 150，删除不必要的大图 | 拆分为多个片段分别编译 |
| `Unable to open "main.pdf"` — 锁文件 | 等 5 秒重试 | 用 `-jobname=slides` 换名输出 |
| 第一遍编译通过但第二遍报错 | 检查引用/交叉引用语法（`\ref` 指向了不存在的标签） | 临时注释交叉引用，仅编译单遍生成主要内容 |

**🔴 CHECKPOINT 4：展示编译结果（PDF 页数/文件大小），询问用户"预览 PDF？重新编译？还是继续交付？"**

**编译完成后**：用 `move main.pdf <output_dir>/` 将 PDF 移到输出目录，或让用户直接在 `template/` 下预览。

### 第六步：输出文件

最终交付：
- `<output_dir>/template/main.pdf` — 最终演示文稿
- `<output_dir>/template/main.tex` — LaTeX 源文件（可 TeXstudio 编辑）
- `<output_dir>/template/figures/` — 插图文件

### 输出示例

以 15 分钟组会汇报为例，输入 `slide_content.md` 包含"沙尘暴中雷电现象"内容时：

```
输出目录/
├── template/
│   ├── main.pdf              ← 18 页 PDF（含封面+目录+16页内容）
│   ├── main.tex              ← LaTeX 源文件（可 TeXstudio 打开编辑）
│   ├── ustcbeamer.sty        ← 模板主题
│   ├── ustctheme.tex
│   ├── figures/
│   │   ├── fig_dust_map.png      ← 沙尘暴分布图（DPI=200）
│   │   ├── fig_lightning_bar.png ← 闪电频次柱状图
│   │   └── fig_mechanism.png     ← 起电机制示意图
│   └── Makefile
```

PDF 结构：
- 第 1 页：封面（标题+作者+机构+日期）
- 第 2 页：汇报提纲
- 第 3 页：研究背景 | 引言
- 第 4-8 页：方法 | 数据
- 第 9-14 页：结果 | 讨论
- 第 15-16 页：结论 | 展望
- 第 17 页：致谢
- 第 18 页：谢谢！

---

## 🚫 反例与黑名单

以下操作可能导致编译失败或输出异常，**应避免**：

| # | 不要做 | 为什么 | 正确做法 |
|---|--------|--------|----------|
| 1 | 修改 `slide_content.md` 中的内容逻辑 | designer 只负责排版，改内容会越界，破坏内容与排版分离 | 内容修改请用 `zhangcy-slide-content-builder` |
| 2 | 在 `template/` 目录外执行 xelatex 编译 | 路径引用（`\input{ustctheme.tex}`、`\includegraphics{figures/xxx.png}`）基于 cwd 解析，目录外找不到文件 | 必须 `cd <output_dir>/template` 后再编译 |
| 3 | 删除/覆盖模板目录中的 `ustcbeamer.sty` 或 `ustctheme.tex` | 这些是模板核心文件，修改后封面/配色断裂 | 不要动模板文件；颜色主题通过 `[bluetheme]` 等选项切换 |
| 4 | 用 Powershell 的 `cp` 代替 `xcopy /E` 复制模板 | 目录结构未被完整复制（缺子目录和隐藏文件） | 用 `xcopy /E` 保持目录结构 |
| 5 | 直接用 `pdflatex` 代替 `xelatex` 编译 | `ctexbeamer` 需 xelatex 引擎处理中文 | 始终用 xelatex 编译 |
| 6 | 图片路径用绝对路径（如 `C:/Users/.../fig.png`） | 换机器/换目录后路径断裂，LaTeX 报 File not found | 用相对路径 `figures/fig.png`（基于 template/ 目录） |

---

## 失败模式总表

以下为各步骤可能遇到的失败场景汇总：

| 步骤 | 症状 | 一线修复 | 兜底 |
|:----:|------|---------|------|
| ① 模板 | 指定模板不存在 | 说明为预留状态 | 回退 `ustc` |
| ② 复制 | 输出目录权限不足 | 换到 `%TEMP%` | 逐层创建目录 |
| ③ LaTeX | `ustcbeamer.sty` not found | 检查 cwd 是否在 template/ | 用绝对路径引用 |
| ③ LaTeX | CTeX 字体不可用 | 确认已安装中文字体 | `\setCJKmainfont{SimSun}` |
| ④ 插图 | SimHei 字体不存在 | `findstr "SimHei" C:\Windows\Fonts\*` | 用英文标签 |
| ④ 插图 | matplotlib 未安装 | `pip install matplotlib` | 用 SVG 替代 |
| ⑤ 编译 | 卡死/内存不足 | 降低图片 DPI 到 150 | 拆分编译 |
| ⑤ 编译 | main.pdf 锁文件 | 等 5 秒重试 | `-jobname=slides` 换名 |
| ⑤ 编译 | 引用/交叉引用报错 | 注释交叉引用 | 单遍编译 |

## 常见问题

### 路径问题

**关键规则：** 所有编译操作必须在 `template/` 目录内进行。`\input{ustctheme.tex}` 和 `\includegraphics{figures/xxx.png}` 都基于 cwd 解析，cwd = template 目录时才能找到。

### 中文字体

- LaTeX：`ctexbeamer` 文档类自动处理中文
- matplotlib 图片：`FontProperties(fname='C:/Windows/Fonts/simhei.ttf')`

### 编译锁文件

`Unable to open "main.pdf"` → 前一进程占用了 PDF，解决方案：
- 等几秒重试
- 或 `-jobname=slides` 换名输出
- 或删除旧 PDF：`del main.pdf`

### TeXstudio 兼容

生成的 `.tex` 文件可直接在 TeXstudio 中打开，F5 编译。TeXstudio 的 cwd 默认为 `.tex` 文件所在目录，所以路径都能正确解析。

### 扩展新模板

添加新模板（如 THU/PKU/通用）：
1. 在 `templates/` 下新建目录
2. 放入 `sty`、`tex`、主题文件和校徽
3. 在本文档的模板表格中添加一行
