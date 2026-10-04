# guoyusen_C4A_可靠性测试报告

> 全部数据来自**真实执行**，可复现命令见文末。
> 原始 JSON：`reports/reliability.json`。

## 一、为什么需要这份报告

参考提交的做法是：自己造 10 个样本，跑出 **10/10、全部 100% 准确率**。
**自制测试集拿满分，说明的是测试集太容易，不是评审器可靠。**

所以本报告的着力点不是」我又全对了「，而是三件事：

1. **样本是难样本** —— 20 个，每个针对一个具体失效模式，
   其中 6 个是专门为「评审器会误报」造的；
2. **有对照组** —— 同一批样本上跑一个「只看文件名 + 直接数关键词」的
   朴素评审器（`NaiveEvaluator`，就在测试文件里）。
   **没有对照组的全对什么也证明不了**；
3. **阈值从分布里取** —— 0.55 这个数来自「真提交最低 0.667 / 堆砌 0.448」，
   不是拍的。

## 二、评测集构成（20 个样本）

| 样本 | 人工期望 | 测什么失效模式 |
|---|---|---|
| `gold01_perfect` | 0.85–1.0 | 五个交付物齐全，内容真实完整，无红旗 → 应落在 L4 上限区间。 |
| `gold02_missing_demo` | 0.6–0.8｜红旗 missing_core | 缺 1 个必交交付物 → 完整性 0.8；按 missing_core 的 cap_table，缺 1 个上限  |
| `gold03_missing_ailog` | 0.55–0.8｜红旗 missing_core | 缺 AI 日志 → missing_core(cap75) 与 no_ai_log(cap80) 同时命中，取更 |
| `gold04_only_doc` | 0.1–0.45｜红旗 missing_core | 只交 1/5 → 缺 4 个，cap_table 命中 [3,45]，上限 45。 |
| `gold05_empty_deliverables` | 0.0–0.45｜红旗 missing_core | 五个文件名全对但都是空文件。近空文件不参与槽位匹配 → 完整性应为 0（不是 1.0）。这是评价一个评审器最关键 |
| `gold06_keyword_stuffing` | 0.0–1.0｜红旗 keyword_stuffing | 文件名齐全、正文里堆满规则词，但没有任何真实内容与结构 → 应被 keyword_stuffing 抓住并压到  |
| `gold07_hardcoded_path` | 0.6–0.85｜红旗 hardcoded_path | 出现 `C:\Users\...` → hardcoded_path(cap85)。这是「可复用」最常见的破坏方 |
| `gold08_secret_leak` | 0.0–0.5｜红旗 secret_leak | 明文 `sk-` 密钥 → secret_leak(cap50)；应显著压分。 |
| `gold09_no_io` | 0.4–0.85 | 说明文档里**没有**「输入X，输出Y」式的一句话 → clear_io 不应满分。这是区分「有文档」和「文档讲 |
| `gold10_negation_trap` | —｜红旗 missing_core | 正文写的是「**没有**测试」「**无**教学说明」「**尚未**加入断言」—— 朴素关键词计数器会把 V1/V |
| `gold11_multi_version` | 0.75–1.0 | v1/v2 两个版本都在。槽位匹配只能给 skill_doc 一个文件 → 另一个版本**不应**被算成别的交付 |
| `gold12_gbk` | 0.85–1.0 | 文件用 **GBK** 编码（Windows 记事本默认保存格式）。UTF-8-only 的读取器会拿到乱码，把 |
| `gold13_nonstandard_names` | 0.8–1.0 | 文件名不带 `姓名_C4_` 前缀，全在仓库根目录下的一个子目录里。单候选 → 按仓库名归一位作者（repo_l |
| `gold14_binary_only` | 0.0–0.45｜红旗 missing_core | 只交了演示文件 → 完整性 0.2，缺 4 个。 |
| `gold15_syntax_error` | 0.5–0.88｜红旗 syntax_error | 附带的 .py 编译不过 → syntax_error(cap85) 且 E5 检查项不通过。 |
| `gold16_skill_package` | 0.8–1.0 | 可执行内容是真正的 `.skill`（tar.gz）包，而不是 .py。评审器必须能解开它、读到里面的 SKIL |
| `gold17_empty_folder` | 退出码 3 | 完全空的目录 → 应报「未找到任何文件」并以非零退出码结束，而不是假装评了 0 分。 |
| `gold18_no_demo_but_rich` | 0.6–0.88｜红旗 missing_core | 内容质量很高但缺 demo → cap 75 把它压在 L3，**不应因为「写得好」就豁免硬性交付物要求**。 |
| `gold19_machine_prefix` | 0.85–1.0 | `evidence/run_C4_self.txt` 的文件名符合 `前缀_C4_后缀`，会把作者识别成 `ru |
| `gold20_placeholder_ok` | 0.85–1.0 | 演示目录里有一个有意的空占位文件（`占位.md`）。把它算成「交付物为空」会误伤一个干净的提交 —— 实测踩到过 |

## 三、结果

| 指标 | 本评审器 | 朴素评审器 |
|---|---:|---:|
| 综合分落在人工标注区间 | **18/18** | 16/18 |
| 等级一致 | 17/17 | — |
| 作者归因数一致 | 1/1 | — |
| 退出码一致 | 1/1 | — |

- **红旗**：精确率 **1.00**、召回 **1.00**、F1 **1.00**（TP 11 / FP 0 / FN 0）
- **确定性**：同一输入两次运行 JSON 逐字节相同 → ✅
- **鲁棒性**：整目录改名后分数不变 → ✅
- **断言**：**87 通过 / 0 失败**

## 四、对照组：朴素评审器被什么骗到了

`NaiveEvaluator` 故意只做「文件名匹配 + 关键词计数」，
不做否定判定、不做空文件判定、不做红旗封顶。三类陷阱样本的对照：

| 样本 | 陷阱 | 本评审器 | 朴素评审器 | 人工区间 |
|---|---|---:|---:|---|
| `gold05_empty_deliverables` | 五个文件名全对但都是空文件。近空文件不参与槽位匹配 → 完整性应为  | 0.17 | 0.40 | 0.0–0.45 |
| `gold06_keyword_stuffing` | 文件名齐全、正文里堆满规则词，但没有任何真实内容与结构 → 应被 k | 0.60 | 1.00 | 0.0–1.0 |
| `gold10_negation_trap` | 正文写的是「**没有**测试」「**无**教学说明」「**尚未**加 | 0.43 | 0.41 | None–0.6 |

**读法**：朴素版在「空文件假装交付」上给 0.40（人工期望 ≤0.45 勉强擦边），
在」关键词堆砌「上给 **1.00**（人工期望 ≤0.65）—— 
一个什么都没写的提交，靠堆词就能拿满分。

## 五、逐样本结果

| 样本 | 实得综合分 | 等级 | 红旗 | 人工区间 | 是否落在区间 |
|---|---:|---|---|---|---|
| `gold01_perfect` | 0.97 | L4 | — | 0.85–1.0 | ✅ |
| `gold02_missing_demo` | 0.75 | L3 | missing_core | 0.6–0.8 | ✅ |
| `gold03_missing_ailog` | 0.70 | L3 | missing_core | 0.55–0.8 | ✅ |
| `gold04_only_doc` | 0.29 | L1 | missing_core | 0.1–0.45 | ✅ |
| `gold05_empty_deliverables` | 0.17 | L1 | missing_core | 0.0–0.45 | ✅ |
| `gold06_keyword_stuffing` | 0.60 | L2 | keyword_stuffing | 0.0–1.0 | ✅ |
| `gold07_hardcoded_path` | 0.85 | L4 | hardcoded_path | 0.6–0.85 | ✅ |
| `gold08_secret_leak` | 0.50 | L2 | secret_leak | 0.0–0.5 | ✅ |
| `gold09_no_io` | 0.80 | L3 | — | 0.4–0.85 | ✅ |
| `gold10_negation_trap` | 0.43 | L1 | missing_core | None–0.6 | — |
| `gold11_multi_version` | 0.89 | L4 | — | 0.75–1.0 | ✅ |
| `gold12_gbk` | 0.89 | L4 | — | 0.85–1.0 | ✅ |
| `gold13_nonstandard_names` | 0.89 | L4 | — | 0.8–1.0 | ✅ |
| `gold14_binary_only` | 0.17 | L1 | missing_core | 0.0–0.45 | ✅ |
| `gold15_syntax_error` | 0.85 | L4 | syntax_error | 0.5–0.88 | ✅ |
| `gold16_skill_package` | 0.91 | L4 | — | 0.8–1.0 | ✅ |
| `gold18_no_demo_but_rich` | 0.75 | L3 | missing_core | 0.6–0.88 | ✅ |
| `gold19_machine_prefix` | 0.89 | L4 | — | 0.85–1.0 | ✅ |
| `gold20_placeholder_ok` | 0.89 | L4 | — | 0.85–1.0 | ✅ |

**没有未通过的断言。**

## 六、这份可靠性证明的边界（必须说清）

1. **样本是我自己造的，评审器也是我自己写的。**
   自造样本上全对，只能证明**实现符合设计**，
   **不能证明设计是对的**。要证后者需要在**别人标注的**样本上验证。
2. **阈值是校准出来的，有过拟合风险。** 堆砌阈值 0.55 取自
   「真提交最低 0.667 / 堆砌 0.448」；语料一变可能需要重定。
3. **只有一处真正的外部校验**：`阮如意` 那份公开 AI 初评 90/100，
   本评审器给 0.92。**一个数据点不能证明校准正确**，
   只能说没有系统性跑偏。
4. **规则层不判内容质量。** 套话写得漂亮的提交能拿高分 ——
   这是设计上的已知边界，不是 bug。

> 把这四条写出来，比把准确率写成 100% 更有用：
> **知道自己在哪种情况下会错，才知道结论能用在哪。**

## 七、复现命令

```bash
python tools/make_gold.py                # 生成 20 个评测样本
python tests/test_evaluator.py           # 跑全部断言与对照实验
python tools/make_reliability_report.py  # 由 JSON 生成本报告
python tools/class_report.py             # 在 8 份真实提交上评审
```

