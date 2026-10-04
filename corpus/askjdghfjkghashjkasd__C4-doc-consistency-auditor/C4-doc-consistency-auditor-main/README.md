# C4 技能分享与传播 · doc-consistency-auditor

> 提交人：2025105400130
> 技能名：doc-consistency-auditor（Markdown 文档一致性审计器）
> 一句话：输入一个 Markdown 文件或目录，输出一份带「文件:行号」的一致性审计报告 + 退出码。

---

## 这是什么

一个**确定性脚本**，扫描 Markdown 文档，定位五类一致性问题：

| 规则 | 检查内容 | 级别 |
|------|----------|------|
| R0 | 文件规模（超大文件跳过告警） | 警告 |
| R1 | 术语漂移（对比术语表命中禁用写法） | 错误 |
| R2 | 内部链接/锚点失效 | 错误 |
| R3 | 标题层级跳跃（## → ####） | 警告 |
| R4 | 重复标题 | 警告 |
| R5 | 交付物清单缺口（README/.skill/AI日志/AAR/skill说明） | 警告 |

## 目录结构

```
C4-技能分享与传播/
├── README.md                          # 本文件
├── 2025105400130_C4_skill说明.md       # 技能说明（解决什么/怎么用/真实案例）
├── 2025105400130_C4_教学说明.md        # 教学说明（上手/常见坑/优化技巧）
├── 2025105400130_C4_AI日志.md          # AI 协作日志
├── 2025105400130_C4_AAR.md             # 七维复盘
├── 2025105400130_C4_demo.png           # demo 截图
├── 2025105400130_C4_doc-consistency-auditor.skill  # 打包的技能包
├── doc-consistency-auditor/            # 技能源码
│   ├── SKILL.md
│   ├── scripts/audit.py
│   └── references/
│       ├── glossary.example.yaml
│       └── manifest.example.yaml
└── demo/
    ├── sample_clean.md                 # 干净样例（应通过）
    └── sample_bad.md                   # 坏样例（含 7 个已知问题）
```

## 快速开始

```bash
# 最简
python3 doc-consistency-auditor/scripts/audit.py --path demo/sample_clean.md

# 完整（术语 + 链接 + 标题 + 交付物清单）
python3 doc-consistency-auditor/scripts/audit.py --path demo \
  --glossary doc-consistency-auditor/references/glossary.example.yaml \
  --manifest doc-consistency-auditor/references/manifest.example.yaml

# 机器可读
python3 doc-consistency-auditor/scripts/audit.py --path demo --json
```

## 交付物清单（对照 C4 要求）

| C4 要求 | 本仓库对应 |
|---------|-----------|
| Skill 说明文档 | `2025105400130_C4_skill说明.md` |
| 可执行内容 | `doc-consistency-auditor/`（SKILL.md + scripts/audit.py + references/） |
| Demo | `2025105400130_C4_demo.png` |
| 教学说明 | `2025105400130_C4_教学说明.md` |
| AI 日志 | `2025105400130_C4_AI日志.md` |
