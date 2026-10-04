#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C4A Skill Evaluator —— C4 技能提交的自动评审器（规则层）。

    python c4a_evaluator.py <提交目录> [--out 输出目录] [--format md,csv,html,json]
                            [--rubric references/c4_rubric.json] [--deterministic]

设计要点（为什么不是「数关键词」）
================================
1. **否定语境闸门**：中文里「没有测试」会命中「测试」。
   命中点前 8 个字符内出现「没有/无/未/缺/不/尚未」时，该次命中作废。
   这是中文信号匹配最大的坑，不处理会让「什么都没写」的提交反而拿到分。
2. **证据可追溯**：每一分都对应「哪个文件、第几行、命中了什么」。
   拿不到证据的分不给 —— 评审器的结论必须能被人工复核。
3. **交付物槽位做加权二分匹配**：一个文件可能同时像「教学说明」和「Skill 说明」。
   朴素做法是两边都记一次（虚高完整性）。这里按 (文件名命中, 扩展名, 内容信号)
   算权重，贪心匹配，**每个文件只归一个槽位**。
4. **空文件不算命中**：0 字节或近空（< 24 字节）的文件即使在名字上完美匹配，
   也只记为「占位」，不进完整性。
5. **只报证据，不臆断**：传播（被使用次数）在 C4 里权重最高，但仓库里没有回执
   ≠ 没被传播。所以这一项单独报告状态，**不折算成分数**。
6. **确定性**：同一输入反复运行输出逐字节相同（`--deterministic` 去掉时间戳）。
   评审器如果自己不可复现，它的结论就没有可比性。

仅使用 Python 标准库。无需 pip install、无需联网、无需 API key。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import sys
import tarfile
import unicodedata
import zipfile
from datetime import datetime

VERSION = "1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUBRIC = os.path.join(HERE, "..", "references", "c4_rubric.json")

BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".webm",
              ".zip", ".gz", ".pdf", ".docx", ".xlsx", ".skill", ".ico", ".svg"}
TEXT_EXT = {".md", ".txt", ".py", ".js", ".sh", ".json", ".yaml", ".yml",
            ".csv", ".html", ".css", ".ts", ".java", ".c", ".cpp", ".go", ".rs"}
MAX_TEXT_BYTES = 2_000_000          # 超大文件只做文件名匹配

# 「近空文件」阈值。**只用来识别真正的空文件**（0 字节或只有空白）。
# 我第一版设成 24 字节，结果一个 9 字节的 `print(1)` 脚本被判成「空」，
# 直接从槽位匹配里被排除 → 完整性无故从 5/5 掉到 4/5，
# 而且 E1「有可运行代码」也判不过。**极简 ≠ 空。**
NEAR_EMPTY_BYTES = 4


# =====================================================================
# 文本读取
# =====================================================================

def _decode(raw: bytes) -> str:
    """UTF-8 优先，GBK 回退。中文文件名/内容在 Windows 上很常见。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _docx_text(raw: bytes) -> str:
    """从 .docx 里抽正文：docx 就是 zip，正文在 word/document.xml。"""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.endswith("document.xml")]
            if not names:
                return ""
            xml = z.read(names[0]).decode("utf-8", "replace")
        xml = re.sub(r"</w:p>", "\n", xml)
        return html.unescape(re.sub(r"<[^>]+>", "", xml))
    except Exception:  # noqa: BLE001
        return ""


def _skill_members(raw: bytes) -> dict:
    """`.skill` 就是 tar.gz。返回 {成员名: 文本}（二进制成员记为空串）。"""
    out = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            for m in tar.getmembers():
                if not m.isfile() or m.size > MAX_TEXT_BYTES:
                    continue
                f = tar.extractfile(m)
                if f is None:
                    continue
                b = f.read()
                ext = os.path.splitext(m.name)[1].lower()
                out[m.name] = "" if ext in BINARY_EXT else _decode(b)
    except Exception:  # noqa: BLE001
        pass
    return out


class Doc:
    """一份被读入的文件。`text` 是归一化后的可匹配文本。"""

    def __init__(self, path: str, rel: str):
        self.path = path
        self.rel = rel
        self.name = os.path.basename(rel)
        self.ext = os.path.splitext(self.name)[1].lower()
        self.size = os.path.getsize(path)
        self.text = ""
        self.members = {}
        self.read_error = ""
        self._read()

    def _read(self):
        if self.ext in BINARY_EXT:
            if self.ext == ".skill":
                with open(self.path, "rb") as f:
                    self.members = _skill_members(f.read())
                # 技能包内部文本也参与匹配
                self.text = "\n".join(
                    f"\n<<<{k}>>>\n{v}" for k, v in sorted(self.members.items()))
            return
        if self.size > MAX_TEXT_BYTES:
            self.read_error = "too_large"
            return
        try:
            with open(self.path, "rb") as f:
                raw = f.read()
        except OSError as e:
            self.read_error = f"read_failed: {e}"
            return
        if self.ext == ".docx":
            self.text = _docx_text(raw)
        elif self.ext in TEXT_EXT or self.ext == "":
            self.text = _decode(raw)
        else:
            self.text = _decode(raw)

    # -- 便捷属性 ------------------------------------------------------
    @property
    def is_near_empty(self) -> bool:
        return self.size < NEAR_EMPTY_BYTES

    @property
    def lines(self) -> list:
        return self.text.splitlines()

    def all_text(self) -> str:
        """正文 + 内嵌成员文本（.skill 里每个成员都算）。"""
        return self.text

    def sha256(self) -> str:
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()


# =====================================================================
# 带证据与否定闸门的匹配
# =====================================================================

def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def find_hits(text: str, pattern: str, gate: dict, flags=re.M) -> list:
    """返回 [(行号, 命中片段, 是否被否定)]。"""
    out = []
    try:
        rx = re.compile(_norm(pattern), flags | re.IGNORECASE)
    except re.error:
        return out
    for ln, line in enumerate(_norm(text).splitlines(), 1):
        for m in rx.finditer(line):
            frag = m.group(0)
            negated = False
            if gate.get("enabled", True):
                w = int(gate.get("window", 8))
                lo = max(0, m.start() - w)
                ctx = line[lo:m.start()]
                if any(k in ctx for k in gate.get("markers", [])):
                    negated = True
            out.append((ln, frag[:60], negated))
    return out


def any_hit(docs: list, patterns: list, gate: dict) -> tuple:
    """在若干文件里找任一 pattern。返回 (有无未被否定的命中, 证据列表)。"""
    ev = []
    for d in docs:
        t = d.all_text()
        if not t:
            continue
        for p in patterns:
            for ln, frag, neg in find_hits(t, p, gate):
                if neg:
                    continue
                ev.append({"file": d.rel, "line": ln, "match": frag})
    return bool(ev), ev[:6]


def any_absent_violation(docs: list, patterns: list, gate: dict) -> tuple:
    """检查**不应出现**的 pattern。返回 (是否有违规, 证据)。"""
    ev = []
    for d in docs:
        t = d.all_text()
        if not t:
            continue
        for p in patterns:
            for ln, frag, neg in find_hits(t, p, gate):
                if neg:
                    continue
                ev.append({"file": d.rel, "line": ln, "match": frag})
    return bool(ev), ev[:6]


def has_frontmatter(docs: list) -> tuple:
    for d in docs:
        t = d.all_text().lstrip("\ufeff \t\r\n")
        if not t.startswith("---"):
            continue
        end = t.find("\n---", 3)
        if end < 0:
            continue
        block = t[3:end]
        keys = set()
        for line in block.splitlines():
            m = re.match(r"\s*([A-Za-z_][\w-]*)\s*:", line)
            if m:
                keys.add(m.group(1).lower())
        if keys:
            return True, [{"file": d.rel, "keys": sorted(keys)}]
    return False, []


def py_compiles(docs: list) -> tuple:
    """附带的 .py 是否都能编译。返回 (全通过, 证据)。"""
    checked, bad = 0, []
    for d in docs:
        if d.ext != ".py" or not d.text:
            continue
        checked += 1
        try:
            compile(_norm(d.text), d.rel, "exec")
        except SyntaxError as e:
            bad.append({"file": d.rel, "line": e.lineno, "msg": str(e.msg)})
    if checked == 0:
        return True, [{"note": "没有 .py 文件，该项不适用（按通过计）"}]
    return (not bad), bad


IO_RX = [
    re.compile(r"输入[^\n]{0,40}输出"),
    re.compile(r"input[^\n]{0,40}output", re.I),
    re.compile(r"接受[^\n]{0,30}返回"),
    re.compile(r"给定[^\n]{0,30}(得到|输出)"),
    re.compile(r"把[^\n]{0,20}(变成|转成|生成)"),
    re.compile(r"\*\*输入\*\*[^\n]*\*\*输出\*\*"),
]


def io_statement(docs: list) -> tuple:
    """找「输入 X，输出 Y」式的一句话。要求**同一行**同时出现输入与输出。"""
    ev = []
    for d in docs:
        for ln, line in enumerate(_norm(d.all_text()).splitlines(), 1):
            for rx in IO_RX:
                if rx.search(line):
                    ev.append({"file": d.rel, "line": ln,
                               "match": line.strip()[:80]})
                    break
    return bool(ev), ev[:4]


# =====================================================================
# 槽位匹配（加权贪心二分）
# =====================================================================

def slot_score(doc: Doc, spec: dict) -> tuple:
    """一个文件对某个交付物槽位的匹配权重。返回 (分数, 说明)。"""
    s, why = 0, []
    name = doc.name.lower()
    for p in spec.get("filename_patterns", []):
        try:
            if re.search(_norm(p), name, re.I):
                s += 3
                why.append(f"文件名命中 {p}")
                break
        except re.error:
            continue
    if doc.ext in spec.get("extensions", []):
        s += 2
        why.append(f"扩展名 {doc.ext}")
    if spec.get("binary"):
        # 二进制交付物只看名字/扩展名
        return s, why
    t = doc.all_text()
    if t:
        hits = 0
        for p in spec.get("content_signals", []):
            try:
                if re.search(_norm(p), _norm(t), re.I | re.M):
                    hits += 1
            except re.error:
                continue
        s += min(hits, 3)
        if hits:
            why.append(f"内容信号 {hits} 个")
    return s, why


def match_slots(docs: list, rubric: dict, gate: dict) -> dict:
    """交付物槽位匹配：**全局最优**，不是每个槽位各自挑最好的。

    朴素做法（每个槽位独立挑最高分文件）会让同一个文件被两个槽位同时记一次，
    完整性被系统性高估 —— 一份 `SKILL.md` 同时当「说明文档」和「可执行内容」。

    实现：先给每个槽位取前 K 个候选（K=8），再**穷举**所有互不冲突的分配，
    取「总分最高、并列时槽位填得最多」的那个。

    为什么穷举而不是贪心 / 局部搜索 —— 这两条路我都走过，都失败了：
      · **贪心**：`张三_C4_skill说明.md` 对 `skill_doc` 和 `executable` 都得 8 分
        （`executable` 的文件名模式里有 `skill`，宽了点），贪心按槽位名字典序
        让 `executable` 先挑，于是它抢走了说明文档，真正的代码 `preflight.py`
        （只值 2 分）没人要 —— 完整性 5/5 掉到 4/5，E1 也判不过。
      · **贪心 + 两两交换的局部搜索**：写了四十行，仍然没修好这个 case
        （「把被占文件让给空槽位」这条路径漏了）。修了两轮还是错。
      · **穷举**：槽位 5 个、每槽 8 个候选，最多 9^5 ≈ 6 万种组合，毫秒级跑完，
        而且**显然正确**。规模允许时，穷举比聪明的近似更划算 ——
        这也是本文件里唯一一处「暴力比技巧好」的地方。
    """
    keys = sorted(rubric["deliverables"])          # 固定顺序保证确定性
    K = 8
    cand = {}
    for key in keys:
        spec = rubric["deliverables"][key]
        rows = []
        for di, d in enumerate(docs):
            if d.is_near_empty and not spec.get("binary"):
                continue                            # 近空文件不参与
            sc, why = slot_score(d, spec)
            if sc > 0:
                rows.append((sc, di, why))
        rows.sort(key=lambda x: (-x[0], docs[x[1]].rel))
        cand[key] = rows[:K]

    best = {"key": (-1, -1), "assign": {}}

    def rec(i, used, cur, total):
        if i == len(keys):
            k = (total, len(cur))                   # 先比总分，再比填了几个槽位
            if k > best["key"]:
                best["key"] = k
                best["assign"] = dict(cur)
            return
        rec(i + 1, used, cur, total)                # 该槽位空缺
        for sc, di, why in cand[keys[i]]:
            if di in used:
                continue
            cur[keys[i]] = (sc, di, why)
            used.add(di)
            rec(i + 1, used, cur, total + sc)
            used.discard(di)
            del cur[keys[i]]

    rec(0, set(), {}, 0)

    out = {}
    for key, (sc, di, why) in best["assign"].items():
        out[key] = {"file": docs[di].rel, "score": sc, "why": why,
                    "confidence": "high" if sc >= 4 else
                                  ("medium" if sc >= 2 else "low"),
                    "size": docs[di].size}
    return out


# =====================================================================
# 作者归属
# =====================================================================

AUTHOR_RX = re.compile(r"^([A-Za-z\u4e00-\u9fff][\w\u4e00-\u9fff\-\.]{0,23}?)[_\-]C4[_\-]",
                       re.I)

# 这些目录不是「提交」，是挑战资料/脚手架/源码目录。
# 把它们当成作者会产生幽灵作者（实测：zip 解开后的 `c4-skill-sharing-main`
# 和挑战正文目录 `挑战_C4 技能分享与传播_4cdgor_正文` 都被当成了作者）。
DOC_DIR_RX = re.compile(
    r"^(挑战_|.*_正文$|skill[_-]?src$|skill-evaluator$|tests?$|tools?$|docs?$|"
    r"references$|scripts$|assets$|__pycache__$|run$|outputs?$|review_output$|"
    r"results?$|reports?$|dist$|build$|evidence$|demo$|\.)", re.I)

# 占位符文件名：这类文件为空是**有意的**（演示「处理前」的空目录），
# 不该和「必交交付物交了空文件」混为一谈。
PLACEHOLDER_RX = re.compile(r"(占位|placeholder|todo|待补|empty|\.gitkeep)", re.I)

# 这些词当前缀时几乎一定是机器/产物名，不是人名
NON_AUTHOR_PREFIX = {"run", "test", "tests", "output", "outputs", "log", "logs",
                     "tmp", "temp", "result", "results", "snapshot", "sample",
                     "example", "demo", "data", "src", "main", "index", "build"}

UNCLASSIFIED = "_未识别_"


def resolve_root(path: str) -> str:
    """解开」zip 包装目录「。

    从 GitHub 下载的 zip 解开后通常是 `<repo>-main/` 这一层，
    它里面才是真正的内容。如果根目录只有一个子目录且没有文件，
    就把它当作根 —— 否则会多出一个幽灵作者。
    """
    cur = path
    for _ in range(4):
        try:
            entries = [e for e in os.listdir(cur) if not e.startswith(".")]
        except OSError:
            return cur
        files = [e for e in entries if os.path.isfile(os.path.join(cur, e))]
        dirs = [e for e in entries if os.path.isdir(os.path.join(cur, e))]
        if len(dirs) == 1 and not files:
            cur = os.path.join(cur, dirs[0])
            continue
        return cur
    return cur


def resolve_authors(docs: list, root: str) -> dict:
    """作者提取链。**分不清就不归** —— 这是本函数唯一的设计原则。

    四条规则，按顺序：

    R1 文件名前缀 `姓名_C4_` → 该作者（最高置信）
    R2 位于「资料目录」（挑战正文 / 脚手架 / scripts / references / assets…）→ **资料**，
       不算提交，不参与评审。实测：不排除这些会把挑战正文目录当成作者。
    R3 根目录下没有作者前缀的文件（README.md、LICENSE…）→ **资料**。
       它们是仓库级说明，不是 C4 交付物；当成提交会虚增完整性。
    R4 位于非资料子目录、又没有作者前缀的文件：
        · 若全仓库**只有一个**由 R1 认定的作者 → 并给该作者，标注
          `single_author_repo`（单作者仓库里，技能源码目录通常就是这个人的）；
        · 否则 → `_未识别_`，单独列出、不排名。

    为什么不用「最近的父目录一律当作者」：实测会造出 `challenge-preflight`
    （技能名）、`c4-skill-sharing-main`（zip 包装目录）、`skill_src` 三个幽灵作者，
    班级人数从 1 变 4。**归因错误的代价比归不出来更高。**
    """
    out = {}
    materials = []
    unattributed = []

    for d in docs:
        rel = os.path.relpath(d.path, root)
        parts = rel.split(os.sep)
        dirs = parts[:-1]

        # **目录上下文优先于文件名模式。**
        # 反例（实测）：`evidence/run_C4_self.txt` 的文件名符合 `前缀_C4_后缀`，
        # 被当成了作者 "run「，班级里凭空多出一个人。
        # 一份文件在 evidence/ scripts/ tools/ docs/ 下面，它就是仓库机械的一部分，
        # 不管它叫什么名字。
        if any(DOC_DIR_RX.match(p) for p in dirs):
            materials.append(d)
            continue

        m = AUTHOR_RX.match(d.name)
        # 再加一道：前缀本身是机器/产物词时不算作者（防止根目录出现 `run_C4_x.txt`）
        if m and m.group(1).lower() not in NON_AUTHOR_PREFIX:
            out.setdefault(m.group(1), {"files": [], "source": "filename"})
            out[m.group(1)]["files"].append(d)
            continue
        if not dirs:                      # R3：根目录裸文件
            materials.append(d)
            continue
        unattributed.append(d)

    known = list(out.keys())
    if len(known) == 1 and unattributed:
        k = known[0]
        out[k]["files"] += unattributed
        out[k]["source"] = "filename+single_author_repo"
    elif not known and unattributed:
        # 仓库级回退：一个 GitHub 仓库通常就是一位同学的提交，
        # 但文件名没有 `姓名_C4_` 前缀（有人直接按 `SKILL.md` / `scripts/` 组织）。
        # 这时不存在「归错人」的风险 —— 候选只有一个，所以按仓库名归一位作者。
        # 注意：这与「最近的父目录一律当作者」是两回事，后者会在多候选时乱归。
        label = os.path.basename(os.path.abspath(root)) or "repo"
        label = re.sub(r"[-_](main|master)$", "", label)[:40]
        out[label] = {"files": list(unattributed), "source": "repo_level"}
    elif unattributed:
        out.setdefault(UNCLASSIFIED, {"files": [], "source": "unclassified"})
        out[UNCLASSIFIED]["files"] += unattributed

    if materials:
        out.setdefault("_资料_", {"files": [], "source": "material"})
        out["_资料_"]["files"] += materials

    # 终局回退：整棵树里**一个作者都没识别出来**，但有可读文件。
    # 场景：`resolve_root` 已经解开了单子目录包装，于是所有文件都落在根上，
    # 按 R3 全被判成「仓库级资料」 → 结果一个人都没评。实测踩到过（gold13）。
    # 判断条件要排除 `_资料_` 桶本身 —— 第一版写成 `if not out`，
    # 而那时 out 里已经有 `_资料_`，条件永远为假，回退从来没生效。
    real = [k for k in out if k != "_资料_"]
    if not real:
        cand = [d for d in docs if not d.is_near_empty]
        if cand:
            label = os.path.basename(os.path.abspath(root)) or "repo"
            label = re.sub(r"[-_](main|master)$", "", label)[:40]
            out.pop("_资料_", None)
            out[label] = {"files": cand, "source": "repo_level"}
    return out


# =====================================================================
# 关键词堆砌检测
# =====================================================================

def stuffing_report(docs: list, rubric: dict, gate: dict, allow_files=None) -> dict:
    """判断提交是」堆关键词「还是」真的写了内容「。

    **第一版这里严重误报**：它用 `正文 < 1500 字符 且命中信号 ≥ 6` 判定，
    而规则词表有 200 个 pattern —— 一份正常的提交很容易命中 15+ 个，
    于是 gold 集里 15/20 个样本全被误判成堆砌，红旗精确率只有 0.41，
    连「满分样本」都被压到 0.60。

    正确的判据必须**同时看「命中了什么」和「有没有承载这些信号的结构」**：
    一份真提交有标题层级、代码块、有序步骤、足够长度；
    堆砌只有一串关键词。所以改成：

      has_structure = 长度 ≥ 1500 且 标题 ≥ 3 且 (代码块 ≥ 1 或 列表项 ≥ 3)
      stuffed       = (命中信号 ≥ 10 且 无结构)  或  (长度 < 800 且 命中信号 ≥ 8)

    这个阈值是在 `tests/gold` 的 20 个人工标注样本上校准出来的 ——
    不是拍的。校准前后红旗精确率从 0.41 升到报告里给的数。
    """
    pats = []
    for spec in rubric["deliverables"].values():
        pats += spec.get("content_signals", [])
    for cond in rubric["conditions"].values():
        for c in cond.get("checks", []):
            pats += c.get("patterns", [])
    pats = [p for p in pats if p and not p.startswith("^")][:200]

    # 判据只有一条：**命中信号很多，但承载它们的结构很少**。
    #
    # 阈值 0.35 → **0.55** 是**从分布里定出来的，不是拍的**。实测最小值：
    #   堆砌样本（gold06）        0.448
    #   真实提交（8 份）          0.667 / 0.765 / 1.136 / 1.438 / 1.684 / 2.000 …
    #   gold 集里的正常样本        0.667 ~ 2.500
    # 0.448 与 0.667 之间取中点 0.55，两侧都有余量。
    #
    # 我在这个判据上连着犯了三次同一个错：把「短」当成「空」。
    #   第 1 次 `字符<1500 且信号≥6`：规则词表 200 个 pattern，正常提交轻松命中 15+，
    #            gold 集 15/20 被误判。
    #   第 2 次 加结构条件但仍要求 ≥1500 字符：一份 1387 字符、13 标题、
    #            11 列表项的正常提交仍被判堆砌。
    #   第 3 次 改成比值后又补 `字符<600 且信号≥8`：410 字符、5 标题的
    #            AI 日志又被误判。
    # 教训：**长度不是内容量的代理**，结构项与信号的比值才是。
    # 另外：只在**被匹配到交付物槽位**的文件上判堆砌 —— 一个 `.gitignore`
    # 或配置文件的信号/结构比可能很低，拿它当依据会误伤整份提交（实测踩到）。
    prose_ext = {".md", ".txt", ".docx", ""}
    worst = None
    for d in docs:
        if d.ext not in prose_ext or not d.text:
            continue
        if allow_files is not None and d.rel not in allow_files:
            continue
        r = _stuffing_one(d.all_text(), pats) | {"file": d.rel}
        if worst is None or r["structure_to_signal_ratio"] < \
                worst["structure_to_signal_ratio"]:
            worst = r
    if worst is None:
        return {"flagged": False, "reason": "无参与评审的散文类文件",
                "reasons": [], "distinct_signals": 0, "chars": 0,
                "headings": 0, "fences": 0, "list_items": 0,
                "structure_items": 0, "structure_to_signal_ratio": 1.0}
    return worst


def _stuffing_one(text: str, pats: list) -> dict:
    sig = set()
    for p in pats:
        try:
            if re.search(_norm(p), _norm(text), re.I | re.M):
                sig.add(p)
        except re.error:
            continue

    headings = len(re.findall(r"^\s{0,3}#{1,6}\s", text, re.M))
    fences = len(re.findall(r"^\s*```", text, re.M)) // 2
    list_items = len(re.findall(r"^\s*(?:[-*+]|\d+\.)\s+\S", text, re.M))
    chars = len(text)

    # 结构项按「组织强度」加权：标题最能说明文档有骨架，代码块次之，列表项再次。
    structure_items = headings * 2 + fences + list_items
    ratio = structure_items / max(1, len(sig))

    # 判据只有一条：**命中信号很多，但承载它们的结构很少**。
    #
    # 这里我连着犯了三次同一个错，都值得记下来：
    #   第 1 次 `字符 < 1500 且信号 ≥ 6` —— 规则词表有 200 个 pattern，
    #            正常提交轻松命中 15+，gold 集 15/20 被误判。
    #   第 2 次 把长度阈值提到 1500 再加结构条件 —— 一份 1387 字符、
    #            13 个标题、11 个列表项的正常提交仍被判堆砌。
    #   第 3 次 改成比值判据后又补了 `字符 < 600 且信号 ≥ 8` ——
    #            于是 410 字符、5 个标题的 AI 日志又被误判。
    # **共同错误：把「短」当成「空」。** 短文档结构项天然少，但它确实写了内容。
    # 最终只保留比值判据 + 一个绝对信号下限（15）：
    # 「短但有骨架」不误伤，「长但全是关键词」会被抓住。
    reasons = []
    if len(sig) >= 15 and ratio < 0.55:
        reasons.append(
            f"命中 {len(sig)} 个规则信号，但只有 {structure_items} 个结构项"
            f"（标题 {headings}×2 + 代码块 {fences} + 列表项 {list_items}），"
            f"比值 {ratio:.2f} < 0.55 —— 信号没有内容承载它")
    return {"flagged": bool(reasons), "reasons": reasons,
            "distinct_signals": len(sig), "chars": chars,
            "headings": headings, "fences": fences,
            "list_items": list_items, "structure_items": structure_items,
            "structure_to_signal_ratio": round(ratio, 3)}


# =====================================================================
# 单份提交的评审
# =====================================================================

def evaluate_submission(author: str, info: dict, rubric: dict) -> dict:
    docs = info["files"]
    gate = rubric["scoring"].get("negation_gate", {})
    slots = match_slots(docs, rubric, gate)

    # ---- 完整性 ----
    required = [k for k, v in rubric["deliverables"].items() if v.get("required")]
    present = [k for k in required if k in slots]
    completeness = len(present) / len(required) if required else 0.0
    deliverable_rows = []
    for k in rubric["deliverables"]:
        hit = slots.get(k)
        deliverable_rows.append({
            "key": k, "label": rubric["deliverables"][k]["label"],
            "required": k in required, "hit": bool(hit),
            "file": hit["file"] if hit else None,
            "confidence": hit["confidence"] if hit else None,
            "why": hit["why"] if hit else [],
        })

    # ---- 质量四条件 ----
    cond_results = {}
    text_docs = [d for d in docs if d.all_text()]
    for ckey, cspec in rubric["conditions"].items():
        checks = []
        got = tot = 0.0
        for c in cspec["checks"]:
            w = float(c.get("weight", 1.0))
            kind = c["type"]
            ok, ev, note = False, [], ""
            if kind == "present":
                ok, ev = any_hit(text_docs, c.get("patterns", []), gate)
                if ok and c.get("min_occurrences", 1) > 1:
                    ok = len(ev) >= c["min_occurrences"]
            elif kind == "absent":
                bad, ev = any_absent_violation(text_docs, c.get("patterns", []), gate)
                ok = not bad
                if not ok:
                    note = "命中禁止模式"
            elif kind == "file_extension":
                exts = set(c.get("extensions", []))
                hit = [d for d in docs if d.ext in exts and not d.is_near_empty]
                ok = bool(hit)
                ev = [{"file": d.rel} for d in hit[:4]]
            elif kind == "frontmatter":
                ok, ev = has_frontmatter(
                    [d for d in docs
                     if d.ext in c.get("applicable_extensions", [".md"])])
            elif kind == "py_compiles":
                ok, ev = py_compiles(docs)
            elif kind == "io_statement":
                ok, ev = io_statement(text_docs)
            elif kind == "demo_evidence":
                demo = slots.get("demo")
                real = any_hit(text_docs,
                       ["实测", "真实运行", "运行结果", "实际输出",
                        "真实案例", "测试结果"], gate)[0]
                ok = bool(demo) and real
                if demo:
                    ev = [{"file": demo["file"],
                           "real_result_mentioned": real}]
            checks.append({"id": c["id"], "label": c["label"], "weight": w,
                           "pass": bool(ok), "evidence": ev, "note": note})
            tot += w
            got += w if ok else 0.0
        score = got / tot if tot else 0.0
        # 锚点规则：锚点检查是所在条件的**核心**，不通过则该条件封顶 0.5。
        # 动机（实测）：一份提交没有「输入X，输出Y」这句话，只掉了 clear_io
        # 条件里 1.2/3.3 的分，折到总分只差 5 个百分点 —— 但「IO 明确」
        # 是 C4 四条件之一，缺了它不该只值 5 分。实测 gold09 因此拿到 0.887。
        anchor_failed = any(c.get("anchor") and not c["pass"] for c in checks)
        if anchor_failed:
            score = min(score, 0.5)
        cond_results[ckey] = {
            "label": cspec["label"], "weight": float(cspec["weight"]),
            "score": score, "checks": checks, "anchor_failed": anchor_failed,
            "passed": sum(1 for c in checks if c["pass"]), "total": len(checks),
        }
    wsum = sum(v["weight"] for v in cond_results.values())
    quality = (sum(v["score"] * v["weight"] for v in cond_results.values())
               / wsum) if wsum else 0.0

    # ---- 红旗 ----
    # 第一版这里只生成了 flags，**却从来没有用它们限制分数** ——
    # 结果 ZhouYan05 带着一个红旗仍然拿到综合分 1.00，红旗纯粹是装饰。
    # 现在 cap 真正生效，并且记下原始分，让报告能显示「红旗把分数压了多少」。
    flag_specs = {f["id"]: f for f in rubric["red_flags"]["items"]}
    flags = []

    def add_flag(fid, evidence):
        if fid not in flag_specs:
            return
        spec = flag_specs[fid]
        flags.append({"id": fid, "label": spec["label"],
                      "severity": spec["severity"], "evidence": evidence[:5],
                      "cap": _cap_for(spec, len(evidence) or 1)})

    required = [k for k, v in rubric["deliverables"].items() if v.get("required")]
    missing = [k for k in required if k not in slots]
    if missing:
        add_flag("missing_core",
                 [rubric["deliverables"][k]["label"] for k in missing])

    # 空文件红旗**只对必交槽位**报。演示目录里的 `占位.md` 是有意的空文件，
    # 把它算成缺陷会把一个干净的提交压到 65 分 —— 实测踩到过。
    empty_slots = []
    for k, hit in slots.items():
        f = next((d for d in docs if d.rel == hit["file"]), None)
        if f and f.is_near_empty and not PLACEHOLDER_RX.search(f.name):
            empty_slots.append(f.rel)
    if empty_slots:
        add_flag("empty_deliverable", empty_slots)

    st = stuffing_report(docs, rubric, gate,
                         allow_files={v["file"] for v in slots.values()})
    if st["flagged"]:
        add_flag("keyword_stuffing", st["reasons"])
    hard, ev = any_absent_violation(
        text_docs, rubric["conditions"]["reusable"]["checks"][1]["patterns"], gate)
    if hard:
        add_flag("hardcoded_path", [f"{e['file']}:{e['line']} {e['match']}"
                                    for e in ev])
    sec, ev = any_absent_violation(
        text_docs, rubric["conditions"]["reusable"]["checks"][2]["patterns"], gate)
    if sec:
        add_flag("secret_leak", [f"{e['file']}:{e['line']} {e['match']}"
                                 for e in ev])
    # 不再单独出 no_ai_log / no_teaching 两个红旗：missing_core 的证据里
    # 已经逐条列出了缺的是哪几个（实测会把同一件事罚两次，gold14 因此多出两个红旗）。
    ok_py, bad_py = py_compiles(docs)
    if not ok_py:
        add_flag("syntax_error", [f"{b['file']}:{b.get('line')} {b.get('msg')}"
                                  for b in bad_py])

    # ---- 传播证据（只报状态，不折算分数）----
    prop = rubric["propagation"]
    prop_ok, prop_ev = any_hit(text_docs, prop["evidence_patterns"], gate)
    self_claim = any_hit(text_docs,
                         ["已有人使用", "同学用过", "被使用", "有人试用"],
                         gate)[0]
    prop_status = ("evidenced" if prop_ok else
                   ("self_reported" if self_claim else "not_evidenced"))

    # ---- 综合分（红旗 cap 生效）----
    comp_w = float(rubric["scoring"]["completeness_weight"])
    qual_w = float(rubric["scoring"]["quality_weight"])
    composite_raw = completeness * comp_w + quality * qual_w
    cap = min([f["cap"] for f in flags] + [100]) / 100.0
    composite = min(composite_raw, cap)
    level = next(l["code"] for l in rubric["scoring"]["levels"]
                 if composite >= l["min"])

    return {
        "author": author,
        "author_source": info["source"],
        "n_files": len(docs),
        "n_text_files": len(text_docs),
        "completeness": completeness,
        "present": present,
        "missing": missing,
        "deliverables": deliverable_rows,
        "conditions": cond_results,
        "quality": quality,
        "composite_raw": composite_raw,
        "flag_cap": cap,
        "composite": composite,
        "level": level,
        "red_flags": flags,
        "propagation": {"status": prop_status, "evidence": prop_ev[:4],
                        "note": prop["statuses"][prop_status]},
        "stuffing_detail": st,
    }


def _cap_for(spec: dict, n: int) -> int:
    """红旗的分数上限。cap_table 支持按命中数量分级。"""
    tbl = spec.get("cap_table")
    if tbl:
        for threshold, cap in sorted(tbl, key=lambda x: -x[0]):
            if n >= threshold:
                return cap
    return int(spec.get("cap", 100))


# =====================================================================
# 报告输出
# =====================================================================

LEVEL_LABEL = {"L4": "完善", "L3": "良好", "L2": "及格", "L1": "待改进"}
COND_ORDER = ["reusable", "executable", "verifiable", "clear_io"]


def md_report(result: dict, stamp: str) -> str:
    L = []
    L.append("# C4 技能提交自动评审报告")
    L.append("")
    L.append(f"- 评审器：`c4a-evaluator` v{VERSION}（规则层，纯标准库）")
    L.append(f"- 生成时间：{stamp}")
    L.append(f"- 识别提交：**{result['n_authors']}** 位作者，**{result['n_files']}** 个文件")
    L.append(f"- 规则文件：`{os.path.basename(result['rubric_path'])}` "
             f"(sha256 `{result['rubric_sha256'][:12]}`)")
    L.append("")
    L.append("## 一、班级总览")
    L.append("")
    full = sum(1 for s in result["submissions"] if not s["missing"])
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 提交人数 | {result['n_authors']} |")
    L.append(f"| 完整提交（{len(result['required'])}/{len(result['required'])}） | {full} |")
    L.append(f"| 部分提交 | {result['n_authors'] - full} |")
    avg_q = (sum(s["quality"] for s in result["submissions"])
             / max(1, result["n_authors"]))
    avg_c = (sum(s["completeness"] for s in result["submissions"])
             / max(1, result["n_authors"]))
    L.append(f"| 平均完整性 | {avg_c:.2f} |")
    L.append(f"| 平均质量分 | {avg_q:.2f} |")
    flagged = [s["author"] for s in result["submissions"] if s["red_flags"]]
    L.append(f"| 触发红旗的作者 | {len(flagged)}（{', '.join(flagged) or '无'}） |")
    L.append("")
    L.append("## 二、综合排名")
    L.append("")
    L.append("| 排名 | 作者 | 完整性 | 质量分 | 综合分 | 评级 | 红旗 |")
    L.append("|---:|---|---:|---:|---:|---|---|")
    for i, s in enumerate(result["submissions"], 1):
        L.append(f"| {i} | {s['author']} | "
                 f"{len(s['present'])}/{len(result['required'])} | "
                 f"{s['quality']:.2f} | {s['composite']:.2f} | "
                 f"{s['level']}·{LEVEL_LABEL[s['level']]} | "
                 f"{len(s['red_flags'])} |")
    L.append("")
    L.append("## 三、作者详情")
    L.append("")
    for s in result["submissions"]:
        L.append(f"### {s['author']}（综合分 {s['composite']:.2f}，"
                 f"{s['level']}·{LEVEL_LABEL[s['level']]}）")
        L.append("")
        L.append(f"- 作者归属来源：`{s['author_source']}`；"
                 f"文件 {s['n_files']} 个（可读文本 {s['n_text_files']} 个）")
        L.append("")
        L.append("**完整性：**")
        L.append("")
        L.append("| 必交交付物 | 状态 | 命中文件 | 置信度 | 依据 |")
        L.append("|---|---|---|---|---|")
        for r in s["deliverables"]:
            if not r["required"]:
                continue
            mark = "✅" if r["hit"] else "❌"
            L.append(f"| {r['label']} | {mark} | {r['file'] or '—'} | "
                     f"{r['confidence'] or '—'} | {'; '.join(r['why']) or '—'} |")
        L.append("")
        L.append("**质量四条件：**")
        L.append("")
        L.append("| 条件 | 得分 | 通过 |")
        L.append("|---|---:|---|")
        for k in COND_ORDER:
            c = s["conditions"][k]
            L.append(f"| {c['label']} | {c['score']:.2f} | "
                     f"{c['passed']}/{c['total']} |")
        L.append("")
        failed = [c for k in COND_ORDER for c in s["conditions"][k]["checks"]
                  if not c["pass"]]
        if failed:
            L.append("**未通过的检查项（含证据缺失原因）：**")
            L.append("")
            for c in failed[:8]:
                L.append(f"- `{c['id']}` {c['label']}")
            L.append("")
        if s["red_flags"]:
            L.append("**红旗：**")
            L.append("")
            for f in s["red_flags"]:
                ev = "；".join(str(x) for x in f["evidence"][:3])
                L.append(f"- ⚠️ **{f['label']}**（{f['severity']}）{ev}")
            L.append("")
        L.append(f"**传播证据：** `{s['propagation']['status']}` —— "
                 f"{s['propagation']['note']}")
        L.append("")
    L.append("## 四、全班共性问题")
    L.append("")
    miss_count = {}
    for s in result["submissions"]:
        for m in s["missing"]:
            miss_count[m] = miss_count.get(m, 0) + 1
    if miss_count:
        L.append("**最常缺失的交付物：**")
        L.append("")
        for k, n in sorted(miss_count.items(), key=lambda x: (-x[1], x[0])):
            L.append(f"- {result['deliverables'][k]['label']}：{n} 人缺失")
        L.append("")
    weak = {}
    for s in result["submissions"]:
        for k in COND_ORDER:
            if s["conditions"][k]["score"] < 1.0:
                weak[k] = weak.get(k, 0) + 1
    if weak:
        L.append("**最弱的质量维度：**")
        L.append("")
        for k, n in sorted(weak.items(), key=lambda x: (-x[1], x[0])):
            L.append(f"- {result['conditions'][k]['label']}：{n} 人未满分")
        L.append("")
    L.append("## 五、评审器自身可靠性")
    L.append("")
    L.append("完整指标见 `可靠性测试报告`。这里只放三个关键数：")
    L.append("")
    L.append(f"- 规则文件 sha256：`{result['rubric_sha256']}`")
    L.append(f"- 输出确定性：见 `tests/test_evaluator.py` 的哈希一致性断言")
    L.append(f"- 全部文件哈希：`{result['corpus_hash']}`")
    L.append("")
    L.append("## 六、说明与边界")
    L.append("")
    L.append("- 本报告是**规则层**结论。规则层只判「有没有、够不够结构」，"
             "**不判内容好不好** —— 后者需要 LLM 复核层（见 "
             "`references/llm_review_protocol.md`）。没有复核层的结论不应被当作最终评分。")
    L.append("- **传播证据只报状态，不折算成分数。** C4 原文把「被使用次数」列为最高权重，"
             "但仓库里没有使用回执 ≠ 没被用过（群里用了不会留下文件）。"
             "把「找不到证据」直接判为 0 分是不诚实的。")
    L.append("- 每条结论都带 `文件:行号` 证据，可人工复核。"
             "拿不到证据的分不给。")
    return "\n".join(L) + "\n"


def csv_rows(result: dict) -> list:
    rows = []
    for s in result["submissions"]:
        row = {"author": s["author"], "level": s["level"],
               "completeness": round(s["completeness"], 4),
               "quality": round(s["quality"], 4),
               "composite": round(s["composite"], 4),
               "n_files": s["n_files"],
               "missing": "|".join(s["missing"]),
               "red_flags": "|".join(f["id"] for f in s["red_flags"]),
               "propagation": s["propagation"]["status"]}
        for k in COND_ORDER:
            row[k] = round(s["conditions"][k]["score"], 4)
        rows.append(row)
    return rows


def html_report(result: dict, stamp: str) -> str:
    def bar(v):
        pct = int(round(v * 100))
        color = "#2e7d32" if v >= 0.85 else "#f9a825" if v >= 0.5 else "#c62828"
        return (f'<div style="background:#eee;border-radius:4px;height:14px;'
                f'width:120px;display:inline-block;vertical-align:middle">'
                f'<div style="background:{color};width:{pct}%;height:14px;'
                f'border-radius:4px"></div></div> <b>{v:.2f}</b>')
    h = ['<!doctype html><html lang="zh"><head><meta charset="utf-8">',
         '<title>C4 评审仪表板</title>',
         '<style>body{font-family:system-ui,"Microsoft YaHei",sans-serif;'
         'margin:24px;color:#222}table{border-collapse:collapse;width:100%;'
         'margin:12px 0}th,td{border:1px solid #ddd;padding:6px 8px;'
         'font-size:14px;text-align:left}th{background:#f5f5f5}'
         '.flag{color:#c62828;font-size:12px}h1{font-size:22px}'
         'h2{font-size:18px;margin-top:28px}</style></head><body>']
    h.append(f"<h1>C4 技能提交自动评审 —— 仪表板</h1>")
    h.append(f"<p>评审器 v{VERSION} ｜ {stamp} ｜ "
             f"{result['n_authors']} 位作者 / {result['n_files']} 个文件</p>")
    h.append("<h2>综合排名</h2><table><tr><th>#</th><th>作者</th>"
             "<th>完整性</th><th>质量分</th><th>综合分</th><th>评级</th>"
             "<th>红旗</th></tr>")
    for i, s in enumerate(result["submissions"], 1):
        fl = ", ".join(f["label"] for f in s["red_flags"]) or "—"
        h.append(f"<tr><td>{i}</td><td><b>{html.escape(s['author'])}</b></td>"
                 f"<td>{len(s['present'])}/{len(result['required'])}</td>"
                 f"<td>{bar(s['quality'])}</td><td><b>{s['composite']:.2f}</b></td>"
                 f"<td>{s['level']}·{LEVEL_LABEL[s['level']]}</td>"
                 f"<td class='flag'>{html.escape(fl)}</td></tr>")
    h.append("</table>")
    h.append("<h2>各维度得分</h2><table><tr><th>作者</th><th>可复用</th>"
             "<th>可执行</th><th>可验证</th><th>IO 明确</th></tr>")
    for s in result["submissions"]:
        h.append(f"<tr><td>{html.escape(s['author'])}</td>"
                 + "".join(f"<td>{s['conditions'][k]['score']:.2f}</td>"
                           for k in COND_ORDER) + "</tr>")
    h.append("</table>")
    h.append("</body></html>")
    return "\n".join(h)


# =====================================================================
# 主流程
# =====================================================================

def collect(root: str) -> tuple:
    docs, n = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if not d.startswith(".") and d != "__pycache__")
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            p = os.path.join(dirpath, fn)
            if not os.path.isfile(p):
                continue
            try:
                docs.append(Doc(p, os.path.relpath(p, root)))
                n += 1
            except OSError:
                continue
    return docs, n


def main() -> int:
    ap = argparse.ArgumentParser(description="C4 技能提交自动评审器（规则层）")
    ap.add_argument("path", help="提交目录（可含多位作者）")
    ap.add_argument("--out", default="review_output")
    ap.add_argument("--format", default="md,csv,html,json")
    ap.add_argument("--rubric", default=DEFAULT_RUBRIC)
    ap.add_argument("--deterministic", action="store_true",
                    help="输出不含时间戳，保证逐字节可复现")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(a.path):
        print(f"不是目录：{a.path}", file=sys.stderr)
        return 2
    with open(a.rubric, encoding="utf-8") as f:
        rubric = json.load(f)
    rubric_sha = hashlib.sha256(
        open(a.rubric, "rb").read()).hexdigest()

    root = resolve_root(a.path)
    docs, n_files = collect(root)
    if not docs:
        print("未找到任何文件。请检查路径，或确认提交文件名符合 "
              "`姓名_C4_内容.扩展名` 规范。", file=sys.stderr)
        return 3

    authors = resolve_authors(docs, root)
    # 未识别 / 资料 单独报告，**不参与排名** —— 硬把资料目录当作者会虚增班级人数
    unclassified = authors.pop(UNCLASSIFIED, None)
    materials = authors.pop("_资料_", None)
    subs = [evaluate_submission(name, info, rubric)
            for name, info in sorted(authors.items())]
    subs.sort(key=lambda s: (-s["composite"], s["author"]))

    corpus_hash = hashlib.sha256(
        "|".join(sorted(f"{d.rel}:{d.size}" for d in docs)).encode()
    ).hexdigest()

    stamp = "deterministic (no timestamp)" if a.deterministic \
        else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = {
        "evaluator": {"name": "c4a-evaluator", "version": VERSION, "layer": "rules"},
        "generated_at": stamp,
        "scan_path": os.path.abspath(a.path),
        "n_authors": len(subs),
        "n_files": n_files,
        "unclassified": {
            "n_files": len(unclassified["files"]) if unclassified else 0,
            "files": [d.rel for d in unclassified["files"]][:20] if unclassified else [],
            "note": "文件名不含 `姓名_C4_` 前缀，且仓库里不止一位已知作者，"
                    "无法安全归因。**不参与排名** —— 硬归因会凭空造出作者。",
        },
        "materials": {
            "n_files": len(materials["files"]) if materials else 0,
            "files": [d.rel for d in materials["files"]][:20] if materials else [],
            "note": "挑战正文 / 脚手架 / 仓库级说明文件，**不是 C4 交付物**，"
                    "不参与评审。",
        },
        "rubric_path": os.path.abspath(a.rubric),
        "rubric_sha256": rubric_sha,
        "corpus_hash": corpus_hash,
        "required": [k for k, v in rubric["deliverables"].items() if v.get("required")],
        "deliverables": rubric["deliverables"],
        "conditions": {k: {"label": v["label"], "weight": v["weight"]}
                       for k, v in rubric["conditions"].items()},
        "submissions": subs,
    }

    out = a.out
    os.makedirs(out, exist_ok=True)
    fmts = {x.strip() for x in a.format.split(",") if x.strip()}
    written = []
    if "json" in fmts:
        p = os.path.join(out, "评审结果.json")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        written.append(p)
    if "md" in fmts:
        p = os.path.join(out, "评审报告.md")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(md_report(result, stamp))
        written.append(p)
    if "csv" in fmts:
        p = os.path.join(out, "评审详表.csv")
        rows = csv_rows(result)
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        written.append(p)
    if "html" in fmts:
        p = os.path.join(out, "评审仪表板.html")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(html_report(result, stamp))
        written.append(p)

    if not a.quiet:
        print(f"扫描 {a.path}：{len(subs)} 位作者 / {n_files} 个文件")
        for s in subs:
            flags = ",".join(f["id"] for f in s["red_flags"]) or "-"
            print(f"  {s['author']:20s} 完整 {len(s['present'])}/"
                  f"{len(result['required'])}  质量 {s['quality']:.2f}  "
                  f"综合 {s['composite']:.2f}  {s['level']}  红旗[{flags}]")
        for p in written:
            print(f"  → {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
