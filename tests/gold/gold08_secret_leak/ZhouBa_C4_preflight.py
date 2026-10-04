#!/usr/bin/env python3
"""最小可运行的自查器（gold 样本用）。"""
import json
import sys


def main(argv):
    if len(argv) < 2:
        print("用法: python preflight.py <文件夹>", file=sys.stderr)
        return 2
    import os
    root = argv[1]
    if not os.path.isdir(root):
        print("不是目录", file=sys.stderr)
        return 3
    files = sorted(os.listdir(root))
    print(json.dumps({"n_files": len(files)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
