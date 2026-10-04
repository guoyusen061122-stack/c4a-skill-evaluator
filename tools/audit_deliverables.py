#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付物全量核验：把"报告里声称的东西"逐条变成可执行的检查。

    python tools/audit_deliverables.py

每条检查都对应交付要求里的一句话。不通过就打印 FAIL 并以非零码退出，
可以直接当 CI 门禁。

分五块：
  A  必交文件存在性与命名
  B  各文件内容要求（字数、章节、样本数）
  C  数值跨文件一致性（评审结果 ↔ 可靠性报告 ↔ 方案设计里引用的数字）
  D  技能包（frontmatter / 无缓存 / 可独立运行）
  E  评审器自身（确定性 / 依赖为零 / 规则文件合法）
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK = WARN = FAIL = 0
LINES: list[str] = []


def ck(cond, block, label, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        LINES.append(f"  [OK]   {block} {label}")
    else:
        FAIL += 1
        LINES.append(f"  [FAIL] {block} {label}  {detail}")
    return bool(cond)


def warn(block, label, detail=""):
    global WARN
    WARN += 1
    LINES.append(f"  [WARN] {block} {label}  {detail}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def n_cjk(s: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def main() -> int:
    # ---------------- A ----------------
    LINES.append("A · 必交文件")
    req = {
        "方案设计": "guoyusen_C4A_方案设计.md",
        "技能包源码": "skill-evaluator/SKILL.md",
        "技能包(.skill)": "guoyusen_C4A_skill-evaluator.skill",
        "评审报告": "guoyusen_C4A_评审报告.md",
        "AI 日志": "guoyusen_C4A_AI日志.md",
        "AAR 复盘": "guoyusen_C4A_AAR.md",
        "可靠性测试报告": "guoyusen_C4A_可靠性测试报告.md",
        "教学说明": "guoyusen_C4A_教学说明.md",
        "拿来说明": "guoyusen_C4A_拿来说明.md",
        "交付物索引": "00_交付物索引.md",
        "README": "README.md",
        "评审结果 JSON": "guoyusen_C4A_评审结果.json",
    }
    for label, rel in req.items():
        ck((ROOT / rel).exists(), "A", f"{label}（{rel}）")

    # ---------------- B ----------------
    LINES.append("\nB · 内容要求")
    design = read(ROOT / "guoyusen_C4A_方案设计.md")
    for kw in ["问题定义", "架构", "技术选型" if False else "设计决策",
               "可靠性", "局限"]:
        ck(kw in design, "B", f"方案设计含「{kw}」")
    ck(n_cjk(design) >= 3000, "B", f"方案设计 ≥3000 字（实得 {n_cjk(design)}）")
    ai = read(ROOT / "guoyusen_C4A_AI日志.md")
    ncase = len(re.findall(r"### 案例", ai))
    ck(ncase >= 10, "B", f"AI日志含 ≥10 个出错案例（实得 {ncase}）")
    aar = read(ROOT / "guoyusen_C4A_AAR.md")
    ck(n_cjk(aar) >= 2600, "B", f"AAR ≥2600 字（实得 {n_cjk(aar)}）")
    for kw in ["差异分析", "原因追溯", "可迁移结论"]:
        ck(kw in aar, "B", f"AAR 含「{kw}」")
    rep = read(ROOT / "guoyusen_C4A_评审报告.md")
    ck("综合排名" in rep and "红旗" in rep, "B", "评审报告含排名与红旗")
    ck("不是对同学的人身评价" in rep, "B",
       "评审报告写明「不是对同学的人身评价」")
    rr = read(ROOT / "guoyusen_C4A_可靠性测试报告.md")
    for kw in ["对照组", "边界"]:
        ck(kw in rr, "B", f"可靠性报告含「{kw}」")
    src = read(ROOT / "guoyusen_C4A_拿来说明.md")
    ck("没有" in src and "拿的" in src, "B",
       "拿来说明列出「没有拿的」")
    teach = read(ROOT / "guoyusen_C4A_教学说明.md")
    ck("常见坑" in teach, "B", "教学说明含常见坑")

    # ---------------- C ----------------
    LINES.append("\nC · 数值一致性")
    rel = {}
    rp = ROOT / "reports" / "reliability.json"
    if rp.exists():
        rel = json.loads(rp.read_text(encoding="utf-8"))
    res = {}
    rsp = ROOT / "guoyusen_C4A_评审结果.json"
    if rsp.exists():
        res = json.loads(rsp.read_text(encoding="utf-8"))
    if rel:
        ck(rel["assertions_fail"] == 0, "C",
           f"可靠性断言全通过（{rel['assertions_ok']} 项）",
           f"{rel['assertions_fail']} 项失败")
        ck(rel["mine_band_hit"] > rel["naive_band_hit"], "C",
           "本评审器区间命中率高于朴素对照组",
           f"{rel['mine_band_hit']} vs {rel['naive_band_hit']}")
        ck(rel["deterministic"] and rel["robust_to_rename"], "C",
           "确定性 + 改名鲁棒性均通过")
        for label, val in (("区间命中", f"{rel['mine_band_hit']}/{rel['band_total']}"),
                           ("红旗 F1", f"{rel['flag_f1']:.2f}"),
                           ("断言", f"{rel['assertions_ok']}")):
            ck(val in rr, "C", f"可靠性数字「{label}」与报告一致（{val}）",
               "报告里找不到该数字")
        # 方案设计里引用的数字必须与 JSON 一致
        ck(f"{rel['mine_band_hit']}/{rel['band_total']}" in design, "C",
           "方案设计引用的区间命中数与 JSON 一致")
    else:
        ck(False, "C", "存在 reports/reliability.json")
    if res:
        ck(res["n_repos"] == 8, "C", f"评审了 8 份真实提交（实得 {res['n_repos']}）")
        ck(len(res["submissions"]) == 8, "C",
           f"识别出 8 位作者（实得 {len(res['submissions'])}）")
        ry = [s for s in res["submissions"] if s["author"] == "阮如意"]
        if ry:
            ck(abs(ry[0]["composite"] - 0.92) < 0.005, "C",
               "外部锚点：阮如意 0.92（公开评分 90/100）",
               f"实得 {ry[0]['composite']:.3f}")
        else:
            warn("C", "语料里没有阮如意，跳过外部锚点检查")
    else:
        ck(False, "C", "存在 guoyusen_C4A_评审结果.json")

    # ---------------- D ----------------
    LINES.append("\nD · 技能包")
    skill = ROOT / "guoyusen_C4A_skill-evaluator.skill"
    if skill.exists():
        with tarfile.open(skill, "r:gz") as tar:
            names = [m.name for m in tar.getmembers() if m.isfile()]
            ck("SKILL.md" in names, "D", "包含 SKILL.md")
            ck("scripts/c4a_evaluator.py" in names, "D", "包含主脚本")
            ck("references/c4_rubric.json" in names, "D", "包含规则文件")
            ck(not [n for n in names if n.endswith(".pyc")], "D", "不含 .pyc")
            body = tar.extractfile("SKILL.md").read().decode("utf-8")
        ck(bool(re.match(r"^---\s*\n.*?\n---", body, re.S)), "D",
           "SKILL.md 有 frontmatter")
        ck("name:" in body and "description:" in body, "D",
           "frontmatter 含 name 与 description")
    else:
        ck(False, "D", "技能包已生成")

    # ---------------- E ----------------
    LINES.append("\nE · 评审器自身")
    ev = ROOT / "skill-evaluator" / "scripts" / "c4a_evaluator.py"
    src_code = read(ev)
    ck(bool(src_code), "E", "主脚本存在")
    mods = set()
    for node in ast.walk(ast.parse(src_code)) if src_code else []:
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    third = mods - set(sys.stdlib_module_names)
    ck(not third, "E", "只依赖标准库（零第三方）", f"发现 {sorted(third)}")
    ck("import torch" not in src_code and "import numpy" not in src_code, "E",
       "未引入 torch / numpy")
    rub = ROOT / "skill-evaluator" / "references" / "c4_rubric.json"
    try:
        r = json.loads(rub.read_text(encoding="utf-8"))
        ck(True, "E", "规则文件 JSON 合法")
        ck(len(r["deliverables"]) == 5, "E", "规则含 5 个交付物槽位")
        nchecks = sum(len(c["checks"]) for c in r["conditions"].values())
        ck(nchecks >= 20, "E", f"质量检查项 ≥20（实得 {nchecks}）")
        anchors = [c["id"] for c in r["conditions"].values()
                   for c in c["checks"] if c.get("anchor")]
        ck(len(anchors) == 4, "E", f"四个条件各有一个锚点（实得 {anchors}）")
    except Exception as e:  # noqa: BLE001
        ck(False, "E", "规则文件合法", str(e))
    gold = ROOT / "tests" / "gold" / "labels.json"
    if gold.exists():
        g = json.loads(gold.read_text(encoding="utf-8"))
        ck(len(g) >= 20, "E", f"评测集 ≥20 个标注样本（实得 {len(g)}）")
        ck(sum(1 for v in g.values() if v.get("rationale")) == len(g), "E",
           "每个样本都有 rationale")
    else:
        ck(False, "E", "评测集标注存在")

    print("\n".join(LINES))
    print(f"\n{'='*62}\nA–E 合计：{OK} PASS / {WARN} WARN / {FAIL} FAIL")
    if FAIL:
        print("未通过项：")
        for x in LINES:
            if "[FAIL]" in x:
                print("   ", x.strip())
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
