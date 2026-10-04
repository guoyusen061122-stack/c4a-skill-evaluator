#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""班级评审：对一个」每人一个目录/仓库「的语料逐个评审，再汇总成一份报告。

    python tools/class_report.py --corpus corpus --out reports

**为什么不把所有提交塞进一棵树里跑一次**：实测会出问题。
8 个仓库的目录形如 `corpus/<repo>/<repo>-main/<文件>`，
多层包装目录让作者归因失效 —— 有前缀的文件能归对，其余 40 个掉进「未识别」。
真实收作业就是「一人一个文件夹」，逐个评审再汇总既简单又符合实际。

这个脚本同时输出每份提交的单独报告，便于逐个复核。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "skill-evaluator" / "scripts" / "c4a_evaluator.py"
RUBRIC = ROOT / "skill-evaluator" / "references" / "c4_rubric.json"

_spec = importlib.util.spec_from_file_location("ev", EV)
ev = importlib.util.module_from_spec(_spec)
sys.modules["ev"] = ev
_spec.loader.exec_module(ev)

LEVEL_LABEL = {"L4": "完善", "L3": "良好", "L2": "及格", "L1": "待改进"}
COND = ["reusable", "executable", "verifiable", "clear_io"]


def eval_one(path: Path, outdir: Path) -> dict | None:
    argv = [str(path), "--out", str(outdir), "--format", "json", "--quiet",
            "--deterministic"]
    old = sys.argv
    sys.argv = ["c4a_evaluator.py"] + argv
    try:
        code = ev.main()
    finally:
        sys.argv = old
    p = outdir / "评审结果.json"
    if code != 0 or not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "corpus"))
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args()

    corpus, out = Path(a.corpus), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    per = out / "per_submission"
    shutil.rmtree(per, ignore_errors=True)
    per.mkdir(parents=True, exist_ok=True)

    repos = sorted(p for p in corpus.iterdir() if p.is_dir())
    print(f"语料 {corpus}：{len(repos)} 个提交目录")
    subs, failed = [], []
    for r in repos:
        d = eval_one(r, per / r.name)
        if d is None or not d["submissions"]:
            failed.append(r.name)
            print(f"  ✗ {r.name}：未能识别出提交")
            continue
        for s in d["submissions"]:
            s["_repo"] = r.name
            subs.append(s)
        names = ", ".join(s["author"] for s in d["submissions"])
        print(f"  ✓ {r.name[:46]:48s} → {names}")

    subs.sort(key=lambda s: (-s["composite"], s["author"]))
    required = 5
    L = []
    L.append("# C4 技能提交自动评审报告")
    L.append("")
    L.append(f"- 评审器：`c4a-evaluator` v{ev.VERSION}（规则层，纯标准库、离线、确定性）")
    L.append(f"- 语料：**{len(repos)} 份真实提交**（来自公开 GitHub 仓库，见 `corpus/`）")
    L.append(f"- 识别出 **{len(subs)}** 位作者；未能识别 {len(failed)} 份"
             + (f"（{', '.join(failed)}）" if failed else ""))
    L.append(f"- 规则文件 sha256：`{__import__('hashlib').sha256(RUBRIC.read_bytes()).hexdigest()}`")
    L.append("")
    L.append("> ⚠️ **这份报告是对真实公开提交的机械评审，不是对同学的人身评价。**")
    L.append("> 结论仅覆盖「交付物齐不齐、结构够不够」，**不判断内容好不好** ——")
    L.append("> 后者需要 LLM 复核层（见 `references/llm_review_protocol.md`）。")
    L.append("")
    L.append("## 一、班级总览")
    L.append("")
    full = sum(1 for s in subs if not s["missing"])
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 提交数 | {len(subs)} |")
    L.append(f"| 完整提交（5/5） | {full} |")
    L.append(f"| 部分提交 | {len(subs) - full} |")
    L.append(f"| 平均质量分 | {sum(s['quality'] for s in subs)/max(1,len(subs)):.2f} |")
    L.append(f"| 触发红旗 | {sum(1 for s in subs if s['red_flags'])} 份 |")
    L.append("")
    L.append("## 二、综合排名")
    L.append("")
    L.append("| 排名 | 作者 | 完整性 | 质量分 | 综合分 | 评级 | 红旗 |")
    L.append("|---:|---|---:|---:|---:|---|---|")
    for i, s in enumerate(subs, 1):
        fl = ", ".join(f["label"] for f in s["red_flags"]) or "—"
        L.append(f"| {i} | {s['author']} | {len(s['present'])}/{required} | "
                 f"{s['quality']:.2f} | **{s['composite']:.2f}** | "
                 f"{s['level']}·{LEVEL_LABEL[s['level']]} | {fl} |")
    L.append("")
    L.append("## 三、各维度得分")
    L.append("")
    L.append("| 作者 | 可复用 | 可执行 | 可验证 | IO 明确 |")
    L.append("|---|---:|---:|---:|---:|")
    for s in subs:
        L.append(f"| {s['author']} | "
                 + " | ".join(f"{s['conditions'][k]['score']:.2f}" for k in COND)
                 + " |")
    L.append("")
    L.append("## 四、全班共性问题")
    L.append("")
    miss = {}
    for s in subs:
        for m in s["missing"]:
            miss[m] = miss.get(m, 0) + 1
    if miss:
        L.append("**缺失的交付物：**")
        L.append("")
        for k, n in sorted(miss.items(), key=lambda x: (-x[1], x[0])):
            L.append(f"- {ev.__dict__.get('_', None) or ''}"
                     f"{ {'skill_doc':'Skill 说明文档','executable':'可执行内容','demo':'Demo','teaching':'教学说明','ai_log':'AI 日志'}.get(k,k) }："
                     f"{n} 人缺失")
    else:
        L.append("**没有人缺交付物。** 8 份提交全部 5/5 —— 说明 C4 的命名规范被普遍遵守；")
        L.append("这也意味着「完整性」这一维度在当前语料上**没有区分度**，")
        L.append("真正拉开差距的是质量四条件。")
    L.append("")
    weak = {}
    for s in subs:
        for k in COND:
            if s["conditions"][k]["score"] < 1.0:
                weak[k] = weak.get(k, 0) + 1
    L.append("**最弱的质量维度：**")
    L.append("")
    for k, n in sorted(weak.items(), key=lambda x: (-x[1], x[0])):
        L.append(f"- {s and ''}"
                 f"{ {'reusable':'可复用','executable':'可执行','verifiable':'可验证','clear_io':'IO 明确'}.get(k,k) }："
                 f"{n} 人未满分")
    L.append("")
    L.append("## 五、红旗明细")
    L.append("")
    any_flag = False
    for s in subs:
        for f in s["red_flags"]:
            any_flag = True
            ev_txt = "；".join(str(x)[:70] for x in f["evidence"][:2])
            L.append(f"- **{s['author']}** · {f['label']}（{f['severity']}）"
                     f"：{ev_txt}")
    if not any_flag:
        L.append("无。")
    L.append("")
    L.append("> `hardcoded_path` 只说明文档里**出现了**绝对路径字样，")
    L.append("> 不代表作者本人就是这么用的 —— 需要人工复核上下文，")
    L.append("> 这也是红旗只压分、不下结论的原因。")
    L.append("")
    L.append("## 六、评审器可靠性")
    L.append("")
    L.append("完整指标见 `../guoyusen_C4A_可靠性测试报告.md` 与 `reliability.json`。这里放结论：")
    L.append("")
    L.append("- 在 **20 个带人工标注的评测样本**上，综合分区间命中、等级、"
             "红旗集合、作者归因数、退出码全部一致；")
    L.append("- 与**朴素评审器**（只看文件名 + 直接数关键词）对照，"
             "朴素版在「空文件假装交付」「关键词堆砌」两类样本上分数显著虚高；")
    L.append("- 同一输入两次运行输出**逐字节相同**；整目录改名后分数不变。")
    L.append("")
    L.append("**但必须说清楚这份可靠性的边界**：评测样本是我自己造的，"
             "评审器也是我自己写的 —— 自造样本上全对，"
             "只能证明「实现符合设计」，不能证明「设计是对的」。")
    L.append("真正的外部校验只有一处：**阮如意**这份提交的公开 AI 初评是 90/100，")
    _ry = [s["composite"] for s in subs if s["author"] == "阮如意"]
    L.append("本评审器给出 "
             + (f"**{_ry[0]:.2f} × 100 = {_ry[0]*100:.0f}/100**。" if _ry
                else "（本语料中未包含该提交）。"))
    L.append("")
    L.append("## 七、逐份报告")
    L.append("")
    L.append("每份提交的完整报告见 `per_submission/<仓库名>/评审报告.md`。")
    L.append("")
    (out / "评审报告.md").write_text("\n".join(L) + "\n", encoding="utf-8",
                                     newline="\n")

    merged = {"evaluator": f"c4a-evaluator v{ev.VERSION}",
              "n_repos": len(repos), "n_authors": len(subs),
              "failed_repos": failed, "submissions": subs}
    (out / "评审结果.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8",
        newline="\n")
    print(f"\n已写出 {out/'评审报告.md'} 与 {out/'评审结果.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
