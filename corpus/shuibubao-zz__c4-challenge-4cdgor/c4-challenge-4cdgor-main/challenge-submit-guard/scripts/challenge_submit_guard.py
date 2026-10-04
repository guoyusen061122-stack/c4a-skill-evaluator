#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
challenge_submit_guard.py — EduSeed / Elite20 挑战提交自检器

输入：一个挑战交付文件夹路径 + 挑战编号（C1…C10H，可自动识别）
输出：一份 Markdown（或 JSON）体检报告 —— 交付物核对 / 命名规范 / 红线扫描 /
      五维粗估 / 提分杠杆排序 / 可直接执行的 TODO 清单

设计原则：
  1. 零第三方依赖 —— 只用标准库。没有 PyYAML 也能跑（内置迷你 YAML 解析器）。
  2. 注册表驱动 —— 所有判定规则来自 references/challenges.yaml，改数据不改代码。
  3. 结果可复核 —— 每条结论都给出证据文件名，不给你一个无法追溯的分数。

用法：
  python challenge_submit_guard.py <交付文件夹> [-c C4]
  python challenge_submit_guard.py <交付文件夹> --json
  python challenge_submit_guard.py <交付文件夹> --out report.md
  python challenge_submit_guard.py --list
  python challenge_submit_guard.py --self-test

退出码：默认 0；--strict 模式下「缺必交物 / 命中红线」返回 1。
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - 老版本 Python 没有 reconfigure
    pass

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REGISTRY = os.path.join(SKILL_DIR, "references", "challenges.yaml")

SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", ".mypy_cache", ".pytest_cache", "dist", "build",
}
TEXT_EXT = {
    ".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".tex", ".bib",
    ".sh", ".bat", ".ps1", ".csv", ".log", ".html", ".htm", ".js", ".ts",
    ".rst", ".ini", ".cfg",
}
MAX_FILE_BYTES = 200_000      # 单个文本文件最多读 200KB 用于关键词取证
MAX_CORPUS_BYTES = 2_000_000  # 语料总量上限，防止超大仓库拖慢扫描

# 脚本无法自动判定的事项 —— 每条都对应一次真实扣分教训，输出在报告第 7 节
MANUAL_CHECKS = [
    "**行为是否真的发生**：稿子写好了 ≠ 发出去了（C3 实测：5 篇稿齐备、文件零缺失，"
    "仍因「未发出」被扣约 15 分）",
    "**内容是否真实可复核**：有没有编造的引用、数据、回应人？宁可留空回填区，也不要编",
    "**陌生人能否照做**：找一个没看过你项目的人按文档走一遍，卡住的地方就是丢分点",
    "**demo 是否现在还能跑**：脚本/命令换台机器重跑一次，别依赖你本机的环境变量",
]

MIN_AI_LOG_CHARS = 800        # AI日志 低于此字数视为「没有实质记录」
MIN_ITERATION_CHARS = 400     # AI日志 低于此字数几乎不可能有迭代痕迹

# AI日志 里能证明「不是一句话指令直接提交」的关键词
ITERATION_KEYWORDS = [
    "迭代", "轮", "v2", "v3", "prompt", "提示词", "修改", "优化", "改进",
    "反馈", "失败", "报错", "重试", "回滚", "调整", "重做", "评审", "初评",
    "revert", "retry", "error", "fix",
]

# 评分信号关键词的同义扩展：rubric 里的词很短，直接子串匹配容易漏
SIGNAL_SYNONYMS = {
    "描述准确": ["描述", "description", "frontmatter", "触发"],
    "结构完整": ["结构", "目录结构", "SKILL.md", "workflow", "工作流", "步骤"],
    "可执行": ["可执行", "可运行", "运行", "命令", "脚本", "python", "executable", "run "],
    "有教学文档": ["教学说明", "教学", "教程", "上手", "tutorial", "how to"],
    "有示例": ["示例", "例子", "example", "样例", "demo"],
    "有演示": ["演示", "demo", "截图", "录屏", "mp4", "screenshot"],
    "README齐全": ["readme", "说明", "readme.md"],
    "可运行": ["运行", "可运行", "执行", "run", "install", "安装"],
    "安装/使用说明": ["安装", "使用说明", "用法", "usage", "install", "快速开始"],
    "多轮迭代": ["迭代", "轮", "v2", "v3", "修改", "优化", "改进"],
    "prompt优化": ["prompt", "提示词", "指令", "改写", "优化"],
    "工作流设计": ["工作流", "workflow", "pipeline", "流程", "管线", "编排"],
    "AI日志佐证": ["ai日志", "ai-log", "ai_log", "日志"],
    "具体问题分析": ["问题", "根因", "分析", "为什么", "原因"],
    "有改进方案": ["改进", "方案", "下一步", "计划", "todo", "优化"],
    "记录迭代过程": ["迭代", "版本", "v1", "v2", "历程", "过程"],
    "含失败经验": ["失败", "踩坑", "坑", "报错", "错误", "教训", "不行", "返工"],
    "覆盖度达标": ["覆盖", "完整", "全量", "清单", "索引"],
    "术语统一": ["术语", "glossary", "统一", "对照表"],
    "无硬伤": ["校对", "校验", "核对", "复核", "检查"],
    "有脚本或清晰步骤": ["脚本", "script", "步骤", "makefile", "命令"],
    "换源可复用": ["复用", "可复跑", "参数化", "换源", "通用"],
    "质量抽检": ["抽检", "抽查", "校验", "审计", "audit", "检查"],
    "可独立使用": ["独立", "单文件", "零依赖", "无需", "自包含"],
    "有证据": ["证据", "evidence", "截图", "记录", "输出"],
    "真实数据": ["真实", "实测", "实际", "real"],
}


# --------------------------------------------------------------------------
# 迷你 YAML 解析器（只支持本技能注册表用到的子集，避免强依赖 PyYAML）
# --------------------------------------------------------------------------


def _strip_comment(line: str) -> str:
    """去掉行尾注释，保留引号内的 #。"""
    out = []
    quote = None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(tok: str):
    tok = tok.strip()
    if not tok:
        return ""
    if tok[0] in ("'", '"') and tok[-1] == tok[0] and len(tok) >= 2:
        body = tok[1:-1]
        if tok[0] == '"':
            body = body.replace('\\"', '"').replace("\\\\", "\\")
        return body
    low = tok.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


def _parse_map(lines, i, indent):
    result = {}
    while i < len(lines):
        ind, content = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise ValueError("缩进异常 (行 %d): %s" % (i + 1, content))
        if content.startswith("- "):
            break
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            nxt = lines[i + 1] if i + 1 < len(lines) else None
            if nxt and nxt[0] > indent:
                result[key], i = _parse_block(lines, i + 1, nxt[0])
            elif nxt and nxt[0] == indent and nxt[1].startswith("- "):
                result[key], i = _parse_list(lines, i + 1, indent)
            else:
                result[key] = None
                i += 1
        else:
            result[key] = _scalar(rest)
            i += 1
    return result, i


def _parse_list(lines, i, indent):
    result = []
    while i < len(lines):
        ind, content = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise ValueError("缩进异常 (行 %d): %s" % (i + 1, content))
        if not content.startswith("- "):
            break
        item = content[2:].strip()
        # 形如 "- key: value" → 列表项是字典，后续更深的缩进行属于同一项
        if re.match(r"^[A-Za-z_][\w\-]*\s*:", item):
            sub = [(indent + 2, item)]
            j = i + 1
            while j < len(lines) and lines[j][0] > indent:
                sub.append(lines[j])
                j += 1
            obj, _ = _parse_map(sub, 0, indent + 2)
            result.append(obj)
            i = j
        else:
            result.append(_scalar(item))
            i += 1
    return result, i


def _parse_block(lines, i, indent):
    if lines[i][1].startswith("- "):
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def mini_yaml_load(text: str):
    lines = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = _strip_comment(raw.strip())
        if not stripped:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, stripped))
    if not lines:
        return {}
    val, _ = _parse_block(lines, 0, lines[0][0])
    return val


def load_registry(path: str):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return mini_yaml_load(text)


# --------------------------------------------------------------------------
# 文件扫描
# --------------------------------------------------------------------------


def collect_files(root: str):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if name.startswith(".") or name.startswith("~$"):
                continue
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            rel = os.path.relpath(full, root).replace("\\", "/")
            files.append(
                {
                    "rel": rel,
                    "name": name,
                    "stem": os.path.splitext(name)[0],
                    "ext": os.path.splitext(name)[1].lower(),
                    "size": size,
                    "full": full,
                }
            )
    files.sort(key=lambda f: f["rel"])
    return files


def build_corpus(files):
    """读取文本文件内容，用于评分信号取证。返回 {rel: content}。"""
    corpus = {}
    total = 0
    for f in files:
        if f["ext"] not in TEXT_EXT or f["size"] == 0:
            continue
        if total >= MAX_CORPUS_BYTES:
            break
        try:
            with open(f["full"], encoding="utf-8", errors="ignore") as fh:
                content = fh.read(MAX_FILE_BYTES)
        except OSError:
            continue
        corpus[f["rel"]] = content
        total += len(content)
    return corpus


def search_corpus(corpus, terms):
    """在语料里找任一关键词，返回 (是否命中, 证据文件名)。"""
    for term in terms:
        low = term.lower()
        for rel, content in corpus.items():
            idx = content.lower().find(low)
            if idx != -1:
                line_no = content.count("\n", 0, idx) + 1
                return True, "%s:%d" % (rel, line_no)
    return False, None


def signal_evidence(corpus, signal):
    """判断一个 rubric 信号能否在交付物里找到证据。

    三级匹配（v2 迭代：C3 实测发现「内容实质」三项信号全部判 0，属于误判）：
      1.0 分 —— 信号原文或同义词精确命中
      0.5 分 —— 中文信号退化成 2 字滑窗片段后命中（例如「提供新信息」→「信息」）
      0.0 分 —— 完全找不到
    返回 (权重, 证据位置, 匹配词)。
    """
    terms = [signal] + SIGNAL_SYNONYMS.get(signal, [])
    ok, ev = search_corpus(corpus, terms)
    if ok:
        return 1.0, ev, signal

    # 退化为 2 字滑窗，避免「文档里有实质内容但没写 rubric 原词」被判 0
    cjk = re.findall(r"[\u4e00-\u9fff]", signal)
    if len(cjk) >= 4:
        frag = ["".join(cjk[i : i + 2]) for i in range(len(cjk) - 1)]
        ok, ev = search_corpus(corpus, frag)
        if ok:
            return 0.5, ev, "片段匹配"
    return 0.0, None, None


# --------------------------------------------------------------------------
# 核心检查
# --------------------------------------------------------------------------


def match_files(files, pattern):
    pat = pattern.lower()
    hits = []
    for f in files:
        if fnmatch.fnmatch(f["name"].lower(), pat) or fnmatch.fnmatch(f["rel"].lower(), pat):
            hits.append(f)
    return hits


NAMING_RE = re.compile(r"^(?P<author>[^_]+)_(?P<cid>C\d+[A-Z]*?)_(?P<part>.+)$", re.IGNORECASE)


def check_deliverables(files, deliverables):
    results = []
    for d in deliverables or []:
        pattern = d.get("pattern") or d.get("label") or ""
        label = d.get("label") or pattern
        hits = match_files(files, pattern)
        nonempty = [h for h in hits if h["size"] > 0]
        results.append(
            {
                "label": label,
                "pattern": pattern,
                "required": bool(d.get("required", True)),
                "found": bool(nonempty),
                "empty_only": bool(hits) and not nonempty,
                "matches": [h["rel"] for h in hits][:6],
                "sizes": [h["size"] for h in hits][:6],
            }
        )
    return results


def check_naming(files, challenge_id, deliverable_rels=None):
    """命名规范检查。

    deliverable_rels：命中必交物的文件集合。「文件名里的挑战号与本挑战不符」只对
    必交物判定 —— evidence/ 里留着 C1/C2 的运行记录属正常情况，不该报警（v5 修正）。
    """
    if deliverable_rels is None:
        deliverable_rels = set()
    conform, nonconform = [], []
    for f in files:
        m = NAMING_RE.match(f["stem"])
        if m:
            conform.append((f["rel"], m.group("author"), m.group("cid")))
        else:
            nonconform.append(f["rel"])
    wrong_cid = [
        (r, a, c)
        for (r, a, c) in conform
        if challenge_id and c.upper() != challenge_id.upper() and r in deliverable_rels
    ]
    return {
        "conform": conform,
        "nonconform": nonconform,
        "wrong_challenge": wrong_cid,
    }


def ai_log_files(files):
    pats = ["*AI日志*", "*ai日志*", "*ai-log*", "*ai_log*", "*AI-log*"]
    seen, out = set(), []
    for p in pats:
        for f in match_files(files, p):
            if f["rel"] not in seen:
                seen.add(f["rel"])
                out.append(f)
    return out


def check_red_flags(files, deliv_results, registry_entry, corpus):
    flags = []
    dims = {d.get("id"): d for d in (registry_entry.get("dimensions") or [])}

    missing = [d["label"] for d in deliv_results if d["required"] and not d["found"]]
    if missing:
        flags.append(
            {
                "id": "missing_artifacts",
                "title": "核心交付物缺失",
                "detail": "缺少：%s" % "、".join(missing),
                "affects": "artifactCompleteness",
                "cap": 5,
                "applies": "artifactCompleteness" in dims,
            }
        )

    logs = ai_log_files(files)
    log_chars = 0
    for f in logs:
        log_chars += len(corpus.get(f["rel"], "")) if f["rel"] in corpus else f["size"]
    if not logs:
        flags.append(
            {
                "id": "no_ai_log",
                "title": "无 AI 使用记录",
                "detail": "文件夹里找不到任何 AI日志 文件",
                "affects": "reflectionQuality",
                "cap": 5,
                "applies": True,
            }
        )
    elif log_chars < MIN_AI_LOG_CHARS:
        flags.append(
            {
                "id": "no_ai_log",
                "title": "AI 记录过薄",
                "detail": "AI日志 有效内容约 %d 字 < 阈值 %d 字，评审可能不认" % (log_chars, MIN_AI_LOG_CHARS),
                "affects": "reflectionQuality",
                "cap": 5,
                "applies": True,
            }
        )

    if logs:
        has_iter, ev = search_corpus(corpus, ITERATION_KEYWORDS)
        if log_chars < MIN_ITERATION_CHARS or not has_iter:
            flags.append(
                {
                    "id": "one_shot_ai",
                    "title": "疑似一句话指令直接提交",
                    "detail": "AI日志 中未发现迭代/prompt修改/失败重试痕迹（%s）"
                    % ("找到证据 %s" % ev if ev else "无关键词命中"),
                    "affects": "aiUsage",
                    "cap": 5,
                    "applies": True,
                }
            )

    empty_files = [f["rel"] for f in files if f["size"] == 0]
    if empty_files:
        flags.append(
            {
                "id": "empty_files",
                "title": "存在空文件",
                "detail": "%d 个文件大小为 0：%s" % (len(empty_files), "、".join(empty_files[:5])),
                "affects": None,
                "cap": None,
                "applies": False,
            }
        )
    return flags


def estimate_scores(registry_entry, deliv_results, corpus, red_flags):
    """按 rubric 信号在交付物里的可追溯证据粗估五维得分。

    这是「机器粗估」，不是平台官方评分 —— 用途是把注意力引到最可能丢分的维度，
    每一条都给出证据位置，方便人工复核。
    """
    dims = registry_entry.get("dimensions") or []
    required = [d for d in deliv_results if d["required"]]
    complete_ratio = (sum(1 for d in required if d["found"]) / len(required)) if required else 1.0

    caps = {}
    for f in red_flags:
        if f.get("affects") and f.get("cap") is not None:
            caps[f["affects"]] = min(caps.get(f["affects"], 999), f["cap"])

    out = []
    for d in dims:
        maxp = d.get("max") or 0
        signals = d.get("signals") or []
        hits, misses = [], []
        weight_sum = 0.0
        for s in signals:
            w, ev, how = signal_evidence(corpus, s)
            weight_sum += w
            rec = {"signal": s, "evidence": ev, "weight": w, "how": how}
            if w >= 1.0:
                hits.append(rec)
            elif w > 0:
                hits.append(rec)  # 弱命中：算部分分，但仍提示补证据
            else:
                misses.append(rec)
        ratio = (weight_sum / len(signals)) if signals else 0.0
        raw = maxp * ratio * (0.6 + 0.4 * complete_ratio)
        est = round(raw, 1)
        capped = d.get("id") in caps
        if capped:
            est = min(est, caps[d["id"]])
        out.append(
            {
                "id": d.get("id"),
                "label": d.get("label"),
                "max": maxp,
                "estimate": est,
                "gap": round(maxp - est, 1),
                "capped": capped,
                "cap": caps.get(d.get("id")),
                "hits": hits,
                "misses": misses,
            }
        )
    return out, complete_ratio


def detect_challenge_id(path, files, registry):
    """猜挑战编号：先看文件夹名，再看文件名里的 _C4_ 样式。"""
    name = os.path.basename(os.path.abspath(path).rstrip("/\\"))
    m = re.search(r"(?:^|[^A-Za-z0-9])(C\d+[A-Z]*)(?:[^A-Za-z0-9]|$)", name, re.IGNORECASE)
    if m and m.group(1).upper() in registry:
        return m.group(1).upper()
    counter = {}
    for f in files:
        m = NAMING_RE.match(f["stem"])
        if m:
            cid = m.group("cid").upper()
            counter[cid] = counter.get(cid, 0) + 1
    for cid, _ in sorted(counter.items(), key=lambda kv: -kv[1]):
        if cid in registry:
            return cid
    return None


# --------------------------------------------------------------------------
# 报告渲染
# --------------------------------------------------------------------------


def render_markdown(report):
    L = []
    e = report["challenge"]
    L.append("# 提交前体检报告：%s" % e["title"])
    L.append("")
    L.append("- **挑战**：`%s`（平台 ID `%s`，截止 %s）" % (report["challenge_id"], e.get("platform_id", "-"), e.get("deadline", "-")))
    L.append("- **路径**：`%s`" % report["path"])
    L.append("- **扫描**：%d 个文件，共 %s" % (report["file_count"], human_size(report["total_bytes"])))
    L.append("- **交付物完整度**：%d / %d（%.0f%%）" % (report["complete_count"], report["required_count"], report["complete_ratio"] * 100))
    L.append("")

    L.append("## 1. 交付物核对")
    L.append("")
    L.append("| 必交物 | 匹配模式 | 状态 | 命中文件 |")
    L.append("|---|---|---|---|")
    for d in report["deliverables"]:
        status = "✅ 已交" if d["found"] else ("⚠️ 空文件" if d["empty_only"] else "❌ 缺失")
        files_txt = "、".join("`%s`" % m for m in d["matches"]) or "—"
        L.append("| %s | `%s` | %s | %s |" % (d["label"], d["pattern"], status, files_txt))
    L.append("")

    L.append("## 2. 命名规范（`姓名_挑战号_部件.扩展名`）")
    L.append("")
    n = report["naming"]
    L.append("- 符合规范：**%d** 个" % len(n["conform"]))
    L.append("- 不符合规范：**%d** 个" % len(n["nonconform"]))
    if n["nonconform"]:
        L.append("- 示例（最多列 8 个）：%s" % "、".join("`%s`" % x for x in n["nonconform"][:8]))
    if n["wrong_challenge"]:
        L.append("- ⚠️ 文件名里的挑战号与本挑战不符：%s" % "、".join("`%s`(写作%s)" % (r, c) for r, _a, c in n["wrong_challenge"][:5]))
    L.append("")

    L.append("## 3. 红线扫描")
    L.append("")
    if not report["red_flags"]:
        L.append("✅ 未命中任何红线。")
    else:
        for f in report["red_flags"]:
            tail = ""
            if f.get("affects") and f.get("applies"):
                tail = " → **%s 维度被压到 ≤ %s 分**" % (f["affects"], f["cap"])
            L.append("- 🚩 **%s**（%s）：%s%s" % (f["title"], f["id"], f["detail"], tail))
    L.append("")

    L.append("## 4. 五维粗估（机器估计，非官方评分）")
    L.append("")
    L.append("| 维度 | 粗估 | 满分 | 差距 | 命中信号 | 缺失信号 |")
    L.append("|---|---:|---:|---:|---|---|")
    total_est = 0.0
    total_max = 0
    for s in report["scores"]:
        total_est += s["estimate"]
        total_max += s["max"]
        cap_note = " ⚠️封顶%s" % s["cap"] if s["capped"] else ""
        L.append(
            "| %s | **%s**%s | %s | %s | %d | %s |"
            % (
                s["label"],
                s["estimate"],
                cap_note,
                s["max"],
                s["gap"],
                len(s["hits"]),
                "、".join(m["signal"] for m in s["misses"]) or "—",
            )
        )
    L.append("")
    L.append("**粗估总分：%s / %d**" % (round(total_est, 1), total_max))
    L.append("")
    L.append("> 粗估逻辑：`维度满分 × 命中信号比例 × (0.6 + 0.4 × 交付物完整度)`，再套用红线封顶。")
    L.append("> 它回答的是「最可能在哪丢分」，不是「我能得几分」——请结合下面的杠杆逐条人工复核。")
    L.append("")

    L.append("## 5. 提分杠杆（按丢分从大到小）")
    L.append("")
    if not report["levers"]:
        L.append("✅ 没有明显缺口，去做最后的通读校对吧。")
    else:
        for i, lv in enumerate(report["levers"], 1):
            L.append("%d. **%s**（丢 %s 分 / 满分 %s）" % (i, lv["label"], lv["gap"], lv["max"]))
            if lv["capped"]:
                L.append("   - 🔴 已被红线封顶到 %s 分，先解红线，否则补内容无效" % lv["cap"])
            for m in lv["misses"]:
                L.append("   - 补信号「%s」：在交付物里留下可复核的证据" % m["signal"])
    L.append("")

    L.append("## 6. TODO（按优先级执行）")
    L.append("")
    for i, t in enumerate(report["todo"], 1):
        L.append("%d. %s" % (i, t))
    L.append("")

    L.append("## 7. 机器查不到、必须人工确认的事")
    L.append("")
    L.append("这一节来自真实教训：文件齐全 ≠ 得分高。脚本只能读文件，读不到「事情有没有真的发生」。")
    L.append("")
    for item in MANUAL_CHECKS:
        L.append("- [ ] %s" % item)
    L.append("")
    L.append("---")
    L.append("")
    L.append("_由 challenge-submit-guard 生成 · 注册表版本 %s · 生成时间 %s_"
             % (report.get("registry_version", "1"), report["generated_at"]))
    return "\n".join(L)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def audit(path, registry, challenge_id=None):
    import datetime

    if not os.path.isdir(path):
        raise SystemExit("路径不是一个文件夹：%s" % path)

    files = collect_files(path)
    corpus = build_corpus(files)

    if challenge_id:
        challenge_id = challenge_id.upper()
        if challenge_id not in registry["challenges"]:
            raise SystemExit("注册表里没有挑战 %s，用 --list 查看支持编号" % challenge_id)
    else:
        challenge_id = detect_challenge_id(path, files, registry["challenges"])
        if not challenge_id:
            raise SystemExit(
                "无法自动识别挑战编号，请用 -c 指定（如 -c C4）。可用编号见 --list。"
            )

    entry = registry["challenges"][challenge_id]
    deliv = check_deliverables(files, entry.get("deliverables"))
    matched_rels = {rel for d in deliv for rel in d["matches"]}
    naming = check_naming(files, challenge_id, matched_rels)
    flags = check_red_flags(files, deliv, entry, corpus)
    scores, complete_ratio = estimate_scores(entry, deliv, corpus, flags)

    required = [d for d in deliv if d["required"]]
    complete_count = sum(1 for d in required if d["found"])

    levers = sorted(scores, key=lambda s: -s["gap"])[:3]

    todo = []
    for d in deliv:
        if d["required"] and not d["found"]:
            todo.append("补交 **%s** —— 建议文件名 `你的名字_%s_%s`" % (d["label"], challenge_id, d["label"]))
        elif d["empty_only"]:
            todo.append("**%s** 存在但是空文件（`%s`），填入内容或删除占位" % (d["label"], "、".join(d["matches"])))
    for f in flags:
        if f["id"] == "missing_artifacts":
            todo.append("解红线 `missing_artifacts`：先把上面缺失的必交物补齐再提交")
        elif f["id"] == "no_ai_log":
            todo.append("解红线 `no_ai_log`：补一份 ≥%d 字的 AI日志（用了什么 AI / 怎么指挥 / 迭代几轮 / 你改了什么）" % MIN_AI_LOG_CHARS)
        elif f["id"] == "one_shot_ai":
            todo.append("解红线 `one_shot_ai`：在 AI日志 里补上迭代过程 —— 第几轮、改了什么 prompt、哪次失败了")
        elif f["id"] == "empty_files":
            todo.append("清理 %s" % f["detail"])
    if naming["nonconform"] and len(naming["nonconform"]) > len(naming["conform"]):
        todo.append(
            "统一文件命名为 `姓名_%s_部件.扩展名`（当前 %d 个不符合），便于评审与自动化盘点"
            % (challenge_id, len(naming["nonconform"]))
        )
    for lv in levers:
        if lv["gap"] >= 5 and not lv["capped"]:
            todo.append("提升「%s」：补齐信号 %s" % (lv["label"], "、".join(m["signal"] for m in lv["misses"]) or "（信号已全命中，需提升质量而非数量）"))

    return {
        "challenge_id": challenge_id,
        "challenge": entry,
        "path": os.path.abspath(path),
        "file_count": len(files),
        "total_bytes": sum(f["size"] for f in files),
        "deliverables": deliv,
        "required_count": len(required),
        "complete_count": complete_count,
        "complete_ratio": complete_ratio,
        "naming": naming,
        "red_flags": flags,
        "scores": scores,
        "levers": levers,
        "todo": todo,
        "registry_version": registry.get("version", "1"),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def cmd_list(registry):
    print("challenge-submit-guard 已注册 %d 个挑战：\n" % len(registry["challenges"]))
    print("| 编号 | 标题 | 必交交付物 |")
    print("|---|---|---|")
    for cid, e in registry["challenges"].items():
        dels = "、".join(d.get("label", "") for d in (e.get("deliverables") or []))
        print("| %s | %s | %s |" % (cid, e.get("title", ""), dels))
    print("\n用法：python challenge_submit_guard.py <文件夹> -c <编号>")


def cmd_self_test(registry):
    """用合成夹具验证安装是否可用 —— 任何人都能在 3 秒内确认脚本没坏。"""
    passed, failed = 0, 0

    def case(name, fn):
        nonlocal passed, failed
        try:
            fn()
            print("  ✅ PASS  %s" % name)
            passed += 1
        except AssertionError as err:
            print("  ❌ FAIL  %s → %s" % (name, err))
            failed += 1

    tmp = tempfile.mkdtemp(prefix="csg-selftest-")
    try:
        # 夹具 1：完整交付
        good = os.path.join(tmp, "good")
        os.makedirs(good)
        write(os.path.join(good, "张三_C4_skill说明.md"), "# 技能说明\n触发短语：XXX\n可执行 脚本\n")
        write(os.path.join(good, "张三_C4_教学说明.md"), "# 教学说明\n示例 example\n上手步骤\n")
        write(os.path.join(good, "张三_C4_demo.png"), "PNG-FAKE")
        write(os.path.join(good, "张三_C4_x.skill"), "PK-FAKE")
        write(os.path.join(good, "张三_C4_AI日志.md"), "迭代记录\n" * 300 + "第2轮 prompt 优化，失败后重试\n")

        def t_good():
            r = audit(good, registry, "C4")
            miss = [d["label"] for d in r["deliverables"] if d["required"] and not d["found"]]
            assert not miss, "应全部找到，实际缺：%s" % miss
            ids = {f["id"] for f in r["red_flags"]}
            assert "missing_artifacts" not in ids, "不应命中 missing_artifacts"
            assert "no_ai_log" not in ids, "AI日志 足够长，不应命中 no_ai_log"
            assert "one_shot_ai" not in ids, "有迭代痕迹，不应命中 one_shot_ai"
            assert r["complete_ratio"] == 1.0, "完整度应为 1.0"

        case("完整交付包 → 5 项必交物全命中、无红线", t_good)

        # 夹具 2：空文件夹
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)

        def t_empty():
            r = audit(empty, registry, "C4")
            ids = {f["id"] for f in r["red_flags"]}
            assert "missing_artifacts" in ids, "空文件夹必须命中 missing_artifacts"
            assert "no_ai_log" in ids, "空文件夹必须命中 no_ai_log"
            ac = [s for s in r["scores"] if s["id"] == "artifactCompleteness"]
            assert ac and ac[0]["capped"], "artifactCompleteness 应被封顶"

        case("空文件夹 → 命中缺失+无日志红线，产物完整性被封顶", t_empty)

        # 夹具 3：一句话 AI 日志
        oneshot = os.path.join(tmp, "oneshot")
        os.makedirs(oneshot)
        for nm in ("a_C4_skill说明.md", "a_C4_教学说明.md", "a_C4_demo.png", "a_C4_x.skill"):
            write(os.path.join(oneshot, nm), "内容")
        write(os.path.join(oneshot, "a_C4_AI日志.md"), "我用AI写完了。")

        def t_oneshot():
            r = audit(oneshot, registry, "C4")
            ids = {f["id"] for f in r["red_flags"]}
            assert "no_ai_log" in ids, "AI日志过短应命中 no_ai_log"
            assert "one_shot_ai" in ids, "无迭代痕迹应命中 one_shot_ai"
            au = [s for s in r["scores"] if s["id"] == "aiUsage"]
            assert au and au[0]["capped"], "aiUsage 应被封顶"

        case("一句话 AI日志 → 命中 one_shot_ai，AI使用维度被封顶", t_oneshot)

        # 夹具 4：自动识别挑战号
        def t_auto():
            r = audit(good, registry, None)
            assert r["challenge_id"] == "C4", "应从文件名自动识别为 C4，实际 %s" % r["challenge_id"]

        case("不传 -c → 从文件名自动识别挑战号", t_auto)

        # 夹具 5：注册表自检
        def t_registry():
            assert len(registry["challenges"]) >= 15, "注册表应覆盖 15+ 个挑战"
            for cid, e in registry["challenges"].items():
                assert e.get("deliverables"), "%s 缺少交付物定义" % cid
                assert e.get("dimensions"), "%s 缺少评分维度" % cid

        case("注册表完整性 → 每个挑战都有交付物与维度定义", t_registry)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n自检结果：%d 通过 / %d 失败" % (passed, failed))
    return 0 if failed == 0 else 1


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def main():
    ap = argparse.ArgumentParser(
        description="EduSeed / Elite20 挑战提交自检器：提交前先查交付物、命名、红线与丢分点",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
        "  python challenge_submit_guard.py ./C4 -c C4\n"
        "  python challenge_submit_guard.py ./C4 --json\n"
        "  python challenge_submit_guard.py --self-test\n",
    )
    ap.add_argument("path", nargs="?", help="挑战交付文件夹路径")
    ap.add_argument("-c", "--challenge", help="挑战编号，如 C4；省略则自动识别")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY, help="挑战注册表 YAML 路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    ap.add_argument("--out", help="把报告写入文件（默认打印到标准输出）")
    ap.add_argument("--strict", action="store_true", help="缺必交物或命中红线时退出码为 1")
    ap.add_argument("--list", action="store_true", help="列出注册表里所有挑战")
    ap.add_argument("--self-test", action="store_true", help="运行内置自检（不需要外部文件）")
    args = ap.parse_args()

    if not os.path.exists(args.registry):
        raise SystemExit("找不到注册表：%s（可用 --registry 指定）" % args.registry)
    registry = load_registry(args.registry)

    if args.list:
        cmd_list(registry)
        return 0

    if args.self_test:
        return cmd_self_test(registry)

    if not args.path:
        ap.print_help()
        return 2

    report = audit(args.path, registry, args.challenge)

    if args.json:
        text = json.dumps(report, ensure_ascii=False, indent=2)
    else:
        text = render_markdown(report)

    if args.out:
        write(args.out, text)
        print("报告已写入：%s" % os.path.abspath(args.out))
    else:
        print(text)

    if args.strict:
        blocking = [f for f in report["red_flags"] if f["id"] in ("missing_artifacts", "no_ai_log", "one_shot_ai")]
        if blocking or report["complete_count"] < report["required_count"]:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
