#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 reliability.json 生成可靠性测试报告，并把班级评审结果就位为交付物。

    python tools/make_reliability_report.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REL = ROOT / "reports" / "reliability.json"
CLASS = ROOT / "reports" / "评审报告.md"


def main() -> int:
    d = json.loads(REL.read_text(encoding="utf-8"))
    rows = d["rows"]
    naive = {r["id"]: r for r in d["naive_rows"]}
    labels = json.loads((ROOT / "tests" / "gold" / "labels.json")
                        .read_text(encoding="utf-8"))

    L = []
    L.append("# guoyusen_C4A_可靠性测试报告")
    L.append("")
    L.append("> 全部数据来自**真实执行**，可复现命令见文末。")
    L.append("> 原始 JSON：`reports/reliability.json`。")
    L.append("")
    L.append("## 一、为什么需要这份报告")
    L.append("")
    L.append("参考提交的做法是：自己造 10 个样本，跑出 **10/10、全部 100% 准确率**。")
    L.append("**自制测试集拿满分，说明的是测试集太容易，不是评审器可靠。**")
    L.append("")
    L.append("所以本报告的着力点不是」我又全对了「，而是三件事：")
    L.append("")
    L.append("1. **样本是难样本** —— 20 个，每个针对一个具体失效模式，")
    L.append("   其中 6 个是专门为「评审器会误报」造的；")
    L.append("2. **有对照组** —— 同一批样本上跑一个「只看文件名 + 直接数关键词」的")
    L.append("   朴素评审器（`NaiveEvaluator`，就在测试文件里）。")
    L.append("   **没有对照组的全对什么也证明不了**；")
    L.append("3. **阈值从分布里取** —— 0.55 这个数来自「真提交最低 0.667 / 堆砌 0.448」，")
    L.append("   不是拍的。")
    L.append("")
    L.append("## 二、评测集构成（20 个样本）")
    L.append("")
    L.append("| 样本 | 人工期望 | 测什么失效模式 |")
    L.append("|---|---|---|")
    for cid in sorted(labels):
        lab = labels[cid]
        if lab.get("mode") == "empty":
            exp = f"退出码 {lab.get('expect_exit')}"
        else:
            lo, hi = lab.get("composite_min"), lab.get("composite_max")
            exp = f"{lo}–{hi}" if lo is not None else "—"
            if lab.get("flags"):
                exp += "｜红旗 " + ",".join(lab["flags"])
        why = lab.get("rationale", "")[:56]
        L.append(f"| `{cid}` | {exp} | {why} |")
    L.append("")
    L.append("## 三、结果")
    L.append("")
    L.append("| 指标 | 本评审器 | 朴素评审器 |")
    L.append("|---|---:|---:|")
    L.append(f"| 综合分落在人工标注区间 | **{d['mine_band_hit']}/{d['band_total']}** "
             f"| {d['naive_band_hit']}/{d['band_total']} |")
    L.append(f"| 等级一致 | {d['level_hit']}/{d['level_total']} | — |")
    L.append(f"| 作者归因数一致 | {d['author_hit']}/{d['author_total']} | — |")
    L.append(f"| 退出码一致 | {d['exit_hit']}/{d['exit_total']} | — |")
    L.append("")
    L.append(f"- **红旗**：精确率 **{d['flag_precision']:.2f}**、"
             f"召回 **{d['flag_recall']:.2f}**、F1 **{d['flag_f1']:.2f}**"
             f"（TP {d['flag_tp']} / FP {d['flag_fp']} / FN {d['flag_fn']}）")
    L.append(f"- **确定性**：同一输入两次运行 JSON 逐字节相同 → "
             f"{'✅' if d['deterministic'] else '❌'}")
    L.append(f"- **鲁棒性**：整目录改名后分数不变 → "
             f"{'✅' if d['robust_to_rename'] else '❌'}")
    L.append(f"- **断言**：**{d['assertions_ok']} 通过 / {d['assertions_fail']} 失败**")
    L.append("")
    L.append("## 四、对照组：朴素评审器被什么骗到了")
    L.append("")
    L.append("`NaiveEvaluator` 故意只做「文件名匹配 + 关键词计数」，")
    L.append("不做否定判定、不做空文件判定、不做红旗封顶。三类陷阱样本的对照：")
    L.append("")
    L.append("| 样本 | 陷阱 | 本评审器 | 朴素评审器 | 人工区间 |")
    L.append("|---|---|---:|---:|---|")
    for cid in ("gold05_empty_deliverables", "gold06_keyword_stuffing",
                "gold10_negation_trap"):
        me = next((r for r in rows if r["id"] == cid), None)
        nv = naive.get(cid)
        lab = labels[cid]
        rng = f"{lab.get('composite_min')}–{lab.get('composite_max')}"
        L.append(f"| `{cid}` | {lab.get('rationale','')[:34]} | "
                 f"{me['composite'] if me else float('nan'):.2f} | "
                 f"{nv['composite'] if nv else float('nan'):.2f} | {rng} |")
    L.append("")
    L.append("**读法**：朴素版在「空文件假装交付」上给 0.40（人工期望 ≤0.45 勉强擦边），")
    L.append("在」关键词堆砌「上给 **1.00**（人工期望 ≤0.65）—— ")
    L.append("一个什么都没写的提交，靠堆词就能拿满分。")
    L.append("")
    L.append("## 五、逐样本结果")
    L.append("")
    L.append("| 样本 | 实得综合分 | 等级 | 红旗 | 人工区间 | 是否落在区间 |")
    L.append("|---|---:|---|---|---|---|")
    for r in rows:
        lab = labels[r["id"]]
        lo, hi = lab.get("composite_min"), lab.get("composite_max")
        ok = "—" if lo is None else ("✅" if lo <= r["composite"] <= hi else "❌")
        L.append(f"| `{r['id']}` | {r['composite']:.2f} | {r['level']} | "
                 f"{','.join(r['flags']) or '—'} | {lo}–{hi} | {ok} |")
    L.append("")
    if d["failures"]:
        L.append("### 未通过的断言")
        L.append("")
        for x in d["failures"]:
            L.append(f"- {x}")
        L.append("")
    else:
        L.append("**没有未通过的断言。**")
        L.append("")
    L.append("## 六、这份可靠性证明的边界（必须说清）")
    L.append("")
    L.append("1. **样本是我自己造的，评审器也是我自己写的。**")
    L.append("   自造样本上全对，只能证明**实现符合设计**，")
    L.append("   **不能证明设计是对的**。要证后者需要在**别人标注的**样本上验证。")
    L.append("2. **阈值是校准出来的，有过拟合风险。** 堆砌阈值 0.55 取自")
    L.append("   「真提交最低 0.667 / 堆砌 0.448」；语料一变可能需要重定。")
    L.append("3. **只有一处真正的外部校验**：`阮如意` 那份公开 AI 初评 90/100，")
    L.append("   本评审器给 0.92。**一个数据点不能证明校准正确**，")
    L.append("   只能说没有系统性跑偏。")
    L.append("4. **规则层不判内容质量。** 套话写得漂亮的提交能拿高分 ——")
    L.append("   这是设计上的已知边界，不是 bug。")
    L.append("")
    L.append("> 把这四条写出来，比把准确率写成 100% 更有用：")
    L.append("> **知道自己在哪种情况下会错，才知道结论能用在哪。**")
    L.append("")
    L.append("## 七、复现命令")
    L.append("")
    L.append("```bash")
    L.append("python tools/make_gold.py                # 生成 20 个评测样本")
    L.append("python tests/test_evaluator.py           # 跑全部断言与对照实验")
    L.append("python tools/make_reliability_report.py  # 由 JSON 生成本报告")
    L.append("python tools/class_report.py             # 在 8 份真实提交上评审")
    L.append("```")
    L.append("")
    (ROOT / "guoyusen_C4A_可靠性测试报告.md").write_text(
        "\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("已写出 guoyusen_C4A_可靠性测试报告.md")

    # 班级评审报告就位为交付物
    if CLASS.exists():
        shutil.copyfile(CLASS, ROOT / "guoyusen_C4A_评审报告.md")
        print("已写出 guoyusen_C4A_评审报告.md")
    # 结果 JSON 与详表
    res = ROOT / "reports" / "评审结果.json"
    if res.exists():
        shutil.copyfile(res, ROOT / "guoyusen_C4A_评审结果.json")
        print("已写出 guoyusen_C4A_评审结果.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
