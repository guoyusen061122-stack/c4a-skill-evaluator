#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc-consistency-auditor — Markdown 文档一致性审计器（仅标准库，零第三方依赖）。

审计规则：
  R0 文件规模     —— 超过上限的文件跳过并告警
  R1 术语一致性   —— 对比术语表(glossary.yaml)，报告「禁用写法」出现位置并给出标准写法
  R2 内部链接/锚点 —— 检查 [text](target) / ![alt](target) 的本地目标是否存在、锚点是否命中
  R3 标题层级跳跃  —— 报告 heading 越级（如 ## 直接跳 ####）
  R4 重复标题     —— 报告同文件内重复的标题文本
  R5 交付物清单   —— 对比 manifest.yaml，报告缺失的必需交付物（glob）

退出码：0=无问题；1=发现问题；2=用法/参数错误。

用法示例：
  python3 audit.py --path ./docs
  python3 audit.py --path ./docs --glossary glossary.yaml --manifest manifest.yaml --out report.md
  python3 audit.py --path ./docs --json
"""

import argparse
import fnmatch
import json
import os
import re
import sys

MD_EXTS = {".md", ".markdown"}
DEFAULT_MAX_BYTES = 5 * 1024 * 1024

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:[ \t]+[\"'][^\"']*[\"'])?\)")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")


# ---------------------------------------------------------------------------
# 极简 YAML 子集解析（本技能声明的约束格式，避免引入 PyYAML 依赖）
# ---------------------------------------------------------------------------

def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'":
        q = s[0]
        end = s.rfind(q, 1)
        if end != -1:
            return s[1:end]
    return s


def _parse_inline_list(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_unquote(x) for x in inner.split(",")]
    return []


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_glossary(text):
    """解析 glossary.yaml（支持本技能声明的极简子集）。

    支持格式：
        rules:
          - standard: "GitHub"
            forbidden: ["github", "Github", "GH"]
    """
    rules = []
    cur = None
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("- "):
            body = s[2:].strip()
            if body.startswith("standard:"):
                cur = {"standard": _unquote(body[len("standard:"):]),
                       "forbidden": []}
                rules.append(cur)
            elif body.startswith("forbidden:") and cur is not None:
                cur["forbidden"] += _parse_inline_list(body[len("forbidden:"):])
        elif s.startswith("forbidden:") and cur is not None:
            cur["forbidden"] += _parse_inline_list(s[len("forbidden:"):])
        # 顶层 'rules:' / 'version:' 等键忽略
    return rules


def parse_manifest(text):
    """解析 manifest.yaml：提取 deliverables 下的 glob 列表。"""
    items = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("- "):
            items.append(_unquote(s[2:].strip()))
    return items


# ---------------------------------------------------------------------------
# 文件扫描与标题 slug
# ---------------------------------------------------------------------------

def iter_md_files(path):
    """yield (rel_path, abs_path)，递归扫描 .md / .markdown。"""
    if os.path.isfile(path):
        if os.path.splitext(path)[1].lower() in MD_EXTS:
            yield os.path.basename(path), path
        return
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for fn in sorted(filenames):
            if os.path.splitext(fn)[1].lower() in MD_EXTS:
                abs_p = os.path.join(dirpath, fn)
                yield os.path.relpath(abs_p, path), abs_p


def slugify(text):
    """GitHub 风格标题锚点：小写、空格/下划线→连字符、去除其余标点（保留 CJK）。"""
    t = text.strip().lower()
    t = re.sub(r"[^\w\u4e00-\u9fff -]", "", t)
    t = re.sub(r"[ _]+", "-", t)
    return t


def issue(level, rule, fname, line, message, suggestion=None):
    return {"level": level, "rule": rule, "file": fname, "line": line,
            "message": message, "suggestion": suggestion}


# ---------------------------------------------------------------------------
# 主审计逻辑
# ---------------------------------------------------------------------------

def run_audit(path, glossary, manifest, max_bytes):
    issues = []
    entries = []
    all_rels = set()

    # 第一遍：收集标题，执行 R0/R1/R3/R4（行级 + 标题流式）
    for rel, abs_p in iter_md_files(path):
        all_rels.add(rel)
        size = os.path.getsize(abs_p)
        if size > max_bytes:
            issues.append(issue("warning", "R0", rel, 0,
                                "文件 %d 字节超过上限 %d 字节，已跳过" % (size, max_bytes),
                                "用 --max-bytes 调高上限，或拆分为小文件"))
            continue

        lines = read_text(abs_p).splitlines()
        fheadings = {}
        seen = {}
        prev_level = 0
        in_fence = False

        for i, line in enumerate(lines, 1):
            fm = FENCE_RE.match(line)
            if fm:
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            # R1 术语一致性
            for r in glossary:
                for bad in r["forbidden"]:
                    if bad in line:
                        issues.append(issue(
                            "error", "R1", rel, i,
                            "出现禁用写法「%s」" % bad,
                            "统一为「%s」" % r["standard"]))

            # 标题：R3 跳跃 / R4 重复
            m = HEADING_RE.match(line)
            if m:
                lvl = len(m.group(1))
                title = m.group(2).strip()
                slug = slugify(title)
                if prev_level and lvl - prev_level > 1:
                    issues.append(issue(
                        "warning", "R3", rel, i,
                        "标题从 H%d 直接跳到 H%d（「%s」）" % (prev_level, lvl, title),
                        "中间补一个 H%d 层级" % (prev_level + 1)))
                prev_level = lvl
                if slug in seen:
                    issues.append(issue(
                        "warning", "R4", rel, i,
                        "标题「%s」重复（首次出现在第 %d 行）" % (title, seen[slug]),
                        "重命名或合并重复标题"))
                else:
                    seen[slug] = i
                fheadings[slug] = i

        entries.append({"rel": rel, "abs": abs_p, "lines": lines,
                        "headings": fheadings})

    # 第二遍：R2 链接/锚点（需要所有文件的标题已就绪）
    for e in entries:
        rel, abs_p, lines = e["rel"], e["abs"], e["lines"]
        in_fence = False
        for i, line in enumerate(lines, 1):
            fm = FENCE_RE.match(line)
            if fm:
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            for m in LINK_RE.finditer(line):
                is_img = m.group(1) == "!"
                target = m.group(3)
                if target.startswith(("http://", "https://", "mailto:", "tel:")):
                    continue

                file_part, anchor = (target.split("#", 1) + [None])[:2] if "#" in target else (target, None)

                if anchor:
                    if file_part == "":
                        if anchor not in e["headings"]:
                            issues.append(issue(
                                "error", "R2", rel, i,
                                "锚点「#%s」未命中任何标题" % anchor,
                                "补同名标题或修正链接"))
                    else:
                        t_abs = os.path.normpath(os.path.join(os.path.dirname(abs_p), file_part))
                        found = next((x for x in entries if x["abs"] == t_abs), None)
                        if found is None:
                            issues.append(issue(
                                "error", "R2", rel, i,
                                "目标文件「%s」不存在" % file_part,
                                "补文件或修正路径"))
                        elif anchor not in found["headings"]:
                            issues.append(issue(
                                "error", "R2", rel, i,
                                "目标「%s」中锚点「#%s」未命中" % (file_part, anchor),
                                "补标题或修正链接"))
                else:
                    if file_part:
                        t_abs = os.path.normpath(os.path.join(os.path.dirname(abs_p), file_part))
                        if not os.path.exists(t_abs):
                            issues.append(issue(
                                "error", "R2", rel, i,
                                "目标「%s」不存在" % file_part,
                                "补文件或修正路径"))

    # R5 交付物清单
    for pat in manifest:
        hit = any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(os.path.basename(rel), pat)
                  for rel in all_rels)
        if not hit:
            issues.append(issue(
                "warning", "R5", ".", 0,
                "交付物「%s」缺失" % pat,
                "补充该交付物文件"))

    return issues


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _loc(it):
    return "%s:%s" % (it["file"], it["line"]) if it["line"] else it["file"]


def print_report(issues, path):
    if not issues:
        print("✅ 审计通过（%s）：未发现一致性问题。" % path)
        return
    errs = [x for x in issues if x["level"] == "error"]
    warns = [x for x in issues if x["level"] == "warning"]
    print("⚠️  审计发现 %d 个问题（错误 %d，警告 %d）：" % (len(issues), len(errs), len(warns)))
    for idx, it in enumerate(issues, 1):
        tag = "错误" if it["level"] == "error" else "警告"
        print("  [%02d] [%s] %s @ %s" % (idx, tag, it["rule"], _loc(it)))
        print("        %s" % it["message"])
        if it["suggestion"]:
            print("        建议：%s" % it["suggestion"])


def render_markdown(issues, path):
    lines = ["# 文档一致性审计报告", "", "- 审计路径：`%s`" % path]
    if not issues:
        lines += ["- 结果：✅ 无问题", ""]
        return "\n".join(lines)
    errs = [x for x in issues if x["level"] == "error"]
    warns = [x for x in issues if x["level"] == "warning"]
    lines += ["- 结果：⚠️ 发现问题 %d（错误 %d，警告 %d）" % (len(issues), len(errs), len(warns)), ""]
    by_rule = {}
    for it in issues:
        by_rule.setdefault(it["rule"], []).append(it)
    for rule in sorted(by_rule):
        items = by_rule[rule]
        lines += ["## %s（%d 条）" % (rule, len(items)), "",
                  "| 文件 | 行 | 问题 | 建议 |", "|---|---|---|---|"]
        for it in items:
            lines.append("| %s | %s | %s | %s |" % (
                it["file"], it["line"] or "-",
                it["message"].replace("|", "\\|"),
                (it["suggestion"] or "-").replace("|", "\\|")))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main(argv):
    p = argparse.ArgumentParser(description="Markdown 文档一致性审计器（stdlib only）")
    p.add_argument("--path", required=True, help="要审计的 .md 文件或目录")
    p.add_argument("--glossary", default=None, help="术语表 YAML（可选）")
    p.add_argument("--manifest", default=None, help="交付物清单 YAML（可选）")
    p.add_argument("--out", default=None, help="将 Markdown 报告写入此文件（可选）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出问题列表")
    p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="跳过超过该字节数的文件")
    args = p.parse_args(argv)

    if not os.path.exists(args.path):
        print("错误：路径不存在：%s" % args.path, file=sys.stderr)
        return 2

    glossary = []
    if args.glossary:
        if not os.path.exists(args.glossary):
            print("错误：术语表不存在：%s" % args.glossary, file=sys.stderr)
            return 2
        glossary = parse_glossary(read_text(args.glossary))

    manifest = []
    if args.manifest:
        if not os.path.exists(args.manifest):
            print("错误：清单不存在：%s" % args.manifest, file=sys.stderr)
            return 2
        manifest = parse_manifest(read_text(args.manifest))

    issues = run_audit(args.path, glossary, manifest, args.max_bytes)

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print_report(issues, args.path)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(render_markdown(issues, args.path))

    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
