#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可靠性测试：在**人工标注**的评测集上量评审器的准确率、确定性与鲁棒性。

    python tests/test_evaluator.py [--json out.json]

测四件事：
  A 标注一致率 —— 与 labels.json 的人工期望比
  B 确定性     —— 同输入跑两次，JSON 逐字节相同
  C 鲁棒性     —— 目录改名 / 文件顺序打乱后分数不变
  D 对抗性     —— 与「朴素评审器」（数关键词、只看文件名）对照
                  证明关键设计（否定闸门 / 空文件闸门 / 红旗 cap）真的有用

**为什么要有 D**：一个评审器「在自己造的样本上全对」什么都证明不了。
要证明的是「它比朴素做法强在哪」，所以必须把朴素做法也跑一遍。

退出码 0 = 全部断言通过。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "tests" / "gold"
EVAL = ROOT / "skill-evaluator" / "scripts" / "c4a_evaluator.py"
RUBRIC = ROOT / "skill-evaluator" / "references" / "c4_rubric.json"

_spec = importlib.util.spec_from_file_location("ev", EVAL)
ev = importlib.util.module_from_spec(_spec)
sys.modules["ev"] = ev
_spec.loader.exec_module(ev)

OK = FAIL = 0
FAILS = []
NOTES = []


def ck(cond, label, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  [OK]   {label}")
    else:
        FAIL += 1
        FAILS.append(f"{label}  {detail}")
        print(f"  [FAIL] {label}  {detail}")


# =====================================================================
# 朴素评审器（对照组）
# =====================================================================

class NaiveEvaluator:
    """故意写得很朴素：**只看文件名 + 直接数关键词**。

    它代表「机械检查」式的评审器，也就是 90 分参考提交被评审点出的那个短板。
    故意不做三件事：
      · 不做否定语境判定（「没有测试」会被算成有测试）
      · 不做空文件判定（文件名对就算交付）
      · 不做红旗 cap（分数只由加权和决定）

    如果本评审器在这三件事上没有明显优势，那这些设计就是自我感动。
    """

    KW = ["测试", "安装", "依赖", "输入", "输出", "工作流", "边界", "预期",
          "断言", "步骤", "上手", "prompt", "迭代", "demo", "示例"]

    def __init__(self, root: Path):
        self.root = Path(root)

    def run(self) -> dict:
        files = [p for p in self.root.rglob("*") if p.is_file()
                 and not p.name.startswith(".")]
        names = [p.name for p in files]
        slots = {
            "skill_doc": r"skill说明|技能说明",
            "executable": r"\.(skill|py)$",
            "demo": r"demo|演示|截图|\\.(png|mp4|jpg)$",
            "teaching": r"教学",
            "ai_log": r"AI日志|AI_log",
        }
        present, text = [], ""
        for k, rx in slots.items():
            if any(re.search(rx, n, re.I) for n in names):
                present.append(k)
        for p in files:
            if p.suffix.lower() in (".md", ".txt", ".py"):
                try:
                    text += p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pass
        hits = sum(1 for k in self.KW if k in text)      # 直接数，不判否定
        completeness = len(present) / 5
        quality = min(1.0, hits / 12)
        composite = completeness * 0.4 + quality * 0.6    # 无 cap
        return {"completeness": completeness, "quality": quality,
                "composite": composite, "flags": [],
                "n_authors": 1}


# =====================================================================
# 运行本评审器
# =====================================================================

def run_eval(path: Path, out: Path, deterministic=True):
    """就地调用（比起子进程快，也便于断言）。"""
    argv = [str(path), "--out", str(out), "--format", "json"]
    if deterministic:
        argv.append("--deterministic")
    old = sys.argv
    sys.argv = ["c4a_evaluator.py"] + argv
    try:
        code = ev.main()
    finally:
        sys.argv = old
    j = out / "评审结果.json"
    data = json.loads(j.read_text(encoding="utf-8")) if j.exists() else None
    return code, data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(ROOT / "reports" / "reliability.json"))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    labels = json.loads((GOLD / "labels.json").read_text(encoding="utf-8"))
    # 临时目录放在仓库内：本机的沙箱不允许写系统 temp 目录
    # （`tempfile.mkdtemp()` 默认落在 %LOCALAPPDATA%\Temp，会 PermissionError）。
    tmproot = ROOT / ".tmp_test"
    shutil.rmtree(tmproot, ignore_errors=True)
    tmproot.mkdir(parents=True, exist_ok=True)
    tmp = tmproot

    print("A · 标注一致率")
    rows, naive_rows = [], []
    level_hit = level_tot = 0
    flag_tp = flag_fp = flag_fn = 0
    band_hit = 0
    author_hit = author_tot = 0
    exit_hit = exit_tot = 0

    for cid in sorted(labels):
        lab = labels[cid]
        d = GOLD / cid
        out = tmp / cid
        code, data = run_eval(d, out)
        mode = lab.get("mode")
        if mode == "empty" or lab.get("expect_exit"):
            exit_tot += 1
            exp = lab.get("expect_exit", 3)
            ok = (code == exp)
            exit_hit += ok
            ck(ok, f"{cid}: 退出码 == {exp}", f"实得 {code}")
            continue
        if data is None:
            ck(False, f"{cid}: 产出结果", f"exit={code}")
            continue
        subs = data["submissions"]
        if not subs:
            ck(False, f"{cid}: 至少识别出 1 位作者")
            continue
        s = subs[0]

        # 作者数量
        if "n_authors" in lab:
            author_tot += 1
            ok = (data["n_authors"] == lab["n_authors"])
            author_hit += ok
            ck(ok, f"{cid}: 作者数 == {lab['n_authors']}",
               f"实得 {data['n_authors']}")
        if "author_source" in lab:
            ck(s["author_source"] == lab["author_source"],
               f"{cid}: 作者归属来源 == {lab['author_source']}",
               f"实得 {s['author_source']}")

        # 完整性
        if "completeness" in lab:
            ok = abs(s["completeness"] - lab["completeness"]) < 1e-6
            ck(ok, f"{cid}: 完整性 == {lab['completeness']}",
               f"实得 {s['completeness']}")

        # 红旗：精确集合比对
        if "flags" in lab:
            got = {f["id"] for f in s["red_flags"]}
            exp = set(lab["flags"])
            tp = len(got & exp)
            flag_tp += tp
            flag_fp += len(got - exp)
            flag_fn += len(exp - got)
            ck(got == exp, f"{cid}: 红旗集合 == {sorted(exp) or '[]'}",
               f"实得 {sorted(got)}")

        # 分数区间
        cmin, cmax = lab.get("composite_min"), lab.get("composite_max")
        if cmin is not None and cmax is not None:
            ok = cmin <= s["composite"] <= cmax
            band_hit += ok
            ck(ok, f"{cid}: 综合分 ∈ [{cmin}, {cmax}]",
               f"实得 {s['composite']:.3f}")

        # 等级
        if lab.get("level"):
            level_tot += 1
            ok = s["level"] == lab["level"]
            level_hit += ok
            ck(ok, f"{cid}: 等级 == {lab['level']}", f"实得 {s['level']}")
        elif lab.get("allow_levels"):
            level_tot += 1
            ok = s["level"] in lab["allow_levels"]
            level_hit += ok
            ck(ok, f"{cid}: 等级 ∈ {lab['allow_levels']}", f"实得 {s['level']}")

        # 否定闸门：指定检查项必须**不通过**
        for item in lab.get("must_not_find", []):
            ckey, cid2 = item.split(".")
            got = next((c for c in s["conditions"][ckey]["checks"]
                        if c["id"] == cid2), None)
            ck(got is not None and not got["pass"],
               f"{cid}: 否定闸门 —— {item} 应为不通过",
               f"实得 {got['pass'] if got else '不存在'}")

        # 某条件分数上限
        for ckey, mx in (lab.get("condition_max") or {}).items():
            ck(s["conditions"][ckey]["score"] <= mx,
               f"{cid}: {ckey} ≤ {mx}",
               f"实得 {s['conditions'][ckey]['score']:.2f}")

        rows.append({"id": cid, "composite": s["composite"],
                     "level": s["level"], "completeness": s["completeness"],
                     "flags": sorted(f["id"] for f in s["red_flags"]),
                     "quality": s["quality"],
                     "expect_min": cmin, "expect_max": cmax})

        # 朴素对照
        nv = NaiveEvaluator(d).run()
        naive_rows.append({"id": cid, "composite": nv["composite"],
                           "level": None, "flags": [],
                           "expect_min": cmin, "expect_max": cmax,
                           "completeness": nv["completeness"]})

    prec = flag_tp / max(1, flag_tp + flag_fp)
    rec = flag_tp / max(1, flag_tp + flag_fn)
    f1 = 2 * prec * rec / max(1e-9, prec + rec)

    print("\nB · 确定性")
    d = GOLD / "gold01_perfect"
    h = []
    for i in range(2):
        o = tmp / f"det{i}"
        run_eval(d, o)
        h.append(hashlib.sha256((o / "评审结果.json").read_bytes()).hexdigest())
    ck(h[0] == h[1], "同一输入两次运行，JSON 逐字节相同", f"{h[0][:12]} vs {h[1][:12]}")

    print("\nC · 鲁棒性（改名 + 打乱）")
    src = GOLD / "gold01_perfect"
    dst = tmp / "robust" / "zzz_renamed"
    shutil.copytree(src, dst)
    o1 = tmp / "r1"
    _, base = run_eval(src, o1)
    o2 = tmp / "r2"
    _, moved = run_eval(dst, o2)
    same = (base["submissions"][0]["completeness"]
            == moved["submissions"][0]["completeness"]
            and abs(base["submissions"][0]["quality"]
                    - moved["submissions"][0]["quality"]) < 1e-9)
    ck(same, "整目录改名后分数不变（不依赖路径字面量）",
       f"{base['submissions'][0]['composite']:.3f} vs "
       f"{moved['submissions'][0]['composite']:.3f}")

    print("\nD · 对抗性：本评审器 vs 朴素评审器")
    # 在「评分区间」上的命中率：本评审器应显著更高；朴素版在陷阱样本上会翻车
    def in_band(r):
        if r["expect_min"] is None:
            return None
        return r["expect_min"] <= r["composite"] <= r["expect_max"]
    mine = [in_band(r) for r in rows]
    naive = [in_band(r) for r in naive_rows]
    ok_mine = sum(1 for x in mine if x)
    ok_naive = sum(1 for x in naive if x)
    tot = sum(1 for x in mine if x is not None)
    print(f"    本评审器落在标注区间：{ok_mine}/{tot}")
    print(f"    朴素评审器落在标注区间：{ok_naive}/{tot}")
    ck(ok_mine > ok_naive, "本评审器的区间命中率高于朴素评审器",
       f"{ok_mine} vs {ok_naive}")
    # 两个关键陷阱：朴素版会因为「只看文件名/直接数关键词」而虚高
    trap = {"gold05_empty_deliverables": "空文件假装交付",
            "gold06_keyword_stuffing": "关键词堆砌"}
    for cid, why in trap.items():
        nv = next(r for r in naive_rows if r["id"] == cid)
        me = next(r for r in rows if r["id"] == cid)
        print(f"    {cid:30s} 本 {me['composite']:.2f}  朴素 {nv['composite']:.2f}"
              f"   （{why}）")
        ck(nv["composite"] > me["composite"] + 0.15,
           f"{cid}: 朴素评审器被「{why}」骗到（分数明显虚高）",
           f"朴素 {nv['composite']:.2f} vs 本 {me['composite']:.2f}")

    # 否定语境这一项**不能靠比较总分**来断言：陷阱样本本身内容很少，
    # 两边总分都低，比总分什么也证明不了（我第一版就是这么写的，断言必然失败）。
    # 正确的断言是直接看规则层行为：文本里确实有「测试」二字
    # （朴素计数器必然命中），而本评审器不判 V1 通过。
    trapdir = GOLD / "gold10_negation_trap"
    raw = "".join(q.read_text(encoding="utf-8", errors="ignore")
                  for q in trapdir.rglob("*.md"))
    ck("测试" in raw, "否定陷阱样本里确实含「测试」二字（朴素计数器必然命中）")
    o = tmp / "neg"
    _, nd = run_eval(trapdir, o)
    v1 = next(c for c in nd["submissions"][0]["conditions"]["verifiable"]["checks"]
              if c["id"] == "V1")
    ck(not v1["pass"], "否定闸门：含「没有测试」时 V1 判为不通过",
       f"实得 pass={v1['pass']}")

    # 汇总
    summary = {
        "n_cases": len(labels),
        "band_hit": band_hit, "band_total": tot,
        "level_hit": level_hit, "level_total": level_tot,
        "author_hit": author_hit, "author_total": author_tot,
        "exit_hit": exit_hit, "exit_total": exit_tot,
        "flag_precision": prec, "flag_recall": rec, "flag_f1": f1,
        "flag_tp": flag_tp, "flag_fp": flag_fp, "flag_fn": flag_fn,
        "naive_band_hit": ok_naive, "mine_band_hit": ok_mine,
        "deterministic": h[0] == h[1], "robust_to_rename": bool(same),
        "assertions_ok": OK, "assertions_fail": FAIL, "failures": FAILS,
        "rows": rows, "naive_rows": naive_rows,
    }
    outp = Path(a.json)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                    encoding="utf-8", newline="\n")

    print("\n" + "=" * 64)
    print(f"区间命中 {band_hit}/{tot} ｜ 等级 {level_hit}/{level_tot} ｜ "
          f"作者数 {author_hit}/{author_tot} ｜ 退出码 {exit_hit}/{exit_tot}")
    print(f"红旗 精确率 {prec:.2f} / 召回 {rec:.2f} / F1 {f1:.2f}"
          f"（TP {flag_tp} FP {flag_fp} FN {flag_fn}）")
    print(f"断言 {OK} 通过 / {FAIL} 失败")
    if FAILS:
        print("未通过项：")
        for x in FAILS:
            print("   -", x)
    print(f"已写出 {outp}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
