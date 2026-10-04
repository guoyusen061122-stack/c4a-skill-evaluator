#!/usr/bin/env sh
# C4A 技能提交自动评审 —— 一键复现（Linux / macOS / WSL）
#
#   sh reproduce.sh
#
# 全程不需要联网、不需要 pip install、不需要 API key。
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
export PYTHONIOENCODING=utf-8
cd "$REPO"

PY="${FORESIGHT_PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
echo "Python: $PY"

echo
echo "[1/6] 生成 20 个带人工标注的评测样本"
"$PY" tools/make_gold.py
"$PY" tools/fix_gold_labels.py >/dev/null

echo
echo "[2/6] 可靠性测试（87 项断言 + 朴素对照组）"
"$PY" tests/test_evaluator.py

echo
echo "[3/6] 在 8 份真实公开提交上评审"
"$PY" tools/class_report.py

echo
echo "[4/6] 生成可靠性报告与交付物"
"$PY" tools/make_reliability_report.py

echo
echo "[5/6] 打包 .skill 并核验可独立运行"
"$PY" tools/build_skill.py

echo
echo "[6/6] 交付物全量核验"
"$PY" tools/audit_deliverables.py
