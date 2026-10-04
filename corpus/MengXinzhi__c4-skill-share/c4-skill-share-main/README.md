# C4 技能分享与传播 — 提交包

- 挑战：C4 技能分享与传播
- 挑战 ID：ch-20260717031424-4cdgor
- 学号：2024106220247
- 技能名称：**deliverable-checker（作业交付物自查器）v1.2**

## 交付物清单

| # | 文件 | 作用 |
|---|------|------|
| 1 | `苗文馨_C4_skill说明.md` | 技能说明：解决什么问题、四条件自证、使用场景、真实案例、已知限制 |
| 2 | `苗文馨_C4_deliverable-checker.skill` | 技能包（ZIP 容器）：`SKILL.md` + `scripts/deliverable_checker.py` + `references/rubric-guide.md` |
| 3 | `苗文馨_C4_deliverable-checker_SKILL.md` | 技能定义原文（与包内 `SKILL.md` 逐字节一致），免解压直接阅读 |
| 4 | `苗文馨_C4_deliverable-checker_rubric-guide.md` | 评分维度证据映射说明（与包内 `references/rubric-guide.md` 逐字节一致） |
| 5 | `苗文馨_C4_教学说明.md` | 从零教学：环境准备 → 运行 → 看报告 → 常见坑 |
| 6 | `苗文馨_C4_demo截图1_缺漏检出.png` | Demo：故意缺漏的模拟提交被正确检出（退出码 1） |
| 7 | `苗文馨_C4_demo截图2_全绿通过.png` | Demo：补齐后全绿通过（退出码 0） |
| 8 | `苗文馨_C4_AI日志.md` | AI 使用日志：4 轮迭代的 prompt、AI 动作、真实踩坑与我的决策 |
| 9 | `苗文馨_C4_提交前自查报告.md` | 用本技能对自己提交夹跑出的自查报告（自查工具自证） |

> 说明：`.skill` 为技能打包文件（实测为 ZIP 容器），包含 `SKILL.md` 与随附脚本，可直接导入使用；
> 第 3、4 项为其内部文件的独立可读副本，便于评审无需解压即可查看。

## 技能一句话

输入「挑战资料包目录 + 你的提交文件夹」，输出一份 Markdown 自查报告：
缺了什么交付物、命名是否合规、会踩哪些红旗、五维评分证据是否齐全。

## 运行方式

```bash
python scripts/deliverable_checker.py --challenge "<挑战资料包>" --submission "<提交文件夹>" --name "苗文馨"
```

仅需 Python 3.8+ 标准库，零第三方依赖；退出码 `0`=全通过 / `1`=有缺口 / `2`=输入错误。
