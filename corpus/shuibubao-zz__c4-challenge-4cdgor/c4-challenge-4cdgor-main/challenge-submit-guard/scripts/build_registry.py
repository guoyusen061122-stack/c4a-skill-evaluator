#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_registry.py — 从 EduSeed 平台导出的挑战资料包重建 challenge-submit-guard 的挑战注册表。

为什么需要这个脚本：
    挑战注册表（references/challenges.yaml）不应该手打 —— 手打会错、会过期。
    平台每次导出都会带 challenge.json + rubric.json，这个脚本直接读它们，
    保证 YAML 里的交付物清单 / 评分维度 / 红线定义 与平台完全一致。

用法：
    python build_registry.py --source "C:/path/to/我的EduSeed挑战" --out references/challenges.yaml

依赖：仅标准库（json / re / argparse）。
"""

import argparse
import json
import os
import re
import sys
from datetime import date

# ---------------------------------------------------------------- 读取平台数据


def load_challenge_packs(source_dir):
    """扫描 source_dir 下的 挑战_*_完整资料 目录，读取 challenge.json + rubric.json。"""
    packs = []
    if not os.path.isdir(source_dir):
        raise SystemExit("源目录不存在: %s" % source_dir)

    for entry in sorted(os.listdir(source_dir)):
        pack_dir = os.path.join(source_dir, entry)
        if not os.path.isdir(pack_dir) or "完整资料" not in entry:
            continue
        cj = os.path.join(pack_dir, "challenge.json")
        rj = os.path.join(pack_dir, "rubric.json")
        if not os.path.exists(cj):
            continue

        with open(cj, encoding="utf-8") as fh:
            cdata = json.load(fh)
        rdata = None
        if os.path.exists(rj):
            with open(rj, encoding="utf-8") as fh:
                rdata = json.load(fh)

        # challenge_id 形如 ch-20260717031424-4cdgor，取平台 ID；编号从目录名推断
        cid = None
        m = re.match(r"挑战_([A-Za-z0-9]+)\s", entry)
        if m:
            cid = m.group(1)

        packs.append(
            {
                "dir": entry,
                "code": cid or (cdata.get("challenge_id") or "")[-6:],
                "challenge": cdata,
                "rubric": rdata,
            }
        )
    return packs


def parse_deliverables(raw):
    """'*skill说明*,*.skill,*教学说明*' -> [{'label':..,'pattern':..}]"""
    if not raw:
        return []
    out = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        label = piece.replace("*", "").strip()
        out.append({"label": label, "pattern": piece, "required": True})
    return out


def parse_dimensions(pack):
    rubric = pack["rubric"]
    dims = []
    if rubric and rubric.get("dimensions"):
        for d in rubric["dimensions"]:
            dims.append(
                {
                    "id": d.get("id"),
                    "label": d.get("label"),
                    "max": d.get("maxPoints"),
                    "signals": list(d.get("signals") or []),
                    "negative": list(d.get("negativeSignals") or []),
                }
            )
        return dims

    # 没有 rubric.json 时，从 challenge.json 的 rubric_dimensions 字符串回落
    raw = (pack["challenge"] or {}).get("rubric_dimensions")
    if raw:
        try:
            obj = json.loads(raw)
            for d in obj.get("dimensions", []):
                dims.append(
                    {
                        "id": d.get("id"),
                        "label": d.get("label"),
                        "max": d.get("maxPoints"),
                        "signals": list(d.get("signals") or []),
                        "negative": list(d.get("negativeSignals") or []),
                    }
                )
        except Exception:
            pass
    return dims


def parse_red_flags(pack):
    rubric = pack["rubric"]
    flags = []
    if rubric and rubric.get("red_flags"):
        for f in rubric["red_flags"]:
            flags.append(
                {
                    "id": f.get("id"),
                    "desc": f.get("description"),
                    "affects": f.get("affectedDimension"),
                    "cap": f.get("maxScore"),
                }
            )
        return flags

    raw = (pack["challenge"] or {}).get("red_flags")
    if raw:
        try:
            obj = json.loads(raw)
            for f in obj.get("flags", []):
                flags.append(
                    {
                        "id": f.get("id"),
                        "desc": f.get("description"),
                        "affects": f.get("affectedDimension"),
                        "cap": f.get("maxScore"),
                    }
                )
        except Exception:
            pass
    return flags


# ---------------------------------------------------------------- YAML 写出


def y(v):
    """把一个标量渲染成安全的 YAML 标量（统一加双引号，避免中文/冒号/井号歧义）。"""
    if v is None:
        return '""'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % s


def dump_registry(challenges, meta):
    L = []
    L.append("# challenges.yaml — challenge-submit-guard 的挑战注册表")
    L.append("#")
    L.append("# 本文件由 scripts/build_registry.py 从 EduSeed 平台导出包自动生成，请勿手改。")
    L.append("# 生成日期: %s" % meta["generated"])
    L.append("# 数据来源: %s" % meta["source"])
    L.append("# 覆盖挑战: %d 个" % len(challenges))
    L.append("#")
    L.append("# 字段含义:")
    L.append("#   deliverables[].pattern  — 用于匹配文件的 glob（对文件名与相对路径同时匹配）")
    L.append("#   deliverables[].required — true 表示必交，缺失即触发 missing_artifacts 红线")
    L.append("#   dimensions[].max        — 该维度满分")
    L.append("#   red_flags[].cap         — 命中该红线时，affects 维度的最高分被压到 cap")
    L.append("")
    L.append("version: 1")
    L.append("generated: %s" % y(meta["generated"]))
    L.append("source: %s" % y(meta["source"]))
    L.append("")
    L.append("challenges:")
    for code, c in challenges:
        L.append("  %s:" % code)
        L.append("    title: %s" % y(c["title"]))
        L.append("    platform_id: %s" % y(c["platform_id"]))
        L.append("    deadline: %s" % y(c["deadline"]))
        if c["deliverables"]:
            L.append("    deliverables:")
            for d in c["deliverables"]:
                L.append("      - label: %s" % y(d["label"]))
                L.append("        pattern: %s" % y(d["pattern"]))
                L.append("        required: %s" % y(d["required"]))
        if c["dimensions"]:
            L.append("    dimensions:")
            for d in c["dimensions"]:
                L.append("      - id: %s" % y(d["id"]))
                L.append("        label: %s" % y(d["label"]))
                L.append("        max: %s" % y(d["max"]))
                if d["signals"]:
                    L.append("        signals:")
                    for s in d["signals"]:
                        L.append("          - %s" % y(s))
                if d["negative"]:
                    L.append("        negative:")
                    for s in d["negative"]:
                        L.append("          - %s" % y(s))
        if c["red_flags"]:
            L.append("    red_flags:")
            for f in c["red_flags"]:
                L.append("      - id: %s" % y(f["id"]))
                L.append("        desc: %s" % y(f["desc"]))
                L.append("        affects: %s" % y(f["affects"]))
                L.append("        cap: %s" % y(f["cap"]))
        L.append("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description="从平台导出包重建 challenges.yaml")
    ap.add_argument(
        "--source",
        default=r"C:\Users\卢怡然\Desktop\我的EduSeed挑战",
        help="包含 挑战_*_完整资料 目录的父目录",
    )
    ap.add_argument("--out", default=None, help="输出 YAML 路径（默认写到脚本同级 references/）")
    ap.add_argument("--json-out", default=None, help="同时导出一份 JSON（便于校验/调试）")
    args = ap.parse_args()

    packs = load_challenge_packs(args.source)
    if not packs:
        raise SystemExit("没有找到任何挑战资料包，请检查 --source")

    challenges = []
    for p in packs:
        c = p["challenge"]
        code = p["code"].upper()
        challenges.append(
            (
                code,
                {
                    "title": c.get("title") or "",
                    "platform_id": c.get("challenge_id") or "",
                    "deadline": c.get("deadline") or "",
                    "deliverables": parse_deliverables(c.get("required_deliverables") or c.get("deliverables")),
                    "dimensions": parse_dimensions(p),
                    "red_flags": parse_red_flags(p),
                },
            )
        )

    meta = {"generated": date.today().isoformat(), "source": "EduSeed 平台导出包 challenge.json + rubric.json"}
    text = dump_registry(challenges, meta)

    out = args.out
    if out is None:
        here = os.path.dirname(os.path.abspath(__file__))
        out = os.path.join(os.path.dirname(here), "references", "challenges.yaml")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({k: v for k, v in challenges}, fh, ensure_ascii=False, indent=2)

    sys.stdout.reconfigure(encoding="utf-8")
    print("已写入 %s" % out)
    print("挑战数: %d" % len(challenges))
    for code, c in challenges:
        print(
            "  %-5s %-45s 交付物 %d 项 / 维度 %d 个 / 红线 %d 条"
            % (code, c["title"][:45], len(c["deliverables"]), len(c["dimensions"]), len(c["red_flags"]))
        )


if __name__ == "__main__":
    main()
