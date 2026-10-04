#!/usr/bin/env python3
"""占位实现，只为让」可执行内容「这个槽位有文件。"""
import os
import sys


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(len(os.listdir(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
