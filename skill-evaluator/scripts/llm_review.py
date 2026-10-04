#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 复核层适配器（OpenAI 兼容端点）。

    ⚠️ 本脚本**没有运行过**。仓库里没有任何来自真实 LLM 的复核结果。⚠️

为什么交付一个没跑过的脚本
--------------------------
规则层判"有没有、够不够结构"，判不了"这份技能好不好用"。所以协议里设计了
第二层。但本环境**没有任何模型 API 凭据**，所以这一层从未真正执行。

把它删掉会让"没做"看起来像"不需要做"。留下来并在最前面写明"未运行"，
才是诚实的处理。这与 C2G 提交里 `run_llm.py` 的处理一致。

三条协议硬规则（详见 references/llm_review_protocol.md）
------------------------------------------------------
1. LLM 只能在规则层基础上做 **±0.15 的有界调整**（规则层可复现，LLM 不可复现；
   允许推翻它，整个评审器的可复现性就没了）；
2. 每次调整必须附 `文件:行号` 证据，且必须回答"规则层为什么错了"；
3. 分歧 ≥0.10 时单独记录，**不静默平均**。

无凭据时**明确报错退出**，不返回伪造的空结果 ——
"没跑"和"跑了但没发现"必须在输出上可区分。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAND = 0.15

PROMPT = """你是 C4「技能分享与传播」提交的复核评审员。规则层已经给出了一份机械评分，
你的任务是**在规则层的基础上做有界修正**，而不是重新打分。

【规则层结论】
作者：{author}
完整性：{completeness:.2f}    缺失：{missing}
四条件得分：{conds}
规则层未通过的检查项：{failed}
规则层红旗：{flags}

【提交内容摘录】
{excerpt}

【任务】
只在你能指出**规则层判断错误的具体位置**时才调整分数，调整幅度不超过 ±0.15。
对每一条调整，必须给出：
  - dimension（四个条件之一：reusable / executable / verifiable / clear_io）
  - delta（-0.15 ~ +0.15）
  - evidence（文件名:行号 + 原文片段）
  - rule_layer_was_wrong_because（规则层为什么错了）

如果规则层没有明显误判，就返回空数组 —— 不要为了显得「我干了活」而强行找问题。

另外回答两个规则层答不了的问题：
  1. summary：这份技能解决了它声称要解决的问题吗？（一句话）
  2. top_suggestion：如果只能提一条改进建议，是哪一条？

只输出 JSON，不要别的文字。格式：
{{"adjustments": [...], "summary": "...", "top_suggestion": "...",
  "confidence": "high|medium|low"}}
"""


def call(prompt: str, model: str) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not key:
        raise SystemExit(
            "未设置 OPENAI_API_KEY —— LLM 复核层需要真实模型凭据。\n"
            "本仓库的**规则层完全不需要**这个变量，也不联网。\n"
            "（这是本脚本「未运行」的原因，不是配置问题。）")
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps({"model": model, "temperature": 0,
                         "messages": [{"role": "user", "content": prompt}]}
                        ).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"模型接口报错 HTTP {e.code}: {e.read()[:300]!r}")
    return d["choices"][0]["message"]["content"]


def excerpt(path: Path, limit: int = 6000) -> str:
    """把提交里的文本文件拼一段摘录给模型看。"""
    buf = []
    for p in sorted(path.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".md", ".txt", ".py"):
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        buf.append(f"===== {p.name} =====\n{t}")
        if sum(len(x) for x in buf) > limit:
            break
    return "\n\n".join(buf)[:limit]


def merge(rule: dict, llm: dict) -> dict:
    """按协议合并：有界调整 + 红旗上限最后套。"""
    adj = llm.get("adjustments") or []
    conf = llm.get("confidence", "medium")
    w = {"high": 1.0, "medium": 0.75, "low": 0.5}.get(conf, 0.75)
    conds = {k: v["score"] for k, v in rule["conditions"].items()}
    disagreements, missing_evidence = [], []
    for a in adj:
        dim = a.get("dimension")
        if dim not in conds:
            continue
        if not a.get("evidence") or not a.get("rule_layer_was_wrong_because"):
            # 规则 2：没有证据或答不出"规则层为什么错"的调整一律丢弃
            missing_evidence.append(a)
            continue
        delta = max(-BAND, min(BAND, float(a.get("delta", 0))))
        conds[dim] = max(0.0, min(1.0, conds[dim] + delta * w))
        if abs(delta) >= 0.10:
            disagreements.append(a)
    wsum = sum(rule["conditions"][k]["weight"] for k in conds)
    quality = sum(conds[k] * rule["conditions"][k]["weight"]
                  for k in conds) / wsum
    composite_raw = rule["completeness"] * 0.4 + quality * 0.6
    composite = min(composite_raw, rule.get("flag_cap", 1.0))   # 红旗最后套
    return {"conditions": conds, "quality": quality,
            "composite_raw": composite_raw, "composite": composite,
            "disagreements": disagreements, "dropped_adjustments": missing_evidence,
            "summary": llm.get("summary"), "top_suggestion": llm.get("top_suggestion"),
            "confidence": conf}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True,
                    help="规则层输出的 评审结果.json")
    ap.add_argument("--submission-root", default="",
                    help="提交所在的目录（用于抽取摘录）")
    ap.add_argument("--out", default="reports/llm_review.json")
    ap.add_argument("--model", default="gpt-4o-mini")
    a = ap.parse_args()

    d = json.loads(Path(a.payload).read_text(encoding="utf-8"))
    out = {}
    for s in d["submissions"]:
        failed = [c["id"] for k in s["conditions"]
                  for c in s["conditions"][k]["checks"] if not c["pass"]]
        ex = excerpt(Path(a.submission_root)) if a.submission_root else "（未提供）"
        prompt = PROMPT.format(
            author=s["author"], completeness=s["completeness"],
            missing=s["missing"],
            conds={k: round(v["score"], 3) for k, v in s["conditions"].items()},
            failed=failed, flags=[f["id"] for f in s["red_flags"]], excerpt=ex)
        txt = call(prompt, a.model)
        m = re.search(r"\{.*\}", txt, re.S)
        llm = json.loads(m.group(0)) if m else {}
        out[s["author"]] = {"rule_layer": s, "llm": llm,
                            "merged": merge(s, llm)}
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                 encoding="utf-8", newline="\n")
    print(f"已写出 {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
