# C4 · 技能分享与传播 —— challenge-preflight

本仓库是课程 **Challenge 4（技能分享与传播）** 的交付物归档。

- 公开仓库：https://github.com/Leo-web-lhy/c4-skill-sharing
- 挑战编号（平台）：`ch-20260717031424-4cdgor`

## 交付物清单

| 文件 | 说明 |
| --- | --- |
| `阮如意_C4_challenge-preflight.skill` | 可安装的技能包（zip 容器）：`SKILL.md` + `scripts/preflight.py` + `references/rules.json` |
| `阮如意_C4_skill说明.md` | 技能说明：解决什么问题、使用场景、输入输出、真实案例、技能四条件自证 |
| `阮如意_C4_教学说明.md` | 教学说明：怎么跑起来、怎么读报告、常见坑、优化技巧、一页速查 |
| `阮如意_C4_demo截图.png` | demo 实测截图：修复前（FAIL）与修复后（PASS）两版真实输出 |
| `阮如意_C4_AI日志.md` | AI 协作日志：用了什么 AI、怎么指挥、迭代轮次、人工介入 |
| `阮如意_C4_AAR.md` | 复盘：目标 vs 实际、踩过的坑、改进项 |
| `skill_src/challenge-preflight/` | 技能源码（可直接阅读与修改） |

## 这个技能做什么

**输入**一个挑战交付目录（加挑战编号），**输出**一份提交前自查报告（`PASS` / `FAIL` + 逐条行动项），把命名不符、缺件、空文件三类机械问题挡在提交门外。

```bash
python scripts/preflight.py --dir "<交付目录>" --challenge C4 --name 阮如意
# 退出码：0 = PASS，1 = FAIL，2 = 参数 / 环境错误
```

- 纯 Python 标准库，**离线、零依赖**，Python 3.9+
- **确定性**：同一目录、同一参数，永远同一份报告
- 规则表 `references/rules.json` 每条都带 `source`；未收录的挑战会在报告里明写，不做齐全性判定

## 快速上手

1. 解压 `阮如意_C4_challenge-preflight.skill`（zip 可直接解压），或直接用 `skill_src/challenge-preflight/`
2. 运行上面的命令
3. 读第一行结论；`FAIL` 就按报告末尾的「行动项」逐条修
4. 改完重跑，直到 `PASS`

详见 `阮如意_C4_教学说明.md`。

## 事实与边界

- C1 / C2 的必交规则来自平台提交前核验的**实测返回**；C4 规则来自 `CHALLENGE.md` 第四节命名表与上传清单。
- C3 / C5–C7 的规则**未收录**（`verified: false`），脚本只做通用检查 —— 宁可少查，也不编规则。
- 本仓库不含任何密钥或凭据；临时文件与工具缓存均未纳入。
