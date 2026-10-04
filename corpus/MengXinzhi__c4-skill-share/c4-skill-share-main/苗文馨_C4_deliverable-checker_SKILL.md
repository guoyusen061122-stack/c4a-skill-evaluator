---
name: deliverable-checker
description: >
  Submission self-check tool for challenge-based courses (e.g. Elite20). Takes a challenge
  pack directory (containing challenge.json / rubric.json) and a student submission folder,
  then produces a Markdown self-check report: which required deliverables are present or
  missing (matched by wildcard pattern), whether filenames follow the naming convention
  (姓名_C编号_说明.ext), which grading red flags would be triggered, and a per-dimension
  self-score checklist against the official rubric. Outputs a Markdown report and an
  optional JSON summary; exits non-zero when deliverables are missing (CI-friendly).
  Use whenever the user says "自查作业", "检查交付物", "提交前检查", "我交齐了吗",
  "check my submission", "deliverable check", "作业自查", "缺了什么交付物",
  or asks whether their submission folder is complete before uploading, or provides a
  submission folder together with a challenge/rubric file and asks for a completeness
  review. Also trigger when the user mentions "red flags", "评分维度自查", or
  "命名规范检查" in the context of homework submission.
---

# Deliverable Checker — 作业交付物自查器

## Purpose

提交作业前最焦虑的问题是："我到底交齐了没有？命名对不对？会不会踩红旗？"

这个技能像一位**助教收作业前的预检员**：在你正式提交之前，先替助教检查一遍——
对照挑战官方定义（challenge.json / rubric.json），逐项核对你文件夹里的交付物，
输出一份人话版自查报告：**缺什么、错什么、哪些评分点有证据、预计踩哪些红旗**。

- **输入**：挑战资料包目录（含 challenge.json）+ 你的提交文件夹
- **输出**：Markdown 自查报告（+ 可选 JSON），含缺失清单、命名检查、红旗预警、五维评分自查表

四个条件全部满足：
- 可复用：只需 Python 3 标准库，零依赖，任何机器能跑
- 可执行：确定性 Python 脚本，不是"感觉上应该交齐了"
- 可验证：给定同样的输入，永远得到同样的报告；缺东西时退出码非 0
- IO 明确：输入两个文件夹路径，输出一份报告

## Prerequisites

- Python 3.8+，**仅标准库**（argparse / json / re / fnmatch / pathlib），无需安装任何第三方包

## Input Formats

### 1. 挑战资料包目录（必须，或用 --pattern 代替）

目录内包含 `challenge.json`，其中关键字段：

```json
{
  "required_deliverables": "*skill说明*,*.skill,*教学说明*,*demo*,*AI日志*",
  "red_flags": "[{\"id\":\"no_ai_log\",...}]",
  "rubric_dimensions": "{\"dimensions\":[{\"id\":\"...\",\"label\":\"...\",\"signals\":[...]}]}"
}
```

- `required_deliverables`：逗号分隔的通配符模式（fnmatch 语义，`*` 匹配任意字符）
- 若没有 challenge.json，可用 `--pattern "*skill说明*,*.skill,..."` 直接传模式，
  用 `--rubric rubric.json` 单独提供评分维度文件（兼容 rubric.json 的
  `dimensions[].id/label/signals` 结构）

### 2. 提交文件夹（必须）

学生自己的交付物所在目录，会**递归扫描**所有子目录（忽略隐藏文件和本脚本的输出报告）。

## Workflow

### Step 1 — Locate the inputs

```bash
python deliverable_checker.py \
  --challenge "E:/挑战合集/挑战_C2_完整资料" \
  --submission "E:/我的提交/C2" \
  --name "ZhangWei" \
  --output "自查报告.md"
```

若 `--challenge` 目录中没有 challenge.json，脚本会打印提示并退出（退出码 2）。
用户只给了提交文件夹时，先问一句："挑战资料包在哪个目录？"或请用户用 --pattern 给出交付物清单。

### Step 2 — Run the checker

直接运行脚本（推荐用 --output 落盘，方便发给同学或附在提交里）：

```bash
python scripts/deliverable_checker.py --challenge <资料包> --submission <提交夹> --output 报告.md
```

脚本内部流程（全部确定性计算，无 AI 判断）：

1. 读 challenge.json → 取 `required_deliverables` 拆成模式列表
2. 递归扫描提交文件夹 → 得到文件清单（跳过隐藏文件、`自查报告.md`/`*_check_report*`）
3. 每个模式 fnmatch 匹配所有文件名 → 得到命中/缺失
4. 命名规范检查：文件 stem 是否匹配 `^(.+)_(C\d+)_(.+)$`
5. 红旗检查：
   - `missing_artifacts`：缺失模式数 > 0
   - `no_ai_log`：没有任何文件匹配 `*AI日志*` / `*AI*log*` / `*AAR*` / `*复盘*`
6. 五维评分自查：把命中文件按类型映射到 rubric 维度（见 references/rubric-guide.md），
   每个维度给出 ✅/⚠️/❌ 与对应证据文件
7. 生成 Markdown 报告 + 可选 --json

### Step 3 — Read the report and fix gaps

报告末尾是 **行动清单**（按优先级排序）：先补缺失的核心交付物，再修命名，
最后确认 AI 日志在。把报告截图或原文随提交一起放进群里，是向助教展示
"提交前自查过"的加分证据。

### Step 4 — Re-run until clean

修完再跑一遍。退出码 0 = 全部通过（可接 CI / 批处理）。

## Report Structure (what the output looks like)

```markdown
# 交付物自查报告 — C4 技能分享与传播
- 提交者：苗文馨 ｜ 提交夹：E:/我的提交/C4 ｜ 检查时间：2026-10-03 20:43

## 1. 必交交付物核对（5 项模式）
| # | 模式 | 状态 | 命中文件 |
|---|------|------|---------|
| 1 | *skill说明* | ✅ | 苗文馨_C4_skill说明.md |
| 2 | *.skill | ❌ 缺失 | — |

## 2. 命名规范检查
❌ 2 个文件不符合 `姓名_C编号_说明.ext`：demo.png, 笔记.md

## 3. 红旗预警
⚠️ no_ai_log：未发现 AI 使用记录/AAR 文件（影响 复盘质量，最多 -5 分）

## 4. 五维评分自查
| 维度 | 满分 | 证据 | 评级 |
|------|------|------|------|
| skillQuality | 25 | deliverable-checker.skill | ✅ |

## 5. 行动清单
1. 【必补】*.skill：打包技能目录为 ZIP 并命名 苗文馨_C4_技能名.skill
```

## Edge Cases

- **challenge.json 不存在**：退出码 2，提示改用 --pattern。
- **提交文件夹不存在或为空**：报告"0 个文件"，所有模式判缺失，不崩溃。
- **delocalized 字段**：challenge.json 里 rubric 可能是字符串化的 JSON（rubric_dimensions 是字符串），
  脚本会自动 json.loads 解包；解不开就跳过评分自查、只做交付物核对。
- **通配符含中文**：fnmatch 对中文文件名正常工作；Windows 下路径统一用 Path 处理，无编码问题。
- **同名多命中**：一个模式命中多个文件时全部列出（如 demo 命中 demo.mp4 + demo截图.png）。
- **误伤脚本自身输出**：跳过名为 自查报告*.md / *_check_report* 的文件。
- **大文件夹**：纯 os 扫描，千级文件秒出；>10 万文件时建议只传子文件夹。
- **required_deliverables 为空**：视为未定义，提示用户改用 --pattern。

## Important Principles

- 只报告事实，不猜测内容质量：脚本判定"有没有、叫什么"，内容好不好由 AI/人判断。
- 缺失 ≠ 扣分定论：红旗预警标注"最多 -N 分"，给的是风险提示不是判决。
- 报告必须可直接行动：每一项缺失都对应一条具体修复建议。
