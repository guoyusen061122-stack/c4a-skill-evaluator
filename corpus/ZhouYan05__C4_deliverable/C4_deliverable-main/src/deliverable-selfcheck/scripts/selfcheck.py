#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deliverable-selfcheck — EduSeed/Elite20 挑战交付物自检器（仅标准库）。

用法:
  python selfcheck.py --workdir ./dir --required "*AI日志*,*AAR*,*.py" \
      [--prefix ZhouYan05] [--title "..."] [--summary "..."] [--json]

退出码: 0=READY, 1=BLOCKED
"""
import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------- 敏感形态
KEY_PATTERNS = [
    (r"sk-[A-Za-z0-9_\-]{12,}", "OpenAI 风格密钥(sk-)"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub PAT(ghp_)"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub 细粒度 PAT"),
    (r"glpat-[A-Za-z0-9_\-]{16,}", "GitLab PAT"),
    (r"\bapi[_-]?key\s*[:=]\s*\S{6,}", "api key 赋值形态"),
    (r"\btoken\s*[:=]\s*\S{6,}", "token 赋值形态"),
]
# 「英文冒号 + 空格」的 key-value 观感：实测最容易被平台误判为密钥形态
KEYVALUE_SHAPE = re.compile(
    r"[A-Za-z0-9\u4e00-\u9fff]"      # 冒号前有实际字符
    r"\s*:\s+"                        # 英文冒号 + 至少一个空格
    r"[A-Za-z0-9\u4e00-\u9fff]",     # 冒号后有内容
)


def glob_regex(pat):
    """标准通配符 -> 正则（直觉语义）。"""
    out, i = [], 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if i + 1 < len(pat) and pat[i + 1] == "*":
                out.append(".*")
                i += 2
                continue
            out.append("[^/\\\\]*")
        elif c == "?":
            out.append("[^/\\\\]")
        elif c == "[":
            j = pat.find("]", i + 1)
            if j == -1:
                out.append(re.escape(c))
            else:
                body = pat[i + 1:j]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body + "]")
                i = j + 1
                continue
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


def literal_core(pat):
    """平台实测语义：去掉所有通配符后，剩下的字面串必须作为
    连续子串出现在文件名里。"""
    core = list(pat)
    out, i = [], 0
    while i < len(core):
        c = core[i]
        if c in "*?":
            i += 1
            continue
        if c == "[":
            j = "".join(core).find("]", i + 1)
            if j != -1:
                i = j + 1
                continue
        out.append(c)
        i += 1
    return "".join(out).strip()


def list_files(workdir):
    files = []
    for root, dirs, names in os.walk(workdir):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for n in names:
            p = os.path.join(root, n)
            files.append({
                "name": n,
                "rel": os.path.relpath(p, workdir).replace("\\", "/"),
                "size": os.path.getsize(p),
                "top": os.path.dirname(os.path.relpath(p, workdir)) == "",
            })
    return sorted(files, key=lambda f: f["rel"])


def check(workdir, required, prefix, title, summary):
    files = list_files(workdir)
    found, missing, warnings = [], [], []

    for item in required:
        core = literal_core(item)
        rx = glob_regex(item)
        lit_hits = [f for f in files if core == "" or core.lower() in f["name"].lower()]
        glob_hits = [f for f in files if rx.match(f["name"])]
        rec = {
            "required": item,
            "literalCore": core,
            "matched": [f["rel"] for f in lit_hits],
            "globOnly": [f["rel"] for f in glob_hits if f not in lit_hits],
        }
        if lit_hits:
            found.append(rec)
        else:
            missing.append(rec)
            if glob_hits:
                warnings.append({
                    "code": "LITERAL_MISMATCH",
                    "item": item,
                    "detail": "这些文件按直觉通配符能命中、但文件名里不含连续字面串 "
                              "「%s」，平台会判为缺失：%s" % (
                                  core, ", ".join(f["rel"] for f in glob_hits)),
                    "action": "把文件名改成同时字面包含所需关键词的名字，"
                              "例如 AI_工作日志与AAR.md -> AI日志与AAR.md",
                })

    for f in files:
        if f["size"] == 0:
            warnings.append({"code": "EMPTY_FILE", "item": f["rel"],
                             "detail": "文件为 0 字节，平台可能视为无效交付",
                             "action": "补内容，或删掉占位文件"})

    if prefix:
        for f in files:
            if f["top"] and prefix.lower() not in f["name"].lower() \
                    and not f["name"].lower().startswith("readme"):
                warnings.append({"code": "MISSING_PREFIX", "item": f["rel"],
                                 "detail": "顶层交付物文件名未包含命名前缀「%s」" % prefix,
                                 "action": "重命名为 %s_... 开头" % prefix})

    for field, text in (("projectTitle", title), ("projectSummary", summary)):
        if not text:
            continue
        for pat, label in KEY_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                warnings.append({"code": "SENSITIVE_KEY", "item": field,
                                 "detail": "命中密钥形态：" + label,
                                 "action": "确认非真实密钥；是则立即吊销并删除"})
        for m in KEYVALUE_SHAPE.finditer(text):
            warnings.append({
                "code": "SENSITIVE_SHAPE", "item": field,
                "detail": "出现「英文冒号+空格」的 key-value 观感片段 %r，"
                          "平台敏感信息过滤可能整单拒绝" % m.group(0),
                "action": "把英文冒号换成破折号或全角冒号，其余内容不动",
            })

    blockers = [w for w in warnings if w["code"] in ("SENSITIVE_SHAPE", "SENSITIVE_KEY")]
    verdict = "BLOCKED" if (missing or blockers) else "READY"
    return {"workdir": os.path.abspath(workdir), "required": required,
            "fileCount": len(files), "found": found, "missing": missing,
            "warnings": warnings, "verdict": verdict}


def render(rep):
    L = ["# 交付物自检报告", "",
         "- 目录: `%s`" % rep["workdir"],
         "- 扫描文件数: %d" % rep["fileCount"],
         "- 结论: **%s**" % rep["verdict"], ""]
    L.append("## 逐项核对")
    for f in rep["found"]:
        L.append("- [x] `%s` -> %s" % (f["required"], ", ".join("`%s`" % m for m in f["matched"])))
    for m in rep["missing"]:
        L.append("- [ ] `%s` -> **缺失**（需字面含「%s」）" % (m["required"], m["literalCore"]))
        if m["globOnly"]:
            L.append("      - 近似命中（平台不认）: %s" % ", ".join("`%s`" % x for x in m["globOnly"]))
    if rep["warnings"]:
        L += ["", "## 风险与待办"]
        for w in rep["warnings"]:
            L.append("- **%s** · %s" % (w["code"], w["item"]))
            L.append("      - %s" % w["detail"])
            if w.get("action"):
                L.append("      - 下一步: %s" % w["action"])
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="EduSeed 挑战交付物自检器")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--required", required=True, help="逗号分隔的通配符清单")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--summary", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.isdir(a.workdir):
        print("目录不存在: " + a.workdir, file=sys.stderr)
        return 2
    required = [x.strip() for x in a.required.split(",") if x.strip()]
    rep = check(a.workdir, required, a.prefix, a.title, a.summary)
    print(json.dumps(rep, ensure_ascii=False, indent=2) if a.json else render(rep))
    return 0 if rep["verdict"] == "READY" else 1


if __name__ == "__main__":
    sys.exit(main())
