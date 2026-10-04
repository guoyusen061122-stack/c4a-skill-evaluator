#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aar_report.py — 复盘 / AAR（After Action Review）报告生成器

一句话说明：
    输入一份结构化的复盘记录（JSON 或「标签: 值」纯文本），
    输出一份结构完整的 Markdown AAR 复盘报告，并附带「复盘深度自检」。

特性：
    * 零第三方依赖（仅用 Python 标准库），开箱即用；
    * 支持两种输入：JSON 文件 或 「标签: 值」纯文本文件；
    * 自动生成「复盘四问」「保持/改进/开始/停止」「根因」「行动计划」等章节；
    * 输出「复盘深度自检」，帮你判断这次复盘是否深入（目标/过程/结果/根因/教训/行动）；
    * 提供 --template / --sample，降低上手门槛。

用法：
    python aar_report.py 复盘记录.json            # 生成报告（打印到终端）
    python aar_report.py 复盘记录.json -o 报告.md  # 生成报告并写入文件
    python aar_report.py --template              # 输出空白 JSON 模板
    python aar_report.py --template -o 模板.json  # 将模板写入文件
    python aar_report.py --sample                # 使用内置示例运行一次
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

__version__ = "1.0.0"


def _force_utf8():
    """让 stdout/stderr 使用 UTF-8，避免 Windows 控制台 GBK 编码报错。"""
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


_force_utf8()

# 可出现在输入里的字段及其中文标签（用于纯文本解析）
LIST_FIELDS = ("keep", "improve", "start", "stop", "root_causes", "lessons", "action_items")
STR_FIELDS = ("title", "date", "objective", "what_happened", "result")

FIELD_LABELS = {
    "title": "标题",
    "date": "日期",
    "objective": "目标",
    "what_happened": "过程",
    "result": "结果",
    "keep": "做对了",
    "improve": "需改进",
    "start": "要开始",
    "stop": "要停止",
    "root_causes": "根因",
    "lessons": "经验教训",
    "action_items": "行动计划",
}

# 兼容英文标签
FIELD_ALIASES = {
    "title": ("标题", "title", "主题"),
    "date": ("日期", "date"),
    "objective": ("目标", "objective", "预期目标", "预期"),
    "what_happened": ("过程", "what_happened", "实际过程", "发生了什么"),
    "result": ("结果", "result", "成果"),
    "keep": ("做对了", "keep", "保持"),
    "improve": ("需改进", "improve", "改进"),
    "start": ("要开始", "start", "开始"),
    "stop": ("要停止", "stop", "停止"),
    "root_causes": ("根因", "root_causes", "根因分析"),
    "lessons": ("经验教训", "lessons", "教训", "心得"),
    "action_items": ("行动计划", "action_items", "行动项", "行动"),
}


# --------------------------------------------------------------------------- #
# 输入解析
# --------------------------------------------------------------------------- #
def load_json(path: Path) -> dict:
    """读取 JSON 文件并返回 dict。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象（{}），例如 {\"title\": \"...\"}")
    return data


def load_text(path: Path) -> dict:
    """解析「标签: 值」纯文本，列表项用 '- ' 或 '* ' 开头。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    data: dict = {}
    current = None  # 当前正在填充的列表字段

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # 列表项（以 - 或 * 开头），追加到当前列表字段
        if line.startswith(("-", "*", "•")) and current:
            item = line.lstrip("-*• ").strip()
            if item:
                if current == "action_items":
                    data.setdefault(current, []).append(_parse_action(item))
                else:
                    data.setdefault(current, []).append(item)
            continue

        # 「标签: 值」行
        if ":" in line or "：" in line:
            parts = re.split(r"[:：]", line, maxsplit=1)
            key = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ""
            field = _resolve_field(key)
            if field is None:
                continue  # 忽略无法识别的标签
            if field in STR_FIELDS:
                data[field] = value
                current = None
            elif field in LIST_FIELDS:
                current = field
                if value:  # 标签行自身也可能带一个值
                    data.setdefault(field, []).append(value)
                else:
                    data.setdefault(field, [])
            continue

        # 无标签的连续文本行 → 追加到当前列表字段（容错）
        if current:
            data.setdefault(current, []).append(line)

    return data


def _resolve_field(label: str):
    """把中文/英文标签解析成标准字段名，失败返回 None。"""
    label_l = label.lower().strip()
    for field, aliases in FIELD_ALIASES.items():
        if label_l in [a.lower() for a in aliases]:
            return field
    return None


def _parse_action(text: str) -> dict:
    """把「行动 | 负责人 | 截止时间 | 优先级」解析成结构化行动项。"""
    parts = [p.strip() for p in text.split("|")]
    return {
        "action": parts[0] if parts[0] else "（未填写）",
        "owner": parts[1] if len(parts) > 1 and parts[1] else "我",
        "deadline": parts[2] if len(parts) > 2 and parts[2] else "—",
        "priority": parts[3] if len(parts) > 3 and parts[3] else "中",
    }


def load_input(path: str) -> dict:
    """按内容自动选择 JSON 或纯文本解析。"""
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"找不到输入文件：{path}")
    raw = p.read_text(encoding="utf-8", errors="replace").lstrip()
    if raw.startswith("{"):
        return load_json(p)
    return load_text(p)


# --------------------------------------------------------------------------- #
# 复盘深度自检
# --------------------------------------------------------------------------- #
def depth_check(data: dict) -> dict:
    """评估一次复盘的完整度，返回每个维度的 (评级, 说明)。"""
    def has(key):
        v = data.get(key)
        return isinstance(v, str) and len(v.strip()) >= 10

    checks = {}

    checks["目标明确"] = (has("objective"), "是否写清了「预期是什么」")
    checks["过程记录"] = (has("what_happened"), "是否记录了「实际发生了什么」")
    checks["结果量化"] = (has("result"), "是否有结果描述（有量化指标更佳）")
    checks["根因分析"] = (bool(data.get("root_causes")), "是否追问了「为什么有差距」")
    checks["经验提炼"] = (bool(data.get("lessons")), "是否沉淀了可复制的教训")
    checks["行动落地"] = (
        bool(data.get("action_items")) and all(
            isinstance(a, dict) and a.get("action") for a in data["action_items"]
        ),
        "是否有带负责人/截止时间的行动项",
    )
    return checks


def _rate(ok: bool) -> str:
    return "✅" if ok else "❌"


# --------------------------------------------------------------------------- #
# 报告渲染
# --------------------------------------------------------------------------- #
def render(data: dict) -> str:
    title = (data.get("title") or "未命名复盘").strip()
    d = data.get("date") or date.today().isoformat()
    objective = (data.get("objective") or "（未填写）").strip()
    what_happened = (data.get("what_happened") or "（未填写）").strip()
    result = (data.get("result") or "（未填写）").strip()

    keep = data.get("keep") or []
    improve = data.get("improve") or []
    start = data.get("start") or []
    stop = data.get("stop") or []
    root_causes = data.get("root_causes") or []
    lessons = data.get("lessons") or []
    metrics = data.get("metrics") or []
    actions = data.get("action_items") or []

    lines = []
    add = lines.append

    add(f"# AAR 复盘报告：{title}")
    add("")
    add(f"> 复盘日期：{d} ｜ 生成工具：aar-report-generator v{__version__}")
    add("")

    add("## 一、背景与目标（预期是什么）")
    add(objective)
    add("")

    add("## 二、实际过程（实际发生了什么）")
    add(what_happened)
    add("")

    add("## 三、结果与差距")
    add(result)
    add("")
    if metrics:
        add("| 指标 | 数值 |")
        add("|------|------|")
        for m in metrics:
            if isinstance(m, dict):
                add(f"| {m.get('name', '—')} | {m.get('value', '—')} |")
            else:
                add(f"| {m} | — |")
        add("")

    add("## 四、复盘四问")
    add("")
    add("| 问题 | 回答 |")
    add("|------|------|")
    add(f"| 1. 预期是什么？ | {_ellipsis(objective)} |")
    add(f"| 2. 实际发生了什么？ | {_ellipsis(what_happened)} |")
    add(f"| 3. 为什么有差距？ | {_ellipsis('；'.join(root_causes) if root_causes else '（未分析）')} |")
    add(f"| 4. 下次怎么做？ | {_ellipsis('；'.join(_action_texts(actions)) if actions else '（未给出）')} |")
    add("")

    add("## 五、保持 · 改进 · 开始 · 停止")
    add("")
    add("| 保持 Keep | 改进 Improve |")
    add("|-----------|-------------|")
    for i in range(max(len(keep), len(improve), 1)):
        k = keep[i] if i < len(keep) else ""
        im = improve[i] if i < len(improve) else ""
        add(f"| {_cell(k)} | {_cell(im)} |")
    add("")
    add("| 开始 Start | 停止 Stop |")
    add("|------------|-----------|")
    for i in range(max(len(start), len(stop), 1)):
        s = start[i] if i < len(start) else ""
        st = stop[i] if i < len(stop) else ""
        add(f"| {_cell(s)} | {_cell(st)} |")
    add("")

    add("## 六、根因分析（5 Why 追问）")
    add("")
    if root_causes:
        for rc in root_causes:
            add(f"- {rc}")
    else:
        add("- （未填写根因，建议追问至少 3 层「为什么」）")
    add("")

    add("## 七、经验教训（可复制的洞察）")
    add("")
    if lessons:
        for l in lessons:
            add(f"- {l}")
    else:
        add("- （未提炼教训）")
    add("")

    add("## 八、行动计划（SMART）")
    add("")
    if actions:
        add("| 优先级 | 行动 | 负责人 | 截止时间 |")
        add("|--------|------|--------|----------|")
        order = {"高": 0, "中": 1, "低": 2}
        for a in sorted(actions, key=lambda x: order.get(str(x.get("priority", "中")), 1) if isinstance(x, dict) else 1):
            if isinstance(a, dict):
                add(
                    f"| {a.get('priority', '中')} | {_cell(a.get('action', ''))} "
                    f"| {_cell(a.get('owner', '我'))} | {a.get('deadline', '—')} |"
                )
            else:
                add(f"| 中 | {_cell(str(a))} | 我 | — |")
    else:
        add("- （未填写行动项）")
    add("")

    add("## 九、一句话总结")
    add("")
    add(_one_liner(data))
    add("")

    # —— 复盘深度自检 ——
    add("---")
    add("")
    add("## 复盘深度自检（自动生成）")
    add("")
    checks = depth_check(data)
    add("| 维度 | 评级 | 说明 |")
    add("|------|------|------|")
    ok_count = 0
    for name, (ok, desc) in checks.items():
        if ok:
            ok_count += 1
        add(f"| {name} | {_rate(ok)} | {desc} |")
    add("")
    total = len(checks)
    add(f"**深度得分：{ok_count} / {total}**")
    if ok_count == total:
        add("")
        add("✅ 这次复盘覆盖了完整闭环（目标→过程→结果→根因→教训→行动），可以直接用于下次行动。")
    elif ok_count >= total - 2:
        add("")
        add("⚠️ 复盘基本完整，但仍有缺口：补齐缺失维度会让复盘更有价值。")
    else:
        add("")
        add("❌ 复盘信息不足，建议补充目标、结果、根因与行动项后再输出。")
    add("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _cell(s: str) -> str:
    """转义 Markdown 表格里的竖线，避免破坏表格。"""
    return str(s).replace("|", "\\|").replace("\n", " ").strip() or "—"


def _ellipsis(s: str, limit: int = 60) -> str:
    s = str(s).replace("\n", " ").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _action_texts(actions):
    out = []
    for a in actions:
        if isinstance(a, dict) and a.get("action"):
            out.append(a["action"])
        elif isinstance(a, str):
            out.append(a)
    return out


def _one_liner(data: dict) -> str:
    """自动生成一句话总结。"""
    title = (data.get("title") or "本次经历").strip()
    lessons = data.get("lessons") or []
    actions = _action_texts(data.get("action_items") or [])
    parts = [f"「{title}」的复盘结论是"]
    if lessons:
        parts.append(f"关键教训：{'；'.join(lessons[:2])}")
    if actions:
        parts.append(f"下一步：{'；'.join(actions[:2])}")
    return "，".join(parts) + "。"


# --------------------------------------------------------------------------- #
# 模板 & 示例
# --------------------------------------------------------------------------- #
TEMPLATE = {
    "title": "在这里填写复盘主题",
    "date": date.today().isoformat(),
    "objective": "预期目标是什么？你希望在这次经历里达成什么？",
    "what_happened": "实际发生了什么？按时间顺序或关键节点描述过程。",
    "result": "最终结果如何？与预期相比差在哪、好在哪？",
    "metrics": [
        {"name": "关键指标1", "value": "数值"},
        {"name": "关键指标2", "value": "数值"},
    ],
    "keep": ["做对了、要继续保留的做法"],
    "improve": ["做得不够好、需要改进的地方"],
    "start": ["之前没做、下次要开始做的事"],
    "stop": ["做了但没用、下次要停止的事"],
    "root_causes": ["导致差距的根本原因（追问为什么）"],
    "lessons": ["沉淀下来、可以复用的经验教训"],
    "action_items": [
        {"action": "具体可执行的下一步", "owner": "我", "deadline": "YYYY-MM-DD", "priority": "高"}
    ],
}

SAMPLE = {
    "title": "第一次在群里分享自研技能",
    "date": "2026-01-15",
    "objective": "把我的「复盘报告生成器」技能教会 10 个同学，并让至少 5 个人真正用起来。",
    "what_happened": (
        "我先在群里发了一条技能介绍和安装说明，附上了一个示例。当天有 3 个同学回复说装好了，"
        "但第二天只有 1 个人反馈真正跑通了。我私聊了那些说「看不懂」的同学，发现大家卡在"
        "「JSON 输入不会写」这一步。于是我补了一个纯文本模板和一张截图，重新发了一遍。"
    ),
    "result": "最终有 6 个同学成功跑通并输出了自己的复盘报告，达成了「5 人使用」的目标，但没有达到「10 人学会」。",
    "metrics": [
        {"name": "回复人数", "value": "11"},
        {"name": "成功使用人数", "value": "6"},
        {"name": "目标使用人数", "value": "5（超额 1 人）"},
    ],
    "keep": ["附上一个可直接跑的示例，极大降低了上手门槛", "对「看不懂」的人主动私聊跟进"],
    "improve": ["第一版说明太依赖 JSON，没照顾非技术同学", "发布前没有找人试读一遍说明"],
    "start": ["发布前先找 1 个同学试跑一次", "为每个常见报错写一句「怎么办」"],
    "stop": ["一次性发大段文字，导致大家没有耐心读完"],
    "root_causes": [
        "高估了大家对 JSON 的熟悉程度（为什么？因为我是用代码的习惯去写说明）",
        "没有做「冷启动测试」——让一个完全陌生的人按说明操作（为什么？因为我默认大家和自己一样）",
    ],
    "lessons": [
        "截图和「先跑通再优化」比大段文字更有效",
        "发布前做一次「陌生人测试」，能提前发现 80% 的卡点",
        "「被使用」比「写得漂亮」更重要，简单可用 > 复杂完整",
    ],
    "action_items": [
        {"action": "把说明改成「纯文本模板 + 截图」双入口", "owner": "我", "deadline": "2026-01-18", "priority": "高"},
        {"action": "找 1 个非技术同学做冷启动测试并记录卡点", "owner": "我", "deadline": "2026-01-20", "priority": "高"},
        {"action": "发布 v2 并收集反馈", "owner": "我", "deadline": "2026-01-22", "priority": "中"},
    ],
}


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="复盘 / AAR 报告生成器：输入结构化复盘记录，输出 Markdown 复盘报告。",
        epilog="示例：python aar_report.py 复盘.json -o 复盘.md",
    )
    parser.add_argument("input", nargs="?", help="输入文件（.json 或「标签: 值」纯文本）")
    parser.add_argument("-o", "--output", help="输出 Markdown 文件路径（缺省打印到终端）")
    parser.add_argument("--template", action="store_true", help="输出空白 JSON 模板")
    parser.add_argument("--sample", action="store_true", help="使用内置示例运行一次")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        if args.template:
            report = json.dumps(TEMPLATE, ensure_ascii=False, indent=2)
            _emit(report + "\n", args.output)
            return 0

        if args.sample:
            data = SAMPLE
        elif args.input:
            data = load_input(args.input)
        else:
            parser.print_help(sys.stderr)
            return 1

        report = render(data)
        _emit(report, args.output)
        return 0

    except (FileNotFoundError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        print("提示：可用 `--template` 生成空白模板，或用 `--sample` 查看示例。", file=sys.stderr)
        return 1


def _emit(text: str, output):
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"✅ 报告已写入：{output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    raise SystemExit(main())
