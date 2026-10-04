# C4 交付：deliverable-selfcheck · Demo 演示

- 作者：ZhouYan05
- 演示对象：`deliverable-selfcheck`（交付物自检器）
- 复跑目录：`_demo/before`（踩坑样本）、`_demo/after`（修好样本）

> 下面两段输出是**真实运行结果**，可原样复现：
> `python scripts/selfcheck.py --workdir _demo/before --required "*skill说明*,*.skill,*教学说明*,*demo*,*AI日志*" --prefix ZhouYan05 --title "C4 技能分享: deliverable-selfcheck"`

---

## 场景一：提交前自检 —— BLOCKED

一个"看起来交齐了"的目录，被查出 4 个问题。

```text
# 交付物自检报告
- 目录: ...\_demo\before
- 扫描文件数: 6
- 结论: **BLOCKED**

## 逐项核对
- [x] `*skill说明*` -> `ZhouYan05_C4_skill说明.md`
- [x] `*.skill`    -> `ZhouYan05_C4_deliverable-selfcheck.skill`
- [x] `*教学说明*` -> `ZhouYan05_C4_教学说明.md`
- [x] `*demo*`     -> `ZhouYan05_C4_demo.md`
- [ ] `*AI日志*`   -> **缺失**（需字面含「AI日志」）

## 风险与待办
- **EMPTY_FILE** · 占位.md
      - 文件为 0 字节，平台可能视为无效交付
      - 下一步: 补内容，或删掉占位文件
- **MISSING_PREFIX** · AI_工作日志与AAR.md
      - 顶层交付物文件名未包含命名前缀「ZhouYan05」
      - 下一步: 重命名为 ZhouYan05_... 开头
- **MISSING_PREFIX** · 占位.md
      - 顶层交付物文件名未包含命名前缀「ZhouYan05」
      - 下一步: 重命名为 ZhouYan05_... 开头
- **SENSITIVE_SHAPE** · projectTitle
      - 出现「英文冒号+空格」的 key-value 观感片段 '享: d'，
        平台敏感信息过滤可能整单拒绝
      - 下一步: 把英文冒号换成破折号或全角冒号，其余内容不动

退出码: 1   (0=READY, 1=BLOCKED)
```

**它抓到了什么（这些坑我都真踩过）：**

1. `AI_工作日志与AAR.md` 这个名字**看起来**含"AI"和"日志"，
   但平台要求的是**连续**子串 `AI日志`，下划线把它断开了 → 判缺失。
   报告直接给出"需字面含『AI日志』"的提示。
2. `占位.md` 是 0 字节占位，会拉低完成度。
3. 两个文件缺命名前缀。
4. 标题里的 `分享: d` 是**英文冒号+空格**，会被平台敏感信息过滤拦下——
   这条如果不提前发现，交付物全对也会**整单被拒**。

---

## 场景二：修好后再自检 —— READY

**只做了三件事**：改文件名（去下划线、加前缀）、删占位文件、把英文冒号换成 `-`。

```text
# 交付物自检报告
- 目录: ...\_demo\after
- 扫描文件数: 5
- 结论: **READY**

## 逐项核对
- [x] `*skill说明*` -> `ZhouYan05_C4_skill说明.md`
- [x] `*.skill`    -> `ZhouYan05_C4_deliverable-selfcheck.skill`
- [x] `*教学说明*` -> `ZhouYan05_C4_教学说明.md`
- [x] `*demo*`     -> `ZhouYan05_C4_demo.md`
- [x] `*AI日志*`   -> `ZhouYan05_C4_AI日志与AAR.md`

退出码: 0
```

注意：`ZhouYan05_C4_AI日志与AAR.md` 这一个文件**同时**命中了
`*AI日志*`（连续子串存在）和 `*AAR*` 两个要求——这就是正确的命名方式。

---

## 对照总结

| | before | after |
| --- | --- | --- |
| 结论 | BLOCKED | READY |
| 退出码 | 1 | 0 |
| 致命问题 | 缺 `*AI日志*` 交付物、标题会被整单拒 | 无 |
| 修复动作 | —— | 改名 / 删除 / 换标点 |

**价值一句话**：把"提交后才发现的失败"提前到"提交前 1 秒就能发现"，
而且每一步都告诉你**具体改什么**。
