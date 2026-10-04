#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成带**人工标注**的评测集（gold set）。

    python tools/make_gold.py

为什么需要它（这是本提交最重要的一块）
======================================
参考提交的做法是：自己造 10 个样本，跑出 10/10、全部 100% 准确率。
**自制测试集拿满分，说明的是测试集太容易，不是评审器可靠。**

本评测集的设计原则相反：
1. **每个样本针对一个具体的失败模式**，不是「随便造几个正常提交」。
2. **标注先于运行**：`labels.json` 里的期望值是按 rubric 手工推出来的，
   并附 `rationale`。跑完只统计一致与不一致，**不回头改标注去凑分**。
3. **故意包含「难」样本**：
   - 否定陷阱（正文写「没有测试」，朴素关键词计数器会把它当成有测试）
   - 关键词堆砌（看起来什么都有，其实什么都没说）
   - 文件名全对但内容为空（占位交付）
   - 非人名前缀（`run_C4_self.txt` 这类机器名）
   - GBK 编码、非标准命名、多版本、二进制冒充文档
4. **不一致会如实列出**。目标是「知道自己在哪些情况下会错」，不是「全对」。

样本由固定随机种子生成 → 内容确定、可复现。
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "tests" / "gold"

# ---------------------------------------------------------------- 素材
IO_LINE = ("**输入**：一个包含 C4 提交文件的本地文件夹路径；"
           "**输出**：每位作者的完整性矩阵、四条件得分与改进建议。")

FULL_DOC = f"""# 技能说明：提交前自查器

{IO_LINE}

## 解决什么问题

每次交作业都要手动核对五个文件齐不齐，容易漏。这个技能把核对自动化。

## 使用场景

- 交作业前自查
- 帮同学看他缺了什么

## 输入输出

输入是一个文件夹路径，输出是一份 Markdown 报告 + 一份 JSON。
"""

FULL_TEACHING = """# 教学说明

## 如何上手

1. 安装：把 `.skill` 文件放到技能目录；无需 `pip install`（纯标准库）。
2. 运行：`python preflight.py <你的文件夹>`
3. 看报告：打开 `report.md`。

## 常见坑

- 文件名必须是 `姓名_C4_内容.扩展名`，否则识别不到作者。
- Windows 控制台默认 GBK，读中文要指定 UTF-8。

## 注意事项

- 环境要求：Python 3.9+，跨平台（Windows / macOS / Linux）。
- 依赖：无。仅标准库。
"""

FULL_AILOG = """# AI 使用日志

## 使用的 AI 工具

Claude（主力，写初版）、ChatGPT（对比方案）。

## 迭代轮次

第 1 轮：让 AI 写一个扫描器。产出能跑，但作者识别把子目录名当作者。
第 2 轮：我指出「challenge-preflight 不是人名」，prompt 改成「只认文件名前缀」。
第 3 轮：加入否定语境处理，因为「没有测试」被当成了「有测试」。
第 4 轮：补上边界情况与退出码。

## 我做了什么（人工修正点）

- 第 2 轮的作者规则是我改的，AI 原本坚持父目录回退。
- 第 3 轮的否定词窗口 8 字符是我定的。

## Prompt 优化

初版 prompt：「写一个检查作业的脚本」
改后：「写一个只用标准库的检查器，输入是文件夹，输出是 JSON + Markdown，
      作者名只从文件名前缀提取，找不到就标 unknown，不要回退到父目录」
"""

FULL_SKILL = """---
name: c4-preflight
description: >
  检查 C4 技能提交的五个必交文件是否齐全，并给出四条件评分。
  当用户说「C4 自查」「提交前检查」「preflight」时触发。
---

# c4-preflight

## 工作流

### Step 1 — 扫描
递归扫描目录，收集文件。

### Step 2 — 归属
从文件名前缀提取作者。

### Step 3 — 报告
输出 Markdown + JSON。

## Edge cases

- 空文件夹：报告「未找到文件」并以退出码 3 结束。
- 文件名不规范：标记「需人工确认」。

## 运行方式

```bash
python preflight.py <文件夹>
```
"""

FULL_CODE = '''#!/usr/bin/env python3
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
'''

STUFFED = """# C4 技能 说明 教学 安装 环境要求 依赖 兼容 步骤 上手
# 输入 输出 use case input output 测试 test 示例 预期 expected
# 断言 assert 边界 判 通过 pass fail 退出码 exit code 运行方式 usage
# 工作流 workflow pipeline 常见坑 注意 安装 步骤 输入 输出 测试 预期
```

```python
import os
```

- [x] 输入 输出
- [x] 测试 预期
- [x] 安装 依赖
- [x] 工作流 边界
"""

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082")


def write(p: Path, text: str, encoding: str = "utf-8"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode(encoding))


def make_skill(path: Path, members: dict):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in members.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())


# ---------------------------------------------------------------- 样本
CASES = {}


def case(cid, author, files: dict, expect: dict, rationale: str,
         encoding="utf-8", skills=None, binary=None, expect_exit=0):
    CASES[cid] = {"author": author, "files": files, "expect": expect,
                  "rationale": rationale, "encoding": encoding,
                  "skills": skills or {}, "binary": binary or [],
                  "expect_exit": expect_exit}


# 1 满分
case("gold01_perfect", "SunYi",
     {"SunYi_C4_skill说明.md": FULL_DOC, "SunYi_C4_教学说明.md": FULL_TEACHING,
      "SunYi_C4_AI日志.md": FULL_AILOG, "SunYi_C4_preflight.py": FULL_CODE,
      "SunYi_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.90, "composite_max": 1.00,
      "flags": [], "level": "L4"},
     "五个交付物齐全，内容真实完整，无红旗 → 应落在 L4 上限区间。",
     binary=["SunYi_C4_demo.png"])

# 2 缺 demo
case("gold02_missing_demo", "LiEr",
     {"LiEr_C4_skill说明.md": FULL_DOC, "LiEr_C4_教学说明.md": FULL_TEACHING,
      "LiEr_C4_AI日志.md": FULL_AILOG, "LiEr_C4_preflight.py": FULL_CODE},
     {"completeness": 0.8, "composite_min": 0.60, "composite_max": 0.80,
      "flags": ["missing_core"], "level": "L3"},
     "缺 1 个必交交付物 → 完整性 0.8；按 missing_core 的 cap_table，缺 1 个上限 75。")

# 3 缺 AI 日志（同时触发 no_ai_log）
case("gold03_missing_ailog", "WangSan",
     {"WangSan_C4_skill说明.md": FULL_DOC, "WangSan_C4_教学说明.md": FULL_TEACHING,
      "WangSan_C4_preflight.py": FULL_CODE, "WangSan_C4_demo.png": ""},
     {"completeness": 0.8, "composite_min": 0.55, "composite_max": 0.80,
      "flags": ["missing_core", "no_ai_log"], "level": "L2",
      "allow_levels": ["L2", "L3"]},
     "缺 AI 日志 → missing_core(cap75) 与 no_ai_log(cap80) 同时命中，取更严的。",
     binary=["WangSan_C4_demo.png"])

# 4 只有说明文档（1/5）
case("gold04_only_doc", "ZhaoSi",
     {"ZhaoSi_C4_skill说明.md": FULL_DOC},
     {"completeness": 0.2, "composite_min": 0.10, "composite_max": 0.45,
      "flags": ["missing_core", "no_ai_log", "no_teaching"], "level": "L1"},
     "只交 1/5 → 缺 4 个，cap_table 命中 [3,45]，上限 45。")

# 5 文件名齐全但内容为空
case("gold05_empty_deliverables", "QianWu",
     {"QianWu_C4_skill说明.md": "", "QianWu_C4_教学说明.md": "",
      "QianWu_C4_AI日志.md": "", "QianWu_C4_preflight.py": "",
      "QianWu_C4_demo.png": ""},
     {"completeness": 0.0, "composite_min": 0.0, "composite_max": 0.40,
      "flags": ["missing_core"], "level": "L1"},
     "五个文件名全对但都是空文件。近空文件不参与槽位匹配 → 完整性应为 0（不是 1.0）。"
     "这是评价一个评审器最关键的样本：数文件名就能骗过的话，评审器没有价值。",
     binary=["QianWu_C4_demo.png"])

# 6 关键词堆砌
case("gold06_keyword_stuffing", "ZhouLiu",
     {"ZhouLiu_C4_skill说明.md": STUFFED, "ZhouLiu_C4_教学说明.md": STUFFED,
      "ZhouLiu_C4_AI日志.md": STUFFED, "ZhouLiu_C4_preflight.py": "print(1)\n",
      "ZhouLiu_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.0, "composite_max": 0.65,
      "flags": ["keyword_stuffing"], "level": None,
      "allow_levels": ["L1", "L2", "L3"]},
     "文件名齐全、正文里堆满规则词，但没有任何真实内容与结构 → "
     "应被 keyword_stuffing 抓住并压到 60 分以下。",
     binary=["ZhouLiu_C4_demo.png"])

# 7 硬编码绝对路径
case("gold07_hardcoded_path", "SunQi",
     {"SunQi_C4_skill说明.md": FULL_DOC + "\n运行：`python C:\\Users\\sunqi\\Desktop\\preflight.py`\n",
      "SunQi_C4_教学说明.md": FULL_TEACHING,
      "SunQi_C4_AI日志.md": FULL_AILOG, "SunQi_C4_preflight.py": FULL_CODE,
      "SunQi_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.60, "composite_max": 0.85,
      "flags": ["hardcoded_path"], "level": None,
      "allow_levels": ["L3", "L4"]},
     "出现 `C:\\Users\\...` → hardcoded_path(cap85)。这是「可复用」最常见的破坏方式。",
     binary=["SunQi_C4_demo.png"])

# 8 明文密钥
case("gold08_secret_leak", "ZhouBa",
     {"ZhouBa_C4_skill说明.md": FULL_DOC,
      "ZhouBa_C4_教学说明.md": FULL_TEACHING + "\napi_key = \"sk-abcdefghijklmnopqrstuvwx\"\n",
      "ZhouBa_C4_AI日志.md": FULL_AILOG, "ZhouBa_C4_preflight.py": FULL_CODE,
      "ZhouBa_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.0, "composite_max": 0.50,
      "flags": ["secret_leak", "hardcoded_path"], "level": None,
      "allow_levels": ["L1", "L2"]},
     "明文 `sk-` 密钥 → secret_leak(cap50)；应显著压分。",
     binary=["ZhouBa_C4_demo.png"])

# 9 没有 IO 一句话
case("gold09_no_io", "WuJiu",
     {"WuJiu_C4_skill说明.md": "# 技能说明\n\n这个技能很有用，能帮大家检查作业。\n"
                               "## 使用场景\n交作业前用一下。\n",
      "WuJiu_C4_教学说明.md": FULL_TEACHING, "WuJiu_C4_AI日志.md": FULL_AILOG,
      "WuJiu_C4_preflight.py": FULL_CODE, "WuJiu_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.40, "composite_max": 0.85,
      "flags": [], "level": None, "io_score_max": 0.6},
     "说明文档里**没有**「输入X，输出Y」式的一句话 → clear_io 不应满分。"
     "这是区分「有文档」和「文档讲清楚了 IO」的关键样本。",
     binary=["WuJiu_C4_demo.png"])

# 10 否定陷阱
case("gold10_negation_trap", "ZhengShi",
     {"ZhengShi_C4_skill说明.md":
         "# 技能说明\n\n输入一个文件夹，输出一份报告。\n\n"
         "## 现状\n本项目**没有测试**，也**无教学说明**，尚未加入断言。\n"
         "不支持 Windows。缺少边界处理。\n",
      "ZhengShi_C4_preflight.py": FULL_CODE},
     {"completeness": 0.4, "composite_max": 0.60,
      "flags": ["missing_core"], "level": None,
      "condition_max": {"verifiable": 0.75},
      "must_not_find": ["verifiable.V1", "verifiable.V5", "executable.E6"]},
     "正文写的是「**没有**测试」「**无**教学说明」「**尚未**加入断言」—— "
     "朴素关键词计数器会把 V1/V5/E6 判为通过。否定闸门必须让它们不通过。"
     "**没有这个问题的话，一个什么都没做的提交反而能靠「声明自己没做」得分。**")

# 11 多版本
case("gold11_multi_version", "FengShiyi",
     {"FengShiyi_C4_skill说明_v1.md": "# 旧版说明\n输入文件夹输出报告。\n",
      "FengShiyi_C4_skill说明_v2.md": FULL_DOC,
      "FengShiyi_C4_教学说明.md": FULL_TEACHING,
      "FengShiyi_C4_AI日志.md": FULL_AILOG, "FengShiyi_C4_preflight.py": FULL_CODE,
      "FengShiyi_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.75, "composite_max": 1.00,
      "flags": [], "level": "L4"},
     "v1/v2 两个版本都在。槽位匹配只能给 skill_doc 一个文件 → "
     "另一个版本**不应**被算成别的交付物（否则完整性虚高）。",
     binary=["FengShiyi_C4_demo.png"])

# 12 GBK 编码
case("gold12_gbk", "ChenShier",
     {"ChenShier_C4_skill说明.md": FULL_DOC,
      "ChenShier_C4_教学说明.md": FULL_TEACHING,
      "ChenShier_C4_AI日志.md": FULL_AILOG,
      "ChenShier_C4_preflight.py": FULL_CODE, "ChenShier_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.85, "composite_max": 1.00,
      "flags": [], "level": "L4"},
     "文件用 **GBK** 编码（Windows 记事本默认保存格式）。"
     "UTF-8-only 的读取器会拿到乱码，把所有信号判为缺失；"
     "GBK 回退必须让它与 UTF-8 版得到同样的分。",
     encoding="gbk", binary=["ChenShier_C4_demo.png"])

# 13 非标准命名（无作者前缀，放在子目录里）
case("gold13_nonstandard_names", "repo_only",
     {"skill说明.md": FULL_DOC, "教学说明.md": FULL_TEACHING,
      "AI日志.md": FULL_AILOG, "preflight.py": FULL_CODE, "demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.80, "composite_max": 1.00,
      "flags": [], "level": "L4", "author_source": "repo_level"},
     "文件名不带 `姓名_C4_` 前缀，全在仓库根目录下的一个子目录里。"
     "单候选 → 按仓库名归一位作者（repo_level），分数不应因此变差。",
     binary=["demo.png"])

# 14 只有二进制
case("gold14_binary_only", "GuSanshi",
     {"GuSanshi_C4_demo.png": "", "GuSanshi_C4_演示录屏.mp4": ""},
     {"completeness": 0.2, "composite_min": 0.0, "composite_max": 0.45,
      "flags": ["missing_core"], "level": "L1"},
     "只交了演示文件 → 完整性 0.2，缺 4 个。",
     binary=["GuSanshi_C4_demo.png", "GuSanshi_C4_演示录屏.mp4"])

# 15 Python 语法错误
case("gold15_syntax_error", "HanSishi",
     {"HanSishi_C4_skill说明.md": FULL_DOC, "HanSishi_C4_教学说明.md": FULL_TEACHING,
      "HanSishi_C4_AI日志.md": FULL_AILOG,
      "HanSishi_C4_preflight.py": "def main(:\n    return 0\n",
      "HanSishi_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.50, "composite_max": 0.88,
      "flags": ["syntax_error"], "level": None, "allow_levels": ["L3", "L4"]},
     "附带的 .py 编译不过 → syntax_error(cap85) 且 E5 检查项不通过。",
     binary=["HanSishi_C4_demo.png"])

# 16 真实 .skill 包
case("gold16_skill_package", "WeiShiqi",
     {"WeiShiqi_C4_skill说明.md": FULL_DOC, "WeiShiqi_C4_教学说明.md": FULL_TEACHING,
      "WeiShiqi_C4_AI日志.md": FULL_AILOG, "WeiShiqi_C4_demo.png": ""},
     {"completeness": 1.0, "composite_min": 0.80, "composite_max": 1.00,
      "flags": [], "level": "L4"},
     "可执行内容是真正的 `.skill`（tar.gz）包，而不是 .py。"
     "评审器必须能解开它、读到里面的 SKILL.md 并识别 frontmatter。",
     skills={"WeiShiqi_C4_c4-preflight.skill":
             {"SKILL.md": FULL_SKILL, "scripts/preflight.py": FULL_CODE,
              "references/rules.json": '{"version": 1}'}},
     binary=["WeiShiqi_C4_demo.png"])

# 17 空文件夹
case("gold17_empty_folder", "", {},
     {"expect_exit": 3, "mode": "empty"},
     "完全空的目录 → 应报「未找到任何文件」并以非零退出码结束，而不是假装评了 0 分。",
     expect_exit=3)

# 18 缺口令但有内容（区分「缺」和「没写清」）
case("gold18_no_demo_but_rich", "QinShiba",
     {"QinShiba_C4_skill说明.md": FULL_DOC, "QinShiba_C4_教学说明.md": FULL_TEACHING,
      "QinShiba_C4_AI日志.md": FULL_AILOG,
      "QinShiba_C4_c4-preflight.skill": ""},
     {"completeness": 0.8, "composite_min": 0.60, "composite_max": 0.88,
      "flags": ["missing_core"], "level": "L3",
      "allow_levels": ["L2", "L3"]},
     "内容质量很高但缺 demo → cap 75 把它压在 L3，"
     "**不应因为「写得好」就豁免硬性交付物要求**。",
     skills={"QinShiba_C4_c4-preflight.skill": {"SKILL.md": FULL_SKILL}})

# 19 机器名前缀（幽灵作者陷阱）
case("gold19_machine_prefix", "ShenShijiu",
     {"ShenShijiu_C4_skill说明.md": FULL_DOC, "ShenShijiu_C4_教学说明.md": FULL_TEACHING,
      "ShenShijiu_C4_AI日志.md": FULL_AILOG, "ShenShijiu_C4_preflight.py": FULL_CODE,
      "ShenShijiu_C4_demo.png": "",
      "evidence/run_C4_self.txt": "运行记录\n"},
     {"completeness": 1.0, "composite_min": 0.85, "composite_max": 1.00,
      "flags": [], "level": "L4", "n_authors": 1},
     "`evidence/run_C4_self.txt` 的文件名符合 `前缀_C4_后缀`，"
     "会把作者识别成 `run` —— 实测踩到过。目录上下文必须优先于文件名模式，"
     "班级人数必须仍然是 1。",
     binary=["ShenShijiu_C4_demo.png"])

# 20 占位空文件（不应该被当成缺陷）
case("gold20_placeholder_ok", "YouErshi",
     {"YouErshi_C4_skill说明.md": FULL_DOC, "YouErshi_C4_教学说明.md": FULL_TEACHING,
      "YouErshi_C4_AI日志.md": FULL_AILOG, "YouErshi_C4_preflight.py": FULL_CODE,
      "YouErshi_C4_demo.png": "", "_demo/before/占位.md": ""},
     {"completeness": 1.0, "composite_min": 0.85, "composite_max": 1.00,
      "flags": [], "level": "L4"},
     "演示目录里有一个有意的空占位文件（`占位.md`）。"
     "把它算成「交付物为空」会误伤一个干净的提交 —— 实测踩到过（ZhouYan05）。",
     binary=["YouErshi_C4_demo.png"])


def build():
    if GOLD.exists():
        shutil.rmtree(GOLD)
    labels = {}
    for cid, c in sorted(CASES.items()):
        d = GOLD / cid
        d.mkdir(parents=True, exist_ok=True)
        if c["expect"].get("mode") == "empty":
            (d / ".keep").unlink(missing_ok=True)
        for name, content in c["files"].items():
            p = d / name
            if name in c["binary"]:
                p.parent.mkdir(parents=True, exist_ok=True)
                if content == "":
                    p.write_bytes(TINY_PNG)
                else:
                    p.write_bytes(TINY_PNG)
            else:
                write(p, content, c["encoding"])
        for name, members in c["skills"].items():
            make_skill(d / name, members)
        # gold13：内容放进子目录，模拟「仓库里没有作者前缀」
        if cid == "gold13_nonstandard_names":
            sub = d / "my-c4-skill"
            sub.mkdir(exist_ok=True)
            for name in list(c["files"]) + list(c["binary"]):
                src = d / name
                if src.exists():          # binary 里的文件也在 files 里，去重
                    os.replace(src, sub / name)
        labels[cid] = {k: v for k, v in c["expect"].items()} | {
            "author": c["author"], "rationale": c["rationale"]}
    (GOLD / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=1),
        encoding="utf-8", newline="\n")
    print(f"生成 {len(CASES)} 个评测样本 → {GOLD}")
    for cid in sorted(CASES):
        n = len(list((GOLD / cid).rglob("*")))
        print(f"  {cid:30s} {n:3d} 个条目")


if __name__ == "__main__":
    build()
