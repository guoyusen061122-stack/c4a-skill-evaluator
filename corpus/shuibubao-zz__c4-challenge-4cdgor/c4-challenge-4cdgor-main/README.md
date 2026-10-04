# C4 技能分享与传播 — 交付包

> 挑战：C4 技能分享与传播（`ch-20260717031424-4cdgor`）｜ 交付人：卢怡然 ｜ 截止 2026-12-31
> 技能：**challenge-submit-guard** — 挑战提交自检器

---

## 一分钟了解

**输入**一个挑战交付文件夹路径 + 挑战编号，**输出**一份体检报告：缺什么、命中哪条红线、
最可能在哪丢分、按什么顺序补。

```bash
python challenge_submit_guard.py "C:/Users/me/Desktop/C4"
```

覆盖 **20 个挑战**（C1–C10H）的交付物清单 / 评分维度 / 红线规则，
注册表由平台导出的 `rubric.json` **自动生成**（非手打），**零第三方依赖**（纯 Python 标准库）。

**它不是评分器，它回答"最可能在哪丢分"。**
最有说服力的数字：对我的 C3 交付包，它粗估 90 分，平台实评 77 分 ——
这 13 分的差距催生了报告第 7 节「机器查不到、必须人工确认的事」，
也是整个技能里最值钱的部分。

## 30 秒验证它能不能跑

```bash
python challenge_submit_guard.py --self-test   # 5 个断言，全绿即装好
```

## 交付物清单

| 必交物 | 文件 | 说明 |
|---|---|---|
| skill说明 | `卢怡然_C4_skill说明.md` | 解决什么问题 / IO / 真实案例 / 设计取舍 |
| 可执行内容 | `卢怡然_C4_challenge-submit-guard.skill` | 可安装 ZIP 包（26.5 KB） |
| ↳ 源码 | `challenge-submit-guard/` | SKILL.md + 2 个脚本 + 挑战注册表 |
| demo | `卢怡然_C4_demo_01~04.png` | 自检 / 真实体检报告 / 提分杠杆 / 20 挑战清单 |
| 教学说明 | `卢怡然_C4_教学说明.md` | 3 分钟上手 / 6 个常见坑 / 优化技巧 |
| AI日志 | `卢怡然_C4_AI日志.md` | 4 轮迭代全记录（3 次被真实数据打脸） |
| AAR | `卢怡然_C4_AAR.md` | 决策取舍 / 失败根因 / 可迁移洞察 |

### 支撑材料

| 文件 | 说明 |
|---|---|
| `evidence/run_C1_real.txt` `run_c1_real.txt` `run_C2_real.txt` `run_C3_real.txt` | 对真实交付包的运行输出（逐字可复核） |
| `evidence/run_C4_self.txt` | 用本技能自检本 C4 提交包的报告 |
| `evidence/selftest_output.txt` / `list_output.txt` | 自检与注册表清单输出 |
| `evidence/install_test.txt` | 解压到陌生目录后重跑自检的记录 |
| `evidence/registry_snapshot.json` | 注册表的 JSON 快照（与 YAML 同源） |
| `tools/render_demo.py` | demo 截图渲染器（只排版真实输出，不改内容） |

## 快速上手

```bash
# 1. 解压 .skill（就是 ZIP），进入 scripts/
python challenge_submit_guard.py --self-test        # 确认环境

# 2. 体检
python challenge_submit_guard.py "你的/交付/文件夹" -c C4

# 3. 按报告第 6 节 TODO 执行 —— 先解红线，再补内容
```

详细教学（含 6 个常见坑）：`卢怡然_C4_教学说明.md`

## 传播状态（诚实区）

| 项 | 状态 |
|---|---|
| 发布到群 | ⏳ 待发出 |
| 被使用次数 | **0**（不编数字） |
| 使用反馈 | ⏳ 待收集 |
| v5 计划 | 粗估改区间 / 多文件夹对比扫描 |

> C4 的最高权重是"被使用次数"。技能的分数最终由传播决定，
> 这部分会在真实发生后回填 —— 包括失败的反馈。

## 已知局限

- 分数是**粗估**（C3 实测偏差 +13），只用于定位丢分维度
- 读不到"行为是否真的发生"（稿子齐 ≠ 发出去了）
- 不解析 PDF/DOCX/XLSX 的内容（只参与文件计数与交付物匹配）

---

_生成：challenge-submit-guard v5 · 2026-10-03_
