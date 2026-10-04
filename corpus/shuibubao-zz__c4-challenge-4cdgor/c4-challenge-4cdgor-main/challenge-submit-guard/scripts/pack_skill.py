#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pack_skill.py — 把 challenge-submit-guard/ 打包成可安装的 .skill 文件。

.skill 的真实格式是 **ZIP**（不是 CHALLENGE.md 里写的 tar.gz —— 实测平台附带的
wechat-doc-mapper.skill / skill-explainer.skill 都是 PK 开头的 ZIP）。
ZIP 内必须有一层以技能名命名的顶层目录，例如：

    challenge-submit-guard/SKILL.md
    challenge-submit-guard/scripts/...
    challenge-submit-guard/references/...

用法：
    python pack_skill.py                       # 输出到 C4 根目录
    python pack_skill.py --out /path/x.skill
"""

import argparse
import os
import sys
import zipfile

SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode"}
SKIP_NAMES = {".DS_Store", "desktop.ini"}


def main():
    ap = argparse.ArgumentParser(description="打包 skill 目录为 .skill（ZIP）")
    ap.add_argument("--skill-dir", default=None, help="技能目录（默认本脚本的上级目录）")
    ap.add_argument("--out", default=None, help="输出 .skill 路径")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    skill_dir = args.skill_dir or os.path.dirname(here)
    skill_dir = os.path.abspath(skill_dir)
    skill_name = os.path.basename(skill_dir)

    if args.out:
        out = os.path.abspath(args.out)
    else:
        # 默认写到 C4 交付包根目录
        out = os.path.join(os.path.dirname(skill_dir), "%s.skill" % skill_name)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    if os.path.exists(out):
        os.remove(out)

    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(skill_dir):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name in SKIP_NAMES or name.startswith("."):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, os.path.dirname(skill_dir)).replace("\\", "/")
                z.write(full, rel)
                count += 1

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("已打包：%s" % out)
    print("顶层目录：%s/" % skill_name)
    print("文件数：%d（%.1f KB）" % (count, os.path.getsize(out) / 1024.0))
    print("\n校验（应看到 SKILL.md 在最外层目录里）：")
    with zipfile.ZipFile(out) as z:
        for n in z.namelist():
            print("  %s" % n)


if __name__ == "__main__":
    main()
