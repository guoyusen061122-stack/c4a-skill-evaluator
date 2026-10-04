---
name: challenge-submit-guard
description: >
  EduSeed / Elite20 挑战提交前自检器。输入一个挑战交付文件夹路径 + 挑战编号（C1…C10H，可自动识别），
  输出一份体检报告：必交交付物核对表、命名规范检查、红线扫描（缺失/无AI日志/一句话提交）、
  五维 rubric 粗估、提分杠杆排序、可执行的 TODO 清单，以及「机器查不到必须人工确认」的清单。
  覆盖 20 个挑战的完整注册表（交付物模式 + 评分维度 + 红线封顶规则），零第三方依赖。
  Use whenever the user says "提交前检查", "帮我看看还缺什么", "挑战自检", "交付物核对",
  "challenge self-check", "pre-submission audit", "submit guard", "C4 缺什么", "还差什么文件",
  "能不能提交了", "rubric 自查", "红线检查", "作业体检", or provides a challenge folder and asks
  whether it is complete / ready to submit / what is missing.
  Also trigger when the user mentions EduSeed / Elite20 / C1-C10 challenge submissions together
  with a folder path, or asks "what will I lose points on".
---

# Challenge Submit Guard（挑战提交自检器）

## Purpose

交作业前最贵的错误，不是写得不好，而是**漏交、命名乱、AI日志太薄被判红线**。
这些错误在提交后才发现，就要多花一轮返工。

这个技能把「提交前检查」这件事固化成一条命令：给它一个文件夹，它对照平台真实的 rubric
告诉你 —— 缺什么、命中哪条红线、最可能在哪丢分、按什么顺序补。

它不是评分器。它回答的是「**最可能在哪丢分**」，不是「我能得几分」。

---

## 一句话 I/O

**输入**：一个挑战交付文件夹路径 + 挑战编号（可自动识别）
**输出**：一份 Markdown 体检报告（7 节），或 `--json` 结构化数据

---

## Prerequisites

- Python 3.8+（**只用标准库**，无需 pip install 任何东西）
- `references/challenges.yaml` —— 挑战注册表，随包提供，覆盖 20 个挑战

注册表由 `scripts/build_registry.py` 从平台导出的 `challenge.json` + `rubric.json` 自动生成，
不是手打的，所以判定规则和平台一致。平台更新后重跑一次脚本即可同步：

```bash
python scripts/build_registry.py --source "C:/path/to/我的EduSeed挑战"
```

---

## Workflow

### Step 0 — 先确认安装没坏（3 秒）

```bash
python scripts/challenge_submit_guard.py --self-test
```

用合成夹具跑 5 个断言（完整包 / 空文件夹 / 一句话日志 / 自动识别 / 注册表完整性）。
全部 PASS 再往下走。这一步是给别人的，不是给你的 —— 让使用者自己确认环境没问题。

### Step 1 — 确定挑战编号

用户在命令里给就用给的（`-c C4`）；没给就自动识别：
1. 文件夹名里的 `C4` 样式（大小写不敏感）
2. 文件名里的 `姓名_C4_部件` 样式（取出现最多的）
3. 都失败 → 报错并提示用 `--list` 查编号

```bash
python scripts/challenge_submit_guard.py --list
```

### Step 2 — 跑体检

```bash
python scripts/challenge_submit_guard.py "C:/Users/me/Desktop/C4" -c C4
```

想存档就加 `--out report.md`；要给程序读就加 `--json`；
要当 CI 门禁用就加 `--strict`（缺必交物或命中红线时退出码 1）。

### Step 3 — 按报告第 6 节的 TODO 顺序补

顺序很重要：**先解红线，再补内容**。
红线会把某个维度直接压到 ≤5 分，此时补再多内容也无效（报告第 5 节会标 🔴）。

### Step 4 — 人工过一遍第 7 节

脚本读得到文件，读不到「事情有没有真的发生」。第 7 节列的 4 条必须人工确认。

---

## 报告结构（7 节）

| 节 | 内容 | 怎么用 |
|---|---|---|
| 1 交付物核对 | 每项必交物的匹配模式、状态、命中文件 | 直接看有没有 ❌ |
| 2 命名规范 | 符合/不符合 `姓名_挑战号_部件.ext` 的数量 | 团队统一命名时用 |
| 3 红线扫描 | 缺失 / 无AI日志 / 一句话提交 / 空文件 | 🚩 必须清零 |
| 4 五维粗估 | 每维度信号命中数、缺失信号、封顶标记 | 定位丢分维度 |
| 5 提分杠杆 | 按丢分从大到小排前 3 | 时间不够就先做第 1 条 |
| 6 TODO | 按优先级的可执行动作 | 照着做 |
| 7 人工确认 | 机器查不到的 4 件事 | 提交前自己打勾 |

---

## 判定规则（可以直接告诉用户，避免争议）

**交付物匹配**：glob 模式对文件名和相对路径同时匹配。
`*.skill` 命中任何 `.skill` 文件；`*AI日志*` 命中 `AI日志.md`、`ai-log.md`、`ai_log.md`。
命中但大小为 0 → 判为「⚠️ 空文件」，不算已交。

**红线封顶**（与平台 rubric 一致）：

| 红线 | 触发条件 | 封顶 |
|---|---|---|
| `missing_artifacts` | 任一必交物缺失 | `artifactCompleteness` ≤ 5 |
| `no_ai_log` | 无 AI日志，或有效内容 < 800 字 | `reflectionQuality` ≤ 5 |
| `one_shot_ai` | AI日志 < 400 字，或无迭代关键词 | `aiUsage` ≤ 5 |
| `empty_files` | 存在 0 字节文件 | 提示，不封顶 |

**分数粗估**：`维度满分 × 命中信号比例 × (0.6 + 0.4 × 交付物完整度)`，再套红线封顶。
信号命中分三级：原文/同义词命中算 1.0；中文信号退化成 2 字片段命中算 0.5；找不到算 0。

**为什么用片段匹配**：实测 C3 交付包，rubric 信号「提供新信息/给出可执行结论/有深度视角」
三项全部判 0，但该文件夹有 34KB 真反思内容 —— 属于明显误判。
退化匹配后该维度从 0/20 升到 10/20（平台实评 17/20），单维度校准明显改善。
代价是整体偏乐观，所以报告里明确写了「这不是官方评分」。

---

## Examples

**例 1：最基本的用法**

> "帮我检查一下 C:/Users/me/Desktop/C4，能不能提交了"

```bash
python scripts/challenge_submit_guard.py "C:/Users/me/Desktop/C4"
```

**例 2：拿真实交付包试跑**（本技能自带的证据）

```bash
python scripts/challenge_submit_guard.py "C:/Users/me/Desktop/C3" -c C3
```

实测输出：7 个文件 / 交付物 3-of-3 / 无红线 / 粗估 90-100。
对照平台实评 77 分，差距全部来自「稿子写好了但没发出去」——
这正是第 7 节「行为是否真的发生」存在的理由。

**例 3：当提交门禁**

```bash
python scripts/challenge_submit_guard.py ./dist -c C5 --strict || echo "还不能提交"
```

**例 4：机器可读输出**

```bash
python scripts/challenge_submit_guard.py ./C4 --json > audit.json
```

---

## Edge Cases

| 情况 | 行为 |
|---|---|
| 路径不是文件夹 | 报错退出，提示路径无效 |
| 自动识别不到挑战号 | 报错并提示 `-c` 或 `--list` |
| 文件夹名小写（`c1`） | 正常识别（大小写不敏感） |
| 空文件夹 | 命中 `missing_artifacts` + `no_ai_log`，产物完整性封顶 ≤5 |
| 交付物存在但 0 字节 | 判「⚠️ 空文件」，不算已交 |
| 超大仓库（>2MB 文本） | 语料读取到上限即停，避免卡死；文件统计不受影响 |
| 二进制文件（pdf/docx/xlsx） | 不读入语料，但参与文件计数和交付物匹配 |
| 没装 PyYAML | 用内置迷你 YAML 解析器，功能完全一致 |
| 注册表里没有该挑战 | `--list` 查编号；改注册表后无需改代码 |
| `.git` / `node_modules` 等 | 自动跳过，不污染统计 |

---

## 设计取舍（写给想改这个技能的人）

1. **零依赖优先于功能丰富**。能用标准库解决就不引入 pip 包 ——
   「别人拿过去就能跑」比「多一个 Excel 输出」重要得多。
   为此内置了一个约 90 行的迷你 YAML 解析器（支持缩进映射、列表、列表套字典、引号转义）。

2. **规则外置，代码不动**。所有判定规则在 `challenges.yaml`。
   新增挑战 = 在注册表加一段；改红线阈值 = 改 YAML。改数据不改代码。

3. **宁可说「粗估」，不要装作「评分」**。分数估计必然不准，
   但「你在内容实质这一维最可能丢分」这个指向是准的，而且每条都给了证据位置。

4. **内置自检优先于文档承诺**。让别人相信技能能用，最有效的方式是让他自己跑一遍
   `--self-test` 看到 5 个绿勾，而不是读一段「应该可以运行」的说明。

---

## File Map

```
challenge-submit-guard/
├── SKILL.md                              ← 你正在读的
├── scripts/
│   ├── challenge_submit_guard.py         ← 主程序（自检器本体）
│   └── build_registry.py                 ← 从平台导出包重建注册表
└── references/
    └── challenges.yaml                   ← 20 个挑战的交付物 / 维度 / 红线
```
