---
name: doc-consistency-auditor
description: >
  审计 Markdown 文档/目录的一致性：术语漂移、失效内部链接与锚点、
  标题层级跳跃、重复标题、交付物清单缺口。输入一个 .md 文件或目录，
  输出结构化审计报告（终端 + Markdown + JSON），退出码 0/1/2。
  触发短语："检查文档一致性"、"文档审计"、"术语不一致"、"断链检查"、
  "标题层级"、"交付物缺什么"、"audit markdown"、"doc consistency"、
  "check broken links in markdown"、"terminology drift"。
---

# doc-consistency-auditor（Markdown 文档一致性审计器）

## Purpose（为什么需要）

多人协作或 AI 批量产出的 Markdown 文档，最常见五类"看不见的坑"：

1. **术语漂移**：同一概念一会儿写「术语表」、一会儿写「词汇表」，读者和检索都混乱。
2. **失效链接/锚点**：改标题后内部 `#锚点` 全部失效，图片路径也经常指向不存在的文件。
3. **标题层级跳跃**：`##` 直接跳到 `####`，目录树断裂、可读性差。
4. **重复标题**：同一文件里两个「## 概述」，锚点歧义。
5. **交付物清单缺口**：该交的文件没交，缺了 `README.md` / `.skill` / `AI日志` 等。

人工逐篇检查费时且极易漏。本技能用一个**确定性脚本**一次性扫出问题，并给出精确到"文件:行号"的位置和修复建议。

**一句话 I/O**：输入「Markdown 文件/目录（+ 可选术语表 YAML + 可选交付物清单 YAML）」，输出「审计报告（终端 + Markdown + JSON）+ 退出码」。

## 四条件自检

| 条件 | 如何满足 |
|------|----------|
| 可复用 | Python 3.8+ 仅标准库，零第三方依赖，陌生人 `python3 audit.py` 直接跑 |
| 可执行 | 有真实可运行脚本 `scripts/audit.py`，非纯理论 |
| 可验证 | 给定含已知错误的样例，能精确报出对应"文件:行号:问题"；干净样例返回退出码 0 |
| IO 明确 | 输入路径 → 输出报告，一句话说清 |

## 前置条件

- Python 3.8+（只用了 `argparse / os / re / json / fnmatch / sys`，无 pip 依赖）
- 审计对象为 `.md` / `.markdown` 文件

## Workflow（怎么用）

### Step 1 — 定位审计对象
确定要审计的**单个文件**或**目录**。目录会被递归扫描 `.md` / `.markdown`（自动跳过隐藏目录）。

### Step 2 — 准备术语表（可选）
若要做术语一致性检查，写一个 `glossary.yaml`（支持的极简 YAML 子集，见 `references/glossary.example.yaml`）：

```yaml
rules:
  - standard: "GitHub"
    forbidden: ["github", "Github", "GH"]
  - standard: "术语表"
    forbidden: ["词汇表"]
```

- `standard`：标准写法（建议统一成它）
- `forbidden`：出现即报告为错误的禁用/别名写法（大小写敏感）

### Step 3 — 运行脚本

```bash
# 最简：只做链接/标题/术语漂移之外的检查（不传术语表则跳过 R1）
python3 scripts/audit.py --path ./docs

# 完整：术语 + 链接 + 标题 + 交付物清单
python3 scripts/audit.py --path ./docs \
  --glossary references/glossary.example.yaml \
  --manifest references/manifest.example.yaml \
  --out audit_report.md

# 机器可读
python3 scripts/audit.py --path ./docs --json
```

### Step 4 — 解读报告
- **退出码 0**：无任何问题
- **退出码 1**：发现问题（报告已逐条列出 `文件:行号`、级别、规则、建议）
- **退出码 2**：参数/路径错误（如路径不存在、术语表文件不存在）

### Step 5 — 修复后复跑
按报告逐条修复，复跑直到退出码 0。可将 `audit.py` 挂进 CI（如 GitHub Actions）或 git pre-commit hook，实现"提交前必过一致性检查"。

## Edge Cases（边界情况）

| 情况 | 行为 |
|------|------|
| 目录为空 / 无 .md 文件 | 返回 0，提示"未发现 Markdown 文件" |
| 超大文件 | 默认超过 5MB 跳过并报 R0 警告；`--max-bytes` 可调高上限 |
| 编码异常 | 以 UTF-8 + `errors="replace"` 读取，不会因坏字节崩溃 |
| 代码块内的词/链接 | 自动跳过 ```` ``` ```` / `~~~` 围栏内部，避免把代码里的 "github" 当术语漂移误报 |
| 外部链接（http/https/mailto/tel） | 不做网络请求（保持离线、确定性），直接跳过不报错 |
| 跨文件锚点 | 链接到 `other.md#标题` 时，会核对目标文件是否真正包含该标题 |
| 未传 `--glossary` | 跳过 R1 术语检查，其余规则照常运行 |
| 非 .md 文件 | 自动忽略 |

## Examples（示例）

### 示例 A：审计一个文档目录
```bash
python3 scripts/audit.py --path demo \
  --glossary references/glossary.example.yaml \
  --manifest references/manifest.example.yaml
```

### 示例 B：单文件 + JSON 输出（供脚本消费）
```bash
python3 scripts/audit.py --path demo/sample_bad.md --glossary references/glossary.example.yaml --json
```

### 示例报告（Markdown 报告节选）
```markdown
# 文档一致性审计报告
- 审计路径：demo
- 问题总数：9（错误 7，警告 2）

## R1 术语一致性（4 条）
| 文件 | 行 | 问题 | 建议 |
|---|---|---|---|
| sample_bad.md | 5 | 出现禁用写法「github」 | 统一为「GitHub」 |
...
```

## 检查规则明细

- **R0 文件规模**：跳过超限文件并告警（warning）
- **R1 术语一致性**：对比 glossary，命中禁用写法即报（error）
- **R2 内部链接/锚点**：本地目标不存在、锚点未命中标题即报（error）
- **R3 标题层级跳跃**：`##` 直接跳 `####` 等越级即报（warning）
- **R4 重复标题**：同文件同 slug 标题重复即报（warning）
- **R5 交付物清单**：manifest 中 glob 未命中任何文件即报（warning）
