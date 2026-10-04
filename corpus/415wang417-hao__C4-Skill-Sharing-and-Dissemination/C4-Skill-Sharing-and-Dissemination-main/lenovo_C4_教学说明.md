---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 60ea5d0126731e33de81577b27285889_6dfc24a1bf1f11f1884b525400cd780f
    ReservedCode1: 7nuU48rzHQkgGWREPHzZg8kKjiUFpBI10pEqJwicga/KQ6GmugcXWQh0Ndx2ao2BejDwld2LkxqUubaBdgGr1rJr7K3WgDbh1vFJWU0RkbdLSoX5v8VtJuK/cTyd4nfT8B0e+V694RVKxyBBCPgNtwTK24KZtl6lZjbme789WbRLrwfl9peAJ4ob++4=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 60ea5d0126731e33de81577b27285889_6dfc24a1bf1f11f1884b525400cd780f
    ReservedCode2: 7nuU48rzHQkgGWREPHzZg8kKjiUFpBI10pEqJwicga/KQ6GmugcXWQh0Ndx2ao2BejDwld2LkxqUubaBdgGr1rJr7K3WgDbh1vFJWU0RkbdLSoX5v8VtJuK/cTyd4nfT8B0e+V694RVKxyBBCPgNtwTK24KZtl6lZjbme789WbRLrwfl9peAJ4ob++4=
---





# smart-file-organizer 教学说明（零基础上手教程）

> 本文档面向**从未用过命令行**的使用者。照着做一遍，你会得到一个自动归类好的文件夹，并且随时能一键还原。
> 配套技能包：`lenovo_C4_smart-file-organizer.skill`
> 参考文件：`references/pitfalls.md`（14 条常见坑原文）、`references/organizing-strategies.md`（扩展名映射表）

---

## 一、先明确：这东西能帮你做什么

把它想象成一个「不用你动手的整理员」。你告诉它整理哪个文件夹，它就把里面散落的文件按规则放进子文件夹：图片进 `图片/`，文档进 `文档/`。整个过程有三条保底承诺：

1. **先看后动**：可以先预览它打算怎么整理，你点头了它才真的动手。
2. **绝不删除**：它只移动文件，不会删掉任何一个。
3. **随时反悔**：整理完不满意，一条命令全部还原。

---

## 二、准备工作：确认电脑里有 Python

按 `Win + R`，输入 `cmd` 回车，打开命令行窗口，输入：

```bash
python --version
```

- 如果显示 `Python 3.7.x` 或更高的版本号 → 可以继续。
- 如果提示「不是内部或外部命令」→ 需要先安装 Python。到 python.org 下载安装包，安装时**务必勾选**「Add Python to PATH」。

> 不需要安装任何额外的库。这个技能只用 Python 自带的功能，不会让你 `pip install` 一堆东西。

---

## 三、安装：把技能包解压出来

`.skill` 文件本质上就是一个压缩包（ZIP 格式），解压后就能用。假设你把文件放在 `D:\技能包\` 目录下：

```bash
cd /d D:\技能包
python -c "import zipfile; zipfile.ZipFile('lenovo_C4_smart-file-organizer.skill').extractall('D:/技能包/smart-file-organizer')"
```

解压后会得到这样的结构：

```
smart-file-organizer/
├── SKILL.md
├── scripts/
│   └── organize.py          ← 真正干活的脚本
└── references/
    ├── organizing-strategies.md
    └── pitfalls.md
```

> 提示：不要用 Windows 自带的右键「解压到当前文件夹」，部分系统版本会因为 `.skill` 不是标准扩展名而报错。用上面这条命令最稳。

---

## 四、第一次整理：五步走完

假设你要整理的是 `D:\Downloads`，脚本位于 `D:\技能包\smart-file-organizer\scripts\organize.py`。

### 第 1 步：进入脚本所在目录

```bash
cd /d D:\技能包\smart-file-organizer
```

### 第 2 步：预览（必做，不会动任何文件）

```bash
python scripts/organize.py "D:/Downloads" --strategy type --dry-run
```

屏幕上会打印计划清单，长得像这样：

```
[DRY-RUN] 计划归类 18 个文件，跳过 2 个：
    sunset.jpg        ->  图片/sunset.jpg
    项目计划书.docx    ->  文档/项目计划书.docx
    合同.pdf          ->  文档/合同_1.pdf   (重命名)
    无扩展名文件       ->  其他/无扩展名文件
```

**这一步要看三件事**：一共要动多少文件、有没有被标「重命名」的、被跳过的 2 个是不是你希望保留的（通常是 `.hidden` 或 `desktop.ini` 这类系统文件）。

### 第 3 步：确认后实际整理

```bash
python scripts/organize.py "D:/Downloads" --strategy type
```

输出：

```
归类完成：成功 18，失败 0，跳过 2。
```

此时回到 `D:\Downloads` 文件夹看，散落的文件已经被收进 `图片/`、`文档/` 等子文件夹。

### 第 4 步：查看报告

目录里会多出一份 `_organize_report_<时间戳>.md`，双击用记事本或任何编辑器打开。里面包含归类概览、每个文件的去向明细、跳过清单及原因、以及成功/失败/跳过统计。

### 第 5 步：不满意就还原

```bash
python scripts/organize.py "D:/Downloads" --undo
```

输出：

```
已还原 18 个文件，失败 0 个，清理空目录 6 个。
```

所有文件回到整理前的位置，本次新建的类别文件夹被自动清空并删除。**已完成一次完整的「整理—还原」闭环**，可以放心大胆地去整理真正重要的目录了。

---

## 五、三种策略：什么时候用哪个

| 你的目标 | 用哪个策略 | 命令示例 |
|---|---|---|
| 通用整理，把杂乱的顶层文件分门别类 | `type`（默认） | `python scripts/organize.py "D:/Downloads" --strategy type` |
| 照片、截图、录屏按拍摄/修改时间归档 | `date` | `python scripts/organize.py "D:/照片" --strategy date` |
| 把发票、合同、简历等特定文件挑出来 | `keyword` | `python scripts/organize.py "D:/Downloads" --strategy keyword --keywords 发票,合同,简历` |

**`date` 策略实操示例**：整理一个混着多年截图的文件夹，执行后会生成 `2025-08/`、`2026-03/`、`2026-09/` 这样的年月文件夹，一眼就能看出每个月的产出量。

**`keyword` 策略实操示例**：下载文件夹里几十个文件混在一起，但只要把发票挑出来：

```bash
python scripts/organize.py "D:/Downloads" --strategy keyword --keywords 发票
```

所有文件名含「发票」两个字的文件会被收进 `发票/` 文件夹，其余归入 `其他/`。

> **关键词优先级规则**：按你传入的顺序决定。若写成 `--keywords 发票,合同`，一个名为「合同发票.pdf」的文件会进入 `发票/`（因为「发票」写在前面）。想让某类优先，就把它排前面。

---

## 六、读懂两份产物

### 6.1 归类报告 `_organize_report_<时间戳>.md`

| 区块 | 看什么 |
|---|---|
| 归类概览 | 处理了多少文件、用了什么策略、总大小 |
| 文件明细 | 每个文件的 `原位置 → 新位置`；带「重命名避免冲突」备注的说明目标位置原本已有同名文件 |
| 跳过清单 | 被跳过的文件及原因（隐藏文件、系统文件、工具自身产物） |
| 结果统计 | 成功 / 失败 / 跳过 三个数字 |

### 6.2 撤销清单 `_organize_undo_<时间戳>.json`

这是「反悔凭据」，记录了每一次移动的源路径和目标路径。**只要不清空回收站式的删除它，你永远可以还原。** 建议整理重要目录后，先别急着删这份 JSON。

---

## 七、常见坑与排查

以下 14 条摘自技能包 `references/pitfalls.md`，按「出问题的时机」分组。遇到问题先在这里对照。

### 7.1 使用前

| # | 坑 | 后果 / 排查 |
|---|---|---|
| 1 | **忘记先 dry-run** | 直接执行会立即改动文件。养成习惯：真实整理前先 `--dry-run` 看一遍；已执行又不满意就 `--undo` 回滚 |
| 2 | **路径含空格或中文没加引号** | 报错找不到路径。务必用引号包住：`python scripts/organize.py "C:/Users/me/Desktop/我的文件" --strategy type`。Windows 反斜杠建议写成正斜杠 `C:/Users/...`，避免转义问题 |
| 3 | **以为会递归整理子文件夹** | 本工具**只处理顶层散落文件**，已有子目录保持不动——这是刻意设计，避免打乱你已有的分类结构。确实需要就分目录多次执行 |
| 4 | **keyword 策略忘了传关键词** | `--strategy keyword` 必须配 `--keywords`，否则报错退出 |

### 7.2 运行中

| # | 坑 | 后果 / 排查 |
|---|---|---|
| 5 | **文件被占用 / 权限不足** | 单个文件失败不会中断整个任务，该文件标记为 `failed` 并记入报告。查看报告「文件明细」里的失败原因，关闭占用程序（Excel、播放器）后重跑即可 |
| 6 | **同名冲突** | 目标已有同名文件时，新文件自动变成 `合同_1.pdf`、`合同_2.pdf`，**绝不覆盖**。看到 `_1` 后缀即说明报告备注里标注了「重命名避免冲突」 |
| 7 | **隐藏文件「消失」却没被归类** | 正常现象。`.` 开头文件、`desktop.ini`、`thumbs.db`、带 Windows 隐藏/系统属性的文件会被跳过，并在报告「跳过清单」中列明原因 |
| 8 | **报告/undo 清单会不会被再次归类** | 不会。工具产物统一以 `_organize_` 开头，运行时自动跳过 |

### 7.3 撤销时

| # | 坑 | 后果 / 排查 |
|---|---|---|
| 9 | **`--undo` 找不到清单** | 默认在目标目录找**最新**的 `_organize_undo_*.json`。若清单被删或移动，用 `--undo-file` 显式指定：`python scripts/organize.py "D:/Downloads" --undo --undo-file "D:/Downloads/_organize_undo_20261003_101500.json"` |
| 10 | **撤销后原位置已有同名文件** | 还原文件自动加 `_1` 后缀，不会被覆盖 |
| 11 | **撤销后残留空文件夹** | 正常情况会自动清理「本次新建且已清空」的类别文件夹；若该文件夹是你事先就存在的（非本次新建），则保留不动——这是为避免误删你的目录 |
| 12 | **撤销只针对「上一次」整理** | undo 清单只记录一次运行的文件。连续整理多次时每次各有一份清单，`--undo` 默认还原最近一次；要还原更早的，用 `--undo-file` 指定对应清单 |

### 7.4 环境相关

| # | 坑 | 后果 / 排查 |
|---|---|---|
| 13 | **Python 版本** | 需要 Python 3.7+，仅用标准库（os / pathlib / json / argparse / datetime / ctypes），无需 pip 安装 |
| 14 | **跨盘移动大量文件较慢** | 同盘内移动是「改名」操作（极快）；跨盘（如 C: → D:）会退化为复制+删除，耗时较长，按需分批执行 |

---

## 八、进阶用法与优化技巧

### 8.1 用 `--undo-file` 建立「版本化回滚」

连续整理同一个目录多次时，每次都会生成独立的时间戳清单。如果你想把目录还原到**第一次**整理前的状态，先列出所有清单：

```bash
dir /b "D:/Downloads/_organize_undo_*.json"
```

再指定要用的那一份：

```bash
python scripts/organize.py "D:/Downloads" --undo --undo-file "D:/Downloads/_organize_undo_20261003_101500.json"
```

> 注意：按时间从早到晚依次回滚才是安全的。直接跳到最早的清单，中间批次的文件可能已被移动，会导致部分还原失败。

### 8.2 多目录批量整理

工具一次只处理一个目录，但可以写一个循环批量跑（先全部 dry-run 确认，再全部执行）：

```bash
for %d in ("D:/Downloads" "C:/Users/me/Desktop") do python scripts/organize.py "%d" --strategy type --dry-run
```

确认无误后，把 `--dry-run` 去掉再跑一遍。

### 8.3 先粗后细的两段式整理

第一步用 `type` 把杂文件分大类；第二步进到 `文档/` 里，用 `keyword` 把发票、合同进一步挑出来：

```bash
python scripts/organize.py "D:/Downloads/文档" --strategy keyword --keywords 发票,合同,简历
```

每次都遵循同一套流程：dry-run → 执行 → 看报告。

### 8.4 整理前的三个习惯动作

1. **关闭占用的程序**：整理前关掉正在编辑的 Excel、Word、播放器，减少「文件被占用」导致的失败。
2. **确认没有重要文件正被其他程序写入**：例如正在下载的大文件，移动它会中断下载。
3. **保留 undo 清单**：整理完成、确认满意之前，不要删除目录里的 `_organize_undo_*.json`。

---

## 九、上手自测清单

照着勾一遍，全部通过说明你已经完全会用：

- [ ] `python --version` 能正确显示版本号
- [ ] 已成功把 `.skill` 解压出 `organize.py`
- [ ] 完成过一次 `--dry-run` 预览，能看懂计划清单
- [ ] 完成过一次真实整理，顶层文件被收进子文件夹
- [ ] 打开过归类报告，能说出「跳过清单」里每个文件被跳过的原因
- [ ] 完成过一次 `--undo` 还原，文件回到原位
- [ ] 知道 `type` / `date` / `keyword` 三种策略分别适合什么场景
- [ ] 遇到报错时会先翻 `references/pitfalls.md` 对照排查

---

## 十、问题速查表

| 现象 | 最可能的原因 | 快速处理 |
|---|---|---|
| 提示找不到路径 | 路径没加引号，或用了单反斜杠 | 加英文引号，路径写成 `D:/xxx` |
| 一个文件没被移动 | 被占用，或属于隐藏/系统文件 | 看报告「文件明细」和「跳过清单」 |
| 出现了 `合同_1.pdf` | 目标位置已有同名文件 | 正常行为，未覆盖，看报告备注 |
| `--undo` 报找不到清单 | 清单被删或改了名 | 用 `--undo-file` 指定完整路径 |
| `keyword` 策略报错退出 | 忘传 `--keywords` | 补上 `--keywords 发票,合同` |
| 子文件夹里的文件没被整理 | 工具不递归，只处理顶层 | 对子目录单独执行一次 |
| 整理后剩了几个文件在顶层 | 那是被跳过的隐藏/系统文件 | 属正常，无需处理 |
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
