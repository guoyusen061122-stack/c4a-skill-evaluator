#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 skill-evaluator/ 打包成可安装的 .skill 文件（就是 tar.gz），并核验。

    python tools/build_skill.py

产出：guoyusen_C4A_skill-evaluator.skill

核验内容：
  · 包里必须有 SKILL.md，且有合法 frontmatter（name + description）
  · 包里不能有 __pycache__ / .pyc / 绝对路径
  · 解包后能**脱离仓库**独立运行（只用包内文件跑一次真实评审）
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "skill-evaluator"
OUT = ROOT / "guoyusen_C4A_skill-evaluator.skill"

SKIP = {"__pycache__", ".pyc", ".DS_Store", ".tmp"}


def collect() -> list:
    files = []
    for dirpath, dirnames, filenames in os.walk(SRC):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for fn in sorted(filenames):
            if fn.endswith(".pyc") or fn in SKIP:
                continue
            p = Path(dirpath) / fn
            files.append((p, p.relative_to(SRC).as_posix()))
    return files


def main() -> int:
    files = collect()
    print(f"打包 {len(files)} 个文件 → {OUT.name}")
    with tarfile.open(OUT, "w:gz") as tar:
        for p, rel in files:
            data = p.read_bytes()
            info = tarfile.TarInfo(rel)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    size = OUT.stat().st_size
    print(f"  包大小 {size:,} B（{size/1024:.1f} KB）")

    # ---- 核验 ----
    ok = True
    with tarfile.open(OUT, "r:gz") as tar:
        names = [m.name for m in tar.getmembers() if m.isfile()]
        if "SKILL.md" not in names:
            print("  ✗ 包里没有 SKILL.md")
            ok = False
        else:
            body = tar.extractfile("SKILL.md").read().decode("utf-8")
            m = re.match(r"^---\s*\n(.*?)\n---", body, re.S)
            if not m:
                print("  ✗ SKILL.md 缺 frontmatter")
                ok = False
            else:
                keys = set(re.findall(r"^\s*([A-Za-z_][\w-]*)\s*:",
                                      m.group(1), re.M))
                miss = {"name", "description"} - keys
                if miss:
                    print(f"  ✗ frontmatter 缺字段 {sorted(miss)}")
                    ok = False
                else:
                    print("  ✓ frontmatter 含 name + description")
        bad = [n for n in names
               if "__pycache__" in n or n.endswith(".pyc")]
        if bad:
            print(f"  ✗ 含缓存文件 {bad[:3]}")
            ok = False

    # ---- 独立运行核验：解包到临时目录，只用包内文件跑一次 ----
    tmp = ROOT / ".tmp_skill"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(OUT, "r:gz") as tar:
        tar.extractall(tmp)
    sample = ROOT / "tests" / "gold" / "gold01_perfect"
    outdir = ROOT / ".tmp_skill_out"
    shutil.rmtree(outdir, ignore_errors=True)
    script = tmp / "scripts" / "c4a_evaluator.py"
    rubric = tmp / "references" / "c4_rubric.json"
    if not script.exists() or not rubric.exists():
        print("  ✗ 包内缺 scripts/ 或 references/")
        ok = False
    else:
        r = subprocess.run(
            [sys.executable, str(script), str(sample), "--out", str(outdir),
             "--format", "json", "--rubric", str(rubric), "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        j = outdir / "评审结果.json"
        if r.returncode == 0 and j.exists():
            d = json.loads(j.read_text(encoding="utf-8"))
            a = d["submissions"][0]
            print(f"  ✓ 脱离仓库独立运行成功：{a['author']} "
                  f"综合 {a['composite']:.2f}")
        else:
            print(f"  ✗ 独立运行失败（exit {r.returncode}）"
                  f"{r.stderr.decode('utf-8', 'replace')[:200]}")
            ok = False
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(outdir, ignore_errors=True)

    print("核验通过" if ok else "核验未通过")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
