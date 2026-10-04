#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""挑战交付物提交前预检器（challenge-preflight）。

纯标准库、离线、确定性：同一个目录永远给出同样的报告。

用法：
    python preflight.py --dir <交付目录> --challenge C4 [--name 阮如意] [--json]

退出码：0 = PASS，1 = FAIL（缺件或空文件），2 = 参数 / 环境错误。
"""
import argparse
import fnmatch
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_RULES = HERE.parent / "references" / "rules.json"


def die(msg, code=2):
    print("[E] " + msg, file=sys.stderr)
    sys.exit(code)


def load_rules(p):
    if not p.exists():
        die("找不到规则文件：%s" % p)
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def rel(root, p):
    return str(Path(p).relative_to(root)).replace("\\", "/")


def collect(root, junk):
    """遍历目录：返回 (文件列表, 杂物列表)。junk 目录整棵跳过。"""
    files, trash = [], []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        kept = []
        for d in sorted(dirnames):
            full = Path(dirpath, d)
            if d in junk:
                trash.append(rel(root, full) + "/")
            else:
                kept.append(d)
        dirnames[:] = kept
        for fn in sorted(filenames):
            full = Path(dirpath, fn)
            if fn in junk:
                trash.append(rel(root, full))
            else:
                files.append(full)
    return files, trash


def matcher(include, exclude):
    inc = [re.compile(p) for p in include]
    exc = [re.compile(p) for p in exclude]

    def ok(r):
        if not any(p.search(r) for p in inc):
            return False
        return not any(p.search(r) for p in exc)

    return ok


def check_required(root, rels, spec):
    out = []
    for rule in spec.get("required", []):
        ok = matcher(rule.get("include", []), rule.get("exclude", []))
        hit = sorted(r for r in rels if ok(r))
        need = int(rule.get("min", 1))
        out.append({
            "label": rule.get("label", "未命名规则"),
            "matched": hit,
            "min": need,
            "pass": len(hit) >= need,
        })
    return out


def detect_name(rels, tag):
    c = Counter()
    for r in rels:
        m = re.match(r"^([^_]+)" + re.escape(tag), r.split("/")[-1])
        if m:
            c[m.group(1)] += 1
    return c.most_common(1)[0][0] if c else ""


def scan_placeholders(root, files, rules):
    exts = set(e.lower() for e in rules.get("textExt", []))
    limit = int(rules.get("placeholderMaxBytes", 3000000))
    words = rules.get("placeholders", [])
    hits = []
    for f in files:
        if f.suffix.lower() not in exts:
            continue
        try:
            if f.stat().st_size > limit:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            for w in words:
                if w.lower() in low:
                    hits.append({"file": rel(root, f), "line": i, "word": w,
                                 "text": line.strip()[:100]})
                    break
            if len(hits) >= 60:
                return hits
    return hits


def fmt_size(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return ("%d B" % int(n)) if u == "B" else ("%.1f %s" % (n, u))
        n /= 1024.0


def _size(f):
    try:
        return f.stat().st_size
    except OSError:
        return -1


def action_items(r):
    items = []
    for c in r["required"]:
        if not c["pass"]:
            items.append("[FAIL] 补齐「%s」：至少需要 %d 个匹配文件，当前 %d 个"
                         % (c["label"], c["min"], len(c["matched"])))
    for e in r["empty"]:
        items.append("[FAIL] 空文件（0 字节），要么写内容要么删掉：%s" % e)
    for m in r["nameMismatch"]:
        items.append("[WARN] 文件名与姓名前缀「%s」不一致：%s" % (r["name"], m))
    if r["placeholders"]:
        items.append("[WARN] 占位符命中 %d 处，逐条人眼确认（可能是正当引用）：见第 4 节"
                     % len(r["placeholders"]))
    if r["junk"]:
        items.append("[WARN] 目录里有不该提交的杂物，上传前排除：%s"
                     % "、".join(r["junk"][:8]))
    if not r["verified"]:
        items.append("[INFO] 挑战 %s 的必交规则未收录，本次未做齐全性判定，请以平台 "
                     "prepare-submission 为准" % r["challenge"])
    if not items:
        items.append("无。机械检查全部通过。")
    return items


def build_report(root_dir, challenge, name, rules_path, extra_ignore=None):
    root = Path(root_dir).resolve()
    if not root.exists() or not root.is_dir():
        die("交付目录不存在或不是目录：%s" % root)
    rules = load_rules(Path(rules_path))
    ch = str(challenge).upper()
    if ch not in rules.get("challenges", {}):
        die("规则表中没有挑战 %s（可选：%s）"
            % (ch, ", ".join(sorted(rules.get("challenges", {})))))
    spec = rules["challenges"][ch]
    junk = set(rules.get("junk", []))
    pats = list(spec.get("ignorePaths", [])) + list(extra_ignore or [])
    # ignorePaths / --ignore 是 glob（如 skill_src/**），不是正则：
    # 直接 re.compile 遇到 ** 会抛 re.error: multiple repeat。
    # 改用 fnmatch 匹配，语义更直觉，也不受正则元字符干扰。
    ignore = list(pats)

    files, trash = collect(root, junk)
    rels = sorted(rel(root, f) for f in files)
    tag = "_%s_" % ch

    inferred = ""
    name = (name or "").strip()
    if spec.get("namePrefixed") and not name:
        inferred = detect_name(rels, tag)
        name = inferred

    checks = check_required(root, rels, spec)
    empty = sorted(rel(root, f) for f in files if _size(f) == 0)
    name_mismatch = []
    if spec.get("namePrefixed") and name:
        name_mismatch = [r for r in rels
                         if tag in r.split("/")[-1] and not r.split("/")[-1].startswith(name)]

    scannable = [f for f in files
                 if not any(fnmatch.fnmatch(rel(root, f), g) for g in ignore)]
    ph = scan_placeholders(root, scannable, rules)

    sizes = sorted(((_size(f), rel(root, f)) for f in files), reverse=True)
    fails = [c for c in checks if not c["pass"]]

    return {
        "dir": str(root),
        "challenge": ch,
        "name": name,
        "nameInferred": inferred,
        "nameFromArg": bool((name or "").strip()) and not inferred,
        "verified": bool(spec.get("verified")),
        "source": spec.get("source", ""),
        "required": checks,
        "empty": empty,
        "nameMismatch": name_mismatch,
        "placeholders": ph,
        "junk": trash,
        "ignored": pats,
        "fileCount": len(files),
        "totalBytes": sum(s for s, _ in sizes if s > 0),
        "topSizes": [{"file": r, "bytes": s} for s, r in sizes[:20]],
        "scannedChars": None,
        "verdict": "FAIL" if (fails or empty) else "PASS",
        "failCount": len(fails) + len(empty),
    }


def render_md(r):
    L = []
    L.append("# 交付物预检报告 · %s" % r["challenge"])
    L.append("")
    L.append("- 目录：`%s`" % r["dir"])
    L.append("- 规则来源：%s（%s）" % (r["source"] or "—",
                                     "已实测" if r["verified"] else "未收录"))
    if r["name"]:
        how = "自动推断" if r["nameInferred"] else "参数指定"
        L.append("- 姓名前缀：`%s`（%s）" % (r["name"], how))
    else:
        L.append("- 姓名前缀：未指定，且未能推断")
    L.append("- 扫描：%d 个文件，总计 %s" % (r["fileCount"], fmt_size(r["totalBytes"])))
    if r["ignored"]:
        L.append("- 占位符扫描已排除：`%s`" % "`, `".join(r["ignored"]))
    L.append("")
    L.append("## 结论：**%s**" % r["verdict"])
    L.append("")
    L.append("> 依据：缺 %d 项必交、%d 个空文件（这两项才会判 FAIL；占位符与杂物只报警告）"
             % (len([c for c in r["required"] if not c["pass"]]), len(r["empty"])))
    L.append("")

    L.append("## 1. 必交项齐全性")
    L.append("")
    if not r["required"]:
        L.append("_该挑战的必交规则未收录（`verified: false`），本次不做齐全性判定。_")
    else:
        L.append("| 结果 | 必交项 | 命中文件 |")
        L.append("| --- | --- | --- |")
        for c in r["required"]:
            mark = "✅" if c["pass"] else "❌"
            hit = "、".join("`%s`" % h for h in c["matched"]) if c["matched"] else "_未找到_"
            L.append("| %s | %s | %s |" % (mark, c["label"], hit))
    L.append("")

    L.append("## 2. 命名 / 姓名前缀")
    L.append("")
    if r["nameMismatch"]:
        for m in r["nameMismatch"]:
            L.append("- ⚠️ `%s` —— 不以 `%s` 开头" % (m, r["name"]))
    else:
        L.append("未发现不一致。")
    L.append("")

    L.append("## 3. 空文件")
    L.append("")
    L.append("无。" if not r["empty"] else "\n".join("- ❌ `%s`" % e for e in r["empty"]))
    L.append("")

    L.append("## 4. 占位符残留（WARN）")
    L.append("")
    if r["placeholders"]:
        L.append("| 文件 | 行 | 命中词 | 片段 |")
        L.append("| --- | --- | --- | --- |")
        for h in r["placeholders"][:25]:
            L.append("| `%s` | %d | `%s` | %s |"
                     % (h["file"], h["line"], h["word"], h["text"].replace("|", "\\|")))
    else:
        L.append("未命中。")
    L.append("")

    L.append("## 5. 不应提交的杂物（WARN）")
    L.append("")
    L.append("无。" if not r["junk"] else "\n".join("- ⚠️ `%s`" % j for j in r["junk"]))
    L.append("")

    L.append("## 6. 体量（前 20 大）")
    L.append("")
    L.append("| 文件 | 大小 |")
    L.append("| --- | --- |")
    for it in r["topSizes"]:
        L.append("| `%s` | %s |" % (it["file"], fmt_size(it["bytes"])))
    L.append("")

    L.append("## 7. 行动项")
    L.append("")
    for i, it in enumerate(action_items(r), 1):
        L.append("%d. %s" % (i, it))
    L.append("")
    L.append("---")
    L.append("由 challenge-preflight v1.0 生成（离线、确定性）。本工具只查机械问题，不评价内容质量。")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="preflight.py",
        description="挑战交付物提交前预检器：命名 / 缺件 / 空文件 / 占位符 / 杂物 / 体量")
    ap.add_argument("--dir", required=True, help="交付目录")
    ap.add_argument("--challenge", required=True, help="挑战编号，如 C4")
    ap.add_argument("--name", default="", help="姓名前缀（可选，未给则自动推断）")
    ap.add_argument("--rules", default=str(DEFAULT_RULES), help="规则表路径")
    ap.add_argument("--ignore", action="append", default=[],
                    help="占位符扫描跳过的路径正则，可重复")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    args = ap.parse_args(argv)

    r = build_report(args.dir, args.challenge, args.name, args.rules, args.ignore)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(render_md(r))
    return 0 if r["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

