# aar-report-generator

> C4 挑战「技能分享与传播」交付仓库 —— 一个把 AAR 复盘碎片整理成结构化复盘报告的可安装技能。

## 这个技能解决什么问题

AAR（After Action Review）复盘人人都在做，但结果常常是「一堆零散感想」：收获、过程、协作、卡点混在一起，写完了也无法复用，下次复盘又要从零开始。

`aar-report-generator` 把这件事变成一次确定性转换：**输入结构化或纯文本的复盘素材，输出固定七维、可归档、可对比的复盘报告**。

## 快速开始

无第三方依赖，Python 3.8+ 即可运行。

```bash
# JSON 输入
python scripts/aar_report.py ../examples/sample_input.json -o report.md

# 纯文本输入（自动做字段映射）
python scripts/aar_report.py ../examples/sample_text_input.txt -o report.md
```

## 目录结构

```
aar-report-generator/
├── SKILL.md                      # 技能说明与触发条件（技能入口）
├── references/
│   └── aar_framework.md          # AAR 七维框架定义与写作要求
└── scripts/
    └── aar_report.py             # 报告生成器（零第三方依赖）
examples/
├── sample_input.json             # JSON 形态输入样例
├── sample_output.md              # 对应输出样例
├── sample_text_input.txt         # 纯文本输入样例
└── sample_text_output.md         # 对应输出样例
```

## 复盘七维框架

报告固定输出以下七个维度，其中「卡点与突破」「ΔR 归因」是区分普通总结与复盘的关键两维：

1. 学到了什么
2. 过程复盘
3. 与 AI 的协作
4. 完成了什么
5. 卡点与突破
6. 改进方向
7. ΔR 归因

## 交付物索引

| 交付物 | 文件 |
| --- | --- |
| 技能说明 | `WangChunYan_C4_skill说明.md` |
| 可安装技能包 | `WangChunYan_C4_aar-report-generator.skill` |
| 教学说明 | `WangChunYan_C4_教学说明.md` |
| demo 演示 | `WangChunYan_C4_demo.md` |
| AI 使用日志 | `WangChunYan_C4_AI日志.md` |

## 安装方式

直接使用仓库中的 `aar-report-generator/` 目录，或将 `WangChunYan_C4_aar-report-generator.skill` 作为技能包安装。

## 已知边界

- 生成器负责**结构**与**完整性校验**，不对复盘内容的真实性与深度作判断；
- 输入缺失的维度会被显式标记为待补，而不是自动编造；
- 纯文本输入依赖启发式字段映射，字段命名高度非标准时建议改用 JSON 输入。
