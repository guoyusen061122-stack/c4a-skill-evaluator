# C4_deliverable · deliverable-selfcheck 交付物自检器

EduSeed Elite20 挑战 **C4 技能分享与传播** 的交付仓库。

- 作者：ZhouYan05
- 技能名：`deliverable-selfcheck`
- 技能包：[`ZhouYan05_C4_deliverable-selfcheck.skill`](./ZhouYan05_C4_deliverable-selfcheck.skill)（tar.gz，可直接安装）

## 这是什么

**在提交课程挑战之前，用一条命令告诉你：交付物缺不缺、文件名对不对、会不会被平台的敏感信息过滤拦下。**

它来自我在 C1–C3 提交中真实踩过的两个坑：

1. **平台通配符是文件名的「字面子串匹配」**，不是模糊匹配。
   要求 `*AI日志*` 时，`AI_工作日志与AAR.md`（下划线断开）会被判**缺失**。
2. **标题里的「英文冒号 + 空格」会被敏感信息过滤误判成密钥**，导致整单被拒。

这两条坑可检测，所以被固化成了工具。

## 快速开始

```bash
# 1. 解包（.skill 就是 tar.gz）
tar -xzf ZhouYan05_C4_deliverable-selfcheck.skill
cd deliverable-selfcheck

# 2. 自检（纯 Python 标准库，零依赖）
python scripts/selfcheck.py \
  --workdir /path/to/my_challenge \
  --required "*skill说明*,*.skill,*教学说明*,*demo*,*AI日志*" \
  --prefix ZhouYan05 \
  --title "你准备提交的标题" \
  --summary "你准备提交的摘要"
```

- 退出码：`0`=READY，`1`=BLOCKED，`2`=目录不存在
- 加 `--json` 输出机器可读结果

## 仓库结构

```
.
├── ZhouYan05_C4_skill说明.md              # 技能说明（含四条件自评、边界）
├── ZhouYan05_C4_教学说明.md               # 教学说明（含练习与常见误解）
├── ZhouYan05_C4_demo.md                   # demo（before/after 真实对照）
├── ZhouYan05_C4_AI日志与AAR.md            # AI 工作日志 + AAR 复盘
├── ZhouYan05_C4_deliverable-selfcheck.skill  # 可安装技能包
├── src/deliverable-selfcheck/             # 技能源码
│   ├── SKILL.md
│   ├── scripts/selfcheck.py               # 全部逻辑，纯标准库
│   ├── references/rulebook.md             # 平台规则速查（实测证据）
│   └── assets/report_template.md          # 报告模板与 JSON 形态
└── _demo/
    ├── before/                            # 踩坑样本 → BLOCKED
    └── after/                             # 修好样本 → READY
```

## 自评：四条件

| 条件 | 说明 |
| --- | --- |
| 可复用 | 与具体挑战无关，任何挑战/学期通用 |
| 可执行 | 纯 Python 标准库，零依赖，不联网 |
| 可验证 | 确定性输出 + 退出码，`_demo` 提供可复跑对照 |
| IO 明确 | 输入=目录+清单+前缀/标题/摘要；输出=Markdown 或 JSON |

## 边界

不替代平台校验（是它的近似实现），只读，不提交/不修改文件，
不解析 PDF/Word 正文。最终以平台返回为准。

## 许可

仅供学习交流使用。
