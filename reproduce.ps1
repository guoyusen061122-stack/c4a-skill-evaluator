# C4A 技能提交自动评审 —— 一键复现（Windows / PowerShell）
#
#   powershell -ExecutionPolicy Bypass -File reproduce.ps1
#
# 六步：评测集 → 测试 → 真实语料评审 → 可靠性报告 → 打包 → 全量核验
# 全程**不需要联网**、**不需要 pip install**、**不需要 API key**。

$ErrorActionPreference = "Continue"
$repo = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

$py = if ($env:FORESIGHT_PYTHON) { $env:FORESIGHT_PYTHON }
      elseif (Test-Path "D:\python\python.exe") { "D:\python\python.exe" }
      else { "python" }
Write-Host "Python: $py" -ForegroundColor Cyan

Write-Host "`n[1/6] 生成 20 个带人工标注的评测样本" -ForegroundColor Cyan
& $py tools\make_gold.py
& $py tools\fix_gold_labels.py | Out-Null

Write-Host "`n[2/6] 可靠性测试（87 项断言 + 朴素对照组）" -ForegroundColor Cyan
& $py tests\test_evaluator.py
if ($LASTEXITCODE -ne 0) {
  Write-Host "  测试未通过，先修好再继续。" -ForegroundColor Red
  exit 1
}

Write-Host "`n[3/6] 在 8 份真实公开提交上评审" -ForegroundColor Cyan
& $py tools\class_report.py

Write-Host "`n[4/6] 生成可靠性报告与交付物" -ForegroundColor Cyan
& $py tools\make_reliability_report.py

Write-Host "`n[5/6] 打包 .skill 并核验可独立运行" -ForegroundColor Cyan
& $py tools\build_skill.py

Write-Host "`n[6/6] 交付物全量核验" -ForegroundColor Cyan
& $py tools\audit_deliverables.py
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
  Write-Host "全部通过。交付物在 $repo" -ForegroundColor Green
} else {
  Write-Host "有未通过项，见上面的 [FAIL] 清单。" -ForegroundColor Red
}
exit $code
